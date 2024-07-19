import json
import logging
import os

from pythonjsonlogger import jsonlogger

from resources.character import CharacterProcessor
from resources.player import PlayerProcessor
from resources.cosmetic_store import CosmeticStoreProcessor
from resources.listen_server import ListenServerProcessor
from resources.main_menu import MainMenuProcessor

from tools.eos_auth import EOSAuthVerifier
from tools.s3_connection import S3Connector
from tools.ydb_connection import YDBConnector


# Initializing logger for YandexCloud

class YcLoggingFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(YcLoggingFormatter, self).add_fields(log_record, record, message_dict)
        log_record['logger'] = record.name
        log_record['level'] = str.replace(str.replace(record.levelname, "WARNING", "WARN"), "CRITICAL", "FATAL")


logHandler = logging.StreamHandler()
logHandler.setFormatter(YcLoggingFormatter('%(message)s %(level)s %(logger)s'))

logger = logging.getLogger(__name__)
logger.propagate = False
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

# Initializing API Keys for accessing API
PLAYER_API_KEY = os.getenv("PLAYER_API_KEY", "")
SERVER_API_KEY = os.getenv("SERVER_API_KEY", "")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

# Initializing connectors to data storages
yc = YDBConnector(logger)
s3 = S3Connector()


def json_response(dict_, status_code=200):
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


def handler(event, context):
    try:
        body = json.loads(event['body'])
    except Exception as e:
        logger.error(f"Couldn't parse body of event")
        return json_response({"error": "Couldn't parse body"}, status_code=400)

    # Validation, using EOS id, EOS token, ECR API token

    # Checking ECR API token
    headers = event.get("headers", [])
    auth_header = headers.get("Ecr-Authorization", "")

    if auth_header == "Api-Key " + PLAYER_API_KEY and PLAYER_API_KEY:
        # Check authentication
        user = headers.get("Ecr-Account", "")
        token_id = headers.get("Ecr-Token", "")

        av = EOSAuthVerifier(logger)
        if not av.validate_token(user, token_id):
            return json_response({"error": "Not authorized (Player Token)"}, status_code=401)
    elif auth_header == "Api-Key " + SERVER_API_KEY and SERVER_API_KEY:
        user = "server"
    elif auth_header == "Api-Key " + BACKEND_API_KEY and BACKEND_API_KEY:
        user = "backend"
    else:
        return json_response({"error": "Not authorized (Api-Key)"}, status_code=401)

    try:
        resource = body["resource"]
        action = body["action"]
        action_data = body["action_data"]

        contour = os.getenv("CONTOUR", "dev")

        processor_init_args = (logger, contour, user, yc, s3)
        if resource == "character":
            processor = CharacterProcessor(*processor_init_args)
        elif resource == "player":
            processor = PlayerProcessor(*processor_init_args)
        elif resource == "cosmetics":
            processor = CosmeticStoreProcessor(*processor_init_args)
        elif resource == "listen_server":
            processor = ListenServerProcessor(*processor_init_args)
        elif resource == "main_menu":
            processor = MainMenuProcessor(*processor_init_args)
        else:
            return json_response({"error": "Unknown resource"}, status_code=400)

        result_data, result_code = processor.API_PROCESS_REQUEST(action, action_data)
        return json_response(result_data, status_code=result_code)

    except Exception as e:
        logger.error(f"Error: {e}")
        return json_response({"error": "Internal error"}, status_code=500)
