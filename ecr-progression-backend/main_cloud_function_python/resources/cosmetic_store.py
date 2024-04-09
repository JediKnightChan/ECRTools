import json
import logging
import traceback
import typing

from common import ResourceProcessor
from marshmallow import Schema, fields, ValidationError

from resources.character import CharacterProcessor
from resources.player import PlayerProcessor
from tools.common_schemas import CharPlayerSchema


class UnlockedCosmeticsGetSchema(CharPlayerSchema):
    pass


class UnlockedCosmeticsModifySchema(CharPlayerSchema):
    item = fields.Str(required=True)


class UnlockedCosmeticsContentSchema(Schema):
    unlocked_cosmetics = fields.List(fields.Str())


class CosmeticStoreProcessor(ResourceProcessor):
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Gets unlocked cosmetic items for given character"""

        schema = UnlockedCosmeticsGetSchema()
        try:
            validated_data = schema.load(request_body)

            player_id = validated_data.get("player_id")
            character_id = validated_data.get("id").hex
            cosmetics_path = self.s3_paths.get_unlocked_cosmetics_s3_path(player_id, character_id)

            # Check if file with unlocked cosmetics data exists
            if self.s3.check_exists(self.s3_paths.get_unlocked_cosmetics_s3_path(player_id, character_id)):
                content = self.s3.get_file_from_s3(cosmetics_path)
                data = json.loads(content)

                json_schema = UnlockedCosmeticsContentSchema()
                try:
                    data = json_schema.load(data)
                except ValidationError:
                    return {"success": False, "error_code": 2, "error": "Unlocked cosmetics data malformed"}, 500
                return {"success": True, "data": data}, 200
            else:
                # Check for character existence
                if self.s3.check_exists(self.s3_paths.get_character_existence_s3_path(player_id, character_id)):
                    return {"success": True, "data": {"unlocked_cosmetics": []}}, 200
                else:
                    # Char doesn't exist, raise 404
                    return {"success": False, "error_code": 1,
                            "error": "Character not found"}, 404

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during cosmetics GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """
        Buy a cosmetic item for a given character. Checking item availability, amount of gold, character level.
        Faction is not checked, player may potentially unlock wrong cosmetics, but they won't be available in the match
        """

        already_unlocked_data, s = self.API_GET(request_body)
        if s != 200:
            return already_unlocked_data, s

        unlocked_cosmetics = already_unlocked_data["data"]["unlocked_cosmetics"]

        schema = UnlockedCosmeticsModifySchema()
        try:

            validated_data = schema.load(request_body)

            player_id = validated_data.get("player_id")
            character_id = validated_data.get("id").hex
            item_id = validated_data.get("item")

            if item_id in unlocked_cosmetics:
                # Already unlocked this
                return {"success": False, "error_code": 3, "error": "Already unlocked"}, 400

            item_found, item_data = self.get_item_data(item_id)
            if not item_found:
                # Item not found
                return {"success": False, "error_code": 4, "error": "Item not found"}, 404

            item_cost_gold = item_data["cost_gold"]
            item_can_be_bought = item_data["can_be_bought"]
            item_required_level = item_data["required_level"]

            if not item_can_be_bought:
                # Can't buy this item
                return {"error": "Item can't be bought", "error_code": 5}, 400

            player_proc = PlayerProcessor(self.logger, self.contour)

            player_data, player_s = player_proc.API_GET({"id": player_id})
            if player_s != 200:
                return player_data, player_s

            gold = player_data["data"]["gold"]
            player_level = player_data["data"]["level"]

            if player_level < item_required_level:
                return {"error": f"Not enough level ({player_level} < {item_required_level})", "error_code": 6}, 400

            if gold >= item_cost_gold:
                # Can afford, buy
                self.update_unlocked_items(player_id, character_id, unlocked_cosmetics + [item_id])
                r, s = player_proc.modify(player_id, 0, 0, 0, -item_cost_gold, "buy_cosmetic", item_id)
                if s == 204:
                    return {"success": True}, 200
                else:
                    return r, s
            else:
                # Can't afford
                return {"error": f"Not enough gold ({gold} < {item_cost_gold})", "error_code": 7}, 400
        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during cosmetics MODIFY with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def update_unlocked_items(self, player_id, character_id, new_unlocked_items):
        cosmetics_path = self.s3_paths.get_unlocked_cosmetics_s3_path(
            player_id,
            character_id
        )

        new_data = {
            "unlocked_cosmetics": new_unlocked_items
        }

        schema = UnlockedCosmeticsContentSchema()
        new_content = schema.dumps(new_data)
        self.s3.upload_file_to_s3(new_content, cosmetics_path)

    @staticmethod
    def get_item_data(item_id) -> typing.Tuple[bool, dict]:
        with open("../data/cosmetics.json", "rb") as f:
            cosmetics_data = json.load(f)
            if item_id in cosmetics_data:
                return True, cosmetics_data[item_id]
            else:
                return False, {}


if __name__ == '__main__':
    store = CosmeticStoreProcessor(logging.getLogger(__name__), "dev")

    player_id = "earlydevtestplayerid"
    char_id = "68f2381b653656b7a5bf9a52e0cd2ca9"
    item_id = "test_cosmetic_item"
    # r, s = store.API_MODIFY({"player_id": player_id, "id": char_id, "item": item_id})
    r, s = store.API_GET({"player_id": player_id, "id": char_id})
    print(r, s)
