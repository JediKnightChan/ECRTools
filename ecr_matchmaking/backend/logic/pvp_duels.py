from logic.common import try_create_pvp_match_common


def determine_team_size_duel(faction1_count, faction2_count):
    """ Determines appropriate team size based on player count and time elapsed from latest player queued"""

    team_size = min(faction1_count, faction2_count, 16)

    if team_size < 2:
        # Not enough: [0, 2)
        return None, None, None
    else:
        return 2, 2, "duel"


def try_create_pvp_match_duel(player_data_map: dict, latest_ts: float, matchmaking_config_for_mode: dict):
    return try_create_pvp_match_common(player_data_map, latest_ts, matchmaking_config_for_mode,
                                       determine_team_size_duel)
