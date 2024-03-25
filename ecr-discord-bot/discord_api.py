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

    def __make_api_request(self, url, data, method="GET", files=None, expect_json=True):
        endpoint = self.API_ENDPOINT + url
        if method == "GET":
            r = requests.get(endpoint, params=data, headers=self.headers, files=files)
        elif method == "POST":
            r = requests.post(endpoint, json=data, headers=self.headers, files=files)
        elif method == "PATCH":
            r = requests.patch(endpoint, json=data, headers=self.headers, files=files)
        elif method == "DELETE":
            r = requests.delete(endpoint, json=data, headers=self.headers, files=files)
        elif method == "PUT":
            r = requests.put(endpoint, json=data, headers=self.headers, files=files)
        else:
            raise NotImplementedError

        if expect_json:
            return r.json(), r.status_code
        else:
            return r.text, r.status_code

    def get_user_data(self, member, server="895445476969705473"):
        return self.__make_api_request(f"guilds/{server}/members/{member}", {})

    def send_message(self, channel_id, message, files=None):
        return self.__make_api_request(f"channels/{channel_id}/messages", message, method="POST", files=files)

    def update_message(self, message_id, channel_id, message):
        return self.__make_api_request(f"channels/{channel_id}/messages/{message_id}", message, method="PATCH")

    def delete_message(self, message_id, channel_id):
        return self.__make_api_request(f"channels/{channel_id}/messages/{message_id}", {}, method="DELETE")

    def respond_to_interaction(self, app_id, interaction_token, message):
        return self.__make_api_request(f"webhooks/{app_id}/{interaction_token}", message, method="POST")

    def react_to_message(self, message_id, channel_id, emoji):
        return self.__make_api_request(f"channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me", {},
                                       method="PUT", expect_json=False)

    def create_thread_from_message(self, message_id, channel_id, name="Thread", auto_archive_duration=4320):
        return self.__make_api_request(f"/channels/{channel_id}/messages/{message_id}/threads",
                                       {"name": name, "auto_archive_duration": auto_archive_duration}, method="POST")

    @staticmethod
    def build_message(content, embed):
        message = {
            "content": content,
            "embed": embed
        }
        return message


class EmbedBuilder:
    @staticmethod
    def build_embed(title, color, fields):
        return {
            "title": title,
            "color": color,
            "fields": fields
        }

    @staticmethod
    def build_field(name, value, inline=False):
        return {
            "name": name,
            "value": value,
            "inline": inline
        }


if __name__ == '__main__':
    dw = DiscordWorker()
    # data, _ = dw.get_user_data("1121526846618607720")
    data, _ = dw.send_message("899258602567630869", dw.build_message("Hello", None))
    d = dw.react_to_message(data.get("id"), data.get("channel_id"), "🟩")
    d2 = dw.react_to_message(data.get("id"), data.get("channel_id"), "🟥")
    print(data)
    print(d)
    print(d2)

    d3 = dw.create_thread_from_message(data.get("id"), data.get("channel_id"), "Discussion")
    print(d3)
