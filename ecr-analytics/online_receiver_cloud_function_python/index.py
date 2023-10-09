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


def update_online_stats(raw_online_data, destroy=False):
    just_created = True
    match_owner = raw_online_data["owner"]

    raw_online_data["latest_match_update_ts"] = time.time()

    try:
        latest_matches_data = json.loads(get_file_from_s3(LATEST_MATCHES_S3_PATH))
    except Exception as e:
        latest_matches_data = {}

    for v in latest_matches_data.values():
        if v["owner"] == raw_online_data["owner"] and v["match_creation_ts"] == raw_online_data["match_creation_ts"]:
            just_created = False

    latest_matches_data[match_owner] = raw_online_data
    new_latest_matches_data = {}
    for k, v in latest_matches_data.items():
        if time.time() - v.get("latest_match_update_ts", 0) > 60 * 30:
            continue
        if time.time() - float(v.get("match_creation_ts", 0)) > 60 * 60:
            continue
        new_latest_matches_data[k] = v

    if destroy:
        new_latest_matches_data.pop(match_owner)

    upload_content_to_s3(json.dumps(new_latest_matches_data, indent=4), LATEST_MATCHES_S3_PATH)
    return just_created


def handler(event, context):
    headers = event.get("headers", [])

    # Checking auth header
    auth_header = headers.get("Ecr-Authorization", "")
    if auth_header == "Api-Key " + PLAYER_API_KEY and PLAYER_API_KEY:
        sender = "player"
    elif auth_header == "Api-Key " + SERVER_API_KEY and SERVER_API_KEY:
        sender = "server"
    else:
        return json_response({"error": "Not authorized"}, status_code=400)

    # Checking game version
    game_version = headers.get("Game-Version", "")
    if not re.match(r"\d+\.\d+\.\d+", game_version):
        return json_response({"error": "Bad game version"})

    # Checking contour
    contour = headers.get("Game-Contour", "")
    if contour not in ["dev", "prod"]:
        return json_response({"error": "Bad game contour"})

    try:
        raw_online_data = json.loads(event["body"])["data"]

        if sender == "server":
            raw_online_data["owner"] = "server"
            raw_online_data["owner_display_name"] = "SERVER"

        print("Processing", raw_online_data)

        just_created = False
        action = raw_online_data.get("action", "update")
        if action == "update":
            just_created = update_online_stats(raw_online_data)
        elif action == "destroy":
            update_online_stats(raw_online_data, destroy=True)

        send_online_update_request(raw_online_data, just_created)

        return json_response({"status": "success"})
    except Exception as e:
        traceback.print_exc()
        return json_response({"error": "internal"}, status_code=500)
