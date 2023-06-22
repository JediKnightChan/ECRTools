import json
import os
import logging

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")


def json_response(dict_, status_code=200):
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }


def lambda_handler(event, context):
    logging.warning(f"Event {event}")

    try:
        body = json.loads(event['body'])
    except Exception as e:
        logging.warning(f"Couldn't parse body of event")
        return json_response({"error": "Couldn't parse body"}, status_code=400)

    try:
        signature = event['headers']["X-Signature-Ed25519"]
        timestamp = event['headers']["X-Signature-Timestamp"]

        verify_key = VerifyKey(bytes.fromhex(PUBLIC_KEY))

        try:
            verify_key.verify(f'{timestamp}{event["body"]}'.encode(), bytes.fromhex(signature))
        except BadSignatureError:
            logging.warning("Invalid request signature")
            return json_response({"error": "Invalid request signature"}, status_code=401)

        body_type = body['type']

        if body_type == 1:
            logging.warning("Type 1 request")
            return json_response({
                'type': 1
            })
        elif body_type == 2:
            return command_handler(body)
        else:
            logging.error(f"Body type unhandled: {body_type}")
            return json_response({"error": "unhandled request type"}, status_code=400)
    except Exception as e:
        logging.error(f"Error: {e}")
        return json_response({"error": "Internal error"}, status_code=500)


def command_handler(body):
    command = body['data']['name']
    logging.warning(f"Discord data {body['data']} ")

    if command == 'start_ecr_server':
        logging.warning("Success, returning start_ecr_server response")
        return json_response({
            'type': 4,
            'data': {
                'content': 'Hello, World.',
            }
        })
    else:
        logging.error(f"Unknown command {command}")
        return json_response({"error": "unhandled command"}, status_code=400)
