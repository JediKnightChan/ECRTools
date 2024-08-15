import json
import traceback
import typing
import os

from common import ResourceProcessor, permission_required, APIPermission
from marshmallow import Schema, fields, validate, ValidationError

from resources.combined_main_menu import CombinedMainMenuProcessor
from resources.player import PlayerProcessor
from tools.common_schemas import CharPlayerSchema


class ProgressionItemType:
    GAMEPLAY_ITEM = "GAMEPLAY_ITEM"
    COSMETIC_ITEM = "COSMETIC_ITEM"
    ADVANCEMENT = "ADVANCEMENT"


ALLOWED_PROGRESSION_ITEM_TYPES = [
    ProgressionItemType.GAMEPLAY_ITEM,
    ProgressionItemType.COSMETIC_ITEM,
    ProgressionItemType.ADVANCEMENT
]


class UnlockedProgressionModifySchema(CharPlayerSchema):
    item = fields.Str(required=True)
    item_type = fields.Str(required=True, validate=validate.OneOf(ALLOWED_PROGRESSION_ITEM_TYPES))


class UnlockedProgressionContentSchema(Schema):
    unlocked_gameplay_items = fields.List(fields.Str())
    unlocked_cosmetic_items = fields.List(fields.Str())
    unlocked_advancements = fields.List(fields.Str())
    quest_status = fields.Dict(keys=fields.Str(), values=fields.Int())


