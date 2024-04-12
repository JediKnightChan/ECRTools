import logging
import traceback
import typing
import datetime
import pandas as pd

from common import ResourceProcessor, permission_required, APIPermission
from tools.common_schemas import ExcludeSchema
from tools.ydb_connection import YDBConnector
from marshmallow import Schema, fields, validate, ValidationError


class PlayerSchema(ExcludeSchema):
    id = fields.Str(required=True)
    level = fields.Int(default=1)
    xp = fields.Int(default=0)
    free_xp = fields.Int(default=0)
    silver = fields.Int(default=0)
    gold = fields.Int(default=0)


class PlayerProcessor(ResourceProcessor):
    """Retrieve data about players"""

    def __init__(self, logger, contour, user):
        super(PlayerProcessor, self).__init__(logger, contour, user)

        self.yc = YDBConnector(logger)

        self.table_name = "players" if self.contour == "prod" else "players_dev"

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get player data by id. Anyone can do it."""

        schema = PlayerSchema(only=("id",))

        try:
            validated_data = schema.load({"id": request_body.get("player_id")})
            player_id = validated_data.get("id")

            query = f"""
                DECLARE $ID AS Utf8;

                SELECT * FROM {self.table_name}
                WHERE
                    id = $ID
                ;
            """

            query_params = {
                '$ID': player_id,
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                if len(result) > 0:
                    dump_schema = PlayerSchema()
                    if len(result[0].rows) > 0:
                        return {"success": True, "data": dump_schema.dump(result[0].rows[0])}, 200
                    else:
                        # User not found, will create new if one who asked about him is himself
                        if self.user == player_id:
                            create_r, create_s = self.__create(player_id)
                            if create_s == 201:
                                return {"success": True, "data": dump_schema.dump({"id": player_id})}, 200
                            else:
                                return self.internal_server_error_response
                        else:
                            return {"success": False}, 404
                else:
                    return {"success": False, "data": None}, 500
            else:
                return self.internal_server_error_response

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during player GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def __create(self, player_id: str) -> typing.Tuple[dict, int]:
        """Create character, only called from API_GET when player doesn't exist"""

        try:
            # Creating row in YDB table
            query = f"""
                DECLARE $ID AS Utf8;

                UPSERT INTO {self.table_name} (id, level, xp, free_xp, silver, gold) VALUES
                    ($ID, 1, 0, 0, 0, 0);
            """

            query_params = {
                '$ID': player_id
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                return {"success": True}, 201
            else:
                return self.internal_server_error_response
        except Exception as e:
            self.logger.error(f"Exception during player CREATE for id {player_id}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def modify(self, player_id, xp_delta, free_xp_delta, silver_delta, gold_delta, source, source_additional_data) -> \
            typing.Tuple[dict, int]:
        """Used for internal modifying of player data (eg granting rewards or spending currency)"""

        r, s = self.API_GET({"player_id": player_id})
        if s != 200:
            return r, s
        else:
            player_data = r["data"]

        try:
            query = f"""
                DECLARE $ID AS Utf8;
                DECLARE $LEVEL AS Uint32;
                DECLARE $XP AS Uint32;
                DECLARE $FREE_XP AS Uint32;
                DECLARE $SILVER AS Uint32;
                DECLARE $GOLD AS Uint32;

                UPDATE {self.table_name}
                SET 
                level = $LEVEL,
                xp = $XP,
                free_xp = $FREE_XP,
                silver = $SILVER,
                gold = $GOLD
                WHERE
                    id = $ID
                ;
            """

            new_xp = max(0, player_data.get("xp") + xp_delta)
            new_level = self._get_level_from_xp(new_xp)
            query_params = {
                '$ID': player_id,
                '$LEVEL': new_level,
                '$XP': new_xp,
                '$FREE_XP': max(0, player_data.get("free_xp") + free_xp_delta),
                '$SILVER': max(0, player_data.get("silver") + silver_delta),
                '$GOLD': max(0, player_data.get("gold") + gold_delta)
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                self.__log_currency_change(player_id, xp_delta, free_xp_delta, silver_delta, gold_delta, source,
                                           source_additional_data)
                return {"success": True}, 204
            else:
                return self.internal_server_error_response
        except Exception as e:
            self.logger.error(f"Exception during player MODIFY: {traceback.format_exc()}")
            return self.internal_server_error_response

    def __log_currency_change(self, player_id, xp_delta, free_xp_delta, silver_delta, gold_delta, source,
                              source_additional_data):
        ts = datetime.datetime.utcnow()
        history_rel_path = f"{ts.year}-{ts.month:02d}-{ts.day:02d}.csv"
        history_path = self.s3_paths.get_currency_history_s3_path(player_id, history_rel_path)

        if self.s3.check_exists(history_path):
            content = self.s3.get_file_from_s3(history_path)
        else:
            content = b""

        content += f"{xp_delta},{free_xp_delta},{silver_delta},{gold_delta}," \
                   f"{source.replace(',', '')},{source_additional_data.replace(',', '')}," \
                   f"{ts.timestamp()}\n".encode("utf-8")
        self.s3.upload_file_to_s3(content, history_path)

    @staticmethod
    def _get_level_from_xp(xp):
        df = pd.read_csv("../data/levels.csv")
        level = 1
        for _, row in df.iterrows():
            if xp >= row["xp_amount"]:
                level = row["level"]
            else:
                break
        return level


if __name__ == '__main__':
    player_id = "earlydevtestplayerid"

    player_proc = PlayerProcessor(logging.getLogger(__name__), "dev", player_id)
    r, s = player_proc.API_GET({"player_id": player_id})
    # r, s = player_proc.modify(player_id, 100, 100, 50, 100, "api_test", "")
    print(s, r)
