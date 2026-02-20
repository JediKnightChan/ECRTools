import random
from heapq import nlargest
from typing import Callable

from models.models import GAME_FACTIONS


def try_create_pvp_match_common(player_data_map: dict, oldest_player_queue_time: float, newest_player_queue_time: float,
                                matchmaking_config_for_mode: dict, determine_team_size: Callable,
                                ignore_faction_min_amount: bool = False):
    """ Attempts to create a PvP match by balancing factions and handling party sizes"""
    # Group players by faction while considering party sizes
    faction_counts = {}
    player_to_party = {}

    for player_id, player_info in player_data_map.items():
        faction = player_info["faction"]
        party_members = player_info["party_members"]
        party_size = len(party_members)

        player_to_party[player_id] = party_members
        if faction not in faction_counts:
            faction_counts[faction] = []
        faction_counts[faction].append((player_id, party_size))

    if len(faction_counts) < 2:
        if ignore_faction_min_amount:
            new_faction_counts = faction_counts.copy()
            for faction in GAME_FACTIONS:
                if faction not in faction_counts:
                    new_faction_counts[faction] = [(None, 0)]
                    if len(new_faction_counts) == 2:
                        break
            faction_counts = new_faction_counts.copy()
        else:
            return  # Not enough diversity

    # Get the two factions with the most total players (counting parties)
    def total_faction_size(faction_data):
        return sum(party_size for _, party_size in faction_data)

    (faction1, faction1_players), (faction2, faction2_players) = nlargest(2, faction_counts.items(),
                                                                          key=lambda x: total_faction_size(x[1]))

    # Sort within factions: prioritize larger parties first, maintaining queue order
    faction1_players.sort(key=lambda x: (-x[1]))
    faction2_players.sort(key=lambda x: (-x[1]))

    # Get total player counts per faction
    faction1_count = total_faction_size(faction1_players)
    faction2_count = total_faction_size(faction2_players)

    # Determine appropriate team size, minimal team size and match type
    team_size, min_team_size, max_team_size, match_type = determine_team_size(faction1_count, faction2_count,
                                                                              oldest_player_queue_time,
                                                                              newest_player_queue_time)
    if not team_size:
        # Not enough players for a match
        return

    # Select players while ensuring team size constraints
    selected_faction1 = []
    selected_faction2 = []
    faction1_used, faction2_used = 0, 0  # Track total selected players per faction

    for player_id, party_size in faction1_players:
        if faction1_used + party_size <= team_size:
            selected_faction1.extend(player_to_party.get(player_id, [player_id]))
            faction1_used += party_size

    for player_id, party_size in faction2_players:
        if faction2_used + party_size <= team_size:
            selected_faction2.extend(player_to_party.get(player_id, [player_id]))
            faction2_used += party_size

    players_in_match = selected_faction1 + selected_faction2

    if faction1_used < min_team_size or faction2_used < min_team_size:
        # Not enough players for the match
        return

    # Determine match name by majority vote
    desired_match_group_votes = {}
    for player_id in players_in_match:
        if player_id not in player_data_map:
            # Skip party members who are not leader
            continue
        desired_match_group = player_data_map[player_id]["desired_match_group"]
        desired_match_group_votes[desired_match_group] = desired_match_group_votes.get(desired_match_group, 0) + 1

    # Pick the most popular match type, fallback if not found
    majority_match_group = max(desired_match_group_votes, key=desired_match_group_votes.get, default=None)
    if majority_match_group not in matchmaking_config_for_mode:
        majority_match_group = random.choice(
            list(matchmaking_config_for_mode.keys())) if matchmaking_config_for_mode else None
    if not majority_match_group:
        return

    # Select a mission based on weights
    missions_to_weights = matchmaking_config_for_mode.get(majority_match_group, {}).get(match_type, {})
    if not missions_to_weights:
        return
    mission = random.choices(list(missions_to_weights.keys()), weights=list(missions_to_weights.values()), k=1)[0]

    faction_setup = f"{faction1}:{faction2}" if random.choice([True, False]) else f"{faction2}:{faction1}"
    final_faction_counts = {faction1: faction1_used, faction2: faction2_used}

    return players_in_match, {"mission": mission, "match_type": match_type, "faction_setup": faction_setup,
                              "max_team_size": max_team_size, "faction_counts": final_faction_counts}


def try_create_pve_match_common(player_data_map: dict, latest_ts: float, matchmaking_config_for_mode: dict,
                                determine_team_size: Callable):
    """ Attempts to create a PvP match by balancing factions and handling party sizes"""
    # Group players by faction while considering party sizes
    faction_counts = {}
    player_to_party = {}

    for player_id, player_info in player_data_map.items():
        faction = player_info["faction"]
        party_members = player_info["party_members"]
        party_size = len(party_members)

        player_to_party[player_id] = party_members
        if faction not in faction_counts:
            faction_counts[faction] = []
        faction_counts[faction].append((player_id, party_size))

    if len(faction_counts) < 1:
        return  # Not enough diversity

    # Get the two factions with the most total players (counting parties)
    def total_faction_size(faction_data):
        return sum(party_size for _, party_size in faction_data)

    ((faction1, faction1_players),) = nlargest(1, faction_counts.items(),
                                               key=lambda x: total_faction_size(x[1]))

    # Sort within factions: prioritize larger parties first, maintaining queue order
    faction1_players.sort(key=lambda x: (-x[1]))

    # Get total player counts per faction
    faction1_count = total_faction_size(faction1_players)

    # Determine appropriate team size, minimal team size and match type
    team_size, min_team_size, max_team_size, match_type = determine_team_size(faction1_count, latest_ts)
    if not team_size:
        # Not enough players for a match
        return

    # Select players while ensuring team size constraints
    selected_faction1 = []
    faction1_used = 0  # Track total selected players per faction

    for player_id, party_size in faction1_players:
        if faction1_used + party_size <= team_size:
            selected_faction1.extend(player_to_party.get(player_id, [player_id]))
            faction1_used += party_size

    players_in_match = selected_faction1

    if faction1_used < min_team_size:
        # Not enough players for the match
        return

    # Determine match name by majority vote
    desired_match_group_votes = {}
    for player_id in players_in_match:
        if player_id not in player_data_map:
            # Skip party members who are not leader
            continue
        desired_match_group = player_data_map[player_id]["desired_match_group"]
        desired_match_group_votes[desired_match_group] = desired_match_group_votes.get(desired_match_group, 0) + 1

    # Pick the most popular match type, fallback if not found
    majority_match_group = max(desired_match_group_votes, key=desired_match_group_votes.get, default=None)
    if majority_match_group not in matchmaking_config_for_mode:
        majority_match_group = random.choice(
            list(matchmaking_config_for_mode.keys())) if matchmaking_config_for_mode else None
    if not majority_match_group:
        return

    # Select a mission based on weights
    missions_to_weights = matchmaking_config_for_mode.get(majority_match_group, {}).get(match_type, {})
    if not missions_to_weights:
        return
    mission = random.choices(list(missions_to_weights.keys()), weights=list(missions_to_weights.values()), k=1)[0]

    return players_in_match, {"mission": mission, "match_type": match_type, "faction_setup": f"{faction1}",
                              "max_team_size": max_team_size}
