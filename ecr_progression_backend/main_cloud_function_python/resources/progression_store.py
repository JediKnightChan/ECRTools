import datetime
import json
import random
import typing
import os

from common import ResourceProcessor, permission_required, APIPermission, api_view, CURRENT_CAMPAIGN_NAME
from marshmallow import Schema, fields, validate, ValidationError

from resources.player import PlayerProcessor
from resources.character import CharacterProcessor
from tools.common_schemas import CharPlayerSchema, ExcludeSchema


class ProgressionItemType:
    GAMEPLAY_ITEM = "GAMEPLAY_ITEM"
    COSMETIC_ITEM = "COSMETIC_ITEM"
    ADVANCEMENT = "ADVANCEMENT"


class LootboxType:
    SUPPLY_CRATE = "SupplyCrate"
    COSMETIC_BUNDLE_ONE_ITEM = "CosmeticBundleOneItem"


ALLOWED_PROGRESSION_ITEM_TYPES = [
    ProgressionItemType.GAMEPLAY_ITEM,
    ProgressionItemType.COSMETIC_ITEM,
    ProgressionItemType.ADVANCEMENT
]


class AchievementSchema(ExcludeSchema):
    char = fields.Int(required=True)
    name = fields.Str(required=True)
    progress = fields.Int(required=True)
    reward_claimed_time = fields.Int()


class PurchaseEntityRequestSchema(CharPlayerSchema):
    item = fields.Str(required=True)
    item_type = fields.Str(required=True, validate=validate.OneOf(ALLOWED_PROGRESSION_ITEM_TYPES))


class ClaimQuestRewardRequestSchema(CharPlayerSchema):
    quest_name = fields.Str(required=True)


class OpenLootboxRequestSchema(CharPlayerSchema):
    lootbox_name = fields.Str(required=True)


class UnlockedProgressionContentSchema(Schema):
    unlocked_gameplay_items = fields.List(fields.Str())
    unlocked_cosmetic_items = fields.List(fields.Str())
    unlocked_advancements = fields.List(fields.Str())
    unlocked_titles = fields.List(fields.Str())


