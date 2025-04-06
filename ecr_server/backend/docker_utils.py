import json
import os
import traceback

import aiodocker
import logging

from system_utils import parse_time_command_output

logger = logging.getLogger(__name__)

GAME_SERVER_IMAGE_NAME = os.getenv("GAME_SERVER_IMAGE_NAME")
if not GAME_SERVER_IMAGE_NAME:
    logger.error("GAME_SERVER_IMAGE_NAME not set")


async def launch_game_docker(region, game_contour, game_version, game_map, game_mode, game_mission, instance_number,
                             resource_units, match_id, faction_setup):
    port_base = 7777
    port = port_base + instance_number
    log_file = f"{match_id}.log"

    async with aiodocker.Docker() as docker_client:
        container = await docker_client.containers.run(
            config={
                "Image": f"{GAME_SERVER_IMAGE_NAME}:{game_version}-{game_contour}",
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
                    "com.eternal-crusade.resourceunits": f"{resource_units}",
                    "com.eternal-crusade.instancenum": f"{instance_number}",
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

        # Getting /usr/bin/time -v logs (cpu, memory stats)
        time_logs = await container.log(stderr=True, follow=False, tail=100)
        stats = parse_time_command_output(time_logs)
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


async def list_game_docker_containers():
    instances = []
    resource_units_total = 0
    async with aiodocker.Docker() as docker_client:
        filter_query = {
            "status": ["running", "created", "restarting"]
        }
        containers = await docker_client.containers.list(all=True, filters=filter_query)
        for container in containers:
            instance_num = container["Labels"].get("com.eternal-crusade.instancenum")
            resource_units = container["Labels"].get("com.eternal-crusade.resourceunits")
            if instance_num is not None:
                instances.append(int(instance_num))
            if resource_units is not None:
                resource_units_total += int(resource_units)
    return containers, instances, resource_units_total


async def pull_image_and_delete_older(new_image, images_to_delete_tags):
    async with aiodocker.Docker() as docker_client:
        if images_to_delete_tags:
            logger.warning(f"IMAGE DELETE: received request with tags {images_to_delete_tags}")
            images = await docker_client.images.list()
            for image in images:
                matched_tags = [t for t in image['RepoTags'] if t in images_to_delete_tags]
                if matched_tags:
                    logger.warning(f"IMAGE DELETE: Image {image['Id']} matched with tags {matched_tags} "
                                   f"and will be deleted")
                    await image.delete(force=True)

        if new_image:
            logger.warning(f"IMAGE PULL: trying to pull image {new_image}")
            await docker_client.pull(new_image)
