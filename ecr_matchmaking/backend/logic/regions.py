import os
import json

with open(os.path.join(os.path.dirname(__file__), "..", "region_groups.json")) as f:
    region_mapping = json.load(f)


def get_region_group_distance_map(region_group):
    region_group = region_group.upper()
    if region_group in ["EU", "RU", "US"]:
        return {
            "EU": {
                "EU": 0,
                "RU": 1,
                "US": 1.1
            },
            "RU": {
                "RU": 0,
                "US": 1.2
            },
            "US": {
                "US": 0
            }
        }
    elif region_group in ["EA"]:
        return {
            "EA": {
                "EA": 0,
            }
        }
    else:
        raise ValueError("Uknown region group {}".format(region_group))


def get_region_group(region):
    return region_mapping.get(region.upper(), "EU")


def get_region_group_ordered(region_group_to_counts, available_region_groups, distance_map):
    available_to_distance_sums = {}
    for a in available_region_groups:
        a = a.upper()
        for r, c in region_group_to_counts.items():
            r = r.upper()
            r1, r2 = sorted([a, r])
            distance = distance_map.get(r1, {}).get(r2, None)
            if distance:
                available_to_distance_sums[a] = available_to_distance_sums.get(a, 0) + distance * c

    if os.getenv("DEBUG_REGION_DISTANCES"):
        print(available_to_distance_sums)
    return sorted(available_to_distance_sums, key=available_to_distance_sums.get, reverse=False)


if __name__ == '__main__':
    print(get_region_group("kz"))

    distance_map = get_region_group_distance_map("ru")
    print(get_region_group_ordered({"ru": 2, "eu": 2, "us": 1}, ["ru", "eu", "ea"], distance_map))
