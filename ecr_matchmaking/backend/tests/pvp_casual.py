import unittest
import time
from logic.pvp_casual import determine_team_size_casual, try_create_pvp_match_casual


class TestMatchmaking(unittest.TestCase):
    def test_determine_team_size(self):
        """Test various team size conditions."""
        current_ts = time.time()

        # Not enough players
        self.assertEqual((None, None, None, None), determine_team_size_casual(1, 0, 100, 100))

        # Enough for low, 1vs1
        self.assertEqual((1, 1, 16, "low"), determine_team_size_casual(1, 1, 100, 100))

        # Enough for low, past low threshold
        self.assertEqual((2, 1, 16, "low"), determine_team_size_casual(2, 2, 61, 61))

        # Enough for low, but waiting
        self.assertEqual((None, None, None, None), determine_team_size_casual(2, 2, 30, 30))

        # Enough for medium match, past threshold
        self.assertEqual((6, 5, 16, "medium"), determine_team_size_casual(6, 6, 46, 46))

        # Large battle (full teams)
        self.assertEqual((12, 8, 16, "large"), determine_team_size_casual(10, 12, 100, 100))

        # Cap at max team size 16
        self.assertEqual((16, 8, 16, "large"), determine_team_size_casual(20, 18, 100, 100))

    def test_try_create_pvp_match(self):
        """Test matchmaking with different party and faction setups."""

        matchmaking_config = {
            "group1": {
                "low": {"low1": 1},
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
        match = try_create_pvp_match_casual(players, 61, 61, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p3", "p4", "p1", "p2"}, set(players_in_match))
        self.assertEqual("low1", mission["mission"])

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
        # self.assertEqual("low1", mission["mission"])

        # Test Case: Not Enough Players
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, 100, 100, matchmaking_config)
        self.assertIsNone(match)

        # Test Case: Medium sized match
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
            "p2": {"faction": "A", "party_members": ["p2", "p3", "p4"], "desired_match_group": "group1"},
            "p5": {"faction": "A", "party_members": ["p5"], "desired_match_group": "group1"},
            "p6": {"faction": "B", "party_members": ["p6"], "desired_match_group": "group1"},
            "p7": {"faction": "B", "party_members": ["p7", "p8", "p9", "p10"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, 50, 50, matchmaking_config)
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
        match = try_create_pvp_match_casual(players, 50, 50, matchmaking_config)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        # All players got into queue, except last party who exceeded
        self.assertEqual({f"p{i}" for i in range(1, 26)}, set(players_in_match))
        self.assertEqual("large1", mission["mission"])

        # Test case: Instant PvP match
        players = {
            "p1": {"faction": "A", "party_members": ["p1"], "desired_match_group": "group1"},
        }
        match = try_create_pvp_match_casual(players, 2, 2, matchmaking_config, instant_creation=True)
        self.assertIsNotNone(match)
        players_in_match, mission = match
        self.assertEqual({"p1", None}, set(players_in_match))
        self.assertEqual("medium1", mission["mission"])

        c = {'pvp': {'PoolAlpha': {'large': {'PromethiumMineSupremacy': 1.0, 'CanyonWasteyardSupremacy': 1.0, 'CycladonComplexSupremacy': 0.25, 'PromethiumMineHoldTheLine': 0.25, 'CanyonWasteyardHoldTheLine': 0.25}, 'medium': {'CycladonComplexSupremacy': 1.0, 'PromethiumMineHoldTheLine': 1.0, 'CanyonWasteyardHoldTheLine': 1.0}, 'low': {'CycladonComplexDuel': 1.0, 'PromethiumMineDuel': 1.0, 'CanyonWasteyardDuel': 1.0}}, 'PoolBeta': {'large': {'MedusaSupremacy': 1.0, 'OlipsisSupremacy': 1.0, 'ToriasSupremacy': 1.0, 'BlackBoltSupremacy': 1.0, 'MedusaHoldTheLine': 0.25, 'OlipsisHoldTheLine': 0.25, 'ToriasHoldTheLine': 0.25, 'BlackBoltHoldTheLine': 0.25}, 'medium': {'MedusaHoldTheLine': 1.0, 'OlipsisHoldTheLine': 1.0, 'ToriasHoldTheLine': 1.0, 'BlackBoltHoldTheLine': 1.0}, 'low': {'MedusaDuel': 1.0, 'OlipsisDuel': 1.0, 'ToriasDuel': 1.0, 'BlackBoltDuel': 1.0}}, 'PoolGamma': {'large': {'CarmineAscentHoldTheLine': 1.0, 'MaggonStationHoldTheLine': 1.0, 'ZedekHoldTheLine': 1.0, 'RailgateRavineHoldTheLine': 1.0}}}, 'pve': {'Vein': {'raid4': {'ForgeOfTheMoltenVein': 1.0}}, 'Inferno': {'raid4': {'InfernoFoundry': 1.0}}, 'Abyss': {'raid4': {'TyrantOfTheAbyss': 1.0}}}}
        players = {'34': {'desired_match_group': 'PoolAlpha', 'faction': 'LoyalSpaceMarines', 'party_members': ['34', '296b5f6beebf4a76a230f7c42ffe9e84|00025613597e40cf8c03f0a0c3b639b1'], 'region_group': 'RU'}, '36': {'desired_match_group': 'PoolAlpha', 'faction': 'LoyalSpaceMarines', 'party_members': ['36', 'f1ec6de28cf94037b87bb482c540dfa0|0002fb83e96243cf980465a07cff8a00'], 'region_group': 'EU'}, '38': {'desired_match_group': 'PoolAlpha', 'faction': 'ChaosSpaceMarines', 'party_members': ['38', 'bcfbe08295684f1584d549ff3980a56a|00027e499d4947199ab68569947a79f2'], 'region_group': 'RU'}, '33': {'desired_match_group': 'PoolAlpha', 'faction': 'ChaosSpaceMarines', 'party_members': ['33', 'c5a7eea3e4c14aecaf4b73a3891bf7d3|0002822ed1b24b3aa9e3aad230d7d601'], 'region_group': 'US'}}
        match = try_create_pvp_match_casual(players, 100, 100, c['pvp'])
        print(match)

if __name__ == "__main__":
    unittest.main()
