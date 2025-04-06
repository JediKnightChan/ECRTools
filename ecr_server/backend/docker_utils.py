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
            config={
                "Image": "ecr_server-gameserver",
                "ExposedPorts": {
                    f"{port}/udp": {},
                    f"{port}/tcp": {},
                },
                "Env": [
                    f"MAP={game_map}",
                    f"MODE={game_mode}",
                    f"MISSION={game_mission}",
                    f"REGION={region}",
                    f"EPIC_APP={os.getenv('EPIC_APP')}",
                    f"GAME_ANALYTICS_KEY={os.getenv('GAME_ANALYTICS_KEY')}",
                    f"LOG={log_file}",
                    f"MATCH_ID={match_id}",
                    f"FACTIONS={faction_setup}",
                    f"PORT={port}",
                ],
                "Labels": {
                    "com.docker.compose.project": "ecr_server",
                    "com.docker.compose.oneoff": "True"
                },
                "HostConfig": {
                    "Binds": [
                        "game_data:/ecr-server/LinuxServer/ECR/Saved/Logs/"
                    ],
                    "PortBindings": {
                        f"{port}/udp": [{"HostPort": f"{port}"}],
                        f"{port}/tcp": [{"HostPort": f"{port}"}],
                    },
                }
            },
            name=f"ecr-gameserver-{match_id}"
        )
        await monitor_container(container, match_id, log_file)


async def monitor_container(container, match_id, log_file):
    try:
        await container.start()
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
        if os.getenv("DO_DELETE_CONTAINERS", None) is not None:
            await container.delete(force=True)
