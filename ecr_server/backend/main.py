import asyncio
import logging
import os
import traceback
import uuid

import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from aiocache import SimpleMemoryCache

from models import StartServerRequest, DownloadUpdateRequest
from docker_utils import launch_game_docker, get_free_instances_and_units, pull_image_and_delete_older

app = FastAPI()

cache = SimpleMemoryCache()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

cache_lock = asyncio.Lock()


async def get_region():
    """Tries to get region data from cache, if not present, fetches regional API"""
    region = await cache.get("region")
    if region and region != "N/A":
        return region

    try:
        async with httpx.AsyncClient() as client:
            r = await client.get("http://ip-api.com/json/")
            r.raise_for_status()
            data = r.json()
            region = data.get("countryCode", "N/A")
            await cache.set("region", region)
            logger.debug(f"Setting region {region}")
    except:
        logger.error("Failed to fetch region")
        logger.error(traceback.format_exc())
        region = "N/A"
    return region


async def launch_server_task(region, game_contour, game_version, game_map, game_mode, game_mission, instance_number,
                             resource_units, match_id, faction_setup):
    logger.debug(f"Launching server version {game_version}:{game_contour} with instance {instance_number}, "
                 f"match id {match_id}, map {game_map}, mode {game_mode}, mission {game_mission}, "
                 f"factions {faction_setup}")
    await launch_game_docker(region, game_contour, game_version, game_map, game_mode, game_mission, instance_number,
                             resource_units, match_id, faction_setup)


@app.post("/launch")
async def launch_game_server(body: StartServerRequest, background_tasks: BackgroundTasks):
    async with cache_lock:
        free_instances, free_resource_units, taken_resource_units, total_resource_units = await get_free_instances_and_units()

        if len(free_instances) == 0:
            raise HTTPException(status_code=503, detail="No free ports available")
        free_instance = free_instances[0]
        free_instances.remove(free_instance)

        if body.resource_units > free_resource_units:
            raise HTTPException(status_code=503, detail="Not enough resource units")

        # Correct for new taken units
        taken_resource_units += body.resource_units
        free_resource_units -= body.resource_units

    region = await get_region()
    background_tasks.add_task(launch_server_task, region, body.game_contour, body.game_version, body.game_map,
                              body.game_mode, body.game_mission, free_instance, body.resource_units,
                              body.match_unique_id, body.faction_setup)

    return {
        "acknowledged": True,
        "free_instances": free_instances,
        "free_resource_units": free_resource_units,
        "taken_resource_units": taken_resource_units,
        "total_resource_units": total_resource_units
    }


@app.post("/check_free_spots")
async def check_free_spots():
    async with cache_lock:
        free_instances, free_resource_units, taken_resource_units, total_resource_units = await get_free_instances_and_units()
        return {
            "free_instances": free_instances,
            "free_resource_units": free_resource_units,
            "taken_resource_units": taken_resource_units,
            "total_resource_units": total_resource_units
        }


@app.post("/pull_image")
async def download_update(body: DownloadUpdateRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(pull_image_and_delete_older, body.new_image, body.images_to_remove)
    return {"acknowledged": True}


@app.on_event("startup")
async def on_startup():
    # Updates game server region from external API
    await get_region()
