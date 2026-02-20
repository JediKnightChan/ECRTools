import unittest
import time
from logic.pve import determine_team_size_pve, determine_team_size_instant_pve, \
    try_create_pve_match, TIME_THRESHOLD_FOR_MATCH_ALONE, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP, \
    determine_team_size_instant_pve


class TestMatchmakingPve(unittest.TestCase):
    def test_determine_team_size_pve(self):
        """Test various team size conditions."""
        current_ts = time.time()

        # Not enough players
        self.assertEqual((None, None, None, None),
                         determine_team_size_pve(1, TIME_THRESHOLD_FOR_MATCH_ALONE - 1, ))

        # Enough for match with not full group, past threshold
        self.assertEqual((2, 2, 4, "raid4"),
                         determine_team_size_pve(2, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP + 1))

        # Enough for match with not full group, but waiting
        self.assertEqual((None, None, None, None),
                         determine_team_size_pve(3, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP - 1))

        # Enough for full group match
        self.assertEqual((4, 4, 4, "raid4"), determine_team_size_pve(4, 5))

        # Cap at max team size 4
        self.assertEqual((4, 4, 4, "raid4"), determine_team_size_pve(12, 5))

    def test_determine_team_size_instant_pve(self):
        """Test various team size conditions."""
        current_ts = time.time()

        # 1 player
        self.assertEqual((1, 1, 4, "raid4"),
                         determine_team_size_instant_pve(1, TIME_THRESHOLD_FOR_MATCH_ALONE - 1))

        # 3 player
        self.assertEqual((3, 1, 4, "raid4"),
                         determine_team_size_instant_pve(3, TIME_THRESHOLD_FOR_MATCH_ALONE - 1))

        # 4 player
        self.assertEqual((4, 1, 4, "raid4"),
                         determine_team_size_instant_pve(4, TIME_THRESHOLD_FOR_MATCH_ALONE - 1))

        # 100 player
        self.assertEqual((4, 1, 4, "raid4"),
                         determine_team_size_instant_pve(100, TIME_THRESHOLD_FOR_MATCH_ALONE - 1))

    def test_try_create_pve_match(self):
        """Test matchmaking with different party and faction setups."""

        matchmaking_config = {
            "group1": {
                "raid4": {"raid4-1": 1},
            }
        }

        # Test Case: 4 people, 1 party of 2
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
            "p3": {"faction": "A", "party_members": ["p3", "p4"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, 5, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p3", "p4", "p1", "p2"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: Prioritizing Larger Party
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
            "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
            "p6": {"faction": "A", "party_members": ["p6"], "desired_match_group": "group1"},
            "p7": {"faction": "A", "party_members": ["p7", "p8"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, 5, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # Larger party prioritized, if not exceeding
        self.assertEqual({"p1", "p2", "p3", "p4"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: Not full group, not enough time
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP - 5,
                                     matchmaking_config)
        self.assertIsNone(match)

        # Test Case: Not full group, enough time
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP + 5,
                                     matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue
        self.assertEqual({"p1", "p2"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: One full group and other players
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4", "p5"], "desired_match_group": "group1"},
            "p6": {"faction": "A", "party_members": ["p6"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, 5, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue, except last party who exceeded
        self.assertEqual({f"p{i}" for i in range(2, 6)}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

    def test_try_create_instant_pve_match(self):
        """Test matchmaking with different party and faction setups."""

        matchmaking_config = {
            "group1": {
                "raid4": {"raid4-1": 1},
            }
        }

        # Test Case: 4 people, 1 party of 2
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
            "p3": {"faction": "A", "party_members": ["p3", "p4"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, 5, matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p3", "p4", "p1", "p2"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: Prioritizing Larger Party
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
            "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
            "p6": {"faction": "A", "party_members": ["p6"], "desired_match_group": "group1"},
            "p7": {"faction": "A", "party_members": ["p7", "p8"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, 5, matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # Larger party prioritized, if not exceeding
        self.assertEqual({"p1", "p2", "p3", "p4"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: Not full group, but it doesn't matter
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
        }
        match = try_create_pve_match(players, TIME_THRESHOLD_FOR_MATCH_WITH_NOT_FULL_GROUP - 5,
                                             matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue
        self.assertEqual({"p1", "p2"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])

        # Test Case: 1 player
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"}
        }
        match = try_create_pve_match(players, 5, matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue, except last party who exceeded
        self.assertEqual({"p1"}, set(players_in_match))
        self.assertEqual("raid4-1", mission["mission"])


if __name__ == "__main__":
    unittest.main()
