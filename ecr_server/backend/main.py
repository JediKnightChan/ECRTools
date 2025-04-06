import asyncio
import logging
import os
import traceback
import uuid

import httpx
from fastapi import FastAPI, BackgroundTasks, HTTPException
from aiocache import SimpleMemoryCache

from models import StartServerRequest
from system_utils import get_cpu_and_ram, parse_time_command_output
from docker_utils import launch_game_docker

app = FastAPI()

cache = SimpleMemoryCache()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

cache_lock = asyncio.Lock()

MAX_GAME_SERVER_INSTANCES = int(os.getenv("MAX_GAME_SERVER_INSTANCES", 10))
DEFAULT_FREE_INSTANCES = list(range(0, MAX_GAME_SERVER_INSTANCES))


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
    except:
        logger.error("Failed to fetch region")
        logger.error(traceback.format_exc())
        region = "N/A"
    return region


async def launch_server_task(game_map, game_mode, game_mission, instance_number, resource_units, match_id,
                             faction_setup):
    try:
        region = await get_region()
        logger.debug(f"Launching server with instance {instance_number}, match id {match_id}, map {game_map}, "
                     f"mode {game_mode}, mission {game_mission}, factions {faction_setup}")
        await launch_game_docker(game_map, game_mode, game_mission, region, instance_number, match_id, faction_setup)
    except Exception as e:
        logger.error(traceback.format_exc())
    finally:
        async with cache_lock:
            # Release port
            game_server_free_instances = await cache.get("game_server_free_instances", None)
            if game_server_free_instances:
                game_server_free_instances.append(instance_number)
                await cache.set("game_server_free_instances", game_server_free_instances)

            # Release resource units
            taken_resource_units = await cache.get("taken_resource_units", 0)
            taken_resource_units -= resource_units
            await cache.set("taken_resource_units", max(0, taken_resource_units))


def check_free_server_resource_units(taken_resource_units):
    """Returns how much resource units are available on server, 1 unit = 2 GB RAM, 1 CPU core"""
    total_cpu, total_ram = get_cpu_and_ram()
    total_resource_units = min(total_cpu, total_ram // 2)
    free_resource_units = max(0, total_resource_units - taken_resource_units)
    return free_resource_units, total_resource_units


@app.post("/launch")
async def launch_game_server(body: StartServerRequest, background_tasks: BackgroundTasks):
    async with cache_lock:
        # Check if ports are available and if yes, reserve
        game_server_free_instances = await cache.get("game_server_free_instances", DEFAULT_FREE_INSTANCES.copy())
        if len(game_server_free_instances) == 0:
            raise HTTPException(status_code=503, detail="No free ports available")
        free_instance = game_server_free_instances[0]
        game_server_free_instances.remove(free_instance)
        await cache.set("game_server_free_instances", game_server_free_instances)

        # Check if resource units are available and if yes, reserve
        taken_resource_units = await cache.get("taken_resource_units", 0)
        free_resource_units, total_resource_units = check_free_server_resource_units(taken_resource_units)
        if body.resource_units > free_resource_units:
            raise HTTPException(status_code=503, detail="Not enough resource units")

        # Correct for new taken units
        taken_resource_units += body.resource_units
        free_resource_units -= body.resource_units
        await cache.set("taken_resource_units", taken_resource_units)

    background_tasks.add_task(launch_server_task, body.game_map, body.game_mode, body.game_mission,
                              free_instance, body.resource_units, body.match_unique_id, body.faction_setup)

    return {"status": "success", "free_instances": game_server_free_instances,
            "free_resource_units": free_resource_units,
            "taken_resource_units": taken_resource_units + body.resource_units,
            "total_resource_units": total_resource_units}


@app.post("/check_free_spots")
async def check_free_spots():
    async with cache_lock:
        # Check if ports are available and if yes, reserve
        game_server_free_instances = await cache.get("game_server_free_instances", DEFAULT_FREE_INSTANCES.copy())
        taken_resource_units = await cache.get("taken_resource_units", 0)
        free_resource_units, total_resource_units = check_free_server_resource_units(
            taken_resource_units)
        return {"free_instances": game_server_free_instances, "free_resource_units": free_resource_units,
                "taken_resource_units": taken_resource_units, "total_resource_units": total_resource_units}


@app.on_event("startup")
async def on_startup():
    # Updates game server region from external API
    await get_region()
