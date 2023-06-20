import requests
import random
import subprocess

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
    region = FALLBACK_REGION

    try:
        r = requests.get("http://ip-api.com/json/")
        data = r.json()
        region = data["countryCode"]
    except:
        print("Couldn't reach ip-api.com to define region, using fallback")
        pass

    return region


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
    selected_match = random.choices(
        list(match_missions.keys()), weights=match_missions_weights, k=1)[0]

    print("Selected mission:", selected_match)
    selected_match_data = match_missions[selected_match]

    launch_command = f"./LinuxServer/ECRServer.sh {selected_match_data['map']} -mode {selected_match_data['mode']}" \
                     f" -mission {selected_match} -region {region} -epicapp=ServerArtifact -log "

    subprocess.run(launch_command, shell=True)
