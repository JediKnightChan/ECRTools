import unittest
import time
from logic.pvp_casual import determine_team_size_casual, try_create_pvp_match_casual


class TestMatchmaking(unittest.TestCase):
    def test_determine_team_size(self):
        """Test various team size conditions."""
        current_ts = time.time()

        # Not enough players
        self.assertEqual((None, None, None, None), determine_team_size_casual(1, 0, current_ts - 100, current_ts))

        # Enough for duel, 1vs1
        self.assertEqual((1, 1, 5, "duel"), determine_team_size_casual(1, 1, current_ts - 100, current_ts))

        # Enough for duel, past duel threshold
        self.assertEqual((2, 1, 5, "duel"), determine_team_size_casual(2, 2, current_ts - 61, current_ts))

        # Enough for duel, but waiting
        self.assertEqual((None, None, None, None), determine_team_size_casual(2, 2, current_ts - 30, current_ts))

        # Enough for medium match, past threshold
        self.assertEqual((6, 5, 8, "medium"), determine_team_size_casual(6, 6, current_ts - 46, current_ts))

        # Large battle (full teams)
        self.assertEqual((12, 8, 16, "large"), determine_team_size_casual(10, 12, current_ts - 100, current_ts))

        # Cap at max team size 16
        self.assertEqual((16, 8, 16, "large"), determine_team_size_casual(20, 18, current_ts - 100, current_ts))

    def test_try_create_pvp_match(self):
        """Test matchmaking with different party and faction setups."""

        current_ts = time.time()
        matchmaking_config = {
            "group1": {
                "duel": {"duel1": 1},
                "medium": {"medium1": 1},
                "large": {"large1": 1},
            }
        }

        # Test Case: Simple 2v2 Duel
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
            "p3": {"faction": "B", "party_members": ["p3", "p4"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, current_ts - 61, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p3", "p4", "p1", "p2"}, set(players_in_match))
        self.assertEqual("duel1", mission["mission"])

        # # Test Case: Prioritizing Larger Party
        # players = {
        #     "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
        #     "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
        #     "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
        #     "p6": {"faction": "B", "party_members": ["p6"], "desired_match_group": "group1"},
        #     "p7": {"faction": "B", "party_members": ["p7", "p8"], "desired_match_group": "group1"},
        # }
        # match = try_create_pvp_match_casual(players, current_ts - 61, matchmaking_config)
        # self.assertIsNotNone(match)
        # players_in_match, mission = match
        # # Larger party prioritized, if not exceeding
        # self.assertEqual({"p1", "p5", "p7", "p8"}, set(players_in_match))
        # self.assertEqual("duel1", mission["mission"])

        # Test Case: Not Enough Players
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, current_ts - 100, matchmaking_config)
        self.assertIsNone(match)

        # Test Case: Medium sized match
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
            "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
            "p6": {"faction": "B", "party_members": ["p6"], "desired_match_group": "group1"},
            "p7": {"faction": "B", "party_members": ["p7", "p8", "p9", "p10"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, current_ts - 50, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue
        self.assertEqual({f"p{i}" for i in range(1, 11)}, set(players_in_match))
        self.assertEqual("medium1", mission["mission"])

        # Test Case: Large scale match
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
            "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
            "p6": {"faction": "A", "party_members": ["p6"], "desired_match_group": "group1"},
            "p7": {"faction": "A", "party_members": ["p7", "p8", "p9", "p10"], "desired_match_group": "group1"},
            "p11": {"faction": "B", "party_members": ["p11", "p12", "p13", "p14"], "desired_match_group": "group1"},
            "p15": {"faction": "B", "party_members": ["p15", "p16", "p17", "p18"], "desired_match_group": "group1"},
            "p19": {"faction": "B", "party_members": ["p19", "p20", "p21", "p22"], "desired_match_group": "group1"},
            "p23": {"faction": "B", "party_members": ["p23", "p24", "p25"], "desired_match_group": "group1"},
            "p27": {"faction": "B", "party_members": ["p27", "p28", "p29"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, current_ts - 50, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue, except last party who exceeded
        self.assertEqual({f"p{i}" for i in range(1, 26)}, set(players_in_match))
        self.assertEqual("large1", mission["mission"])

        # Test case: Instant PvP match
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, current_ts - 2, matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p1", None}, set(players_in_match))
        self.assertEqual("medium1", mission["mission"])


if __name__ == "__main__":
    unittest.main()
