import logging
import traceback
import typing
import datetime
import json
import os

from common import ResourceProcessor, permission_required, APIPermission, batch_iterator
from tools.common_schemas import ExcludeSchema
from tools.ydb_connection import YDBConnector
from marshmallow import fields, ValidationError


class PlayerSchema(ExcludeSchema):
    id = fields.Int(required=True)
    egs_id = fields.Str(required=True)
    egs_nickname = fields.Str()
    steam_id = fields.Str()
    steam_nickname = fields.Str()

    email = fields.Email()
    email_confirmed = fields.Boolean()
    # Secret, don't allow to spread it out of backend
    email_confirmation_code = fields.Str()

    xp = fields.Int()
    subscription_status = fields.Int()
    subscription_end = fields.DateTime()

    permissions = fields.Int()

    created_time = fields.Int()


class PlayerProcessor(ResourceProcessor):
    """Retrieve data about players"""

    def __init__(self, logger, contour, user, yc, s3):
        super(PlayerProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = "ecr_players" if self.contour == "prod" else "ecr_players_dev"

        with open(os.path.join(os.path.dirname(__file__), "../data/levels.json")) as f:
            self.levelling_data = json.load(f)

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Gets player data by internal id"""

        schema = PlayerSchema(only=("id",))
        try:
            validated_data = schema.load(request_body)
            query = f"""
                DECLARE $ID AS Int64;

                SELECT * FROM {self.table_name}
                WHERE
                    id = $ID
                ;
            """

            query_params = {
                '$ID': validated_data.get("id"),
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                if len(result) > 0:
                    dump_schema = PlayerSchema()
                    if len(result[0].rows) > 0:
                        return {"success": True, "data": dump_schema.dump(result[0].rows[0])}, 200
                    else:
                        # User not found by internal id
                        return {"success": False}, 404
                else:
                    return {"success": False, "data": None}, 500
            else:
                return self.internal_server_error_response
        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def batch_grant_xp(self, players_to_xp_deltas: dict, source: str, source_additional_data: str) -> typing.Tuple[
        dict, int]:
        """Used for internal batch granting XP"""

        try:
            for chunk in batch_iterator(players_to_xp_deltas.items(), 100):
                batch = [
                    {"id": player_id, "delta": max(xp_delta, 0)}
                    for player_id, xp_delta in chunk
                ]

                query = f"""
                    DECLARE $batch AS List<Struct<id: Int64, delta: Int64>>;

                    UPSERT INTO {self.table_name} (id, xp)
                    SELECT
                        b.id,
                        COALESCE(t.xp, 0) + b.delta AS xp
                    FROM AS_TABLE($batch) AS b
                    INNER JOIN {self.table_name} AS t
                    ON b.id = t.id;
                """

                query_params = {"$batch": batch}
                result, code = self.yc.process_query(query, query_params)

                if code != 0:
                    return self.internal_server_error_response

                # Log each XP grant
                for row in batch:
                    self.__log_currency_change(row["id"], None, row["delta"], source, source_additional_data)

            return {"success": True}, 204

        except Exception:
            self.logger.error(f"Exception during player BATCH GRANT XP: {traceback.format_exc()}")
            return self.internal_server_error_response


    def grant_xp(self, player: int, xp_delta: int, source: str, source_additional_data: str) -> typing.Tuple[
        dict, int]:
        """Used for internal granting XP"""

        r, s = self.API_GET({"id": player})
        if s != 200:
            return r, s
        else:
            player_data = r["data"]

        try:
            query = f"""
                DECLARE $ID AS Int64;
                DECLARE $XP AS Int64;

                UPDATE {self.table_name}
                SET 
                    xp = $XP
                WHERE
                    id = $ID
                ;
            """

            old_xp = player_data.get("xp")
            new_xp = max(0, old_xp + xp_delta)
            query_params = {
                '$ID': player,
                '$XP': new_xp,
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                self.__log_currency_change(player, old_xp, xp_delta, source, source_additional_data)
                return {"success": True}, 204
            else:
                return self.internal_server_error_response
        except Exception as e:
            self.logger.error(f"Exception during player GRANT XP: {traceback.format_exc()}")
            return self.internal_server_error_response

    def __log_currency_change(self, player_id, old_xp, xp_delta, source, source_additional_data):
        ts = datetime.datetime.now(tz=datetime.timezone.utc)
        history_rel_path = f"{ts.year}-{ts.month:02d}-{ts.day:02d}.csv"
        history_path = self.s3_paths.get_player_currency_history_s3_path(player_id, history_rel_path)

        if self.s3.check_exists(history_path):
            content = self.s3.get_file_from_s3(history_path)
        else:
            content = b""

        content += f"{old_xp},{xp_delta}," \
                   f"{source.replace(',', '')},{source_additional_data.replace(',', '')}," \
                   f"{ts.hour}:{ts.minute}:{ts.second}\n".encode("utf-8")
        self.s3.upload_file_to_s3(content, history_path)

    def get_level_from_xp(self, xp):
        level = 1
        for row in self.levelling_data:
            if xp >= row["xp_amount"]:
                level = row["level"]
            else:
                break
        return level


if __name__ == '__main__':
    from tools.s3_connection import S3Connector

    egs_id = "c5a7eea3e4c14aecaf4b73a3891bf7d3"
    egs_nickname = "JediKnightChan"
    player = 4

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    player_proc = PlayerProcessor(logger, "dev", egs_id, yc, s3)

    # r, s = player_proc.API_GET({"id": player})
    # r, s = player_proc.grant_xp(player, 100, "api_test", "")
    # r, s = player_proc._get_by_egs_id(egs_id, egs_nickname)
    r, s = player_proc.batch_grant_xp({player: 888}, "api_test", "")
    print(s, r)
