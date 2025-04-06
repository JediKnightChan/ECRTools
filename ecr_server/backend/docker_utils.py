import os
import traceback

import aiodocker
import logging

logger = logging.getLogger(__name__)


async def launch_game_docker(game_map, game_mode, game_mission, region, instance_number, match_id,
                             faction_setup):
    port_base = 7777
    port = port_base + instance_number
    log_file = f"{match_id}.log"

    async with aiodocker.Docker() as docker_client:
        container = await docker_client.containers.run(
            "ecr_server-gameserver",
            environment={
                "MAP": game_map,
                "MODE": game_mode,
                "MISSION": game_mission,
                "REGION": region,
                "EPIC_APP": os.getenv("EPIC_APP"),
                "ANALYTICS_KEY": os.getenv("GAME_ANALYTICS_KEY"),
                "LOG": log_file,
                "MATCH_ID": match_id,
                "FACTIONS": faction_setup,
                "PORT": port
            },
            ports={
                f"{port}/udp": f"{port}/udp",  # expose random host port
                f"{port}/tcp": f"{port}/tcp"
            },
            volumes={
                "game_logs/": {
                    "bind": "/ecr-server/LinuxServer/ECR/Saved/Logs/",
                    "mode": "rw"
                }
            },
            detach=True
        )
        await monitor_container(container, match_id, log_file)


async def monitor_container(container, match_id, log_file):
    try:
        container.start()
        response = await container.wait()
        response_status = response["StatusCode"]
        stats = await container.stats(stream=False)
        if response_status == 0:
            logger.debug(f"Container with match id {match_id} finished gracefully with stats {stats}")
        else:
            logger.error(f"Container with match id {match_id} failed with code {response_status}, stats {stats}")
    except Exception as e:
        logger.error(f"Error during monitoring container with match id {match_id}: {e}")
        logger.error(traceback.format_exc())
    finally:
        container.delete(force=True)
