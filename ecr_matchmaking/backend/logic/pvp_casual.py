import time

from logic.common import try_create_pvp_match_common

TIME_THRESHOLD_FOR_DUEL = 60
TIME_THRESHOLD_FOR_MEDIUM_SIZED_MATCH = 45


def determine_team_size_casual(faction1_count, faction2_count, oldest_player_queue_time):
    """ Determines appropriate team size based on player count and time elapsed from oldest player queued"""

    team_size = min(faction1_count, faction2_count, 16)
    max_team_size = max(faction1_count, faction2_count)

    if team_size < 1:
        # Not enough for any match: [0, 1)
        return None, None, None, None
    elif team_size < 5:
        if oldest_player_queue_time > TIME_THRESHOLD_FOR_DUEL:
            # Enough only for duel: [1, 5)
            return min(max_team_size, 5), 1, 5, "duel"
        return None, None, None, None  # Wait for more players
    elif team_size < 8:
        if oldest_player_queue_time > TIME_THRESHOLD_FOR_MEDIUM_SIZED_MATCH:
            # Enough for medium-sized matched (e.g. Hold The Line): [5, 8)
            return min(max_team_size, 8), 5, 8, "medium"
        return None, None, None, None
    else:
        # Large battles: [8, 16]
        return min(max_team_size, 16), 8, 16, "large"


def determine_team_size_instant_pvp(faction1_count, faction2_count, oldest_player_queue_time):
    """Instantly starts a pvp match"""

    max_team_size = max(faction1_count, faction2_count)
    return max_team_size, 0, 8, "medium"


def try_create_pvp_match_casual(player_data_map: dict, oldest_player_queue_time: float, matchmaking_config_for_mode: dict,
                                instant_creation=False):
    return try_create_pvp_match_common(player_data_map, oldest_player_queue_time, matchmaking_config_for_mode,
                                       determine_team_size_instant_pvp if instant_creation else determine_team_size_casual,
                                       ignore_faction_min_amount=instant_creation)
