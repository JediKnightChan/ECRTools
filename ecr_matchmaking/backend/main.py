import os
import traceback
import uuid
import time
import json
import logging

import httpx
from aiocache import SimpleMemoryCache
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from redis.asyncio import Redis

from models.models import *
from logic.pvp_casual import try_create_pvp_match_casual, try_create_instant_pvp_match
from logic.pvp_duels import try_create_pvp_match_duel
from logic.pve import try_create_pve_match, try_create_instant_pve_match
from logic.game_server_utils import try_to_launch_match
from logic.regions import get_region_group

app = FastAPI()

redis = Redis(host=os.getenv("REDIS_HOST"), port=6379, password=os.getenv("REDIS_PASSWORD"), decode_responses=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Constants
PLAYER_EXPIRATION = 30  # Player stays in queue for 30 seconds without additional requests
MATCH_EXPIRATION = 300  # Matches expire after 5 minutes
MATCH_CREATION_LOCK_TIMEOUT = 10  # Create a match attempt locks another attempts for 10 seconds

# State
cache = SimpleMemoryCache()

with open("matchmaking_config.json", "r") as f:
    matchmaking_config = json.load(f)


def GET_REDIS_PLAYER_KEY(pool_id, player_id):
    """This key stores data about the player until it expires"""
    return f"player:{pool_id}:{player_id}"


def GET_REDIS_PLAYER_QUEUE_KEY(pool_id):
    """This sorted set stores queued players by time they entered matchmaking"""
    return f"player_queue:{pool_id}"


def GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id):
    """This sorted set stores queued players by time they last connected to matchmaking
    (for expiration of those who stopped connecting)"""
    return f"player_expire_queue:{pool_id}"


def GET_REDIS_MATCH_KEY(player_id):
    """This key stores data about match assigned to player"""
    return f"match:{player_id}"


def GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id):
    """Allow only 1 match creation in time per pool"""
    return f"matchmaking_lock:{pool_id}"


def GET_REDIS_GAME_SERVERS_QUEUE_KEY():
    """In this queue game servers are registered, ordered by amount of free resource units"""
    return f"game_servers"


def GET_REDIS_GAME_SERVER_KEY(server):
    """Stores information about server"""
    return f"game_server:{server}"


async def acquire_match_creation_lock(pool_id):
    """Locks match creation for pool if isn't locked already, if locked, returns False"""
    lock_key = GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id)
    # Set only if it doesn't exist
    return await redis.set(lock_key, "locked", ex=MATCH_CREATION_LOCK_TIMEOUT, nx=True)


async def release_match_creation_lock(pool_id):
    """Unlocks match creation for pool"""
    lock_key = GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id)
    await redis.delete(lock_key)  # Remove lock


async def update_mission_data():
    """Updates mission data from ecr service backend"""
    async with httpx.AsyncClient() as client:
        r = await client.get("https://storage.yandexcloud.net/ecr-service/api/ecr/server_data/match_data.json")
        r.raise_for_status()
        mission_data = r.json()["missions"]
        await cache.set("mission_data", mission_data)


async def remove_player_from_all_queues(player_id: str):
    # Remove the player from all queues
    async for key in redis.scan_iter(f"player:*:{player_id}"):
        pool_id = key.split(":")[1]  # Extract pool_id from key

        # Remove player specific data
        await redis.delete(key)
        await redis.zrem(GET_REDIS_PLAYER_QUEUE_KEY(pool_id), player_id)
        await redis.zrem(GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id), player_id)


async def add_player_to_queue(player_id: str, pool_id: str, player_data: dict):
    player_key = GET_REDIS_PLAYER_KEY(pool_id, player_id)

    # Update player info in Redis
    await redis.setex(player_key, PLAYER_EXPIRATION, json.dumps(player_data))

    # Add player to queue
    queue_key = GET_REDIS_PLAYER_QUEUE_KEY(pool_id)
    await redis.zadd(queue_key, {player_id: time.time()})


