from logic.common import try_create_pvp_match_common


def determine_team_size_duel(faction1_count, faction2_count, oldest_player_queue_time, newest_player_queue_time):
    """ Determines appropriate team size based on player count and time elapsed from latest player queued"""

    team_size = min(faction1_count, faction2_count, 16)
    max_team_size = max(faction1_count, faction2_count)

    if team_size < 5:
        # Not enough: [0, 5)
        return None, None, None, None
    else:
        return min(max_team_size, 5), 2, 5, "duel"


def try_create_pvp_match_duel(player_data_map: dict, oldest_player_queue_time: float, newest_player_queue_time: float,
                              matchmaking_config_for_mode: dict):
    return try_create_pvp_match_common(player_data_map, oldest_player_queue_time, newest_player_queue_time,
                                       matchmaking_config_for_mode, determine_team_size_duel)
