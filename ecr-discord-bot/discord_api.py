import os
import requests


class DiscordWorker:
    def __init__(self):
        self.API_ENDPOINT = "https://discordapp.com/api/"

        self.bot_token = os.getenv("BOT_TOKEN", "")
        if not self.bot_token:
            raise ValueError("Bot token is not set")

        self.headers = {
            "Authorization": f"Bot {self.bot_token}"
        }

    def __make_api_request(self, url, data, method="GET"):
        endpoint = self.API_ENDPOINT + url
        if method == "GET":
            r = requests.get(endpoint, params=data, headers=self.headers)
        elif method == "POST":
            r = requests.post(endpoint, json=data, headers=self.headers)
        else:
            raise NotImplementedError

        return r.json(), r.status_code

    def get_user_data(self, member, server="895445476969705473"):
        return self.__make_api_request(f"guilds/{server}/members/{member}", {})


if __name__ == '__main__':
    dw = DiscordWorker()
    data, _ = dw.get_user_data("1121526846618607720")
    print(data)
