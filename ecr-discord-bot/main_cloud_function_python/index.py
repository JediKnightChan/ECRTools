import json
import os
import logging
import requests

from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

from permissions import DiscordPermissions
from yandex_api import YandexWorker

PUBLIC_KEY = os.getenv("PUBLIC_KEY", "")


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


def get_command_option(command_data, name):
    options = command_data["options"]
    for option in options:
        if option["name"] == name:
            return option["value"]
    return None


def lambda_handler(event, context):
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
    command_data = body['data']
    command = command_data['name']
    logging.warning(f"Discord data {body['data']} ")

    up = DiscordPermissions(body["member"])

    def get_server_instance_from_command_data(command_data_):
        """Returns instance id, region and response if error"""

        def get_region_to_instance(region_):
            region_to_instance = {
                "ru": "epdvna5is52f8i85vsst"
            }
            return region_to_instance.get(region_, None)

        region = get_command_option(command_data_, "region")
        if not region:
            return None, region, discord_text_response("Error: unknown region")

        instance = get_region_to_instance(region)
        if not instance:
            return None, region, discord_text_response("Error: server for this region could not be found")

        return instance, region, None

    if command == 'start_ecr_server':
        if up.is_user_creator() or up.is_user_community_manager():
            instance, region, error_response = get_server_instance_from_command_data(command_data)
            if not instance:
                return error_response

            new_match_data = {
              "missions": {
                "mission_1": {
                  "weight": 1,
                  "map": "",
                  "mode": ""
                },
                "mission_2": {
                  "weight": 1,
                  "map": "",
                  "mode": ""
                },
                "mission_3": {
                  "weight": 1,
                  "map": "",
                  "mode": ""
                },
                "mission_4": {
                  "weight": 1,
                  "map": "",
                  "mode": ""
                },
                "mission_5": {
                  "weight": 1,
                  "map": "",
                  "mode": ""
                }
              }
            }
            _count = 0
            for i in range (1, 6):
                _mission = get_command_option(command_data, 'mission_'+str(i))
                if not _mission:
                    del new_match_data['missions']['mission_'+str(i)]
                    _count = _count + 1
                else:
                    if (_mission == 'zedek_a_deepstrike'):
                        new_match_data['missions']['mission_'+str(i)]['map'] = '/Game/Maps/ZedekNew_TH'
                    
                    _gamemode = get_command_option(command_data, 'gamemode_'+str(i))
                    if not _gamemode:
                        new_match_data['missions']['mission_'+str(i)]['mode'] = 'pvp'
                    else:
                        new_match_data['missions']['mission_'+str(i)]['mode'] = _gamemode
            
            # No mission params, put default mission on
            if (_count == 5) :
                new_match_data['missions']['mission']['map'] = '/Game/Maps/ZedekNew_TH'
                new_match_data['missions']['mission']['mode'] = 'pvp'

            _headers = {
                'Content-Type': 'application/json',
            }
            res = requests.put("https://ecr-service.website.yandexcloud.net/api/ecr/server_data/match_data.json", headers=_headers, json=new_match_data)
            # auth=('USER ID', 'KEY') to authorise update?
            if (!(res.ok)):
                return discord_text_response(f"Failed updating server data ({region})")
            
            yw = YandexWorker()
            res, _ = yw.start_instance(instance)
            if res.get("done", "") == False:
                return discord_text_response(f"Starting ecr server ({region})")
            else:
                if res.get("code", None) == 9:
                    return discord_text_response(f"Server already running ({region})")
                else:
                    return discord_text_response(f"Unknown status ({region})")
        else:
            return discord_text_response("You are not allowed to use this command")
    elif command == "stop_ecr_server":
        if up.is_user_creator() or up.is_user_community_manager() or up.is_user_admin() or up.is_user_project_developer():
            instance, region, error_response = get_server_instance_from_command_data(command_data)
            if not instance:
                return error_response

            yw = YandexWorker()
            res, _ = yw.stop_instance(instance)
            if res.get("done", "") == False:
                return discord_text_response(f"Stopping ecr server ({region})")
            else:
                return discord_text_response(f"Server already stopped ({region})")
        else:
            return discord_text_response("You are not allowed to use this command")
    else:
        logging.error(f"Unknown command {command}")
        return json_response({"error": "unhandled command"}, status_code=400)
