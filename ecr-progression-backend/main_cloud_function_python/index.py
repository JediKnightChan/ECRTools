import json
import logging
import os

from resources.character import CharacterProcessor
from resources.currency import CurrencyProcessor

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


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

    # Here should be validation, using EOS id, EOS token, ECR API token
    pass

    try:
        resource = body["resource"]
        action = body["action"]
        action_data = body["action_data"]

        contour = os.getenv("CONTOUR", "dev")

        if resource == "character":
            processor = CharacterProcessor(logger, contour)
        elif resource == "currency":
            processor = CurrencyProcessor(logger, contour)
        else:
            return json_response({"error": "Unknown resource"}, status_code=400)

        result_data, result_code = processor.API_PROCESS_REQUEST(action, action_data)
        return json_response(result_data, status_code=result_code)

    except Exception as e:
        logger.fatal(f"Error: {e}")
        return json_response({"error": "Internal error"}, status_code=500)
