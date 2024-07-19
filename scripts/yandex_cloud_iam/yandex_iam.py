import time
import jwt
import os
import requests
import json


class YandexIamAuth:
    def get_headers(self):
        i_am_token = self.get_i_am_token()
        return {
            "Authorization": f"Bearer {i_am_token}"
        }

    def __get_compute_admin_jwt_token(self):
        # Чтение закрытого ключа из JSON-файла
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "private_key.json"), 'r') as f:
            obj = f.read()
            obj = json.loads(obj)
            private_key = obj['private_key']
            key_id = obj['id']
            service_account_id = obj['service_account_id']

        now = int(time.time())
        payload = {
            'aud': 'https://iam.api.cloud.yandex.net/iam/v1/tokens',
            'iss': service_account_id,
            'iat': now,
            'exp': now + 3600
        }

        return jwt.encode(
            payload,
            private_key,
            algorithm='PS256',
            headers={'kid': key_id})

    def get_i_am_token(self):
        jwt_token = self.__get_compute_admin_jwt_token()
        r = requests.post("https://iam.api.cloud.yandex.net/iam/v1/tokens", json={"jwt": jwt_token})
        iam_token = r.json()["iamToken"]
        return iam_token


if __name__ == '__main__':
    dw = YandexIamAuth()
    iam_token = dw.get_i_am_token()
    print(iam_token)
