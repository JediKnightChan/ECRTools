import time
import jwt
import os
import requests


class YandexWorker:
    def __init__(self):
        self.API_ENDPOINT = "https://compute.api.cloud.yandex.net/compute/v1/"

        self.compute_admin_id = os.getenv("COMPUTE_ADMIN_ID", "")
        if not self.compute_admin_id:
            raise ValueError("COMPUTE_ADMIN_ID not set")

        self.api_key_id = os.getenv("COMPUTE_ADMIN_KEY_ID", "")
        if not self.api_key_id:
            raise ValueError("COMPUTE_ADMIN_KEY_ID not set")

    def get_headers(self):
        i_am_token = self.get_i_am_token()
        return {
            "Authorization": f"Bearer {i_am_token}"
        }

    def __get_compute_admin_jwt_token(self):
        with open("compute-admin-private.pem", 'r') as private:
            private_key = private.read()

        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': self.compute_admin_id,
            'iat': now,
            'exp': now + 360}

        return jwt.encode(
            payload,
            private_key,
            algorithm='PS256',
            headers={'kid': self.api_key_id})

    def get_i_am_token(self):
        jwt_token = self.__get_compute_admin_jwt_token()
        r = requests.post("https://iam.api.cloud.yandex.net/iam/v1/tokens", json={"jwt": jwt_token})
        iam_token = r.json()["iamToken"]
        return iam_token

    def __make_api_request(self, url, data, method="GET"):
        endpoint = self.API_ENDPOINT + url
        if method == "GET":
            r = requests.get(endpoint, params=data, headers=self.get_headers())
        elif method == "POST":
            r = requests.post(endpoint, json=data, headers=self.get_headers())
        else:
            raise NotImplementedError

        return r.json(), r.status_code

    def start_instance(self, instance_id):
        """Will return 'code': 9 if already running, else 'done': False"""
        return self.__make_api_request(f"instances/{instance_id}:start", {}, method="POST")

    def stop_instance(self, instance_id):
        """Will return 'done': True if already stopped, else 'done': False"""
        return self.__make_api_request(f"instances/{instance_id}:stop", {}, method="POST")


if __name__ == '__main__':
    dw = YandexWorker()
    data, r = dw.start_instance("epdvna5is52f8i85vsst")
    print(data, r)