async def try_create_match(pool_id: str):
    queue_key = GET_REDIS_PLAYER_QUEUE_KEY(pool_id)
    player_expire_queue_key = GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id)
    version_and_contour, pool_name = pool_id.split(":")

    expired_players = await redis.zrangebyscore(player_expire_queue_key, "-inf", time.time() - PLAYER_EXPIRATION)

    # Remove expired players in batches of 1000
    for i in range(0, len(expired_players), 1000):
        batch = expired_players[i:i + 1000]
        await redis.zrem(queue_key, *batch)

    # Fetch enough players to allow faction balancing (2 factions, max 16 players per team)
    players_and_ts = await redis.zrange(queue_key, 0, 16 * 2 - 1, withscores=True)

    player_data_map = {}
    faction_counts = {}
    region_group_counts = {}
    latest_ts = 0
    for player_id, queued_ts in players_and_ts:
        player_key = GET_REDIS_PLAYER_KEY(pool_id, player_id)
        player_data = await redis.get(player_key)
        if not player_data:
            # Skip expired or corrupted players
            continue

        player_info = json.loads(player_data)
        player_data_map[player_id] = player_info
        faction = player_info.get("faction")
        faction_counts[faction] = faction_counts.get(faction, 0) + 1
        region_group = player_info.get("region_group")
        region_group_counts[region_group] = region_group_counts.get(region_group, 0) + 1
        latest_ts = max(latest_ts, queued_ts)

    # Update faction counts in cache
    await cache.set("faction_counts", faction_counts)

    if pool_name == "pvp_casual":
        outcome = try_create_pvp_match_casual(player_data_map, latest_ts, matchmaking_config["missions"]["pvp"])
    elif pool_name == "pvp_duels":
        outcome = try_create_pvp_match_duel(player_data_map, latest_ts, matchmaking_config["missions"]["pvp"])
    elif pool_name == "pvp_instant":
        outcome = try_create_instant_pvp_match(player_data_map, latest_ts, matchmaking_config["missions"]["pvp"])
    elif pool_name == "pve":
        outcome = try_create_pve_match(player_data_map, latest_ts, matchmaking_config["missions"]["pve"])
    elif pool_name == "pve_instant":
        outcome = try_create_instant_pve_match(player_data_map, latest_ts, matchmaking_config["missions"]["pve"])
    else:
        raise NotImplementedError

    if not outcome:
        # Get faction counts dynamically
        return {"status": "waiting", "faction_counts": faction_counts}

    players_in_match, match_data = outcome
    all_mission_data = await cache.get("mission_data", {})
    mission_data = all_mission_data.get(match_data["mission"])
    if not mission_data:
        logger.error(f"Couldn't find mission data for {match_data['mission']} in {all_mission_data}")
        return {"status": "waiting", "faction_counts": faction_counts}

    resource_units_required = matchmaking_config["resource_units"][match_data["match_type"]]
    available_servers = await redis.zrangebyscore(GET_REDIS_GAME_SERVERS_QUEUE_KEY(), resource_units_required, "inf",
                                                  start=0, num=10)

    logger.debug(f"Retrieved {len(available_servers)} available servers for match creation")

    if not available_servers:
        # No servers available, need to launch new
        logger.error("No servers available to handle match creation, need to launch")
        return {"status": "waiting", "faction_counts": faction_counts}
    else:
        servers_to_region_groups = {}
        for server in available_servers:
            server_data = await redis.get(GET_REDIS_GAME_SERVER_KEY(server))
            if server_data:
                server_data = json.loads(server_data)
                # Check if server has free ports
                free_instances_amount = server_data["free_instances_amount"]
                if free_instances_amount > 0:
                    region_group = server_data["region_group"]
                    servers_to_region_groups[server] = region_group
                else:
                    logger.warning(f"Skipping server {server} because of low free instances: {free_instances_amount}")

        match_id = str(uuid.uuid4())
        success, successful_server, server_response = await try_to_launch_match(
            logger=logger,
            region_group_counts=region_group_counts,
            servers_to_region_groups=servers_to_region_groups,
            resource_units=resource_units_required,
            version_and_contour=version_and_contour,
            game_map=mission_data["map"],
            game_mission=match_data["mission"],
            game_mode=mission_data["mode"],
            match_id=match_id,
            faction_setup=match_data["faction_setup"]
        )
        if success:
            match_details = {
                "status": "match",
                "match_id": match_id,
                "mission": match_data["mission"]
            }

            # Notify players and remove them from queue
            for player_id in players_in_match:
                if player_id is not None:
                    await redis.setex(GET_REDIS_MATCH_KEY(player_id), MATCH_EXPIRATION, json.dumps(match_details))
                    await redis.delete(GET_REDIS_PLAYER_KEY(pool_id, player_id))
                    await redis.zrem(queue_key, player_id)

            # Update data abut game server
            free_resource_units = server_response["free_resource_units"]
            await redis.zadd(GET_REDIS_GAME_SERVERS_QUEUE_KEY(), {successful_server: free_resource_units})

            server_data = json.dumps({
                "region_group": get_region_group(server_response["region"]),
                "free_instances_amount": server_response["free_instances_amount"]
            })
            await redis.set(GET_REDIS_GAME_SERVER_KEY(successful_server), server_data)

            return match_details
        else:
            logger.error("No server could handle match launch request")
            return {"status": "waiting", "faction_counts": faction_counts}