class ProgressionStoreProcessor(ResourceProcessor):
    """Purchase and view unlocked progression (cosmetic items, gameplay items, advancements, quests) for characters"""

    def __init__(self, logger, contour, user, yc, s3):
        super(ProgressionStoreProcessor, self).__init__(logger, contour, user, yc, s3)

        self.ach_table_name = self.get_table_name_for_contour("ecr_achievements")
        self.campaign_char_results_table_name = self.get_table_name_for_contour("ecr_campaign_results_chars")

    def API_CUSTOM_ACTION(self, action: str, request_body: dict) -> typing.Tuple[dict, int]:
        if action == "buy":
            return self.API_BUY(request_body)
        elif action == "claim_quest_reward":
            return self.API_CLAIM_QUEST_REWARD(request_body)
        elif action == "open_lootbox":
            return self.API_OPEN_LOOTBOX(request_body)

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict, include_achievements: bool = True, include_campaign_progress: bool = True) -> \
            typing.Tuple[dict, int]:
        """Gets unlocked progression for given character. Anyone can do it"""

        schema = CharPlayerSchema()
        validated_data = schema.load(request_body)

        player = validated_data.get("player")
        char = validated_data.get("char")
        progression_path = self.s3_paths.get_unlocked_progression_s3_path(player, char)

        achievements = {}
        if include_achievements:
            query = f"""
                DECLARE $CHAR AS Int64;

                SELECT * FROM {self.ach_table_name}
                WHERE
                    char = $CHAR
                ;
            """

            query_params = {
                '$CHAR': validated_data.get("char"),
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                if len(result) > 0:
                    dump_schema = AchievementSchema()
                    achievements_raw = [dump_schema.dump(r) for r in result[0].rows]
                    for achievement in achievements_raw:
                        achievements[achievement["name"]] = {
                            "progress": achievement["progress"],
                            "reward_claimed_time": achievement["reward_claimed_time"]
                        }
            else:
                return self.internal_server_error_response

        campaign_progress = -1
        if include_campaign_progress and CURRENT_CAMPAIGN_NAME:
            query = f"""
                DECLARE $CHAR AS Int64;
                DECLARE $CAMPAIGN AS Utf8;

                SELECT * FROM {self.campaign_char_results_table_name}
                WHERE
                    char = $CHAR AND
                    campaign = $CAMPAIGN
                LIMIT 1;
            """

            query_params = {
                '$CHAR': validated_data.get("char"),
                '$CAMPAIGN': CURRENT_CAMPAIGN_NAME,
            }

            result, code = self.yc.process_query(query, query_params)
            if code != 0 or len(result) == 0:
                raise Exception("Failed to get campaign progress")

            if len(result[0].rows) == 0:
                campaign_progress = 0
            else:
                campaign_progress = result[0].rows[0]["won_matches"]

        # Check if file with unlocked cosmetics data exists
        if self.s3.check_exists(progression_path):
            content = self.s3.get_file_from_s3(progression_path)
            data = json.loads(content)

            json_schema = UnlockedProgressionContentSchema()
            try:
                data = json_schema.load(data)
            except ValidationError:
                return {"success": False, "error_code": 2, "error": "Unlocked progression data malformed"}, 500

            return {
                "success": True,
                "data": {
                    **data,
                    "campaign_progress": campaign_progress,
                    "quest_status": achievements
                }
            }, 200
        else:
            return {
                "success": True,
                "data": {
                    "unlocked_gameplay_items": [],
                    "unlocked_cosmetic_items": [],
                    "unlocked_advancements": [],
                    "unlocked_titles": [],
                    "campaign_progress": campaign_progress,
                    "quest_status": achievements
                }
            }, 200

    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_BUY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """
        Buy a progression entity (gameplay or cosmetic item or advancement) for a given character.
        Checking item availability, amount of currency, character level

        Only owning player can do it.
        """

        already_unlocked_data, s = self.API_GET(request_body, include_achievements=False)
        if s != 200:
            return already_unlocked_data, s

        schema = PurchaseEntityRequestSchema()

        validated_data = schema.load(request_body)

        player = validated_data.get("player")
        char = validated_data.get("char")
        item_id = validated_data.get("item").lower()
        item_type = validated_data.get("item_type")

        unlocked_gameplay_items = already_unlocked_data["data"]["unlocked_gameplay_items"]
        unlocked_cosmetic_items = already_unlocked_data["data"]["unlocked_cosmetic_items"]
        unlocked_advancements = already_unlocked_data["data"]["unlocked_advancements"]
        unlocked_titles = already_unlocked_data["data"]["unlocked_titles"]

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

        player_proc = PlayerProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        player_data, player_s = player_proc.API_GET({"id": player})
        if player_s != 200:
            return player_data, player_s

        player_level = player_proc.get_level_from_xp(player_data["data"]["xp"])

        character_proc = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        character_data, character_s = character_proc.API_LIST({"player": player})
        if character_s != 200:
            return character_data, character_s

        char_data = None
        for char_data_piece in character_data["data"]:
            if char_data_piece["id"] == char:
                char_data = char_data_piece

        if char_data is None:
            return {"error": f"No character {char}", "error_code": 1}, 404

        char_faction = char_data["faction"]
        char_free_xp = char_data["free_xp"]
        char_silver = char_data["silver"]
        char_gold = char_data["gold"]

        item_found, item_data = self._get_item_data(item_id, item_type, char_faction)
        if not item_found:
            # Item not found
            self.logger.warning(f"Entity not found {item_type} for faction {char_faction}: item {item_id}")
            return {"success": False, "error_code": 4, "error": f"Entity not found: "
                                                                f"{item_id}, {item_type}, {char_faction}"}, 404

        item_cost_xp, item_cost_silver, item_cost_gold = item_data["cost"]

        item_is_enabled = item_data["is_enabled"]
        item_is_purchasable = item_data["is_purchasable"]
        item_required_level = item_data.get("required_level", 0)
        item_required_advancement = item_data.get("required_advancement", None)

        # Check item is purchasable
        if not item_is_purchasable or not item_is_enabled:
            return {"error": "Item can't be purchased", "error_code": 5}, 400

        # Check item advancement was unlocked
        if item_required_advancement and item_required_advancement not in unlocked_advancements:
            return {"error": f"Advancement {item_required_advancement} required", "error_code": 6}, 400

        # Check level
        if player_level < item_required_level:
            return {"error": f"Not enough level ({player_level} < {item_required_level})", "error_code": 8}, 400

        # Check cost
        if char_gold >= item_cost_gold and char_silver >= item_cost_silver and char_free_xp >= item_cost_xp:
            # Can afford, buy

            # For advancement, unlock granted gameplay items too
            if item_type == ProgressionItemType.ADVANCEMENT:
                for granted_gameplay_item in item_data.get("granted_gameplay_items", []):
                    granted_gameplay_item = granted_gameplay_item.lower()
                    unlocked_gameplay_items.append(granted_gameplay_item)

            self.update_unlocked_items(player, char, unlocked_gameplay_items,
                                       unlocked_cosmetic_items, unlocked_advancements, unlocked_titles)
            r, s = character_proc.modify_currency(char, -item_cost_xp, -item_cost_silver,
                                                  -item_cost_gold, log_action,
                                                  f"{item_id} for {char}")
            if s == 204:
                return {"success": True, "cost": [item_cost_xp, item_cost_silver, item_cost_gold]}, 200
            else:
                return r, s
        else:
            # Can't afford
            return {
                "error": f"Not enough currency, "
                         f"needed: ({item_cost_xp}, {item_cost_silver}, {item_cost_gold}), "
                         f"available ({char_free_xp}, {char_silver}, {char_gold})",
                "error_code": 9}, 400

    @api_view
    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_CLAIM_QUEST_REWARD(self, request_body: dict) -> typing.Tuple[dict, int]:
        """
        Claim quest reward for a given character

        Only owning player can do it.
        """

        already_unlocked_data, s = self.API_GET(request_body, include_achievements=True)
        if s != 200:
            return already_unlocked_data, s

        schema = ClaimQuestRewardRequestSchema()

        validated_data = schema.load(request_body)

        player = validated_data.get("player")
        char = validated_data.get("char")
        quest_name = validated_data.get("quest_name").lower()

        unlocked_gameplay_items = already_unlocked_data["data"]["unlocked_gameplay_items"]
        unlocked_cosmetic_items = already_unlocked_data["data"]["unlocked_cosmetic_items"]
        unlocked_advancements = already_unlocked_data["data"]["unlocked_advancements"]
        unlocked_titles = already_unlocked_data["data"]["unlocked_titles"]

        character_proc = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        character_data, character_s = character_proc.API_LIST({"player": player})
        if character_s != 200:
            return character_data, character_s

        char_data = None
        for char_data_piece in character_data["data"]:
            if char_data_piece["id"] == char:
                char_data = char_data_piece

        if char_data is None:
            return {"error": f"No character {char}", "error_code": 1}, 404

        char_faction = char_data["faction"]

        found_quest, quest_data = self._get_quest_data(quest_name, char_faction)
        if not found_quest:
            return {"error": f"No quest {quest_name} for faction {char_faction}", "error_code": 2}, 404

        if self._check_quest(quest_name, already_unlocked_data["data"]["quest_status"], quest_data):
            # Grant item rewards
            for reward_gameplay_item in quest_data["reward_gameplay_items"]:
                reward_gameplay_item = reward_gameplay_item.lower()
                if reward_gameplay_item not in unlocked_gameplay_items:
                    unlocked_gameplay_items.append(reward_gameplay_item)

            for reward_cosmetic_item in quest_data["reward_cosmetic_items"]:
                reward_cosmetic_item = reward_cosmetic_item.lower()
                if reward_cosmetic_item not in unlocked_cosmetic_items:
                    unlocked_cosmetic_items.append(reward_cosmetic_item)

            reward_title = quest_data["reward_title"].lower()
            if reward_title and reward_title not in unlocked_titles:
                unlocked_titles.append(reward_title)

            self.update_unlocked_items(player, char, unlocked_gameplay_items,
                                       unlocked_cosmetic_items, unlocked_advancements, unlocked_titles)

            # Grant currencies
            reward_gold = quest_data["reward_gold"]
            reward_silver = quest_data["reward_silver"]
            reward_free_xp = quest_data["reward_free_xp"]

            if reward_gold != 0 or reward_silver != 0 or reward_free_xp != 0:
                r, s = character_proc.modify_currency(char, reward_free_xp, reward_silver,
                                                      reward_gold, "quest_reward",
                                                      f"{quest_name} for {char}")
                if s != 200:
                    return r, s

            # Marking quest as reward claimed
            query = f"""
                DECLARE $CHAR AS Int64;
                DECLARE $NAME AS Utf8;
                DECLARE $REWARD_CLAIMED_TIME AS Datetime;

                UPDATE {self.ach_table_name}
                SET
                    reward_claimed_time = $REWARD_CLAIMED_TIME
                WHERE
                    char = $CHAR
                    AND name = $NAME
                ;
            """

            query_params = {
                '$CHAR': char,
                '$NAME': quest_name,
                '$REWARD_CLAIMED_TIME': int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp()),
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                return {"success": True}, 200
            else:
                return self.internal_server_error_response
        else:
            return {"error": f"Quest {quest_name} not completed or already claimed on char {char}",
                    "error_code": 3}, 400

    @api_view
    @permission_required(APIPermission.OWNING_PLAYER_ONLY)
    def API_OPEN_LOOTBOX(self, request_body: dict) -> typing.Tuple[dict, int]:
        """
        Open lootbox for a given character

        Only owning player can do it
        """

        already_unlocked_data, s = self.API_GET(request_body, include_achievements=False)
        if s != 200:
            return already_unlocked_data, s

        schema = OpenLootboxRequestSchema()

        validated_data = schema.load(request_body)

        player = validated_data.get("player")
        char = validated_data.get("char")
        lootbox_name = validated_data.get("lootbox_name").lower()

        unlocked_gameplay_items = already_unlocked_data["data"]["unlocked_gameplay_items"]
        unlocked_cosmetic_items = already_unlocked_data["data"]["unlocked_cosmetic_items"]
        unlocked_advancements = already_unlocked_data["data"]["unlocked_advancements"]
        unlocked_titles = already_unlocked_data["data"]["unlocked_titles"]

        character_proc = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        character_data, character_s = character_proc.API_LIST({"player": player})
        if character_s != 200:
            return character_data, character_s

        char_data = None
        for char_data_piece in character_data["data"]:
            if char_data_piece["id"] == char:
                char_data = char_data_piece

        if char_data is None:
            return {"error": f"No character {char}", "error_code": 1}, 404

        char_faction = char_data["faction"]
        char_silver = char_data["silver"]
        char_gold = char_data["gold"]

        found_lootbox, lootbox_data = self._get_lootbox_data(lootbox_name, char_faction)
        if not found_lootbox:
            return {"error": f"No lootbox {lootbox_name} for faction {char_faction}", "error_code": 2}, 404

        _, lootbox_cost_silver, lootbox_cost_gold = lootbox_data["cost"]

        # Check cost
        if char_gold >= lootbox_cost_gold and char_silver >= lootbox_cost_silver:

            won_items = self._get_random_item_from_lootbox(char_faction, unlocked_gameplay_items,
                                                           unlocked_cosmetic_items,
                                                           lootbox_data)
            if won_items is None:
                return {"error": f"Lootbox {lootbox_name} not available for char {char}",
                        "error_code": 3}, 400

            if lootbox_data["type"] == LootboxType.SUPPLY_CRATE:
                for won_item in won_items:
                    won_item = won_item.lower()
                    if won_item not in unlocked_gameplay_items:
                        unlocked_gameplay_items.append(won_item)
            elif lootbox_data["type"] == LootboxType.COSMETIC_BUNDLE_ONE_ITEM:
                for won_item in won_items:
                    won_item = won_item.lower()
                    if won_item not in unlocked_cosmetic_items:
                        unlocked_cosmetic_items.append(won_item)
            else:
                raise NotImplementedError(f"Unknown lootbox type {lootbox_data['type']}")

            # Can afford, buy
            self.update_unlocked_items(player, char, unlocked_gameplay_items,
                                       unlocked_cosmetic_items, unlocked_advancements, unlocked_titles)
            r, s = character_proc.modify_currency(char, 0, -lootbox_cost_silver,
                                                  -lootbox_cost_gold, "buy_lootbox",
                                                  f"{lootbox_name} (won {won_items}) for {char}")

            if s == 204:
                return {"success": True, "cost": [0, lootbox_cost_silver, lootbox_cost_gold],
                        "won_items": won_items}, 200
            else:
                return r, s
        else:
            # Can't afford
            return {
                "error": f"Not enough currency, "
                         f"needed: ({lootbox_cost_silver}, {lootbox_cost_gold}), "
                         f"available ({char_silver}, {char_gold})",
                "error_code": 4}, 400

    def update_unlocked_items(self, player, char, unlocked_gameplay_items,
                              unlocked_cosmetic_items, unlocked_advancements,
                              unlocked_titles):
        progression_path = self.s3_paths.get_unlocked_progression_s3_path(
            player,
            char
        )

        new_data = {
            "unlocked_gameplay_items": list(set(unlocked_gameplay_items)),
            "unlocked_cosmetic_items": list(set(unlocked_cosmetic_items)),
            "unlocked_advancements": list(set(unlocked_advancements)),
            "unlocked_titles": list(set(unlocked_titles)),
        }

        schema = UnlockedProgressionContentSchema()
        new_content = schema.dumps(new_data)
        self.s3.upload_file_to_s3(new_content, progression_path)

    def _check_quest(self, quest_name: str, quests_for_player: dict, quest_data: dict) -> bool:
        quest_for_player = quests_for_player.get(quest_name, {})
        current_progress = quest_for_player.get("progress", 0)
        reward_claimed_time = quest_for_player.get("reward_claimed_time")
        if reward_claimed_time is not None:
            # Claimed reward
            return False
        else:
            return current_progress >= quest_data["max_value"]

    def _get_quest_data(self, quest_name: str, faction: str) -> typing.Tuple[bool, dict]:
        filepath = f"../data/quests/quests_{faction.lower()}.json"

        final_filepath = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(final_filepath):
            with open(final_filepath) as f:
                quest_data = json.load(f)
                if quest_name in quest_data:
                    return True, quest_data[quest_name]
                else:
                    return False, {}
        else:
            self.logger.warning(f"Quest filepath {filepath} doesn't exist")
            return False, {}

    def _get_random_item_from_lootbox(self, faction: str, player_unlocked_gameplay_items: list,
                                      player_unlocked_cosmetic_items: list,
                                      lootbox_data: dict) -> typing.Union[list, None]:
        lootbox_rarity_chances = lootbox_data["rarity_chances"]
        lootbox_main_rarity = lootbox_data["main_rarity"]

        lootbox_available = False
        rarity_to_items = {}

        lootbox_type = lootbox_data["type"]

        if lootbox_type == LootboxType.SUPPLY_CRATE:
            filepath = f"../data/gameplay_items/gameplay_items_{faction.lower()}.json"
            unlocked_items = player_unlocked_gameplay_items
            required_subfaction = None
        elif lootbox_type == LootboxType.COSMETIC_BUNDLE_ONE_ITEM:
            filepath = f"../data/cosmetic_items/cosmetic_items_{faction.lower()}.json"
            unlocked_items = player_unlocked_cosmetic_items
            required_subfaction = lootbox_data.get("required_subfaction", None)
        else:
            raise NotImplementedError(f"Not implemented lootbox type {lootbox_type}")

        final_filepath = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(final_filepath):
            with open(final_filepath) as f:
                item_data = json.load(f)
                for item, item_piece in item_data.items():
                    item = item.lower()
                    if item_piece["is_lootbox_granted"] and item not in unlocked_items:
                        if lootbox_main_rarity:
                            if item_piece["rarity"] == lootbox_main_rarity:
                                lootbox_available = True
                            elif item_piece["rarity"] not in lootbox_rarity_chances:
                                continue

                        if required_subfaction:
                            if item_piece.get("subfaction", None) == required_subfaction:
                                lootbox_available = True
                            else:
                                continue

                        rarity_to_items.setdefault(item_piece["rarity"], []).append(item)
        else:
            self.logger.warning(f"Items filepath {filepath} doesn't exist")
            return None

        if lootbox_available:
            if lootbox_type == LootboxType.SUPPLY_CRATE:
                # For supply crate, first get a rarity, then within it, get an item
                available_rarity_chances = {}
                for rarity, chance in lootbox_rarity_chances.items():
                    if rarity in rarity_to_items:
                        available_rarity_chances[rarity] = chance

                won_rarity = \
                    random.choices(list(available_rarity_chances.keys()), list(available_rarity_chances.values()), k=1)[
                        0]

                return [random.choice(rarity_to_items[won_rarity])]
            elif lootbox_type == LootboxType.COSMETIC_BUNDLE_ONE_ITEM:
                # For cosmetic bundle with 1 item, just select 1 item
                all_items = []
                for rarity, items in rarity_to_items.items():
                    all_items += items
                return [random.choice(all_items)]
            else:
                raise NotImplementedError(f"Not implemented lootbox type {lootbox_type}")
        else:
            return None

    def _get_lootbox_data(self, lootbox_name: str, faction: str) -> typing.Tuple[bool, dict]:
        filepath = f"../data/lootboxes/lootboxes_{faction.lower()}.json"

        final_filepath = os.path.join(os.path.dirname(__file__), filepath)
        if os.path.exists(final_filepath):
            with open(final_filepath) as f:
                lootbox_data = json.load(f)
                if lootbox_name in lootbox_data:
                    return True, lootbox_data[lootbox_name]
                else:
                    return False, {}
        else:
            self.logger.warning(f"Lootbox filepath {filepath} doesn't exist")
            return False, {}

    def _external_unlock(self, player, char, gameplay_items_to_unlock, cosmetics_to_unlock,
                         advancements_to_unlock, titles_to_unlock):
        already_unlocked_data, s = self.API_GET({"player": player, "char": char}, include_achievements=False,
                                                include_campaign_progress=False)

        if s != 200:
            return already_unlocked_data, s

        unlocked_gameplay_items = already_unlocked_data["data"]["unlocked_gameplay_items"]
        unlocked_cosmetic_items = already_unlocked_data["data"]["unlocked_cosmetic_items"]
        unlocked_advancements = already_unlocked_data["data"]["unlocked_advancements"]
        unlocked_titles = already_unlocked_data["data"]["unlocked_titles"]

        for item in gameplay_items_to_unlock:
            item = item.lower()
            if item not in unlocked_gameplay_items:
                unlocked_gameplay_items.append(item)

        for item in cosmetics_to_unlock:
            item = item.lower()
            if item not in unlocked_cosmetic_items:
                unlocked_cosmetic_items.append(item)

        for item in advancements_to_unlock:
            item = item.lower()
            if item not in unlocked_advancements:
                unlocked_advancements.append(item)

        for item in titles_to_unlock:
            item = item.lower()
            if item not in unlocked_titles:
                unlocked_titles.append(item)

        self.update_unlocked_items(player, char, unlocked_gameplay_items, unlocked_cosmetic_items,
                                   unlocked_advancements, unlocked_titles)
        return {"success": True}, 200

    def _external_unlock_everything(self, player, char):
        character_proc = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        character_data, character_s = character_proc.API_LIST({"player": player})
        if character_s != 200:
            return character_data, character_s

        char_data = None
        for char_data_piece in character_data["data"]:
            if char_data_piece["id"] == char:
                char_data = char_data_piece

        if char_data is None:
            return {"error": f"No character {char}", "error_code": 1}, 404

        faction = char_data["faction"]

        with open(f"../data/gameplay_items/gameplay_items_{faction.lower()}.json", "r", encoding="utf-8") as f:
            gameplay_items_data = json.load(f)
            gameplay_items = [el for el, data in gameplay_items_data.items()]

        with open(f"../data/cosmetic_items/cosmetic_items_{faction.lower()}.json", "r", encoding="utf-8") as f:
            cosmetic_items_data = json.load(f)
            cosmetic_items = [el for el, data in cosmetic_items_data.items()]

        with open(f"../data/advancements/advancements_{faction.lower()}.json", "r", encoding="utf-8") as f:
            advancements_data = json.load(f)
            advancements = [el for el, data in advancements_data.items()]

        with open(f"../data/quests/quests_{faction.lower()}.json", "r", encoding="utf-8") as f:
            quests_data = json.load(f)
            titles = [data["reward_title"] for el, data in quests_data.items() if data["reward_title"]]

        r, s = self._external_unlock(player, char, gameplay_items, cosmetic_items, advancements, titles)
        return r, s

    def _get_item_data(self, item_id: str, item_type: str, faction: str) -> typing.Tuple[bool, dict]:
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
                if item_id in item_data:
                    return True, item_data[item_id]
                else:
                    return False, {}
        else:
            self.logger.warning(f"Progression filepath {filepath} doesn't exist")
            return False, {}

    def _clear_all_progression(self, player, char, clear_quest_status=True):
        self.update_unlocked_items(player, char, [], [], [], [])

        if clear_quest_status:
            # Quest already existed, updating progress
            query = f"""
                DECLARE $CHAR as Int64;

                DELETE FROM {self.ach_table_name}
                WHERE
                    char = $CHAR
                ;
            """
            query_params = {
                '$CHAR': char,
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                return {"success": True}, 200
            else:
                return self.internal_server_error_response


if __name__ == '__main__':
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector
    import logging

    player = 4
    char = 2
    item_id = "sm_node_wg1_ja_fuel"
    item_type = ProgressionItemType.ADVANCEMENT

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()
    store = ProgressionStoreProcessor(logger, "dev", player, yc, s3)
    store._clear_all_progression(player, char)
    r, s = store.API_GET({"player": player, "char": char})
    # r, s = store.API_BUY({"player": player, "char": char, "item": item_id, "item_type": item_type})
    # r, s = store.API_CLAIM_QUEST_REWARD({"player": player, "char": char, "quest_name": "ba_veteran_t1"})
    # r, s = store.API_OPEN_LOOTBOX({"player": player, "char": char, "lootbox_name": "chapterbundle_ultramarines"})
    # r, s = store._external_unlock(player, char, ["SM_Multi-melta_Unique01"], [], [])
    # r, s = store._external_unlock_everything(player, char)
    print(r, s)

    # store._clear_all_progression(player, char)
