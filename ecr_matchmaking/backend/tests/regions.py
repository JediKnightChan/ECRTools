import os
import unittest
import time
from logic.regions import get_region_group_ordered, get_region_group_distance_map, get_region_group

os.environ["DEBUG_REGION_DISTANCES"] = "1"


class TestRegions(unittest.TestCase):
    def test_get_region_group(self):
        self.assertEqual("EU", get_region_group("eu"))
        self.assertEqual("US", get_region_group("us"))
        self.assertEqual("RU", get_region_group("ru"))
        self.assertEqual("EA", get_region_group("cn"))
        self.assertEqual("EA", get_region_group("hk"))
        self.assertEqual("EA", get_region_group("tw"))

        # Uppercase
        self.assertEqual("RU", get_region_group("RU"))

    def test_get_region_group_ordered(self):
        # Same on eu and ru, then us players appear
        region_group_counts = {"ru": 12, "eu": 12, "us": 11}
        available_groups = ["ru", "eu"]
        distance_map = get_region_group_distance_map(list(region_group_counts.keys())[0])
        self.assertListEqual(["EU", "RU"], get_region_group_ordered(region_group_counts, available_groups, distance_map))

        # More on ru than on eu
        region_group_counts = {"ru": 13, "eu": 12}
        available_groups = ["ru", "eu"]
        distance_map = get_region_group_distance_map(list(region_group_counts.keys())[0])
        self.assertListEqual(["RU", "EU"],
                             get_region_group_ordered(region_group_counts, available_groups, distance_map))

        # More on EU
        region_group_counts = {"ru": 13, "eu": 15, "us": 12}
        available_groups = ["ru", "eu"]
        distance_map = get_region_group_distance_map(list(region_group_counts.keys())[0])
        self.assertListEqual(["EU", "RU"],
                             get_region_group_ordered(region_group_counts, available_groups, distance_map))

        # US server available
        region_group_counts = {"ru": 13, "eu": 15, "us": 15}
        available_groups = ["ru", "eu", "us"]
        distance_map = get_region_group_distance_map(list(region_group_counts.keys())[0])
        self.assertListEqual(["EU", "US", "RU"],
                             get_region_group_ordered(region_group_counts, available_groups, distance_map))

        # No players of this group
        region_group_counts = {"eu": 5}
        available_groups = ["ru"]
        distance_map = get_region_group_distance_map("eu")
        self.assertListEqual(["RU"],
                             get_region_group_ordered(region_group_counts, available_groups, distance_map))

    def test_prod_cases(self):
        # Prod case
        region_group_counts = {'RU': 1}
        servers_to_region_groups = {'51.250.98.83': 'RU'}
        distance_map = get_region_group_distance_map("eu")
        ordered_server_groups = get_region_group_ordered(region_group_counts,
                                                         list(set(servers_to_region_groups.values())),
                                                         distance_map)
        self.assertListEqual(["RU"], ordered_server_groups)


if __name__ == "__main__":
    unittest.main()
