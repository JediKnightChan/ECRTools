import json
import os
import logging

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError
from pythonjsonlogger import jsonlogger

from permissions import DiscordPermissions
from queue_sender import DiscordMessageQueueSender


class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = str.replace(str.replace(record.levelname, "WARNING", "WARN"), "CRITICAL", "FATAL")


PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")
queue_sender = DiscordMessageQueueSender()

logHandler = logging.StreamHandler()
logHandler.setFormatter(YcLoggingFormatter('%(message)s %(level)s %(logger)s'))

logger = logging.getLogger(__name__)
logger.propagate = False
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)


def json_response(dict_, status_code=200):
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


def discord_text_response(text):
    return json_response({
        'type': 4,
        'data': {
            'content': text,
        }
    })


def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
    except Exception as e:
        logger.error(f"Couldn't parse body of event")
        return json_response({"error": "Couldn't parse body"}, status_code=400)

    try:
        signature = event['headers']["X-Signature-Ed25519"]
        timestamp = event['headers']["X-Signature-Timestamp"]

        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))

        try:
            verify_key.verify(f'{timestamp}{event["body"]}'.encode(), bytes.fromhex(signature))
        except BadSignatureError:
            logger.error("Invalid request signature")
            return json_response({"error": "Invalid request signature"}, status_code=401)

        body_type = body['type']

        if body_type == 1:
            return json_response({
                'type': 1
            })
        elif body_type == 2:
            return command_handler(body)
        else:
            return json_response({"error": "unhandled request type"}, status_code=400)
    except Exception as e:
        logger.fatal(f"Error: {e}")
        return json_response({"error": "Internal error"}, status_code=500)


def command_handler(body):
    command_data = body['data']
    command = command_data['name']
    logger.warning(f"Discord data {body} ")

    up = DiscordPermissions(body["member"])

    community_manager_commands_to_responses = {
        "start_ecr_server": "Starting ECR server queued",
        "stop_ecr_server": "Stopping ECR server queued",
        "set_ecr_server_mission": "Setting ECR server mission queued",
        "get_ecr_server_missions": "Getting ECR server missions queued",
        "set_match_creation_forbidden": "Forbidding/allowing match creation queued"
    }

    all_server_members_commands_to_banned_roles_and_responses = {
        "suggest_ecr_change": ("1216132337134473288", "Your suggested ECR gameplay change is queued for processing")
    }

    if command in community_manager_commands_to_responses:
        if up.is_user_creator() or up.is_user_admin() or up.is_user_community_manager():
            queue_sender.send_message_to_discord_commands_queue(body)
            return discord_text_response(community_manager_commands_to_responses[command])
        else:
            return discord_text_response("You are not allowed to use this command")
    elif command in all_server_members_commands_to_banned_roles_and_responses:
        banned_role, response = all_server_members_commands_to_banned_roles_and_responses[command]
        if up.has_role(banned_role):
            return discord_text_response("You are not allowed to use this command")
        else:
            queue_sender.send_message_to_discord_commands_queue(body)
            return discord_text_response(response)
    else:
        logger.fatal(f"Unknown command {command}")
        return json_response({"error": "unhandled command"}, status_code=400)
