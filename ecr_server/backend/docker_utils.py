import json
import os
import traceback

import aiodocker
import logging

import httpx

from system_utils import parse_time_command_output, check_free_server_resource_units
from s3_connection import S3Connector

logger = logging.getLogger(__name__)

GAME_SERVER_IMAGE_NAME = os.getenv("GAME_SERVER_IMAGE_NAME")
if not GAME_SERVER_IMAGE_NAME:
    logger.error("GAME_SERVER_IMAGE_NAME not set")

MAX_GAME_SERVER_INSTANCES = int(os.getenv("MAX_GAME_SERVER_INSTANCES", 10))
DEFAULT_FREE_INSTANCES = list(range(0, MAX_GAME_SERVER_INSTANCES))


async def launch_game_docker(region, game_contour, game_version, game_map, game_mode, game_mission, instance_number,
                             resource_units, match_id, faction_setup, max_team_size):
    port_base = 7777
    port = port_base + instance_number
    log_file = f"{match_id}.log"
    s3_log_key = f"ecr-game/{game_contour}/{game_version}/server_logs/{log_file}"

    async with aiodocker.Docker() as docker_client:
        container = await docker_client.containers.run(
            config={
                "Image": f"{GAME_SERVER_IMAGE_NAME}:{game_version}-{game_contour}",
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
                    f"MAX_TEAM_SIZE={max_team_size}",
                    f"PORT={port}",
                    f"LAUNCH_WITH_TIME={os.getenv('LAUNCH_WITH_TIME')}"
                ],
                "Labels": {
                    "com.eternal-crusade.resourceunits": f"{resource_units}",
                    "com.eternal-crusade.instancenum": f"{instance_number}",
                },
                "HostConfig": {
                    "NetworkMode": "host",
                    "Binds": [
                        "ecr_server_game_data:/ecr-server/LinuxServer/ECR/Saved/Logs/"
                    ],
                }
            },
            name=f"ecr-gameserver-{match_id}"
        )
        stats = await monitor_container(container, match_id)

        # Letting matchmaking know about free resources and game server resource stats
        free_instances, free_resource_units, taken_resource_units, total_resource_units = await get_free_instances_and_units()
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "region": region,
                    "resource_units": resource_units,
                    "free_resource_units": free_resource_units,
                    "free_instances_amount": len(free_instances)
                }
                r = await client.post("https://matchmaking.eternal-crusade.com/register_or_update_game_server", json=data,
                                      headers={"Authorization": f"Api-Key {os.getenv('MATCHMAKING_API_KEY')}"})
                r.raise_for_status()
        except Exception as e:
            logger.error(f"Error during matchmaking notification about game server exit: {e}")
            logger.error(traceback.format_exc())

        # Letting matchmaking know about resource usage
        try:
            async with httpx.AsyncClient() as client:
                data = {
                    "region": region,
                    "match_id": match_id,
                    "stats": stats
                }
                r = await client.post("https://matchmaking.eternal-crusade.com/register_game_server_stats", json=data,
                                      headers={"Authorization": f"Api-Key {os.getenv('MATCHMAKING_API_KEY')}"})
                r.raise_for_status()
        except Exception as e:
            logger.error(f"Error during matchmaking request with stats metrics: {e}")
            logger.error(traceback.format_exc())

        # Uploading server log to S3
        log_fp = f"/ecr-server/LinuxServer/ECR/Saved/Logs/{log_file}"
        if os.path.exists(log_fp):
            s3 = S3Connector()
            with open(log_fp, "r") as f:
                log_content = f.read()
            await s3.upload_file_to_s3(log_content, s3_log_key)

async def monitor_container(container, match_id):
    stats = {}
    try:
        await container.start()
        response = await container.wait()
        response_status = response["StatusCode"]

        # Getting /usr/bin/time -v logs (cpu, memory stats)
        time_log_lines = await container.log(stderr=True, follow=False, tail=100)
        time_logs = "".join(time_log_lines)
        stats = parse_time_command_output(time_logs)
        if response_status == 0:
            logger.debug(f"Container with match id {match_id} finished gracefully with stats {stats}")
        else:
            container_all_logs_lines = await container.log(stdout=True, stderr=True, follow=False, tail=100)
            container_all_logs = "".join(container_all_logs_lines)
            logger.error(f"Container with match id {match_id} failed with code {response_status}, stats {stats}")
            logger.error(container_all_logs)
    except Exception as e:
        logger.error(f"Error during monitoring container with match id {match_id}: {e}")
        logger.error(traceback.format_exc())
    finally:
        if os.getenv("DO_DELETE_CONTAINERS", None) == "1":
            logger.debug(f"Removing container with match id {match_id}")
            await container.delete(force=True)
    return stats


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


async def get_free_instances_and_units():
    all_instances = DEFAULT_FREE_INSTANCES
    _, taken_instances, taken_resource_units = await list_game_docker_containers()

    free_instances = [inst for inst in all_instances if inst not in taken_instances]
    free_resource_units, total_resource_units = check_free_server_resource_units(taken_resource_units)

    return free_instances, free_resource_units, taken_resource_units, total_resource_units


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
