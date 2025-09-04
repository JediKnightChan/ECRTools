import logging
import random
import traceback
import typing
import datetime
import json
import os

from common import ResourceProcessor, permission_required, APIPermission, batch_iterator, api_view
from tools.common_schemas import ExcludeSchema
from tools.ydb_connection import YDBConnector
from marshmallow import fields, validate, ValidationError

DAILY_TYPES_TO_REWARDS = {
    "Daily1": 25,
    "Daily2": 25,
    "Weekly": 200
}


class DailyActivitySchema(ExcludeSchema):
    """Representation of daily activity table"""

    char = fields.Int(required=True)
    date = fields.Str(required=True)
    type = fields.Str(required=True, validate=validate.OneOf(DAILY_TYPES_TO_REWARDS.keys()))
    quest = fields.Str(required=True)
    progress = fields.Int(required=True)
    created_time = fields.Int()


class DailyActivityGetSchema(ExcludeSchema):
    """GET request to retrieve daily and weekly activity for a given char"""

    char = fields.Int(required=True)


class DailyActivityProcessor(ResourceProcessor):
    """Retrieve data about players"""

    def __init__(self, logger, contour, user, yc, s3):
        super(DailyActivityProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_dailies")

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Gets daily activity for today"""

        # Excluding faction from schema
        schema = DailyActivityGetSchema()
        validated_data = schema.load(request_body)

        now = datetime.datetime.now(datetime.timezone.utc)
        daily_key, weekly_key = self.__get_daily_and_weekly_key_for_timestamp(now)

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
        daily1_quest = "DailyWins"  # constant
        daily2_quest = random.choice(["DailyKills", "DailyExecutions", "DailyCaptures"])
        weekly_quest = random.choice(["WeeklyKills", "WeeklyExecutions", "WeeklyCaptures"])

        char = validated_data.get("char")
        created_time = int(now.timestamp())
        query_params = {
            "$batch": [
                {"char": char, "date": daily_key, "type": "daily1", "quest": daily1_quest, 'created_time': created_time},
                {"char": char, "date": daily_key, "type": "daily2", "quest": daily2_quest, 'created_time': created_time},
                {"char": char, "date": weekly_key, "type": "weekly", "quest": weekly_quest, 'created_time': created_time},
            ]
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            if len(result) > 0:
                if len(result[0].rows) > 0:
                    dump_schema = DailyActivitySchema()
                    dumped_rows = [dump_schema.dump(r) for r in result[0].rows]
                    return {"success": True, "data": {el["type"]: el for el in dumped_rows}}, 200
                else:
                    return {"success": False, "data": {}}, 404
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

    @staticmethod
    def __get_daily_and_weekly_key_for_timestamp(timestamp):
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
