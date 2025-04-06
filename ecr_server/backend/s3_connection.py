import os
import aioboto3
from botocore.exceptions import ClientError


class S3Connector:
    def __init__(self, bucket_name='ecr-analytics'):
        self.bucket_name = bucket_name
        self.endpoint_url = 'https://storage.yandexcloud.net'
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.region_name = "ru-central1"

    async def _get_s3_client(self):
        """Helper function to initialize the S3 client."""
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.aws_access_key_id,
            aws_secret_access_key=self.aws_secret_access_key,
            region_name=self.region_name,
        ) as client:
            return client

    async def get_file_from_s3(self, s3_key):
        async with await self._get_s3_client() as s3:
            response = await s3.get_object(Bucket=self.bucket_name, Key=s3_key)
            content = await response['Body'].read()
            return content

    async def upload_file_to_s3(self, content, s3_key):
        async with await self._get_s3_client() as s3:
            await s3.put_object(Bucket=self.bucket_name, Key=s3_key, Body=content)

    async def check_exists(self, s3_key):
        async with await self._get_s3_client() as s3:
            try:
                await s3.head_object(Bucket=self.bucket_name, Key=s3_key)
                return True
            except ClientError as e:
                if e.response['Error']['Code'] == "404":
                    return False
                else:
                    raise
