import datetime
import logging
import traceback
import typing

from resources.player import PlayerSchema
from tools.ydb_connection import YDBConnector


class AuthenticationProcessor:
    def __init__(self, logger, contour, yc):
        self.logger = logger
        self.contour = contour
        self.yc = yc

        self.table_name = "ecr_players" if self.contour == "prod" else "ecr_players_dev"

    def get_player_by_egs_id(self, egs_id, egs_nickname):
        """Gets player data by EGS id"""

        query = f"""
            DECLARE $EGS_ID AS Utf8;

            SELECT * FROM {self.table_name}
            WHERE
                egs_id = $EGS_ID
            ;
        """

        query_params = {
            '$EGS_ID': egs_id,
        }

        result, code = self.yc.process_query(query, query_params)

        if code == 0:
            if len(result) > 0:
                dump_schema = PlayerSchema()
                if len(result[0].rows) > 0:
                    return {"success": True, "data": dump_schema.dump(result[0].rows[0])}, 200
                else:
                    if egs_nickname:
                        create_r, create_s = self.__create_player_by_egs_id(egs_id, egs_nickname)
                        if create_s == 201:
                            return self.get_player_by_egs_id(egs_id, egs_nickname)
                        else:
                            return self.internal_server_error_response
                    else:
                        return {"success": False,
                                "error": "Couldn't find egs_id, so egs_nickname required"}, 400
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

    def __create_player_by_egs_id(self, egs_id: str, egs_nickname: str) -> typing.Tuple[dict, int]:
        """Create character, only called from API_GET when player doesn't exist"""

        # Creating row in YDB table
        query = f"""
            DECLARE $EGS_ID AS Utf8;
            DECLARE $EGS_NICK AS Utf8;
            DECLARE $CREATED_TIME AS Datetime;

            UPSERT INTO {self.table_name} 
            (
            egs_id, egs_nickname, steam_id, steam_nickname, 
            email, email_confirmed, email_confirmation_code, 
            xp, subscription_status, subscription_end, 
            permissions, created_time
            ) 
            VALUES
                (
                $EGS_ID, $EGS_NICK, "", "",
                "", false, "",
                0, 0, NULL,
                0, $CREATED_TIME);
        """

        query_params = {
            '$EGS_ID': egs_id,
            '$EGS_NICK': egs_nickname,
            '$CREATED_TIME': int(datetime.datetime.now().timestamp()),
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            return {"success": True}, 201
        else:
            return self.internal_server_error_response

    @property
    def internal_server_error_response(self) -> typing.Tuple[dict, int]:
        return {"error": "Internal server error"}, 500


if __name__ == '__main__':
    egs_id = "c5a7eea3e4c14aecaf4b73a3891bf7d3"
    egs_nickname = "JediKnightChan"

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)

    auth_proc = AuthenticationProcessor(logger, "dev", yc)
    r, s = auth_proc.get_player_by_egs_id(egs_id, egs_nickname)
    print(s, r)
