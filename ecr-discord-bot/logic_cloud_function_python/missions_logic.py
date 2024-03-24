import json
import os
import requests
import boto3

S3_SERVER_DATA_FOLDER = "api/ecr/server_data"
S3_MATCH_DATA_KEY = f"{S3_SERVER_DATA_FOLDER}/match_data.json"
S3_WANTED_MISSION_KEY = f"{S3_SERVER_DATA_FOLDER}/wanted_mission.json"

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def get_file_from_s3(s3_key):
    obj_response = s3.get_object(Bucket='ecr-service', Key=s3_key)
    content = obj_response['Body'].read()
    return content


def upload_file_to_s3(content, s3_key):
    s3.put_object(Bucket='ecr-service', Key=s3_key, Body=content)


def get_available_missions():
    match_data = json.loads(get_file_from_s3(S3_MATCH_DATA_KEY))
    return list(match_data["missions"].keys())


def set_wanted_mission(wanted_mission):
    if wanted_mission.lower().strip() == "none":
        wanted_mission = ""

    new_content = {
        "wanted_mission": wanted_mission
    }
    upload_file_to_s3(json.dumps(new_content, indent=4), S3_WANTED_MISSION_KEY)


def get_wanted_mission():
    wanted_mission = json.loads(get_file_from_s3(S3_WANTED_MISSION_KEY)).API_GET("wanted_mission")
    if wanted_mission == "":
        wanted_mission = "None"
    return wanted_mission
