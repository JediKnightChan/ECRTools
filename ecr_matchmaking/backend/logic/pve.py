import random
import time

from logic.common import try_create_pve_match_common

TIME_THRESHOLD_FOR_MATCH_ALONE = 360
TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP = 180


def determine_team_size_pve(faction1_count, latest_ts, current_ts=None):
    """ Determines appropriate team size based on player count and time elapsed from latest player queued"""

    if current_ts is None:
        current_ts = time.time()

    team_size = min(faction1_count, 4)

    if team_size < 2:
        # Player is alone in queue
        if current_ts - latest_ts > TIME_THRESHOLD_FOR_MATCH_ALONE:
            return team_size, 1, "raid4"
        return None, None
    elif team_size < 4:
        # Not full group: [2, 4)
        if current_ts - latest_ts > TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP:
            return team_size, 2, "raid4"
        return None, None, None
    else:
        return 4, 4, "raid4"


def determine_team_size_instant(faction1_count, latest_ts, current_ts=None):
    """Instantly assigns player to PvE match"""

    if current_ts is None:
        current_ts = time.time()
    team_size = min(faction1_count, 4)
    return team_size, 1, "raid4"


def try_create_pve_match(player_data_map, latest_ts, matchmaking_config_for_mode):
    return try_create_pve_match_common(player_data_map, latest_ts, matchmaking_config_for_mode, determine_team_size_pve)


def try_create_instant_pve_match(player_data_map, latest_ts, matchmaking_config_for_mode):
    return try_create_pve_match_common(player_data_map, latest_ts, matchmaking_config_for_mode, determine_team_size_instant)
