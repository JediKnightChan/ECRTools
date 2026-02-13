import datetime
import os
import traceback
import typing
import uuid
import json

from marshmallow import fields, validate, ValidationError

from common import ResourceProcessor, CURRENT_CAMPAIGN_NAME, batch_iterator, permission_required, api_view, \
    APIPermission
from resources.daily_activity import DailyActivityProcessor, DailyActivitySchema
from tools.common_schemas import ExcludeSchema, ECR_FACTIONS
from tools.challenge import verify_challenge
from tools.tg_connection import send_telegram_message

# Constants for checking rewards granting abuse (due to P2P nature of the game)
MATCH_REWARD_TIME_DELTA_THRESHOLD = int(os.getenv("MATCH_REWARD_TIME_DELTA_THRESHOLD", 0))
MATCH_REWARD_XP_HARD_LIMIT = int(os.getenv("MATCH_REWARD_XP_HARD_LIMIT", 10000))
MATCH_AGGREGATION_THRESHOLD_PERIOD = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 86400))
MATCH_AGGREGATION_MAX_VALUE_XP = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 100000))
MATCH_AGGREGATION_MAX_VALUE_MATCH_COUNT = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 10))

# Silver rewards for PvP and PvE modes for winning team / losing team
MATCH_SILVER_REWARDS = {
    "pvp": [200, 200],
    "pve": [300, 0]
}


class CharMatchResultsSchema(ExcludeSchema):
    player = fields.Int(required=True)
    char = fields.Int(required=True)
    xp = fields.Int(required=True)
    achievements = fields.Dict(keys=fields.Str(), values=fields.Int(), required=True)
    dailies = fields.Dict(keys=fields.Str(), values=fields.Int(), required=True, validate=validate.Length(max=3))
    is_winner = fields.Bool(required=True)


class FactionMatchResultsSchema(ExcludeSchema):
    faction = fields.Str(required=True, validate=validate.OneOf(ECR_FACTIONS))
    is_winner = fields.Bool(required=True)


class MatchResultsSchema(ExcludeSchema):
    match_id = fields.UUID(required=True)
    challenge = fields.Str(required=True)
    char_results = fields.List(fields.Nested(CharMatchResultsSchema), required=True)
    faction_results = fields.List(fields.Nested(FactionMatchResultsSchema), required=True)


class MatchCreateSchema(ExcludeSchema):
    match_id = fields.UUID(required=True)
    token = fields.UUID(required=True)
    host = fields.Str(required=True)
    mission = fields.Str(required=True)
    created_ts = fields.Int(required=True)
    finished_ts = fields.Int(required=True)

    max_granted_xp = fields.Int(required=True)
    players_rewarded = fields.Int(required=True)


