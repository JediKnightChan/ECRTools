import json
import logging
import traceback

from yandex_api import YandexWorker
from discord_api import DiscordWorker
from missions_logic import get_available_missions, get_wanted_mission, set_wanted_mission


def get_command_option(command_data, name):
    options = command_data["options"]
    for option in options:
        if option["name"] == name:
            return option["value"]
    return None


def get_server_instance_from_command_data(command_data_):
    """Returns instance id, region and response if error"""

    def get_region_to_instance(region_):
        region_to_instance = {
            "ru": "epdvna5is52f8i85vsst"
        }
        return region_to_instance.get(region_, None)

    region = get_command_option(command_data_, "region")
    if not region:
        return None, region, "Error: unknown region"

    instance = get_region_to_instance(region)
    if not instance:
        return None, region, "Error: server for this region could not be found"

    return instance, region, None


def handler(event, context):
    interaction_data = {}
    try:
        messages = event.get("messages", [])
        if len(messages) > 0:
            message_body = messages[0].get("details", {}).get("message", {}).get("body", "{}")
            interaction_data = json.loads(message_body)
    except Exception as e:
        logging.error(traceback.format_exc())

    command_data = interaction_data.get("data", {})
    command_name = command_data.get("name")

    dw = DiscordWorker()

    def discord_text_response(text):
        dw.respond_to_interaction(
            interaction_data.get("application_id"),
            interaction_data.get("token"),
            dw.build_message(text, None)
        )
        return {
            'statusCode': 200,
            'body': text,
        }

    if command_name == "start_ecr_server":
        instance, region, error_response = get_server_instance_from_command_data(command_data)
        if not instance:
            return discord_text_response(error_response)

        yw = YandexWorker()
        res, _ = yw.start_instance(instance)
        if not res.get("done", ""):
            return discord_text_response(f"Starting ecr server ({region})")
        else:
            if res.get("code", None) == 9:
                return discord_text_response(f"Server already running ({region})")
            else:
                return discord_text_response(f"Unknown status ({region})")
    elif command_name == "stop_ecr_server":
        instance, region, error_response = get_server_instance_from_command_data(command_data)
        if not instance:
            return discord_text_response(error_response)

        yw = YandexWorker()
        res, _ = yw.stop_instance(instance)
        if res.get("done", "") == False:
            return discord_text_response(f"Stopping ecr server ({region})")
        else:
            return discord_text_response(f"Server already stopped ({region})")
    elif command_name == "set_ecr_server_mission":
        available_missions = get_available_missions()
        mission = get_command_option(command_data, "mission")
        real_mission = None
        if mission.lower() == "none":
            real_mission = "none"
        else:
            for candidate in available_missions:
                if candidate.lower() == mission.lower():
                    real_mission = candidate
            if real_mission is None:
                return discord_text_response(f"Couldn't find mission {mission}")
        set_wanted_mission(real_mission)
        return discord_text_response(f"Setting wanted mission {real_mission}")
    elif command_name == "get_ecr_server_missions":
        available_missions = get_available_missions()
        return discord_text_response("Available missions:\n\n" + "\n".join(available_missions))
    else:
        return discord_text_response("Can't handle: unknown command")
