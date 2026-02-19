import random
import time

from logic.common import try_create_pve_match_common

TIME_THRESHOLD_FOR_MATCH_ALONE = 360
TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP = 180


def determine_team_size_pve(faction1_count, oldest_player_queue_time):
    """ Determines appropriate team size based on player count and time elapsed from latest player queued"""

    team_size = min(faction1_count, 4)

    if team_size < 2:
        # Player is alone in queue
        if oldest_player_queue_time > TIME_THRESHOLD_FOR_MATCH_ALONE:
            return team_size, 1, 4, "raid4"
        return None, None, None, None
    elif team_size < 4:
        # Not full group: [2, 4)
        if oldest_player_queue_time > TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP:
            return team_size, 2, 4, "raid4"
        return None, None, None, None
    else:
        return 4, 4, 4, "raid4"


def determine_team_size_instant_pve(faction1_count, oldest_player_queue_time):
    """Instantly assigns player to PvE match"""

    team_size = min(faction1_count, 4)
    return team_size, 1, 4, "raid4"


def try_create_pve_match(player_data_map, oldest_player_queue_time, matchmaking_config_for_mode, instant_creation=False):
    return try_create_pve_match_common(player_data_map, oldest_player_queue_time, matchmaking_config_for_mode, determine_team_size_instant_pve if instant_creation else determine_team_size_pve)
