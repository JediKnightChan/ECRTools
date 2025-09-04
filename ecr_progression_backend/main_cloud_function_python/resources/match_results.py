import datetime
import os
import traceback
import typing
import uuid
import json

from marshmallow import fields, validate, ValidationError

from common import ResourceProcessor, AdminUser, batch_iterator
from tools.common_schemas import ExcludeSchema, ECR_FACTIONS
from tools.challenge import verify_challenge
from tools.tg_connection import send_telegram_message

# Constants
MATCH_REWARD_TIME_DELTA_THRESHOLD = int(os.getenv("MATCH_REWARD_TIME_DELTA_THRESHOLD", 0))

MATCH_REWARD_SILVER_HARD_LIMIT = int(os.getenv("MATCH_REWARD_SILVER_HARD_LIMIT", 1000))
MATCH_REWARD_XP_HARD_LIMIT = int(os.getenv("MATCH_REWARD_XP_HARD_LIMIT", 10000))
MATCH_REWARD_SILVER_SOFT_LIMIT = int(os.getenv("MATCH_REWARD_SILVER_SOFT_LIMIT", 999))
MATCH_REWARD_XP_SOFT_LIMIT = int(os.getenv("MATCH_REWARD_XP_SOFT_LIMIT", 9999))

MATCH_REWARD_AGGREGATION_THRESHOLD_PERIOD = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 86400))
MATCH_REWARD_AGGREGATION_MAX_VALUE_XP = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 50000))
MATCH_REWARD_AGGREGATION_MAX_VALUE_SILVER = int(os.getenv("MATCH_REWARD_AGGREGATION_THRESHOLD", 5000))

# Campaign status variables
CURRENT_CAMPAIGN_NAME = os.getenv("CURRENT_CAMPAIGN_NAME", "TestCampaign")


class CharMatchResultsSchema(ExcludeSchema):
    player = fields.Int(required=True)
    char = fields.Int(required=True)
    silver = fields.Int(required=True)
    xp = fields.Int(required=True)
    achievements = fields.Dict(keys=fields.Str(), values=fields.Int(), required=True)
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
    host = fields.Int(required=True)
    mission = fields.Str(required=True)
    created_ts = fields.Int(required=True)
    finished_ts = fields.Int(required=True)

    max_granted_silver = fields.Int(required=True)
    max_granted_xp = fields.Int(required=True)
    players_rewarded = fields.Int(required=True)


