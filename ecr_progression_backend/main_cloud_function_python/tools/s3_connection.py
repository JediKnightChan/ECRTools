import os
import boto3

from botocore.exceptions import ClientError


class S3Connector:
    def __init__(self, bucket_name='ecr-progression'):
        # Connecting to S3 Object Storage
        self.s3_session = boto3.session.Session()
        self.s3 = self.s3_session.client(
            service_name='s3',
            endpoint_url='https://storage.yandexcloud.net',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name="ru-central1"
        )
        self.bucket_name = bucket_name

    def get_file_from_s3(self, s3_key):
        obj_response = self.s3.get_object(Bucket=self.bucket_name, Key=s3_key)
        content = obj_response['Body'].read()
        return content

    def upload_file_to_s3(self, content, s3_key):
        self.s3.put_object(Bucket=self.bucket_name, Key=s3_key, Body=content)

    def check_exists(self, s3_key):
        try:
            self.s3.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            else:
                raise e


if __name__ == '__main__':
    s3 = S3Connector()
    r = s3.check_exists("prod/player_data2/")
    print(r)
