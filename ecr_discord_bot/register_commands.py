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
    "name": "set_match_creation_forbidden",
    "description": "During planned games prohibit hosting from players, make sure to reset it in the end of event",
    "options": [
        {
            "type": 5,
            "name": "forbidden",
            "description": "Forbid/allow",
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
