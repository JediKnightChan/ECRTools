import time

from logic.common import try_create_pvp_match_common

TIME_THRESHOLD_FOR_DUEL = 60
TIME_THRESHOLD_FOR_MEDIUM_SIZED_MATCH = 45


def determine_team_size_casual(faction1_count, faction2_count, latest_ts, current_ts=None):
    """ Determines appropriate team size based on player count and time elapsed from latest player queued"""

    if current_ts is None:
        current_ts = time.time()

    team_size = min(faction1_count, faction2_count, 16)
    max_team_size = max(faction1_count, faction2_count)

    if team_size < 2:
        # Not enough for any match: [0, 2)
        return None, None, None
    elif team_size < 5:
        if current_ts - latest_ts > TIME_THRESHOLD_FOR_DUEL:
            # Enough only for duel: [2, 5)
            return 2, 2, "duel"
        return None, None, None  # Wait for more players
    elif team_size < 8:
        if current_ts - latest_ts > TIME_THRESHOLD_FOR_MEDIUM_SIZED_MATCH:
            # Enough for medium-sized matched (e.g. Hold The Line): [5, 8)
            return min(max_team_size, 8), 5, "medium"
        return None, None, None
    else:
        # Large battles: [8, 16]
        return min(max_team_size, 16), 8, "large"


def try_create_pvp_match_casual(player_data_map: dict, latest_ts: float, matchmaking_config_for_mode: dict):
    return try_create_pvp_match_common(player_data_map, latest_ts, matchmaking_config_for_mode,
                                       determine_team_size_casual)
