import random
import time

from heapq import nlargest

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


def try_create_pve_match(player_data_map: dict, latest_ts: float, matchmaking_config_for_mode: dict):
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

    (faction1, faction1_players) = nlargest(1, faction_counts.items(),
                                            key=lambda x: total_faction_size(x[1]))

    # Sort within factions: prioritize larger parties first, maintaining queue order
    faction1_players.sort(key=lambda x: (-x[1]))

    # Get total player counts per faction
    faction1_count = total_faction_size(faction1_players)

    # Determine appropriate team size, minimal team size and match type
    team_size, min_team_size, match_type = determine_team_size_pve(faction1_count, latest_ts)
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

    return players_in_match, mission
