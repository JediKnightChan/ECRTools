import asyncio

from fastapi import FastAPI, HTTPException, Request
from redis.asyncio import Redis
import uuid
import time
import json

app = FastAPI()

redis = Redis(host="localhost", port=6379, decode_responses=True)

PLAYER_EXPIRATION = 30  # Player stays in queue for 30 seconds
MATCH_EXPIRATION = 300  # Matches expire after 5 minutes

players_last_active_ts = {}


async def remove_player_from_all_queues(player_id: str):
    # Remove the player from all queues
    async for key in redis.scan_iter(f"player:*:{player_id}"):
        pool_id = key.split(":")[1]  # Extract pool_id from key
        await redis.delete(key)
        await redis.zrem(f"queue:{pool_id}", player_id)
        if player_id in players_last_active_ts:
            players_last_active_ts.pop(player_id)


async def add_player_to_queue(player_id: str, pool_id: str, desired_match: str):
    timestamp = time.time()
    player_key = f"player:{pool_id}:{player_id}"

    # Update player info in Redis
    await redis.setex(player_key, PLAYER_EXPIRATION, json.dumps({"desired_match": desired_match}))
    await redis.zadd(f"queue:{pool_id}", {player_id: timestamp})
    players_last_active_ts[player_id] = timestamp


async def try_create_match(pool_id: str):
    queue_key = f"queue:{pool_id}"
    # Get the first 16 players in the pool
    players = await redis.zrange(queue_key, 0, 15)

    if len(players) < 16:
        return  # Not enough players to form a match

    # Collect desired_match votes and prepare match details
    desired_match_votes = {}
    players_in_match = []

    for player_id in players:
        player_key = f"player:{pool_id}:{player_id}"
        player_data = await redis.get(player_key)
        if not player_data:
            continue  # Skip expired players

        player_info = json.loads(player_data)
        desired_match = player_info["desired_match"]
        players_in_match.append(player_id)
        desired_match_votes[desired_match] = desired_match_votes.get(desired_match, 0) + 1

        # Remove player from queue and Redis
        await redis.delete(player_key)
        await redis.zrem(queue_key, player_id)
        if player_id in players_last_active_ts:
            players_last_active_ts.pop(player_id)

    # Determine match name by majority vote
    majority_match = max(desired_match_votes.items(), key=lambda x: x[1])[0]
    match_id = str(uuid.uuid4())
    match_url = f"https://game.example.com/matches/{match_id}"

    # Notify players of the match details
    match_details = {"match_id": match_id, "match_name": majority_match, "url": match_url}
    for player_id in players_in_match:
        await redis.setex(f"match:{player_id}", MATCH_EXPIRATION, json.dumps(match_details))
    return match_details


@app.post("/reenter_matchmaking_queue")
async def reenter_matchmaking_queue(request: Request):
    data = await request.json()
    player_id = data["player_id"]
    pool_id = data["pool_id"]
    desired_match = data.get("desired_match")  # Required only for the first entry

    # Check if the player is already in the queue
    player_key = f"player:{pool_id}:{player_id}"
    match_data = await redis.get(f"match:{player_id}")
    if match_data:
        match_details = json.loads(match_data)
        return {"status": "match", **match_details}

    # Reenter or add to the queue
    if desired_match:
        await add_player_to_queue(player_id, pool_id, desired_match)
    elif not await redis.exists(player_key):
        raise HTTPException(status_code=400, detail="Player not in queue. Provide desired_match to reenter.")

    # Extend player expiration if already in queue
    await redis.expire(player_key, PLAYER_EXPIRATION)
    players_last_active_ts[player_id] = time.time()

    # Try to create a match
    match_details = await try_create_match(pool_id)
    if not match_details:
        return {"status": "waiting"}
    else:
        return {"status": "match", **match_details}


@app.post("/leave_matchmaking_queue")
async def leave_matchmaking_queue(request: Request):
    data = await request.json()
    player_id = data["player_id"]

    await remove_player_from_all_queues(player_id)
    # Remove match data if exists
    await redis.delete(f"match:{player_id}")
    return {"status": "success", "message": "Player removed from queue"}


async def clear_expired_players():
    while True:
        players_to_remove = []
        for player, ts in players_last_active_ts:
            if time.time() - ts >= PLAYER_EXPIRATION:
                players_to_remove.append(player)

        for player in players_to_remove:
            await remove_player_from_all_queues(player)

        await asyncio.sleep(5)


@app.on_event("startup")
async def setup_expired_players_clearing():
    """Starts the background task for clearing expired players"""
    asyncio.create_task(clear_expired_players())


# Cleanup Redis on shutdown
@app.on_event("shutdown")
async def shutdown():
    await redis.close()
