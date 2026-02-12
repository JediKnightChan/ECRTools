import json
import traceback
import typing
import datetime

from marshmallow import fields, validate, ValidationError
from common import ResourceProcessor, permission_required, APIPermission, batch_iterator, api_view

from tools.common_schemas import ECR_FACTIONS, ExcludeSchema


class CharacterSchema(ExcludeSchema):
    id = fields.Int(required=True)
    player = fields.Int(required=True)

    name = fields.Str(
        required=True,
        validate=validate.Regexp(
            regex=r'^[a-zA-Z\s]{1,30}$',
            error='String must contain only English characters and spaces, up to 30'
        )
    )
    faction = fields.Str(
        required=True,
        validate=validate.OneOf(ECR_FACTIONS),
    )

    # Currencies
    free_xp = fields.Int(default=0)
    silver = fields.Int(default=0)
    gold = fields.Int(default=0)

    # Guild
    guild = fields.Int(required=False)
    guild_role = fields.Int(required=False)

    created_time = fields.Int()


class CharacterProcessor(ResourceProcessor):
    """Retrieve data about characters, create and modify them"""

    def __init__(self, logger, contour, user, yc, s3):
        super(CharacterProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_characters")

    @api_view
    @permission_required(APIPermission.SERVER_OR_OWNING_PLAYER)
    def API_LIST(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all characters data for given player. Only owning player or server can do it"""

        schema = CharacterSchema(only=("player",))

        validated_data = schema.load(request_body)

        query = f"""
            DECLARE $PLAYER AS Int64;

            SELECT * FROM {self.table_name}
            WHERE
                player = $PLAYER
            ;
        """

        query_params = {
            '$PLAYER': validated_data.get("player"),
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            if len(result) > 0:
                dump_schema = CharacterSchema()
                return {"success": True, "data": [dump_schema.dump(r) for r in result[0].rows]}, 200
            else:
                return {"success": False, "data": []}, 500
        else:
            return self.internal_server_error_response

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get character by id, everyone can do it"""

        schema = CharacterSchema(only=("id",))

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
                if len(result[0].rows) > 0:
                    dump_schema = CharacterSchema()
                    return {"success": True, "data": dump_schema.dump(result[0].rows[0])}, 200
                else:
                    return {"success": True, "data": {}}, 404
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

    @api_view
    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_CREATE(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Create character, ID is generated with UUID. Only owning player can do it"""

        schema = CharacterSchema(only=("player", "faction", "name"))
        validated_data = schema.load(request_body)

        r, s = self.API_LIST({"player": validated_data.get("player")})
        if s == 200:
            # Checking if character with the same faction doesn't exist for the player
            already_existing_factions = [c["faction"] for c in r["data"]]
            if validated_data.get("faction") in already_existing_factions:
                return {"success": False,
                        "error_code": 1,
                        "error": "Character of this faction already exists for this player"}, \
                    400

            name_code, name_result = self._validate_character_name_is_unique(validated_data)
            if name_code == 0:
                if len(name_result) > 0:
                    if len(name_result[0].rows) > 0:
                        return {"success": False,
                                "error_code": 2,
                                "error": "Character with this name already exists"}, \
                            400
                    else:
                        # No characters with such name, can create
                        pass
                else:
                    return {"success": False, "data": None}, 500
            else:
                return self.internal_server_error_response
        else:
            return {"success": False}, s

        # Creation time of a character is now
        created_time = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

        # Creating row in YDB table
        query = f"""
            DECLARE $PLAYER AS Int64;
            DECLARE $CHARACTER_NAME AS String;
            DECLARE $FACTION AS Utf8;
            DECLARE $CREATED_TIME AS Datetime;

            UPSERT INTO {self.table_name} (player, name, faction, free_xp, silver, gold, guild, guild_role, created_time) VALUES
                ($PLAYER, $CHARACTER_NAME, $FACTION, 0, 0, 0, NULL, 0, $CREATED_TIME);
        """

        query_params = {
            '$PLAYER': validated_data.get("player"),
            '$CHARACTER_NAME': validated_data.get("name").encode("utf-8"),
            '$FACTION': validated_data.get("faction"),
            '$CREATED_TIME': created_time
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            return {"success": True}, 201
        else:
            return self.internal_server_error_response

    @api_view
    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Allow to modify only character of yours (its name), query is filtered by player"""

        # Excluding faction from schema
        schema = CharacterSchema(only=("player", "id", "name"))

        validated_data = schema.load(request_body)

        name_code, name_result = self._validate_character_name_is_unique(validated_data)
        if name_code == 0:
            if len(name_result) > 0:
                if len(name_result[0].rows) > 0:
                    return {"success": False,
                            "error_code": 2,
                            "error": "Character with this name already exists"}, \
                        400
                else:
                    # No characters with such name, can modify name
                    pass
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

        query = f"""
            DECLARE $ID AS Int64;
            DECLARE $PLAYER AS Int64;
            DECLARE $CHARACTER_NAME AS String;

            UPDATE {self.table_name}
            SET 
                name = $CHARACTER_NAME
            WHERE
                id = $ID 
                AND player = $PLAYER
            ;
        """

        query_params = {
            '$ID': validated_data.get("id"),
            '$PLAYER': validated_data.get("player"),
            '$CHARACTER_NAME': validated_data.get("name").encode("utf-8")
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            return {"success": True}, 204
        else:
            return self.internal_server_error_response

    def _validate_character_name_is_unique(self, validated_data):
        # Checking if no other characters exist with the same name
        name_query = f"""
                    DECLARE $CHARACTER_NAME AS String;

                    SELECT * FROM {self.table_name}
                    WHERE
                    name = $CHARACTER_NAME
                    LIMIT 1
                ;
                """
        name_query_params = {
            '$CHARACTER_NAME': validated_data.get("name").encode("utf-8"),
        }
        name_result, name_code = self.yc.process_query(name_query, name_query_params)
        return name_code, name_result

    def _delete_character(self, char):
        query = f"""
            DECLARE $ID AS Int64;

            DELETE FROM {self.table_name}
            WHERE
                id = $ID
            ;
        """

        query_params = {
            '$ID': char
        }

        result, code = self.yc.process_query(query, query_params)

        if code == 0:
            return {"success": True}, 204
        else:
            return self.internal_server_error_response

    def modify_currency(self, char: int, free_xp_delta: int, silver_delta: int, gold_delta: int, source: str,
                        source_additional_data: str) -> typing.Tuple[
        dict, int]:
        """Used for changing currency (match rewards use internal batch granting function)"""

        r, s = self.API_GET({"id": char})
        if s != 200:
            return r, s
        else:
            char_data = r["data"]

        query = f"""
            DECLARE $ID AS Int64;
            DECLARE $FREE_XP AS Int64;
            DECLARE $SILVER AS Int64;
            DECLARE $GOLD AS Int64;
            
            UPDATE {self.table_name}
            SET 
                free_xp = $FREE_XP,
                silver = $SILVER,
                gold = $GOLD
            WHERE
                id = $ID
            ;
        """

        old_free_xp = char_data.get("free_xp")
        old_silver = char_data.get("silver")
        old_gold = char_data.get("gold")

        query_params = {
            '$ID': char,
            '$FREE_XP': max(old_free_xp + free_xp_delta, 0),
            '$SILVER': max(old_silver + silver_delta, 0),
            '$GOLD': max(old_gold + gold_delta, 0)
        }

        result, code = self.yc.process_query(query, query_params)

        if code == 0:
            self.__log_currency_change(char_data["player"], char, old_free_xp, free_xp_delta, old_silver,
                                       silver_delta, old_gold,
                                       gold_delta, source, source_additional_data)
            return {"success": True}, 204
        else:
            return self.internal_server_error_response

    def __log_currency_change(self, player, char, old_free_xp, free_xp_delta, old_silver, silver_delta, old_gold,
                              gold_delta, source, source_additional_data):
        ts = datetime.datetime.now(tz=datetime.timezone.utc)
        history_rel_path = f"{ts.year}-{ts.month:02d}-{ts.day:02d}.csv"
        history_path = self.s3_paths.get_character_currency_history_s3_path(player, char, history_rel_path)

        if self.s3.check_exists(history_path):
            content = self.s3.get_file_from_s3(history_path)
        else:
            content = b""

        content += f"{old_free_xp},{free_xp_delta}," \
                   f"{old_silver},{silver_delta}," \
                   f"{old_gold},{gold_delta}," \
                   f"{source.replace(',', '')},{source_additional_data.replace(',', '')}," \
                   f"{ts.hour}:{ts.minute}:{ts.second}\n".encode("utf-8")
        self.s3.upload_file_to_s3(content, history_path)


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    player = 4
    char = 2
    char_proc = CharacterProcessor(logger, "dev", player, yc, s3)
    # r, s = char_proc.API_CREATE(
    #     {"player": player, "name": "Bane Of Loyalists", "faction": "ChaosSpaceMarines"})

    # r, s = char_proc.API_LIST({"player": player})
    r, s = char_proc.API_GET({"id": char})
    print(s, r)
    # r, s = char_proc.API_MODIFY({"player": player, "id": 1, "name": "Bane of Loyalists"})
    # r, s = char_proc._delete_character(1)
    r, s = char_proc.modify_currency(char, 500000, 50000, 5000, "api_test", "")
    print(s, r)

    r, s = char_proc.API_GET({"id": char})
    print(s, r)
    # r, s = char_proc.batch_modify_currency({2: {"player": 4, "free_xp": 100, "silver": 100, "gold": 100}}, "api_test", "")
    # print(s, r)
