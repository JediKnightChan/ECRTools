# Upload ecr-service index.json and api folder to S3,
# used on Windows because of problems with the aws cli on it

import os

import boto3

# Connecting to S3 Object Storage
s3_session = boto3.session.Session()
s3 = s3_session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="ru-central1"
)


def upload_file_to_s3(filepath, s3_key):
    print(f"Uploading {filepath} to {s3_key}")
    with open(filepath, "rb") as f:
        s3.put_object(Bucket='ecr-service', Key=s3_key, Body=f.read())


upload_file_to_s3("index.json", "index.json")

for root, _, files in os.walk("api/"):
    for file in files:
        fp = os.path.join(root, file).replace("\\", "/")
        upload_file_to_s3(fp, fp)
