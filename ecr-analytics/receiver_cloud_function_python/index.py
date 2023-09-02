import datetime
import re

import boto3
import json
import os
import traceback

PLAYER_API_KEY = os.getenv("PLAYER_API_KEY", "")
SERVER_API_KEY = os.getenv("SERVER_API_KEY", "")

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def upload_content_to_s3(content, s3_key):
    s3.put_object(Bucket='ecr-analytics', Key=s3_key, Body=content)


def json_response(dict_, status_code=200):
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


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
        raw_analytics_data = json.loads(event["body"])
        raw_analytics_data["sender"] = sender
        raw_analytics_data["game_version"] = game_version
        raw_analytics_data["contour"] = contour

        # No indents, but allow non ASCII
        new_formatted_content = json.dumps(raw_analytics_data, ensure_ascii=False)
        s3_key = f"ecr-game/{contour}/{game_version}/raw/{datetime.datetime.now().isoformat()}.json"
        upload_content_to_s3(new_formatted_content, s3_key)

        return json_response({"status": "success"})
    except Exception as e:
        traceback.print_exc()
        return json_response({"error": "internal"}, status_code=500)
