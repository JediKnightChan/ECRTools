import os

import requests

API_ENDPOINT = 'https://discord.com/api/v10'
CLIENT_ID = os.getenv("CLIENT_ID", "")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

if not CLIENT_SECRET or not CLIENT_ID:
    raise ValueError("Creds missing")


def get_token():
    data = {
        'grant_type': 'client_credentials',
        'scope': 'applications.commands.update'
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    r = requests.post('%s/oauth2/token' % API_ENDPOINT, data=data, headers=headers, auth=(CLIENT_ID, CLIENT_SECRET))
    r.raise_for_status()
    return r.json()


if __name__ == '__main__':
    r = get_token()
    print(r)
