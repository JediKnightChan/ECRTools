import os
import traceback
import uuid
import time
import json

from aiocache import SimpleMemoryCache
from fastapi import FastAPI, HTTPException, Request
from redis.asyncio import Redis

from models.models import ReenterMatchmakingRequest, LeaveMatchmakingRequest
from logic.pvp_casual import try_create_pvp_match_casual
from logic.pvp_duels import try_create_pvp_match_duel
from logic.pve import try_create_pve_match, try_create_instant_pve_match

app = FastAPI()

redis = Redis(host="redis_db", port=6379, password=os.getenv("REDIS_PASSWORD"), decode_responses=True)

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


def GET_REDIS_QUEUE_KEY(pool_id):
    """This sorted set stores queued players by time they entered matchmaking"""
    return f"queue:{pool_id}"


def GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id):
    """This sorted set stores queued players by time they last connected to matchmaking
    (for expiration of those who stopped connecting)"""
    return f"expire_queue:{pool_id}"


def GET_REDIS_MATCH_KEY(player_id):
    """This key stores data about match assigned to player"""
    return f"match:{player_id}"


def GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id):
    """Allow only 1 match creation in time per pool"""
    return f"matchmaking_lock:{pool_id}"


async def acquire_match_creation_lock(pool_id):
    """Locks match creation for pool if isn't locked already, if locked, returns False"""
    lock_key = GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id)
    # Set only if it doesn't exist
    return await redis.set(lock_key, "locked", ex=MATCH_CREATION_LOCK_TIMEOUT, nx=True)


async def release_match_creation_lock(pool_id):
    """Unlocks match creation for pool"""
    lock_key = GET_REDIS_MATCH_CREATION_LOCK_KEY(pool_id)
    await redis.delete(lock_key)  # Remove lock


async def remove_player_from_all_queues(player_id: str):
    # Remove the player from all queues
    async for key in redis.scan_iter(f"player:*:{player_id}"):
        pool_id = key.split(":")[1]  # Extract pool_id from key

        # Remove player specific data
        await redis.delete(key)
        await redis.zrem(GET_REDIS_QUEUE_KEY(pool_id), player_id)
        await redis.zrem(GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id), player_id)


async def add_player_to_queue(player_id: str, pool_id: str, player_data: dict):
    player_key = GET_REDIS_PLAYER_KEY(pool_id, player_id)

    # Update player info in Redis
    await redis.setex(player_key, PLAYER_EXPIRATION, json.dumps(player_data))

    # Add player to queue
    queue_key = GET_REDIS_QUEUE_KEY(pool_id)
    await redis.zadd(queue_key, {player_id: time.time()})


async def try_create_match(pool_id: str):
    queue_key = GET_REDIS_QUEUE_KEY(pool_id)
    player_expire_queue_key = GET_REDIS_PLAYER_EXPIRE_QUEUE_KEY(pool_id)
    pool_name = pool_id.split(":")[2]

    expired_players = await redis.zrangebyscore(player_expire_queue_key, "-inf", time.time() - PLAYER_EXPIRATION)

    # Remove expired players in batches of 1000
    for i in range(0, len(expired_players), 1000):
        batch = expired_players[i:i + 1000]
        await redis.zrem(queue_key, *batch)

    # Fetch enough players to allow faction balancing (2 factions, max 16 players per team)
    players_and_ts = await redis.zrange(queue_key, 0, 16 * 2 - 1, withscores=True)

    player_data_map = {}
    faction_counts = {}
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
        latest_ts = max(latest_ts, queued_ts)

    # Update faction counts in cache
    await cache.set("faction_counts", faction_counts)

    if pool_name == "pvp_casual":
        outcome = try_create_pvp_match_casual(player_data_map, latest_ts, matchmaking_config["pvp"])
    elif pool_name == "pvp_duels":
        outcome = try_create_pvp_match_duel(player_data_map, latest_ts, matchmaking_config["pvp"])
    elif pool_name == "pve":
        outcome = try_create_pve_match(player_data_map, latest_ts, matchmaking_config["pve"])
    elif pool_name == "pve_instant":
        outcome = try_create_instant_pve_match(player_data_map, latest_ts, matchmaking_config["pve"])
    else:
        raise NotImplementedError

    if not outcome:
        # Get faction counts dynamically
        return {"status": "waiting", "faction_counts": faction_counts}

    players_in_match, match = outcome

    # Create match
    match_id = str(uuid.uuid4())
    match_url = f"https://game.example.com/matches/{match_id}"
    match_details = {
        "status": "match",
        "match_id": match_id,
        "match_name": match,
        "url": match_url
    }

    # Notify players and remove them from queue
    for player_id in players_in_match:
        await redis.setex(GET_REDIS_MATCH_KEY(player_id), MATCH_EXPIRATION, json.dumps(match_details))
        await redis.delete(GET_REDIS_PLAYER_KEY(pool_id, player_id))
        await redis.zrem(queue_key, player_id)

    return match_details


@app.post("/reenter_matchmaking_queue")
async def reenter_matchmaking_queue(body: ReenterMatchmakingRequest):
    player_id = body.player_id
    pool_name = body.pool_name
    game_version = body.game_version
    game_contour = body.game_contour

    pool_id = f"{game_contour}:{game_version}:{pool_name}"

    # Parameters expected to be set only during first entry
    desired_match_group = body.desired_match_group
    faction = body.faction

    # Check if the player is already assigned to a match
    match_data = await redis.get(GET_REDIS_MATCH_KEY(player_id))
    if match_data:
        match_details = json.loads(match_data)
        return {"status": "match", **match_details}

    # Reenter or add to the queue
    player_key = GET_REDIS_PLAYER_KEY(pool_id, player_id)
    if desired_match_group and faction:
        await add_player_to_queue(player_id, pool_id, {
            "desired_match_group": desired_match_group,
            "faction": faction
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


# Cleanup Redis on shutdown
@app.on_event("shutdown")
async def shutdown():
    await redis.close()
