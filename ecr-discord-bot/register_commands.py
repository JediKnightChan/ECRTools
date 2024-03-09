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
    "name": "suggest_ecr_change",
    "description": "Suggest one gameplay change for ECR and put it to a vote",
    "options": [
        {
            "type": 3,
            "name": "title",
            "description": "Title",
            "required": True
        },
        {
            "type": 3,
            "name": "desc",
            "description": "Description and reasoning",
            "required": True
        }
    ]
}

response = requests.post(
    "https://discord.com/api/v8/applications/1121516250972041298/guilds/895445476969705473/commands",
    headers=headers,
    json=json_data,
)

print(response.text)
