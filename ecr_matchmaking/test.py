import requests

body_json = {
    "player_id": "12345",
    "pool_id": "prod",
    "desired_match": "carmine_group"
}

url_end = "reenter_matchmaking_queue"
r = requests.post(f"https://matchmaking.eternal-crusade.com/{url_end}", json=body_json)
print(r.json())
