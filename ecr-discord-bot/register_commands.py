import os
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("Wrong creds")

# For authorization, you can use either your bot token
headers = {
    "Authorization": f"Bot {BOT_TOKEN}"
}

# Common values definition
region_choices = [
                {
                    'name': 'Russian Region',
                    'value': 'ru',
                },
                {
                    'name': 'European Region',
                    'value': 'eu',
                },
                {
                    'name': 'North American Region',
                    'value': 'us',
                },
            ]

mission_choices = [
                {
                    'name': 'Zedek (A) - Deepstrike',
                    'value': '/Game/Maps/ZedekNew_TH',
                },
            ]

gamemode_choices = [
                {
                    'name': 'PvP',
                    'value': 'pvp',
                },
                {
                    'name': 'Pve',
                    'value': 'pve',
                },
				{
                    'name': 'PvPvE',
                    'value': 'pvpve',
                },
            ]

# Start ECR server command
json_data_1 = {
    'name': 'start_ecr_server',
    'description': 'Launch an ECR server',
    'options': [
        {
            'type': 3,
            'name': 'region',
            'description': 'Region of the server',
            'required': True,
            'choices': region_choices
        },
		{
			'type': 3,
			'name': 'mission_1',
			'description': 'Mission to launch',
			'choices': mission_choices
		},
		{
			'type': 3,
			'name': 'gamemode_1',
			'description': 'Gamemode to use',
			'choices': gamemode_choices
		},
		{
			'type': 3,
			'name': 'mission_2',
			'description': 'Mission to launch',
			'choices': mission_choices
		},
		{
			'type': 3,
			'name': 'gamemode_2',
			'description': 'Gamemode to use',
			'choices': gamemode_choices
		},
		{
			'type': 3,
			'name': 'mission_3',
			'description': 'Mission to launch',
			'choices': mission_choices
		},
		{
			'type': 3,
			'name': 'gamemode_3',
			'description': 'Gamemode to use',
			'choices': gamemode_choices
		},
		{
			'type': 3,
			'name': 'mission_4',
			'description': 'Mission to launch',
			'choices': mission_choices
		},
		{
			'type': 3,
			'name': 'gamemode_4',
			'description': 'Gamemode to use',
			'choices': gamemode_choices
		},
		{
			'type': 3,
			'name': 'mission_5',
			'description': 'Mission to launch',
			'choices': mission_choices
		},
		{
			'type': 3,
			'name': 'gamemode_5',
			'description': 'Gamemode to use',
			'choices': gamemode_choices
		},
    ],
}

# Stop ECR server command
json_data_2 = {
    'name': 'stop_ecr_server',
    'description': 'Stop an ECR server',
    'options': [
        {
            'type': 3,
            'name': 'region',
            'description': 'Region of the server',
            'required': True,
            'choices': region_choices
        },
    ],
}

# Add Start ECR server command
response = requests.post(
    "https://discord.com/api/v8/applications/1121516250972041298/guilds/895445476969705473/commands",
    headers=headers,
    json=json_data_1,
)

print(response.text)

# Add Stop ECR server command
response = requests.post(
    "https://discord.com/api/v8/applications/1121516250972041298/guilds/895445476969705473/commands",
    headers=headers,
    json=json_data_2,
)

print(response.text)



# Suggestion ECR server command
# /suggest_improvement {message}
json_data_3 = {
    'name': 'suggest_improvement',
    'description': 'Suggest an improvement for ECR',
    'options': [
        {
            'type': 3,
            'name': 'suggestion',
            'description': 'Your Suggestion',
            'required': True
        },
    ],
}

# Add Suggestion ECR server command
response = requests.post(
    "https://discord.com/api/v8/applications/1121516250972041298/guilds/895445476969705473/commands",
    headers=headers,
    json=json_data_3,
)

print(response.text)