class MatchResultsProcessor(ResourceProcessor):
    """Processes match results"""

    def __init__(self, logger, contour, user, yc, s3):
        super(MatchResultsProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_matches")
        self.players_table_name = self.get_table_name_for_contour("ecr_players")
        self.chars_table_name = self.get_table_name_for_contour("ecr_characters")
        self.ach_table_name = self.get_table_name_for_contour("ecr_achievements")
        self.campaign_table_name = self.get_table_name_for_contour("ecr_campaign_results")
        self.campaign_chars_table_name = self.get_table_name_for_contour("ecr_campaign_results_chars")

        # Remember all quest names
        self.all_quest_names = []
        for faction in ECR_FACTIONS:
            filepath = f"../data/quests/quests_{faction.lower()}.json"
            final_filepath = os.path.join(os.path.dirname(__file__), filepath)
            with open(final_filepath) as f:
                quest_data = json.load(f)
                self.all_quest_names += list(quest_data.keys())

    def API_CREATE(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Registers match in the backend system. Usable by anyone, including players"""

        schema = MatchCreateSchema(only=("match_id", "mission"))
        try:
            validated_data = schema.load(request_body)

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
                '$MISSION': validated_data.get("mission"),
                '$CREATED_TIME': created_time
            }

            result, code = self.yc.process_query(query, query_params)
            if code == 0:
                return {"success": True, "data": {"token": token}}, 201
            else:
                return self.internal_server_error_response

        except ValidationError as e:
            return {"error": e.messages}, 400
        except Exception as e:
            self.logger.error(f"Exception during character CREATE with body {request_body}: {traceback.format_exc()}")
            return self.internal_server_error_response

    def API_MODIFY(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Applies match results (rewards) in the backend system. Usable by anyone, including players,
        challenge must be passed to verify results are not fake"""

        match_results_schema = MatchResultsSchema()

        match_results_validated = match_results_schema.load(request_body)

        # Received properties
        received_challenge = match_results_validated.get("challenge")
        match_id = match_results_validated.get("match_id").hex

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
        if code == 0:
            if len(result) > 0:
                if len(result[0].rows) > 0:
                    match_schema = MatchCreateSchema()
                    match_creation_data = match_schema.dump(result[0].rows[0])
                else:
                    return {"success": False, "data": {}}, 404
            else:
                return {"success": False, "data": None}, 500
        else:
            return self.internal_server_error_response

        # Check challenge
        if not self.is_user_server_or_backend():
            if not verify_challenge(received_challenge, match_creation_data, match_results_validated):
                send_telegram_message(f"Challenge fail: user {self.user} failed challenge for match {match_id}")
                return {"success": False, "error": "Not authorized"}, 403

        # Check that user is same as created match
        if str(match_creation_data["host"]) != str(self.user):
            send_telegram_message(f"Attempt to grant match results by non host: user {self.user} tried for match "
                                  f"{match_id} with host {match_creation_data['host']}")
            return {"success": False, "error": "Not found"}, 403

        # Check that match reward wasn't granted before
        if match_creation_data["finished_ts"] is not None:
            send_telegram_message(f"Attempt for second call to match results: user {self.user} "
                                  f"tried for match {match_id}")
            return {"success": False, "error": "Not found"}, 404

        # Check that at least N seconds passed since match creation
        now_ts = int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

        if now_ts - match_creation_data["created_ts"] < MATCH_REWARD_TIME_DELTA_THRESHOLD:
            send_telegram_message(
                f"Attempt to grant match reward for match below time threshold ({MATCH_REWARD_TIME_DELTA_THRESHOLD}): user {self.user} "
                f"tried for match {match_id}")
            return {"success": False, "error": "Bad request"}, 400

        max_silver = 0
        max_xp = 0

        currency_source = "match"
        currency_source_additional = f"match {match_id} by {match_creation_data['host']}"

        # This list ensures no player will receive XP more than once in a match
        players_granted_xp = []
        # Match results are grouped by char / faction to remove possible duplicates
        char_results = {char_result["char"]: char_result for char_result in match_results_validated["char_results"]}
        faction_results = {faction_result["faction"]: faction_result for faction_result in
                           match_results_validated["faction_results"]}

        # Batch requests to DB data with player rewards
        char_currency_modify_batch_request = {}
        player_xp_modify_batch_request = {}
        achievements_batch_request = []
        char_winners_batch_request = {}

        for char_result in char_results.values():
            char_result_xp = max(0, char_result["xp"])
            char_result_silver = max(0, char_result["silver"])

            # Checking soft limits to send warnings
            if char_result_xp > MATCH_REWARD_XP_SOFT_LIMIT:
                send_telegram_message(
                    f"SOFT XP limit exceeded by player {char_result['player']} (char {char_result['char']}) "
                    f"with {char_result_xp} in match {match_id} by host {self.user}")
            if char_result_silver > MATCH_REWARD_SILVER_SOFT_LIMIT:
                send_telegram_message(
                    f"SOFT SILVER limit exceeded by player {char_result['player']} (char {char_result['char']}) "
                    f"with {char_result_silver} in match {match_id} by host {self.user}")

            # Checking hard limits to decline reward
            if char_result_xp > MATCH_REWARD_XP_HARD_LIMIT:
                self.logger.error(f"Player {char_result['player']} (char {char_result['char']}) exceeded "
                                  f"hard XP limit with {char_result_xp} in match {match_id} by {self.user}")
                continue
            if char_result_silver > MATCH_REWARD_SILVER_HARD_LIMIT:
                self.logger.error(f"Player {char_result['player']} (char {char_result['char']}) exceeded "
                                  f"hard SILVER limit with {char_result_silver} in match {match_id} by {self.user}")
                continue

            # Granting XP to player
            if char_result["player"] not in players_granted_xp:
                # Will grant XP to player in batch request in the future
                player_xp_modify_batch_request[char_result["player"]] = char_result_xp
                players_granted_xp.append(char_result["player"])

            # Will grant XP and Silver to char in batch request in the future
            char_currency_modify_batch_request[char_result["char"]] = {
                "player": char_result["player"],
                "free_xp": char_result_xp,
                "silver": char_result_silver,
                "gold": 0
            }

            # Will grant achievement progress to char in batch request in the future
            for ach_name, ach_progress in char_result["achievements"].items():
                if ach_name in self.all_quest_names:
                    achievements_batch_request.append({
                        "char": char_result["char"],
                        "name": ach_name,
                        "progress_delta": ach_progress,
                    })

            # Will increase win count if campaign is ongoing (will work only from dedicated servers)
            if char_result["is_winner"]:
                char_winners_batch_request[char_result["char"]] = {}

            # Remember max given currency for statistics
            if char_result["xp"] > max_xp:
                max_xp = char_result["xp"]
            if char_result["silver"] > max_silver:
                max_silver = char_result["silver"]

        # Atomic transaction database changes (grant rewards, then mark match as finished, to avoid multiple rewards granting)
        tx_queries_and_params = []

        # Rewards (player xp, chars currencies, quest progress)
        tx_queries_and_params += self.__get_queries_for_batch_grant_xp(player_xp_modify_batch_request)
        tx_queries_and_params += self.__get_queries_for_batch_modify_currency(char_currency_modify_batch_request)
        tx_queries_and_params += self.__get_queries_for_batch_grant_quest_progress(achievements_batch_request)

        # If campaign is ongoing, then for factions that won increase win count (will work only from dedicated servers)
        print(faction_results)
        for faction, faction_result in faction_results.items():
            if faction_result["is_winner"]:
                tx_queries_and_params += self.__get_queries_to_notify_match_won_by_faction(faction)
        tx_queries_and_params += self.__get_queries_to_notify_chars_match_won(char_winners_batch_request)

        # Mark match as finished
        tx_queries_and_params += self.__get_queries_for_mark_match_finished(char_results, match_id, max_silver,
                                                                            max_xp)
        print(tx_queries_and_params)
        # Apply atomic transaction
        result, code = self.yc.process_queries_in_atomic_transaction(tx_queries_and_params)
        if code != 0:
            logger.error("Couldn't grant rewards because atomic transaction failed")
            return self.internal_server_error_response

        # If host is player, perform soft check to see how much max currency per match he granted within time interval
        self.__perform_aggregated_currency_grant_soft_check(match_id, max_silver, max_xp, now_ts)

        # Return success
        return {"success": True}, 200

    def __get_queries_for_mark_match_finished(self, char_results, match_id, max_silver, max_xp):
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
                max_granted_silver = $MAX_GRANTED_SILVER, 
                max_granted_xp = $MAX_GRANTED_XP, 
                players_rewarded = $PLAYERS_REWARDED
            WHERE
                match_id = $MATCH_ID
            ;
            """

        query_params = {
            '$MATCH_ID': match_id,
            '$FINISHED_TIME': finished_time,
            '$MAX_GRANTED_SILVER': max_silver,
            '$MAX_GRANTED_XP': max_xp,
            '$PLAYERS_REWARDED': len(char_results),
        }
        return [(query, query_params)]

    def __perform_aggregated_currency_grant_soft_check(self, match_id, max_silver, max_xp, now_ts):
        """If player is as host, then check soft limits for granting xp and silver within some time (eg 1 day)"""

        if not self.is_user_server_or_backend():
            query = f"""
                DECLARE $HOST AS Utf8;
                DECLARE $CREATED_TIME AS Datetime;

                SELECT
                    COALESCE(SUM(max_granted_silver), 0) AS sum_max_granted_silver,
                    COALESCE(SUM(max_granted_xp), 0) AS sum_max_granted_xp
                FROM {self.table_name}
                WHERE 
                    host = $HOST AND 
                    created_ts >= $CREATED_TIME
                ;
                """

            query_params = {
                '$HOST': str(self.user),
                '$CREATED_TIME': now_ts - MATCH_REWARD_AGGREGATION_THRESHOLD_PERIOD,
            }

            result, code = self.yc.process_query(query, query_params)

            if code == 0:
                if len(result) > 0:
                    if len(result[0].rows) > 0:
                        aggregated_reward_data = result[0].rows[0]
                        sum_max_granted_silver = aggregated_reward_data["sum_max_granted_silver"] + max_silver
                        sum_max_granted_xp = aggregated_reward_data["sum_max_granted_xp"] + max_xp
                        if sum_max_granted_silver > MATCH_REWARD_AGGREGATION_MAX_VALUE_SILVER:
                            send_telegram_message(f"AGGREGATED SILVER exceeded by host {self.user} "
                                                  f"with {sum_max_granted_silver} in match {match_id}")
                        if sum_max_granted_xp > MATCH_REWARD_AGGREGATION_MAX_VALUE_XP:
                            send_telegram_message(f"AGGREGATED XP exceeded by host {self.user} "
                                                  f"with {sum_max_granted_silver} in match {match_id}")
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
        """Constructs queries for batch currency modifying for characters"""

        queries_and_params = []

        for chunk in batch_iterator(chars_to_data.items(), 100):
            batch = [
                {
                    "id": char_id,
                    "player": char_data["player"],
                    "free_xp_delta": max(char_data["free_xp"], 0),
                    "silver_delta": max(char_data["silver"], 0),
                    "gold_delta": max(char_data["gold"], 0),
                }
                for char_id, char_data in chunk
            ]

            query = f"""
                DECLARE $batch AS List<Struct<id: Int64, free_xp_delta: Int64, silver_delta: Int64, gold_delta: Int64>>;

                UPSERT INTO {self.chars_table_name} (id, free_xp, silver, gold)
                SELECT
                    b.id,
                    COALESCE(t.free_xp, 0) + b.free_xp_delta AS free_xp,
                    COALESCE(t.silver, 0) + b.silver_delta AS silver,
                    COALESCE(t.gold, 0) + b.gold_delta AS gold
                FROM AS_TABLE($batch) AS b
                INNER JOIN {self.chars_table_name} AS t
                ON b.id = t.id;
            """

            query_params = {"$batch": batch}
            queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_for_batch_grant_quest_progress(self, ach_data: list):
        """Constructs queries for batch granting quest progress"""

        queries_and_params = []
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

    def __get_queries_to_notify_match_won_by_faction(self, faction):
        """Constructs queries to increase faction win count during campaign (for faction that won the match), only for dedicated servers"""

        queries_and_params = []
        if CURRENT_CAMPAIGN_NAME:
            if self.is_user_server_or_backend(allow_emulation=True):
                query = f"""
                    DECLARE $batch AS List<Struct<campaign: Utf8, faction: Utf8, won_delta: Int64>>;

                    UPSERT INTO {self.campaign_table_name} (campaign, faction, won_matches)
                    SELECT
                        b.campaign,
                        b.faction,
                        COALESCE(t.won_matches, 0) + b.won_delta AS won_matches
                    FROM AS_TABLE($batch) AS b
                    LEFT JOIN {self.campaign_table_name} AS t
                        ON b.campaign = t.campaign AND b.faction = t.faction;
                """

                query_params = {
                    "$batch": [{
                        "campaign": CURRENT_CAMPAIGN_NAME,
                        "faction": faction,
                        "won_delta": 1
                    }]
                }

                queries_and_params.append((query, query_params))
        return queries_and_params

    def __get_queries_to_notify_chars_match_won(self, char_wins):
        """Constructs queries to increase character win counts in current campaign, only for dedicated servers"""

        queries_and_params = []
        if CURRENT_CAMPAIGN_NAME:
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


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector
    import time

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    player = 4
    char = 2
    match_proc = MatchResultsProcessor(logger, "dev", player, yc, s3)

    match_id = uuid.uuid4().hex
    r, s = match_proc.API_CREATE(
        {"match_id": match_id, "mission": "test"})
    print(s, r)

    time.sleep(2)

    # match_id = "8bbdf0e13d95466dbd2754209be33692"
    r, s = match_proc.API_MODIFY(
        {
            "match_id": match_id,
            "challenge": "",
            "char_results": [
                {
                    "player": player,
                    "char": char,
                    "silver": 1000,
                    "xp": 10000,
                    "achievements": {
                        "sm_altweapon_bolter": 10
                    },
                    "is_winner": True
                }
            ],
            "faction_results": [
                {
                    "faction": "LoyalSpaceMarines",
                    "is_winner": True
                }
            ]
        }
    )
    print(s, r)
