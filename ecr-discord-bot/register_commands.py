import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("Wrong creds")

# For authorization, you can use either your bot token
headers = {
    "Authorization": f"Bot {BOT_TOKEN}"
}

json_data = {
    "name": "stop_ecr_server",
    "description": "Stops ECR server in the specified region",
    "options": [
        {
            "type": 3,
            "name": "region",
            "description": "Server Region",
            "required": True,
            "choices": [
                {
                    "name": "RU",
                    "value": "ru",
                },
                {
                    "name": "EU",
                    "value": "eu",
                },
                {
                    "name": "US",
                    "value": "us",
                },
            ],
        },
    ],
}

response = requests.post(
    "https://discord.com/api/v8/applications/1121516250972041298/guilds/895445476969705473/commands",
    headers=headers,
    json=json_data,
)

print(response.text)