@app.post("/reenter_matchmaking_queue")
async def reenter_matchmaking_queue(body: ReenterMatchmakingRequest):
    player_id = body.player_id
    pool_name = body.pool_name
    game_version = body.game_version
    game_contour = body.game_contour
    region = body.region

    pool_id = f"{game_version}-{game_contour}:{pool_name}"

    # Parameters expected to be set only during first entry
    desired_match_group = body.desired_match_group
    faction = body.faction
    party_members = body.party_members

    # Check if the player is already assigned to a match
    match_data = await redis.get(GET_REDIS_MATCH_KEY(player_id))
    if match_data:
        match_details = json.loads(match_data)
        return {"status": "match", **match_details}

    # Reenter or add to the queue
    player_key = GET_REDIS_PLAYER_KEY(pool_id, player_id)
    if desired_match_group and faction and party_members:
        # Even if player didn't mention himself in party, do it for him
        if player_id in party_members:
            party_members.remove(player_id)
        party_members.insert(0, player_id)

        await add_player_to_queue(player_id, pool_id, {
            "desired_match_group": desired_match_group,
            "faction": faction,
            "party_members": party_members,
            "region_group": get_region_group(region)
        })
    elif not await redis.exists(player_key):
        raise HTTPException(status_code=400, detail="Player not in queue. Provide required parameters.")

    # Extend player expiration
    await redis.expire(player_key, PLAYER_EXPIRATION)
    # Set player last update time in player expire queue
    await redis.zadd(GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id), {player_id: time.time()})

    # Try to create a match
    got_lock = await acquire_match_creation_lock(pool_id)
    if got_lock:
        try:
            res = await try_create_match(pool_id)
        except Exception as e:
            res = {"status": "server_error"}
            traceback.print_exc()
        finally:
            # Release lock after execution
            await release_match_creation_lock(pool_id)
    else:
        faction_counts = await cache.get("faction_counts")
        res = {"status": "waiting", "faction_counts": faction_counts}
    return res


@app.post("/leave_matchmaking_queue")
async def leave_matchmaking_queue(body: LeaveMatchmakingRequest):
    player_id = body.player_id

    await remove_player_from_all_queues(player_id)
    # Remove match data if exists
    await redis.delete(GET_REDIS_MATCH_KEY(player_id))
    return {"status": "success", "message": "Player removed from queue"}


@app.post("/register_or_update_game_server")
async def register_or_update_game_server(request: Request, body: RegisterGameServerRequest):
    server_ip = request.client.host
    region_group = get_region_group(body.region)
    free_resource_units = body.free_resource_units
    free_instances_amount = body.free_instances_amount

    logger.debug(f"Registering game server {server_ip} ({region_group}): "
                 f"free instances amount {free_instances_amount}, free resource units {free_resource_units}")
    await redis.zadd(GET_REDIS_GAME_SERVERS_QUEUE_KEY(), {server_ip: free_resource_units})

    server_data = json.dumps({
        "region_group": region_group,
        "free_instances_amount": free_instances_amount
    })
    await redis.set(GET_REDIS_GAME_SERVER_KEY(server_ip), server_data)
    return {"status": "success", "message": "Server registered"}


@app.post("/unregister_game_server")
async def unregister_game_server(request: Request):
    server_ip = request.client.host

    logger.debug(f"Unregistering game server {server_ip}")

    server_key = GET_REDIS_GAME_SERVER_KEY(server_ip)
    await redis.zrem(GET_REDIS_GAME_SERVERS_QUEUE_KEY(), server_ip)
    await redis.delete(server_key)

    return {"status": "success", "message": "Server unregistered"}


@app.post("/register_game_server_stats")
async def register_game_server_stats(request: Request, body: RegisterGameServerStats):
    server_ip = request.client.host
    logger.debug(f"Received game server stats from {server_ip}: {body.match_id}: {body.stats}")
    return {"status": "success", "message": "Stats registered"}


@app.post("/update_mission_data")
async def update_mission_data_handler(background_tasks: BackgroundTasks):
    background_tasks.add_task(update_mission_data)
    return {"status": "success", "message": "Acknowledged"}


# Cleanup Redis on shutdown
@app.on_event("shutdown")
async def shutdown():
    await redis.close()


@app.on_event("startup")
async def on_startup():
    # Updates match data
    await update_mission_data()
