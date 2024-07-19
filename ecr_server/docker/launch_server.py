import requests
import random
import subprocess
import os

FALLBACK_REGION = "N/A"
FALLBACK_MATCH_DATA = {
    "missions": {
        "ZedekSmallDeepStrike": {
            "weight": 1,
            "map": "/Game/Maps/ZedekNew_TH",
            "mode": "pvp"
        }
    }
}


def get_region():
    env_value = os.getenv("REGION", "")
    if env_value:
        return env_value

    region = FALLBACK_REGION

    try:
        r = requests.get("http://ip-api.com/json/")
        data = r.json()
        region = data["countryCode"]
    except:
        print("Couldn't reach ip-api.com to define region, using fallback")
        pass

    return region


def get_wanted_mission():
    wanted_mission = None
    try:
        r = requests.get("https://ecr-service.website.yandexcloud.net/api/ecr/server_data/wanted_mission.json")
        data = r.json()
        wanted_mission = data["wanted_mission"]
    except:
        print("Couldn't get wanted mission")
        pass

    return wanted_mission if wanted_mission else None


def get_match_data():
    match_data = FALLBACK_MATCH_DATA

    try:
        r = requests.get("https://ecr-service.website.yandexcloud.net/api/ecr/server_data/match_data.json")
        data = r.json()
        match_data = data
    except:
        print("Couldn't reach ecr-service to define match data, using fallback")
    return match_data


if __name__ == '__main__':
    region = get_region()
    print(region)

    match_data = get_match_data()
    match_missions = match_data["missions"]
    match_missions_weights = [mission_data["weight"] for mission_data in match_missions.values()]

    selected_match = get_wanted_mission()
    if selected_match is None or selected_match not in match_missions:
        selected_match = random.choices(
            list(match_missions.keys()), weights=match_missions_weights, k=1)[0]

    print("Selected mission:", selected_match)
    selected_match_data = match_missions[selected_match]

    launch_command = f"./LinuxServer/ECRServer.sh {selected_match_data['map']} -mode {selected_match_data['mode']}" \
                     f" -mission {selected_match} -region {region} -epicapp=ServerArtifact" \
                     f" -analytics-key=8822acbd-460f-4a84-9bd1-97ab82007384 -log"

    subprocess.run(launch_command, shell=True)