class ProgressionStoreProcessor(ResourceProcessor):
    """Purchase and view unlocked progression (cosmetic items, gameplay items, advancements, quests) for characters"""

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Gets unlocked progression for given character. Anyone can do it"""

        schema = CharPlayerSchema()
        try:
            validated_data = schema.load(request_body)

            player_id = validated_data.get("player_id")
            character_id = validated_data.get("id").hex
            progression_path = self.s3_paths.get_unlocked_progression_s3_path(player_id, character_id)

            # Check if file with unlocked cosmetics data exists
            if self.s3.check_exists(self.s3_paths.get_unlocked_progression_s3_path(player_id, character_id)):
                content = self.s3.get_file_from_s3(progression_path)
                data = json.loads(content)

                json_schema = UnlockedProgressionContentSchema()
                try:
                    data = json_schema.load(data)
                except ValidationError:
                    return {"success": False, "error_code": 2, "error": "Unlocked progression data malformed"}, 500
                return {"success": True, "data": data}, 200
            else:
                # Check for character existence
                if self.s3.check_exists(self.s3_paths.get_character_existence_s3_path(player_id, character_id)):
                    return {"success": True, "data": {"unlocked_gameplay_items": [], "unlocked_cosmetic_items": [],
                                                      "unlocked_advancements": [], "quest_status": {}}}, 200
                else:
                    # Char doesn't exist, raise 404
                    return {"success": False, "error_code": 1,
                            "error": "Character not found"}, 404

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during progression GET with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """
        Buy a progression entity (gameplay or cosmetic item or advancement) for a given character.
        Checking item availability, amount of currency, character level and other requirements (quest, advancement).

        Only owning player can do it.
        """

        already_unlocked_data, s = self.API_GET(request_body)
        if s != 200:
            return already_unlocked_data, s

        schema = UnlockedProgressionModifySchema()

        try:
            validated_data = schema.load(request_body)

            player_id = validated_data.get("player_id")
            character_id = validated_data.get("id").hex
            item_id = validated_data.get("item").lower()
            item_type = validated_data.get("item_type")

            unlocked_gameplay_items = already_unlocked_data["data"]["unlocked_gameplay_items"]
            unlocked_cosmetic_items = already_unlocked_data["data"]["unlocked_cosmetic_items"]
            unlocked_advancements = already_unlocked_data["data"]["unlocked_advancements"]
            quest_status = already_unlocked_data["data"]["quest_status"]

            if item_type == ProgressionItemType.GAMEPLAY_ITEM:
                old_unlocked_items = unlocked_gameplay_items.copy()
                unlocked_gameplay_items.append(item_id)
                log_action = "buy_gameplay_item"
            elif item_type == ProgressionItemType.COSMETIC_ITEM:
                old_unlocked_items = unlocked_cosmetic_items.copy()
                unlocked_cosmetic_items.append(item_id)
                log_action = "buy_cosmetic_item"
            elif item_type == ProgressionItemType.ADVANCEMENT:
                old_unlocked_items = unlocked_advancements.copy()
                unlocked_advancements.append(item_id)
                log_action = "buy_advancement"
            else:
                raise ValueError(f"Wrong ProgressionItemType: {item_type}")

            if item_id in old_unlocked_items:
                # Already unlocked this
                return {"success": False, "error_code": 3, "error": "Already unlocked"}, 400

            main_menu_proc = CombinedMainMenuProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
            player_proc = PlayerProcessor(self.logger, self.contour, self.user, self.yc, self.s3)

            main_menu_data, main_menu_s = main_menu_proc.API_GET({"player_id": player_id})
            if main_menu_s != 200:
                return main_menu_data, main_menu_s

            player_data = main_menu_data["data"]["player"]
            player_free_xp = player_data["free_xp"]
            player_silver = player_data["silver"]
            player_gold = player_data["gold"]
            player_level = player_data["level"]

            char_data = None
            for char_data_piece in main_menu_data["data"]["characters"]:
                if char_data_piece["id"] == character_id:
                    char_data = char_data_piece

            if char_data is None:
                return {"error": f"No character {character_id}", "error_code": 1}, 404

            char_faction = char_data["faction"]

            item_found, item_data = self.get_item_data(item_id, item_type, char_faction)
            if not item_found:
                # Item not found
                self.logger.warning(f"Entity not found {item_type} for faction {char_faction}: item {item_id}")
                return {"success": False, "error_code": 4, "error": f"Entity not found: "
                                                                    f"{item_id}, {item_type}, {char_faction}"}, 404

            item_cost_xp, item_cost_silver, item_cost_gold = item_data["cost"]

            item_is_purchasable = item_data["is_purchasable"]
            item_required_level = item_data["required_level"]
            item_required_advancement = item_data["required_advancement"]
            item_required_quest = item_data["required_quest"]

            # Check item is purchasable
            if not item_is_purchasable:
                return {"error": "Item can't be purchased", "error_code": 5}, 400

            # Check item advancement was unlocked
            if item_required_advancement and item_required_advancement not in unlocked_advancements:
                return {"error": f"Advancement {item_required_advancement} required", "error_code": 6}, 400

            # Check item quest was unlocked
            if item_required_quest and not self.check_quest(item_required_quest, quest_status):
                return {"error": f"Quest {item_required_quest} required", "error_code": 7}, 400

            # Check level
            if player_level < item_required_level:
                return {"error": f"Not enough level ({player_level} < {item_required_level})", "error_code": 8}, 400

            # Check cost
            if player_gold >= item_cost_gold and player_silver >= item_cost_silver and player_free_xp >= item_cost_xp:
                # Can afford, buy
                self.update_unlocked_items(player_id, character_id, unlocked_gameplay_items,
                                           unlocked_cosmetic_items, unlocked_advancements, quest_status)
                r, s = player_proc.modify(player_id, 0, -item_cost_xp, -item_cost_silver, -item_cost_gold, log_action,
                                          f"{item_id} for {character_id}")
                if s == 204:
                    return {"success": True, "cost": [item_cost_xp, item_cost_silver, item_cost_gold]}, 200
                else:
                    return r, s
            else:
                # Can't afford
                return {
                           "error": f"Not enough currency, "
                                    f"needed: ({item_cost_xp}, {item_cost_silver}, {item_cost_gold}), "
                                    f"available ({player_free_xp}, {player_silver}, {player_gold})",
                           "error_code": 9}, 400
        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during cosmetics MODIFY with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def check_quest(self, quest_name: str, player_quest_status: dict) -> bool:
        return True

    def update_unlocked_items(self, player_id, character_id, unlocked_gameplay_items,
                              unlocked_cosmetic_items, unlocked_advancements, quest_status):
        progression_path = self.s3_paths.get_unlocked_progression_s3_path(
            player_id,
            character_id
        )

        new_data = {
            "unlocked_gameplay_items": unlocked_gameplay_items,
            "unlocked_cosmetic_items": unlocked_cosmetic_items,
            "unlocked_advancements": unlocked_advancements,
            "quest_status": quest_status
        }

        schema = UnlockedProgressionContentSchema()
        new_content = schema.dumps(new_data)
        self.s3.upload_file_to_s3(new_content, progression_path)

    def get_item_data(self, item_id: str, item_type: str, faction: str) -> typing.Tuple[bool, dict]:
        if item_type == ProgressionItemType.GAMEPLAY_ITEM:
            filepath = f"../data/gameplay_items/gameplay_items_{faction.lower()}.json"
        elif item_type == ProgressionItemType.COSMETIC_ITEM:
            filepath = f"../data/cosmetic_items/cosmetic_items_{faction.lower()}.json"
        elif item_type == ProgressionItemType.ADVANCEMENT:
            filepath = f"../data/advancements/advancements_{faction.lower()}.json"
        else:
            raise ValueError(f"Wrong ProgressionItemType: {item_type}")

        final_filepath = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(final_filepath):
            with open(final_filepath) as f:
                item_data = json.load(f)
                print(item_data)
                if item_id in item_data:
                    return True, item_data[item_id]
                else:
                    return False, {}
        else:
            self.logger.warning(f"Progression filepath {filepath} doesn't exist")
            return False, {}

    def _clear_all_progression(self, player_id, character_id):
        self.update_unlocked_items(player_id, character_id, [], [], [], {})


if __name__ == '__main__':
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector
    import logging

    player_id = "c5a7eea3e4c14aecaf4b73a3891bf7d3"
    char_id = "79e06c5855fb527e866b25a7fc1281b7"
    item_id = "BA_Torso_ChaliceAndWings"
    item_type = ProgressionItemType.COSMETIC_ITEM

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()
    store = ProgressionStoreProcessor(logger, "dev", player_id, yc, s3)

    r, s = store.API_GET({"player_id": player_id, "id": char_id})
    # r, s = store.API_MODIFY({"player_id": player_id, "id": char_id, "item": item_id, "item_type": item_type})
    print(r, s)

    # store._clear_all_progression(player_id, char_id)

