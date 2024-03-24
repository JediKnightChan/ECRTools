import datetime
import json
import logging
import traceback
import typing
import pandas as pd

from common import ResourceProcessor
from marshmallow import Schema, fields, validate, ValidationError

from resources.character import CharacterProcessor
from tools.common_schemas import CharPlayerSchema


class CurrencyGetSchema(CharPlayerSchema):
    pass


class CurrencyContentSchema(Schema):
    xp = fields.Integer(required=True)
    free_xp = fields.Integer(required=True)
    silver = fields.Integer(required=True)
    gold = fields.Integer(required=True)


class CurrencyProcessor(ResourceProcessor):
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get currency data for given player id and character id"""

        schema = CurrencyGetSchema()
        try:
            validated_data = schema.load(request_body)

            currency_path = self.s3_paths.get_currency_s3_path(
                validated_data.get("player_id"),
                validated_data.get("id").hex
            )

            if self.s3.check_exists(currency_path):
                content = self.s3.get_file_from_s3(currency_path)
                data = json.loads(content)

                json_schema = CurrencyContentSchema()
                try:
                    data = json_schema.load(data)
                except ValidationError:
                    return {"success": False, "error_code": 2, "error": "Currency data malformed"}, 500
                return {"success": True, "data": data}, 200
            else:
                # Check for character existence
                if self.s3.check_exists(self.s3_paths.get_character_existence_s3_path(validated_data.get("player_id"),
                                                                                      validated_data.get("id").hex)):
                    return {"success": True, "data": {"xp": 0, "free_xp": 0, "silver": 0, "gold": 0}}, 200
                else:
                    # Char doesn't exist
                    return {"success": False, "error_code": 1,
                            "error": "Character not found"}, 404

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during currency GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def save_currency_data(self, player_id, character_id, xp, free_xp, silver, gold):
        data = {
            "xp": max(xp, 0),
            "free_xp": max(free_xp, 0),
            "silver": max(silver, 0),
            "gold": max(gold, 0)
        }

        json_schema = CurrencyContentSchema()
        json_content = json_schema.dumps(data)
        self.s3.upload_file_to_s3(json_content, self.s3_paths.get_currency_s3_path(
            player_id,
            character_id
        ))
        return data

    def log_currency_change(self, player_id, character_id, xp_delta, free_xp_delta, silver_delta, gold_delta, source,
                            source_additional_data):
        ts = datetime.datetime.utcnow()
        history_rel_path = f"{ts.year}-{ts.month:02d}-{ts.day:02d}.csv"
        history_path = self.s3_paths.get_currency_history_s3_path(player_id, character_id, history_rel_path)

        if self.s3.check_exists(history_path):
            content = self.s3.get_file_from_s3(history_path)
        else:
            content = b""

        content += f"{xp_delta},{free_xp_delta},{silver_delta},{gold_delta}," \
                   f"{source.replace(',', '')},{source_additional_data.replace(',', '')},{ts.timestamp()}\n".encode(
            "utf-8")
        self.s3.upload_file_to_s3(content, history_path)

    def change_currencies(self, player_id: str, character_id: str, xp_delta: int, free_xp_delta: int, silver_delta: int,
                          gold_delta: int, source: str,
                          source_additional_data: str = ""):

        r, s = self.API_GET({"player_id": player_id, "id": character_id})
        if s == 200:
            data = r["data"]

            if xp_delta != 0:
                self.process_xp_change(player_id, character_id, data["xp"], xp_delta)

            self.log_currency_change(player_id, character_id, xp_delta, free_xp_delta, silver_delta, gold_delta, source,
                                     source_additional_data)
            self.save_currency_data(
                player_id, character_id,
                data["xp"] + xp_delta, data["free_xp"] + free_xp_delta,
                data["silver"] + silver_delta, data["gold"] + gold_delta
            )
            return {"success": True}, 204
        else:
            return r, s

    def process_xp_change(self, player_id, character_id, old_xp, xp_delta):
        new_level = self.get_level_from_xp(old_xp + xp_delta)

        char_proc = CharacterProcessor(self.logger, self.contour)
        char_proc.change_level(player_id, character_id, new_level)

    @staticmethod
    def get_level_from_xp(xp):
        df = pd.read_csv("../data/levels.csv")
        level = 1
        for _, row in df.iterrows():
            if xp >= row["xp_amount"]:
                level = row["level"]
            else:
                break
        return level


if __name__ == '__main__':
    cur_proc = CurrencyProcessor(logging.getLogger(__name__), "dev")
    player_id = "earlydevtestplayerid"
    char_id = "38b920becf4d57d688f3ed6e4a2866c4"

    # cur_proc.change_currencies(player_id, char_id, 0, 0, 12, 100, "raw_testing")
    # r, s = cur_proc.API_GET({"player_id": player_id, "id": char_id})
    # print(s, r)

    print(cur_proc.get_level_from_xp(10000000))
