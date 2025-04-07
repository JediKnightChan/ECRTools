import traceback

import httpx
from logic.regions import get_region_group_ordered, get_region_group_distance_map


async def try_to_launch_match(logger, region_group_counts, servers_to_region_groups, resource_units, version_and_contour, game_map,
                              game_mission, game_mode, match_id, faction_setup):
    distance_map = get_region_group_distance_map("eu")
    ordered_server_groups = get_region_group_ordered(region_group_counts, list(set(servers_to_region_groups.values())),
                                                     distance_map)
    if not ordered_server_groups:
        logger.error(
            f"Trying to create match, but ordered server group empty: {ordered_server_groups} for {region_group_counts}")
        return False, None, None

    for ordered_region_group in ordered_server_groups:
        for server, region_group in servers_to_region_groups.items():
            if region_group == ordered_region_group:
                try:
                    async with httpx.AsyncClient() as client:
                        r = await client.post(f"http://{server}/launch", json={
                            "game_version": version_and_contour.split("-")[0],
                            "game_contour": version_and_contour.split("-")[1],
                            "game_map": game_map,
                            "game_mode": game_mode,
                            "game_mission": game_mission,
                            "resource_units": resource_units,
                            "match_unique_id": str(match_id),
                            "faction_setup": faction_setup
                        })
                        r.raise_for_status()
                        data = r.json()
                        return True, server, data
                except Exception as e:
                    logger.error(f"Error during server launch request: {e}")
                    logger.error(traceback.format_exc())

    return False, None, None