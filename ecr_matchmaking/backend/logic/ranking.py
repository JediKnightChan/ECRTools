import trueskill

from mpmath import mp
mp.dps = 250

# Initialize TrueSkill environment
env = trueskill.TrueSkill(backend='mpmath')


# Function to update ratings after a 2vs2 match
def update_2vs2_ratings(player1, player2, player3, player4, outcome):
    """
    Update the ratings of players after a 2vs2 match.

    :param player1: TrueSkill rating of player 1
    :param player2: TrueSkill rating of player 2
    :param player3: TrueSkill rating of player 3
    :param player4: TrueSkill rating of player 4
    :param outcome: 1 if team1 wins, 0 if team2 wins
    :return: Updated TrueSkill ratings for all players
    """
    # Players in each team
    team1 = [player1, player2]  # Player 1 and Player 2 are in Team 1
    team2 = [player3, player4]  # Player 3 and Player 4 are in Team 2

    # Determine match outcome
    if outcome == 1:
        # Team 1 wins
        result = [0, 1]
    elif outcome == 0:
        # Team 2 wins
        result = [1, 0]
    else:
        raise ValueError("Invalid outcome value. It must be 0 or 1.")

    # Rate the players based on the outcome
    updated_players = env.rate([team1, team2], result)

    # Return updated player ratings
    return updated_players


# Example player ratings (initial ratings)
player1 = trueskill.Rating(mu=60, sigma=1)
player2 = trueskill.Rating(mu=60, sigma=1)
player3 = trueskill.Rating(mu=60, sigma=1)
player4 = trueskill.Rating(mu=60, sigma=1)

# Outcome of the match: 1 means Team 1 won, 0 means Team 2 won
outcome = 0 # Example: Team 1 wins

print(env.quality([[player1, player2], [player3, player4]]))

# Update the ratings after the match
updated_ratings = update_2vs2_ratings(player1, player2, player3, player4, outcome)

# Print the updated ratings
print("Updated ratings after the match:")
print(f"Team 1's rating: {updated_ratings[0]}")
print(f"Team 2's rating: {updated_ratings[1]}")

