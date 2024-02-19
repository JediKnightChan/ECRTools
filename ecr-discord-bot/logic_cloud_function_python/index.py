import json
import logging
import traceback

from yandex_api import YandexWorker
from google_api import GoogleWorker

from discord_api import DiscordWorker
from missions_logic import get_available_missions, get_wanted_mission, set_wanted_mission


google_servers_data = {
    "us": {"zone": "us-central1-a", "name": "instance-1"},
    "eu": {"zone": "europe-west3-c", "name": "instance-20240219-143622"}
}


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
        if error_response:
            return discord_text_response(error_response)

        if region.lower() in ['ru']:
            yw = YandexWorker()
            res, _ = yw.start_instance(instance)
            if not res.get("done", ""):
                return discord_text_response(f"Starting {region.upper()}")
            else:
                if res.get("code", None) == 9:
                    return discord_text_response(f"{region.upper()} already running")
                else:
                    return discord_text_response(f"Unknown status: {region.upper()}")
        elif region.lower() in google_servers_data:
            gw = GoogleWorker()
            sd = google_servers_data[region.lower()]
            try:
                gw.start_instance(sd["zone"], sd["name"])
                return discord_text_response(f"Starting {region.upper()}")
            except Exception as e:
                return discord_text_response(f"Couldn't start {region.upper()} ({e})")
        else:
            return discord_text_response(f"Don't know region: {region.upper()}")

    elif command_name == "stop_ecr_server":
        instance, region, error_response = get_server_instance_from_command_data(command_data)
        if error_response:
            return discord_text_response(error_response)

        if region.lower() in ["ru"]:
            yw = YandexWorker()
            res, _ = yw.stop_instance(instance)
            if res.get("done", "") == False:
                return discord_text_response(f"Stopping {region.upper()}")
            else:
                return discord_text_response(f"Server already stopped: {region.upper()}")
        elif region.lower() in google_servers_data:
            gw = GoogleWorker()
            sd = google_servers_data[region.lower()]
            try:
                gw.stop_instance(sd["zone"], sd["name"])
                return discord_text_response(f"Stopping {region.upper()}")
            except Exception as e:
                return discord_text_response(f"Couldn't stop {region.upper()} ({e})")
        else:
            return discord_text_response(f"Don't know region: {region.upper()}")
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
