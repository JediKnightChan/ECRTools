import json
import logging
import traceback
import typing
import datetime
import uuid

from common import ResourceProcessor, permission_required, APIPermission
from tools.common_schemas import CharPlayerSchema, ECR_FACTIONS
from tools.ydb_connection import YDBConnector
from marshmallow import fields, validate, ValidationError


class CharacterSchema(CharPlayerSchema):
    name = fields.Str(
        required=True,
        validate=validate.Regexp(
            regex=r'^[a-zA-Z\s]+$',
            error='String must contain only English characters and spaces.'
        )
    )
    faction = fields.Str(
        required=True,
        validate=validate.OneOf(ECR_FACTIONS),
    )

    guild = fields.UUID(required=False)
    guild_role = fields.Int(required=False)
    campaign_progress = fields.Int(required=False)


class CharacterProcessor(ResourceProcessor):
    """Retrieve data about characters, create and modify them"""

    def __init__(self, logger, contour, user):
        super(CharacterProcessor, self).__init__(logger, contour, user)

        self.yc = YDBConnector(logger)
        self.uuid_namespace = uuid.UUID('d824c96d-64b0-5ffd-a7ad-68ff02af0f07')

        self.table_name = "characters" if self.contour == "prod" else "characters_dev"

    @permission_required(APIPermission.SERVER_OR_OWNING_PLAYER)
    def API_LIST(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all characters data for given player_id. Only owning player or server can do it"""

        schema = CharacterSchema(only=("player_id",))

        try:
            validated_data = schema.load(request_body)

            query = f"""
                DECLARE $PLAYER_ID AS Utf8;

                SELECT * FROM {self.table_name}
                WHERE
                    player_id = $PLAYER_ID
                ;
            """

            query_params = {
                '$PLAYER_ID': validated_data.get("player_id"),
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

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character LIST with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get character by id, everyone can do it"""

        schema = CharacterSchema(only=("id",))

        try:
            validated_data = schema.load(request_body)

            query = f"""
                DECLARE $ID AS Utf8;

                SELECT * FROM {self.table_name}
                WHERE
                    id = $ID
                ;
            """

            query_params = {
                '$ID': validated_data.get("id").hex,
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

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_CREATE(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Create character, ID is generated with UUID. Only owning player can do it"""

        schema = CharacterSchema(only=("player_id", "faction", "name"))

        try:
            validated_data = schema.load(request_body)

            r, s = self.API_LIST({"player_id": validated_data.get("player_id")})
            if s == 200:
                # Checking if character with the same faction doesn't exist for the player
                already_existing_factions = [c["faction"] for c in r["data"]]
                if validated_data.get("faction") in already_existing_factions:
                    return {"success": False,
                            "error_code": 1,
                            "error": "Character of this faction already exists for this player"}, \
                           400

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

            # Generating character id
            dt = datetime.datetime.utcnow()
            character_id = uuid.uuid5(self.uuid_namespace, validated_data.get("player_id")
                                      + str(dt.timestamp())).hex

            # Creating character folder
            self.s3.upload_file_to_s3(
                json.dumps({"ts": dt.timestamp(), "initial_name": validated_data.get("name")}),
                self.s3_paths.get_char_folder_file_s3_path(validated_data.get("player_id"), character_id,
                                                           "creation_data.json")
            )

            # Creating row in YDB table
            query = f"""
                DECLARE $ID AS Utf8;
                DECLARE $PLAYER_ID AS Utf8;
                DECLARE $CHARACTER_NAME AS String;
                DECLARE $FACTION AS Utf8;

                UPSERT INTO {self.table_name} (id, player_id, name, faction, guild, guild_role, campaign_progress) VALUES
                    ($ID, $PLAYER_ID, $CHARACTER_NAME, $FACTION, NULL, NULL, NULL);
            """

            query_params = {
                '$ID': character_id,
                '$PLAYER_ID': validated_data.get("player_id"),
                '$CHARACTER_NAME': validated_data.get("name").encode("utf-8"),
                '$FACTION': validated_data.get("faction")
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                return {"success": True}, 201
            else:
                return self.internal_server_error_response

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character CREATE with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Allow to modify only character of yours (its name), query is filtered by player_id"""

        # Excluding faction from schema
        schema = CharacterSchema(partial=("faction",))

        try:
            validated_data = schema.load(request_body)

            query = f"""
                DECLARE $ID AS Utf8;
                DECLARE $PLAYER_ID AS Utf8;
                DECLARE $CHARACTER_NAME AS String;

                UPDATE {self.table_name}
                SET 
                name = $CHARACTER_NAME,
                faction = faction,
                player_id = player_id,
                guild = guild,
                guild_role = guild_role,
                campaign_progress = campaign_progress
                WHERE
                    id = $ID 
                    AND player_id = $PLAYER_ID
                ;
            """

            query_params = {
                '$ID': validated_data.get("id").hex,
                '$PLAYER_ID': validated_data.get("player_id"),
                '$CHARACTER_NAME': validated_data.get("name").encode("utf-8")
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                return {"success": True}, 204
            else:
                return self.internal_server_error_response

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character MODIFY with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response


if __name__ == '__main__':
    player_id = "earlydevtestplayerid"
    char_proc = CharacterProcessor(logging.getLogger(__name__), "dev", player_id)
    # r, s = char_proc.API_CREATE(
    #     {"player_id": "earlydevtestplayerid", "name": "JUST A TEST CHAR", "faction": "LoyalSpaceMarines"})

    r, s = char_proc.API_LIST({"player_id": player_id})
    # r, s = char_proc.API_GET(
    #     {"id": "68f2381b653656b7a5bf9a52e0cd2ca9"})

    # r, s = char_proc.API_MODIFY({"id": "68f2381b653656b7a5bf9a52e0cd2ca9", "name": "Loyal Legionnaire"})
    print(s, r)
