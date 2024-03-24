import datetime
import re
import time
import requests
import boto3
import json
import os
import traceback

PLAYER_API_KEY = os.getenv("PLAYER_API_KEY", "")
SERVER_API_KEY = os.getenv("SERVER_API_KEY", "")
LATEST_MATCHES_S3_PATH = "ecr-online/latest_matches.json"
MATCHES_ONLINE_S3_DIR = "ecr-online/match-online"

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def send_online_update_request(raw_online_data, just_created=False):
    params = {
        "integration": "raw"
    }
    data = {
        "created": "1" if just_created else "0",
        "raw_online_data": raw_online_data
    }
    requests.post("https://functions.yandexcloud.net/d4e49uhbphl49mn0pot5", params=params, json=data)


def upload_content_to_s3(content, s3_key):
    s3.put_object(Bucket='ecr-analytics', Key=s3_key, Body=content)


def get_file_from_s3(s3_key):
    obj_response = s3.get_object(Bucket='ecr-analytics', Key=s3_key)
    content = obj_response['Body'].read()
    return content


def json_response(dict_, status_code=200):
    print("Returning response", status_code, dict_)
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


def update_current_online_stats(raw_online_data, destroy=False):
    """Update current match data for current online stats"""
    match_owner = raw_online_data["owner"]

    raw_online_data["latest_match_update_ts"] = time.time()

    try:
        latest_matches_data = json.loads(get_file_from_s3(LATEST_MATCHES_S3_PATH))
    except Exception as e:
        latest_matches_data = {}

    latest_matches_data[match_owner] = raw_online_data
    new_latest_matches_data = {}
    for k, v in latest_matches_data.items():
        if time.time() - v.API_GET("latest_match_update_ts", 0) > 60 * 7:
            continue
        if time.time() - float(v.API_GET("started_ts", 0)) > 60 * 30:
            continue
        new_latest_matches_data[k] = v

    if destroy:
        new_latest_matches_data.pop(match_owner)

    upload_content_to_s3(json.dumps(new_latest_matches_data, indent=4), LATEST_MATCHES_S3_PATH)


def update_overall_online_stats(raw_online_data):
    """Add raw online data to dict of today matches if player amount increased"""

    dt = datetime.datetime.fromtimestamp(float(raw_online_data["match_creation_ts"]))
    s3_file = f"{MATCHES_ONLINE_S3_DIR}/{dt.year}/{dt.year}-{dt.month}-{dt.day}.json"
    match_id = raw_online_data["owner"] + "_" + raw_online_data["match_creation_ts"]

    try:
        latest_matches_data = json.loads(get_file_from_s3(s3_file))
    except Exception as e:
        latest_matches_data = {}

    latest_player_amount = latest_matches_data.get(match_id, {"player_amount": "0"}).get("player_amount", "0")
    if int(raw_online_data["player_amount"]) >= int(latest_player_amount):
        latest_matches_data[match_id] = raw_online_data

    upload_content_to_s3(json.dumps(latest_matches_data, indent=4), s3_file)


def handler(event, context):
    headers = event.API_GET("headers", [])

    # Checking auth header
    auth_header = headers.API_GET("Ecr-Authorization", "")
    if auth_header == "Api-Key " + PLAYER_API_KEY and PLAYER_API_KEY:
        sender = "player"
    elif auth_header == "Api-Key " + SERVER_API_KEY and SERVER_API_KEY:
        sender = "server"
    else:
        return json_response({"error": "Not authorized"}, status_code=400)

    # Checking game version
    game_version = headers.API_GET("Game-Version", "")
    if not re.match(r"\d+\.\d+\.\d+", game_version):
        return json_response({"error": "Bad game version"})

    # Checking contour
    contour = headers.API_GET("Game-Contour", "")
    if contour not in ["dev", "prod"]:
        return json_response({"error": "Bad game contour"})

    try:
        raw_online_data = json.loads(event["body"])["data"]

        if sender == "server":
            raw_online_data["owner"] = "server"
            raw_online_data["owner_display_name"] = "SERVER"

        print("Processing", raw_online_data)

        # Update current online
        just_created = False
        action = raw_online_data.API_GET("action", "update")
        if action == "update":
            update_current_online_stats(raw_online_data)
        elif action == "destroy":
            update_current_online_stats(raw_online_data, destroy=True)
        elif action == "create":
            just_created = True
            update_current_online_stats(raw_online_data)

        # Send request to discord bot to update current online
        send_online_update_request(raw_online_data, just_created)

        # Update overall today matches statistics
        update_overall_online_stats(raw_online_data)

        return json_response({"status": "success"})
    except Exception as e:
        traceback.print_exc()
        return json_response({"error": "internal"}, status_code=500)