class MatchResultsProcessor(ResourceProcessor):
    """Processes match results"""

    def __init__(self, logger, contour, user, yc, s3):
        super(MatchResultsProcessor, self).__init__(logger, contour, user, yc, s3)

        self.dap = DailyActivityProcessor(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_matches")
        self.players_table_name = self.get_table_name_for_contour("ecr_players")
        self.chars_table_name = self.get_table_name_for_contour("ecr_characters")
        self.ach_table_name = self.get_table_name_for_contour("ecr_achievements")
        self.campaign_table_name = self.get_table_name_for_contour("ecr_campaign_results")
        self.campaign_chars_table_name = self.get_table_name_for_contour("ecr_campaign_results_chars")
        self.dailies_table_name = self.get_table_name_for_contour("ecr_dailies")

        # Remember all achievements names
        self.all_achievements_names = []
        for faction in ECR_FACTIONS:
            filepath = f"../data/quests/quests_{faction.lower()}.json"
            final_filepath = os.path.join(os.path.dirname(__file__), filepath)
            with open(final_filepath) as f:
                achievements_data = json.load(f)
                self.all_achievements_names += list(achievements_data.keys())

        # Remember all missions data
        missions_filepath = os.path.join(os.path.dirname(__file__), f"../data/missions/missions.json")
        with open(missions_filepath, "r") as f:
            self.missions_data = json.load(f)

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_CREATE(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Registers match in the backend system. Usable by anyone, including players"""

        schema = MatchCreateSchema(only=("match_id", "mission"))
        validated_data = schema.load(request_body)
        mission = validated_data.get("mission").lower()

        # Check mission is correct
        if mission not in self.missions_data:
            return {"error": f"Mission {mission} is unknown"}, 400

        # Generated properties
        created_time = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        token = uuid.uuid4().hex

        # Creating row in YDB table
        query = f"""
            DECLARE $MATCH_ID AS Utf8;
            DECLARE $TOKEN AS Utf8;
            DECLARE $HOST AS Utf8;
            DECLARE $MISSION AS Utf8;
            DECLARE $CREATED_TIME AS Datetime;

            UPSERT INTO {self.table_name} (match_id, token, host, mission, created_ts, finished_ts, max_granted_silver, max_granted_xp, players_rewarded) VALUES
                ($MATCH_ID, $TOKEN, $HOST, $MISSION, $CREATED_TIME, NULL, NULL, NULL, NULL);
        """

        query_params = {
            '$MATCH_ID': validated_data.get("match_id").hex,
            '$TOKEN': token,
            '$HOST': str(self.user),
            '$MISSION': mission,
            '$CREATED_TIME': created_time
        }

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            silver_reward_win = self.get_silver_reward_for_mission(mission, True)
            silver_reward_lose = self.get_silver_reward_for_mission(mission, False)
            return {
                "success": True,
                "data": {
                    "token": token,
                    "silver_reward_win": silver_reward_win,
                    "silver_reward_lose": silver_reward_lose
                }
            }, 201
        else:
            return self.internal_server_error_response

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Applies match results (rewards) in the backend system. Usable by anyone, including players,
        challenge must be passed to verify results are not fake"""

        match_results_schema = MatchResultsSchema()
        match_results = match_results_schema.load(request_body)
        match_id = match_results.get("match_id").hex

        # 1. Fetch match data and verify it can accept match results
        match_creation_data = self._get_and_verify_match(match_id, match_results.get("challenge"), match_results)
        if match_creation_data is None:
            return {"success": False, "error": "Granting results not possible"}, 404

        # 2. Process match results into batch DB operations
        tx_queries_and_params, max_xp = self._process_match_results(match_results, match_creation_data)

        # 3. Apply transaction
        result, code = self.yc.process_queries_in_atomic_transaction(tx_queries_and_params)
        if code != 0:
            self.logger.error("Couldn't grant rewards because atomic transaction failed")
            return self.internal_server_error_response

        # 4. Soft check for suspicious grants
        now_ts = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        self.__perform_aggregated_currency_grant_soft_check(
            match_id, now_ts
        )

        # Return success
        return {"success": True}, 200

    def _get_and_verify_match(self, match_id: str, received_challenge: str, match_results: dict) -> typing.Optional[
        dict]:
        """Fetch match from DB and check challenge, host, timing rules."""

        # Finding match, which was created on start
        query = f"""
            DECLARE $MATCH_ID AS Utf8;

            SELECT * FROM {self.table_name}
            WHERE
                match_id = $MATCH_ID
            ;
        """

        query_params = {
            '$MATCH_ID': match_id,
        }

        result, code = self.yc.process_query(query, query_params)

        # Check that match already exists in DB
        if code == 0 and len(result) > 0 and len(result[0].rows) > 0:
            match_schema = MatchCreateSchema()
            match_creation_data = match_schema.dump(result[0].rows[0])
        else:
            return None

        # Check challenge
        if not self.is_user_server_or_backend():
            if not verify_challenge(received_challenge, match_creation_data, match_results):
                send_telegram_message(f"Challenge fail: user {self.user} failed challenge for match {match_id}")
                return None

        # Check that user is same as created match
        if str(match_creation_data["host"]) != str(self.user):
            send_telegram_message(f"Attempt to grant match results by non host: user {self.user} tried for match "
                                  f"{match_id} with host {match_creation_data['host']}")
            return None

        # Check that match reward wasn't granted before
        if match_creation_data["finished_ts"] is not None:
            send_telegram_message(f"Attempt for second call to match results: user {self.user} "
                                  f"tried for match {match_id}")
            return None

        # Check that at least N seconds passed since match creation
        now_ts = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        if now_ts - match_creation_data["created_ts"] < MATCH_REWARD_TIME_DELTA_THRESHOLD:
            send_telegram_message(
                f"Attempt to grant match reward for match below time threshold ({MATCH_REWARD_TIME_DELTA_THRESHOLD}): user {self.user} "
                f"tried for match {match_id}")
            return None

        return match_creation_data

    def _process_match_results(self, match_results: dict, match_creation_data: dict):
        """Constructs batch queries for atomic transaction to save match results"""

        now_raw = datetime.datetime.now(tz=datetime.timezone.utc)
        daily_key, weekly_key = self.dap.get_daily_and_weekly_key_for_timestamp(now_raw)

        # Prepare batch requests
        player_xp_req, char_currency_req, achievements_req = {}, {}, []
        dailies_req, dailies_gold_req, char_winners_req = [], {}, {}
        max_xp = 0

        char_results = {c["char"]: c for c in match_results["char_results"]}
        faction_results = {f["faction"]: f for f in match_results["faction_results"]}

        chars_old_progress = self.__get_chars_dailies_progress(char_results.keys(), daily_key, weekly_key)
        if chars_old_progress is None:
            raise Exception("Couldn't fetch old daily progress for characters, aborting")

        players_granted_xp = []

        for char_result in char_results.values():
            self._process_char_result(
                char_result, match_creation_data["mission"], match_results["match_id"].hex,
                players_granted_xp, chars_old_progress,
                daily_key, weekly_key,
                player_xp_req, char_currency_req,
                achievements_req, dailies_req,
                dailies_gold_req, char_winners_req
            )
            max_xp = max(max_xp, char_result["xp"])

        # Build final queries
        tx_queries = []
        tx_queries += self.__get_queries_for_batch_grant_xp(player_xp_req)
        tx_queries += self.__get_queries_for_batch_modify_currency(char_currency_req)
        tx_queries += self.__get_queries_for_batch_grant_achievements_progress(achievements_req)
        tx_queries += self.__get_queries_for_batch_grant_daily_activity_progress(dailies_req)
        tx_queries += self.__get_queries_for_batch_grant_daily_activity_rewards(dailies_gold_req)

        # If campaign is ongoing, and it's PvP, then queries to notify about win (for faction, char) are added
        if len(faction_results) == 2:
            # Change campaign results only for 1vs1 faction matches, though for char activity anything is counted
            for faction, res in faction_results.items():
                tx_queries += self.__get_queries_to_notify_match_played_by_faction(faction,
                                                                                   match_creation_data["mission"],
                                                                                   res["is_winner"])
        tx_queries += self.__get_queries_to_notify_chars_match_won(char_winners_req, match_creation_data["mission"])

        tx_queries += self.__get_queries_for_mark_match_finished(char_results, match_results["match_id"].hex, max_xp)

        return tx_queries, max_xp

    def _process_char_result(
            self,
            char_result: dict,
            mission: str,
            match_id: str,
            players_granted_xp: list,
            chars_old_progress: dict,
            daily_key: str,
            weekly_key: str,
            player_xp_req: dict,
            char_currency_req: dict,
            achievements_req: list,
            dailies_req: list,
            dailies_gold_req: dict,
            char_winners_req: dict,
    ) -> None:
        """Process a single character result and update batch request collections."""

        char_id = char_result["char"]
        player_id = char_result["player"]
        char_xp = max(0, char_result["xp"])
        char_silver = self.get_silver_reward_for_mission(mission, char_result["is_winner"])

        # Limit checks
        self._check_reward_limits(char_id, player_id, char_xp, match_id)

        # XP grant
        if player_id not in players_granted_xp:
            player_xp_req[player_id] = char_xp
            players_granted_xp.append(player_id)

        # Currency grant
        char_currency_req[char_id] = {
            "player": player_id,
            "free_xp": char_xp,
            "silver": char_silver,
        }

        # Achievements
        for ach_name, ach_progress in char_result["achievements"].items():
            if ach_name.lower() in self.all_achievements_names:
                achievements_req.append({
                    "char": char_id,
                    "name": ach_name.lower(),
                    "progress_delta": ach_progress,
                })

        # Dailies and weeklies
        for daily_quest, progress_delta in char_result["dailies"].items():
            daily_quest = daily_quest.lower()

            if daily_quest not in self.dap.dailies_data or progress_delta <= 0:
                continue

            quest_data = self.dap.dailies_data[daily_quest]
            quest_type = quest_data["type"]
            quest_target_progress = quest_data["max_value"]
            quest_reward = quest_data["reward_gold"]

            # Date key differs for dailies and weeklies
            date_key = weekly_key if quest_type == "weekly" else daily_key

            # Daily wins capped at +1 per match
            if daily_quest == "daily_wins":
                progress_delta = min(progress_delta, 1)

            dailies_req.append({
                "char": char_id,
                "date_key": date_key,
                "type": quest_type,
                "quest": daily_quest,
                "progress_delta": progress_delta,
            })

            # Daily rewards
            old_progress_key = (char_id, quest_type, daily_quest)
            if old_progress_key in chars_old_progress:
                old_progress = chars_old_progress[old_progress_key]["progress"]
                if old_progress < quest_target_progress <= old_progress + progress_delta:
                    dailies_gold_req[char_id] = dailies_gold_req.get(char_id, 0) + quest_reward

        # Campaign winner tracking for chars
        if char_result.get("is_winner"):
            char_winners_req[char_id] = {}

    def _check_reward_limits(self, char_id: int, player_id: int, xp: int, match_id: str) -> None:
        """Checks that for given player rewards are within soft / hard limits"""

        if xp > MATCH_REWARD_XP_HARD_LIMIT:
            send_telegram_message(
                f"HARD XP limit exceeded by player {player_id} (char {char_id}) "
                f"with {xp} in match {match_id} by host {self.user}"
            )
            self.logger.error(
                f"Player {player_id} (char {char_id}) exceeded hard XP limit "
                f"with {xp} in match {match_id} by {self.user}"
            )
            raise ValueError("Hard XP limit exceeded")

    def __get_chars_dailies_progress(self, chars: typing.Iterable, daily_key: str, weekly_key: str) -> typing.Union[
        dict, None]:
        """Retrieves from DB daily activity progress for the specified chars"""

        query = f"""
            DECLARE $batch AS List<Struct<char:Int64, date:Utf8, type:Utf8>>;
            
            SELECT t.*
            FROM AS_TABLE($batch) AS b
            LEFT JOIN {self.dailies_table_name} AS t
              ON  t.char = b.char
              AND t.date = b.date
              AND t.type = b.type;
        """

        batch = []
        for char in chars:
            batch += [
                {"char": char, "date": daily_key, "type": "daily1"},
                {"char": char, "date": daily_key, "type": "daily2"},
                {"char": char, "date": weekly_key, "type": "weekly"},
            ]
        query_params = {"$batch": batch}

        result, code = self.yc.process_query(query, query_params)
        if code == 0:
            if len(result) > 0:
                if len(result[0].rows) > 0:
                    dump_schema = DailyActivitySchema()
                    dumped_rows = [dump_schema.dump(r) for r in result[0].rows]
                    dailies_index = {}
                    for row in dumped_rows:
                        dailies_index[(row["char"], row["type"], row["quest"])] = row
                    return dailies_index

        logger.error("Couldn't retrieve data about daily activity")
        return None

    def __get_queries_for_mark_match_finished(self, char_results, match_id, max_xp):
        """Constructs query for updating match data in DB, eg set match as completed"""

        finished_time = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())
        query = f"""
            DECLARE $MATCH_ID AS Utf8;
            DECLARE $FINISHED_TIME AS Datetime;
            DECLARE $MAX_GRANTED_SILVER AS Int32;
            DECLARE $MAX_GRANTED_XP AS Int32;
            DECLARE $PLAYERS_REWARDED AS Int32;

            UPDATE {self.table_name}
            SET 
                finished_ts = $FINISHED_TIME,
                max_granted_xp = $MAX_GRANTED_XP, 
                players_rewarded = $PLAYERS_REWARDED
            WHERE
                match_id = $MATCH_ID
            ;
            """

        query_params = {
            '$MATCH_ID': match_id,
            '$FINISHED_TIME': finished_time,
            '$MAX_GRANTED_XP': max_xp,
            '$PLAYERS_REWARDED': len(char_results),
        }
        return [(query, query_params)]

    def __perform_aggregated_currency_grant_soft_check(self, match_id, now_ts):
        """If player is as host, then check soft limits for granting xp and silver within some time (eg 1 day)"""

        if not self.is_user_server_or_backend():
            query = f"""
                DECLARE $HOST AS Utf8;
                DECLARE $CREATED_TIME AS Datetime;

                SELECT
                    COALESCE(SUM(max_granted_xp), 0) AS sum_max_granted_xp,
                    COUNT(*) AS matches_count
                FROM {self.table_name}
                WHERE 
                    host = $HOST AND 
                    created_ts >= $CREATED_TIME
                ;
                """

            query_params = {
                '$HOST': str(self.user),
                '$CREATED_TIME': now_ts - MATCH_AGGREGATION_THRESHOLD_PERIOD,
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                if len(result) > 0:
                    if len(result[0].rows) > 0:
                        aggregated_reward_data = result[0].rows[0]
                        sum_max_granted_xp = aggregated_reward_data["sum_max_granted_xp"]
                        total_created_matches = aggregated_reward_data["matches_count"]
                        if sum_max_granted_xp > MATCH_AGGREGATION_MAX_VALUE_XP:
                            send_telegram_message(f"AGGREGATED XP exceeded by host {self.user} "
                                                  f"with {sum_max_granted_xp} in match {match_id}")
                        if total_created_matches > MATCH_AGGREGATION_MAX_VALUE_MATCH_COUNT:
                            send_telegram_message(f"AGGREGATED MATCH COUNT exceeded by host {self.user} "
                                                  f"with {total_created_matches} in match {match_id}")
                    else:
                        logger.error("Couldn't perform aggregated reward check, no rows")
                else:
                    logger.error("Couldn't perform aggregated reward check, no result")
            else:
                logger.error("Couldn't perform aggregated reward check, internal error")

    def __get_queries_for_batch_grant_xp(self, players_to_xp_deltas: dict) -> list:
        """Construct queries for internal batch granting XP"""

        queries_and_params = []
        for chunk in batch_iterator(players_to_xp_deltas.items(), 100):
            batch = [
                {"id": player_id, "delta": max(xp_delta, 0)}
                for player_id, xp_delta in chunk
            ]

            query = f"""
                DECLARE $batch AS List<Struct<id: Int64, delta: Int64>>;

                UPSERT INTO {self.players_table_name} (id, xp)
                SELECT
                    b.id,
                    COALESCE(t.xp, 0) + b.delta AS xp
                FROM AS_TABLE($batch) AS b
                INNER JOIN {self.players_table_name} AS t
                ON b.id = t.id;
            """

            query_params = {"$batch": batch}

            queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_for_batch_modify_currency(self, chars_to_data: dict) -> list:
        """Constructs queries for batch currency (XP, silver) modifying for characters"""

        queries_and_params = []

        for chunk in batch_iterator(chars_to_data.items(), 100):
            batch = [
                {
                    "id": char_id,
                    "player": char_data["player"],
                    "free_xp_delta": max(char_data["free_xp"], 0),
                    "silver_delta": max(char_data["silver"], 0)
                }
                for char_id, char_data in chunk
            ]

            query = f"""
                DECLARE $batch AS List<Struct<id: Int64, free_xp_delta: Int64, silver_delta: Int64>>;

                UPSERT INTO {self.chars_table_name} (id, free_xp, silver)
                SELECT
                    b.id,
                    COALESCE(t.free_xp, 0) + b.free_xp_delta AS free_xp,
                    COALESCE(t.silver, 0) + b.silver_delta AS silver
                FROM AS_TABLE($batch) AS b
                INNER JOIN {self.chars_table_name} AS t
                ON b.id = t.id;
            """

            query_params = {"$batch": batch}
            queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_for_batch_grant_achievements_progress(self, ach_data: list):
        """Constructs queries for batch granting achievements progress, dedicated servers only"""

        queries_and_params = []
        if self.is_user_server_or_backend(allow_emulation=True):
            for chunk in batch_iterator(ach_data, 200):
                batch = [
                    {
                        "char": ach_data_piece["char"],
                        "name": ach_data_piece["name"],
                        "progress_delta": max(ach_data_piece["progress_delta"], 0),
                    }
                    for ach_data_piece in chunk
                ]

                query = f"""
                    DECLARE $batch AS List<Struct<char: Int64, name: Utf8, progress_delta: Int64>>;
    
                    UPSERT INTO {self.ach_table_name} (char, name, progress)
                    SELECT
                        b.char,
                        b.name,
                        COALESCE(t.progress, 0) + b.progress_delta AS progress
                    FROM AS_TABLE($batch) AS b
                    LEFT JOIN {self.ach_table_name} AS t
                        ON b.char = t.char AND b.name = t.name;
                """

                query_params = {"$batch": batch}
                queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_for_batch_grant_daily_activity_progress(self, daily_progress):
        """Constructs queries for batch update daily activities"""

        queries_and_params = []
        for chunk in batch_iterator(daily_progress, 200):
            batch = [
                {
                    "char": el["char"],
                    "date": el["date_key"],
                    "type": el["type"],
                    "quest": el["quest"],
                    "progress_delta": max(el["progress_delta"], 0),
                }
                for el in chunk
            ]

            query = f"""
                DECLARE $batch AS List<Struct<char: Int64, date: Utf8, type: Utf8, quest: Utf8, progress_delta: Int64>>;

                UPSERT INTO {self.dailies_table_name} (char, date, type, quest, progress)
                SELECT
                    b.char,
                    b.date,
                    b.type,
                    b.quest,
                    COALESCE(t.progress, 0) + b.progress_delta AS progress
                FROM AS_TABLE($batch) AS b
                INNER JOIN {self.dailies_table_name} AS t
                    ON t.char = b.char
                   AND t.date = b.date
                   AND t.type = b.type
                   AND t.quest = b.quest;
            """

            query_params = {"$batch": batch}
            queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_for_batch_grant_daily_activity_rewards(self, chars_to_gold):
        """Constructs queries for batch grant gold reward for daily activities"""

        queries_and_params = []
        for chunk in batch_iterator(chars_to_gold.items(), 200):
            batch = [
                {
                    "id": char,
                    "gold_delta": max(gold, 0)
                }
                for char, gold in chunk
            ]

            query = f"""
                DECLARE $batch AS List<Struct<id: Int64, gold_delta: Int64>>;

                UPSERT INTO {self.chars_table_name} (id, gold)
                SELECT
                    b.id,
                    COALESCE(t.gold, 0) + b.gold_delta AS gold
                FROM AS_TABLE($batch) AS b
                INNER JOIN {self.chars_table_name} AS t
                ON b.id = t.id;
            """

            query_params = {"$batch": batch}
            queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_to_notify_match_played_by_faction(self, faction, mission, did_win):
        """Constructs queries to increase faction win count during campaign (for faction that won the match), only for dedicated servers"""

        queries_and_params = []
        if CURRENT_CAMPAIGN_NAME and self.is_mission_pvp(mission):
            if self.is_user_server_or_backend(allow_emulation=True):
                query = f"""
                    DECLARE $batch AS List<Struct<campaign: Utf8, faction: Utf8, won_delta: Int64, played_delta: Int64>>;

                    UPSERT INTO {self.campaign_table_name} (campaign, faction, won_matches, played_matches)
                    SELECT
                        b.campaign,
                        b.faction,
                        COALESCE(t.won_matches, 0) + b.won_delta AS won_matches,
                        COALESCE(t.played_matches, 0) + b.played_delta AS played_matches
                    FROM AS_TABLE($batch) AS b
                    LEFT JOIN {self.campaign_table_name} AS t
                        ON b.campaign = t.campaign AND b.faction = t.faction;
                """

                query_params = {
                    "$batch": [{
                        "campaign": CURRENT_CAMPAIGN_NAME,
                        "faction": faction,
                        "won_delta": 1 if did_win else 0,
                        "played_delta": 1
                    }]
                }

                queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_to_notify_chars_match_won(self, char_wins, mission):
        """Constructs queries to increase character win counts in current campaign, only for dedicated servers"""

        queries_and_params = []
        if CURRENT_CAMPAIGN_NAME and self.is_mission_pvp(mission):
            if self.is_user_server_or_backend(allow_emulation=True):
                for chunk in batch_iterator(char_wins.items(), 100):
                    batch = [
                        {
                            "char": char_id,
                            "campaign": CURRENT_CAMPAIGN_NAME,
                            "won_delta": 1
                        }
                        for char_id, _ in chunk
                    ]

                    query = f"""
                        DECLARE $batch AS List<Struct<char: Int64, campaign: Utf8, won_delta: Int64>>;
    
                        UPSERT INTO {self.campaign_chars_table_name} (char, campaign, won_matches)
                        SELECT
                            b.char,
                            b.campaign,
                            COALESCE(t.won_matches, 0) + b.won_delta AS won_matches
                        FROM AS_TABLE($batch) AS b
                        LEFT JOIN {self.campaign_chars_table_name} AS t
                            ON b.char = t.char AND b.campaign = t.campaign;
                    """

                    query_params = {"$batch": batch}

                    queries_and_params.append((query, query_params))
        return queries_and_params

    def get_silver_reward_for_mission(self, mission, is_winner):
        """Returns silver reward for given mission considering if it's victory or not"""

        mission_mode = self.missions_data[mission]["mode"]
        reward_list = MATCH_SILVER_REWARDS[mission_mode]
        reward_list_index = 0 if is_winner else 1
        return reward_list[reward_list_index]

    def is_mission_pvp(self, mission):
        """Returns True if mission is PvP"""

        return self.missions_data[mission]["mode"] == "pvp"


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector
    import time

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    player = "server"
    char = 2
    match_proc = MatchResultsProcessor(logger, "dev", player, yc, s3)

    match_id = uuid.uuid4().hex
    r, s = match_proc.API_CREATE(
        {"match_id": match_id, "mission": "ThirdPersonMapTestingRoom"})
    print(s, r)

    time.sleep(2)

    # match_id = "8bbdf0e13d95466dbd2754209be33692"
    r, s = match_proc.API_MODIFY(
        {
            "match_id": match_id,
            "challenge": "",
            "char_results": [
                {
                    "player": 4,
                    "char": char,
                    "xp": 10000,
                    "achievements": {
                        "title_theemperorsfinest": 10000
                    },
                    "dailies": {
                        "weekly_captures": 1,
                        "daily_wins": 1,
                        "non_existing_daily": 13,
                    },
                    "is_winner": True
                }
            ],
            "faction_results": [
                {
                    "faction": "LoyalSpaceMarines",
                    "is_winner": True
                },
                {
                    "faction": "ChaosSpaceMarines",
                    "is_winner": False
                }
            ]
        }
    )
    print(s, r)
