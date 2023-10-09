import json
import os
import time

import boto3

from common.discord_api import DiscordWorker, EmbedBuilder

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)

# ID of the channel and message you want to update
CURRENT_ONLINE_CHANNEL_ID = os.getenv('CURRENT_ONLINE_CHANNEL_ID')
CURRENT_ONLINE_MESSAGE_ID = os.getenv('CURRENT_ONLINE_MESSAGE_ID')

MATCHES_CREATED_CHANNEL_ID = os.getenv('MATCHES_CREATED_CHANNEL_ID')
LATEST_MATCHES_S3_PATH = "ecr-online/latest_matches.json"


def send_match_created_message(raw_match_data):
    dw = DiscordWorker()
    message = f"{raw_match_data['owner_display_name']} created mission {raw_match_data['mission']} " \
              f"on map {raw_match_data['map']}, region {raw_match_data['region']}"
    dw.send_message(MATCHES_CREATED_CHANNEL_ID, dw.build_message(message, ""))


def update_match_message(match_data):
    dw = DiscordWorker()
    eb = EmbedBuilder()

    embed = {
        "title": "CURRENT ONLINE",
        "color": 16753152,
        "fields": []
    }

    def get_splitter():
        return eb.build_field("-" * 83, "")

    def get_match_part(host_name, region, player_amount, started_ts, match_creation_ts, map_name):
        created = f"created <t:{int(match_creation_ts)}:R>"

        if started_ts == 0:
            started = "not started"
        else:
            started = f"started <t:{int(started_ts)}:R>"

        match_info = f"{map_name} ({started}, {created})"
        return [
            eb.build_field("HOST", host_name + f" ({region})", True),
            eb.build_field("PLAYERS", player_amount, True),
            eb.build_field("MATCH", match_info, True)
        ]

    embed["fields"].append(get_splitter())
    embed["fields"].append(eb.build_field("Match amount", len(match_data), True))
    embed["fields"].append(eb.build_field("Player amount", sum([m["player_amount"] for m in match_data]), True))

    now_ts = time.time()
    embed["fields"].append(
        eb.build_field("Last updated", f"<t:{int(now_ts)}:f>", True))

    if len(match_data):
        embed["fields"].append(get_splitter())
        embed["fields"].append(eb.build_field("Top 4 matches", ""))

        best_match_data = sorted(match_data, key=lambda x: x["player_amount"], reverse=True)[:4]
        for match in best_match_data:
            embed["fields"] += get_match_part(match["owner_display_name"], match["region"], match["player_amount"],
                                              match["started_ts"], match["match_creation_ts"],
                                              match["map"])
            embed["fields"].append(eb.build_field("\u200B", ""))

    data, _ = dw.update_message(CURRENT_ONLINE_MESSAGE_ID, CURRENT_ONLINE_CHANNEL_ID, dw.build_message("", embed))
    print("Discord response", data)


def get_file_from_s3(s3_key):
    obj_response = s3.get_object(Bucket='ecr-analytics', Key=s3_key)
    content = obj_response['Body'].read()
    return content


def get_online_stats():
    try:
        latest_matches_data = json.loads(get_file_from_s3(LATEST_MATCHES_S3_PATH))
    except Exception as e:
        latest_matches_data = {}

    new_latest_matches_data = {}
    for k, v in latest_matches_data.items():
        last_update_td = time.time() - v.get("latest_match_update_ts", 0)
        created_td = time.time() - float(v.get("match_creation_ts", 0))

        if last_update_td > 60 * 30:
            continue

        if created_td > 60 * 60:
            continue

        v["player_amount"] = int(v["player_amount"])
        v["match_creation_ts"] = float(v["match_creation_ts"])
        v["started_ts"] = float(v["started_ts"])

        new_latest_matches_data[k] = v

    matches = list(new_latest_matches_data.values())
    return matches


def handler(event, context):
    # Updating discord current online
    matches = get_online_stats()
    print("Matches", matches)
    update_match_message(matches)

    try:
        if event.get("created", "0") == "1":
            send_match_created_message(event.get('raw_online_data', {}))
        return {
            "statusCode": 200
        }
    except Exception as e:
        return {
            "statusCode": 400
        }


if __name__ == '__main__':
    handler({}, {})
