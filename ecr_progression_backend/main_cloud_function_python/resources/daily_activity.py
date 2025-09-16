import logging
import random
import traceback
import typing
import datetime
import json
import os

from common import ResourceProcessor, permission_required, APIPermission, batch_iterator, api_view
from tools.common_schemas import ExcludeSchema, CharPlayerSchema
from tools.ydb_connection import YDBConnector
from marshmallow import fields, validate, ValidationError

DAILY_TYPES = [
    "daily1",
    "daily2",
    "weekly"
]


class DailyActivitySchema(ExcludeSchema):
    """Representation of daily activity table"""

    char = fields.Int(required=True)
    date = fields.Str(required=True)
    type = fields.Str(required=True, validate=validate.OneOf(DAILY_TYPES))
    quest = fields.Str(required=True)
    progress = fields.Int(required=True)
    created_time = fields.Int()


class DailyActivityProcessor(ResourceProcessor):
    """Retrieve data about players"""

    def __init__(self, logger, contour, user, yc, s3):
        super(DailyActivityProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_dailies")

        dailies_filepath = os.path.join(os.path.dirname(__file__), f"../data/dailies/dailies.json")
        with open(dailies_filepath, "r") as f:
            self.dailies_data = json.load(f)

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Gets daily activity for today"""

        schema = CharPlayerSchema(only=("char",))
        validated_data = schema.load(request_body)

        now = datetime.datetime.now(datetime.timezone.utc)
        daily_key, weekly_key = self.get_daily_and_weekly_key_for_timestamp(now)

        query = f"""
            DECLARE $batch AS List<Struct<char: Int64, date: Utf8, type: Utf8, quest: Utf8, created_time: Datetime>>;
            
            UPSERT INTO {self.table_name} (char, date, type, quest, progress, created_time)
            SELECT
                b.char,
                b.date,
                b.type,
                COALESCE(t.quest, b.quest) AS quest,               -- keep existing quest, else use new
                COALESCE(t.progress, 0) AS progress,               -- keep progress if exists, else 0
                COALESCE(t.created_time, b.created_time) AS created_time  -- keep old time if exists, else new
            FROM AS_TABLE($batch) AS b
            LEFT JOIN {self.table_name} AS t
                ON b.char = t.char
               AND b.date = t.date
               AND b.type = t.type;
            
            -- Return all rows we just touched
            SELECT q.*
            FROM {self.table_name} AS q
            JOIN AS_TABLE($batch) AS b
              ON q.char = b.char
             AND q.date = b.date
             AND q.type = b.type;
        """

        # Pick quests
        daily1_quest = self._get_random_daily_with_type("daily1")  # constant "daily_wins" right now
        daily2_quest = self._get_random_daily_with_type("daily2")
        weekly_quest = self._get_random_daily_with_type("weekly")

        char = validated_data.get("char")
        created_time = int(now.timestamp())
        query_params = {
            "$batch": [
                {"char": char, "date": daily_key, "type": "daily1", "quest": daily1_quest,
                 'created_time': created_time},
                {"char": char, "date": daily_key, "type": "daily2", "quest": daily2_quest,
                 'created_time': created_time},
                {"char": char, "date": weekly_key, "type": "weekly", "quest": weekly_quest,
                 'created_time': created_time},
            ]
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            if len(result) > 0:
                if len(result[0].rows) > 0:
                    dump_schema = DailyActivitySchema()
                    dumped_rows = [dump_schema.dump(r) for r in result[0].rows]
                    return {
                        "success": True,
                        "data": {
                            el["type"]: {
                                **el,
                                "gold": self.dailies_data.get(el["quest"], {}).get("reward_gold"),
                                "reset_ts": self.get_next_reset_timestamp(el['type'] != 'weekly')}
                            for el in dumped_rows
                        }
                    }, 200
                else:
                    return {"success": False, "data": {}}, 404
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

    @staticmethod
    def get_daily_and_weekly_key_for_timestamp(timestamp):
        """Gets for given timestamp daily and weekly date ids according to their reset times"""

        # Reset dailies at 12:00 UTC
        daily_moment = timestamp - datetime.timedelta(hours=12)
        daily_key = daily_moment.strftime("%Y-%m-%d")

        # Reset weeklies each Tuesday 12:00 UTC
        weekly_moment = timestamp - datetime.timedelta(hours=12)
        days_since_tuesday = (weekly_moment.weekday() - 1) % 7
        tuesday = weekly_moment - datetime.timedelta(days=days_since_tuesday)
        weekly_key = tuesday.strftime("%Y-%m-%d")
        return daily_key, weekly_key

    @staticmethod
    def get_next_reset_timestamp(
            is_daily: bool,
            daily_reset_hour: int = 12,
            daily_reset_minute: int = 0,
            weekly_reset_weekday: int = 1,  # 0 = Monday, 1 = Tuesday ... 6 = Sunday
            tz=datetime.timezone.utc
    ) -> int:
        """
        Returns the timestamp (epoch seconds) of the next reset for daily / weekly
        """

        now = datetime.datetime.now(tz)

        # Start from today's daily reset
        reset = datetime.datetime(
            now.year, now.month, now.day,
            daily_reset_hour, daily_reset_minute, tzinfo=tz
        )
        if now >= reset:
            reset += datetime.timedelta(days=1)

        # Adjust for weekly reset if needed
        if not is_daily:
            while reset.weekday() != weekly_reset_weekday:
                reset += datetime.timedelta(days=1)

        return int(reset.timestamp())

    def _get_random_daily_with_type(self, daily_type):
        """From possible dailies selects 1 random with given type"""

        options = []
        weights = []
        for daily_name, daily_data in self.dailies_data.items():
            if daily_data["is_enabled"] and daily_data["type"] == daily_type:
                options.append(daily_name)
                weights.append(daily_data["chance_weight"])

        # Check for empty
        if len(options) == 0:
            raise Exception(f"No enabled dailies with type {daily_type}, couldn't select")

        return random.choices(options, weights=weights)[0]

    def _change_current_daily(self, char, daily_type, new_quest):
        """Sets new quest for given char and daily"""

        query = f"""
            DECLARE $CHAR AS Int64;
            DECLARE $DATE AS Utf8;
            DECLARE $TYPE AS Utf8;
            DECLARE $QUEST AS Utf8;
             
            UPDATE {self.table_name}
            SET
                quest = $QUEST
            WHERE
                char = $CHAR AND
                type = $TYPE AND
                date = $DATE
            ;
        """

        now = datetime.datetime.now(datetime.timezone.utc)
        daily_key, weekly_key = self.get_daily_and_weekly_key_for_timestamp(now)

        query_params = {
            "$CHAR": char,
            "$DATE": weekly_key if daily_type == "weekly" else daily_key,
            "$TYPE": daily_type,
            "$QUEST": new_quest
        }

        result, code = self.yc.process_query(query, query_params)
        if code != 0:
            return {"success": False}, 500
        else:
            return {"success": True}, 200

    def _clear_current_dailies(self, char):
        """Clears current dailies and weekly for given char"""

        query = f"""
            DECLARE $CHAR AS Int64;
            DECLARE $DATE_DAILY AS Utf8;
            DECLARE $DATE_WEEKLY AS Utf8;

            DELETE FROM {self.table_name}
            WHERE
                char = $CHAR AND
                date IN ($DATE_DAILY, $DATE_WEEKLY)
            ;
        """

        now = datetime.datetime.now(datetime.timezone.utc)
        daily_key, weekly_key = self.get_daily_and_weekly_key_for_timestamp(now)

        query_params = {
            "$CHAR": char,
            "$DATE_DAILY": daily_key,
            "$DATE_WEEKLY": weekly_key
        }

        result, code = self.yc.process_query(query, query_params)
        if code != 0:
            return {"success": False}, 500
        else:
            return {"success": True}, 200


if __name__ == '__main__':
    from tools.s3_connection import S3Connector

    char = 2
    player = 4

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    daily_proc = DailyActivityProcessor(logger, "dev", player, yc, s3)

    r, s = daily_proc.API_GET({"char": char})
    print(s, r)

    # r, s = daily_proc._change_current_daily(char, "daily2", "daily_kills_bolter_tyranids")
    # print(s, r)

    # r, s = daily_proc._clear_current_dailies(char)
    # print(s, r)
