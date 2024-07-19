import json
import os
import boto3


class DiscordMessageQueueSender:
    def __init__(self):
        # Message queue

        self.session = boto3.session.Session()
        self.client = self.session.client(
            service_name='sqs',
            endpoint_url='https://message-queue.api.cloud.yandex.net',
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name="ru-central1"
        )

        self.DISCORD_COMMANDS_QUEUE = self.client.get_queue_url(QueueName='discord-commands-queue')['QueueUrl']

    def __send_message(self, message_body, queue_url, message_group_id=None, message_deduplication_id=None):
        self.client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body,
            MessageGroupId=message_group_id,
            MessageDeduplicationId=message_deduplication_id
        )

    def send_message_to_discord_commands_queue(self, command_data):
        json_string = json.dumps(command_data)
        self.__send_message(json_string, self.DISCORD_COMMANDS_QUEUE, "discord-commands",
                            str(hash(json_string)))
