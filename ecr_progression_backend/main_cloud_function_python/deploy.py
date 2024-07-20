import base64

import requests
import os
import io
import zipfile

from scripts.yandex_cloud_iam.yandex_iam import YandexIamAuth


class VirtualZip:
    def __init__(self):
        self.zip_buffer = io.BytesIO()
        self.zip_file = zipfile.ZipFile(self.zip_buffer, 'w')

    def add_file(self, file_path):
        self.zip_file.write(file_path)

    def add_dir(self, dir_path):
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                self.zip_file.write(file_path)

    def get_content(self):
        self.zip_file.close()
        return self.zip_buffer.getvalue()


def get_new_version_content():
    myzip = VirtualZip()

    myzip.add_dir("./resources/")
    myzip.add_dir("./data/")
    myzip.add_dir("./tools/")

    myzip.add_file("./authorized_key.json")
    myzip.add_file("./common.py")
    myzip.add_file("./index.py")
    myzip.add_file("./requirements.txt")

    binary_content = myzip.get_content()
    return binary_content


def deploy_new_cloud_function_version(headers, version_content=None, version_to_copy=None, to_prod=False):
    env_vars = [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "SERVER_API_KEY",
        "BACKEND_API_KEY",
        "EOS_CLIENT_ID",
        "YDB_DB_PATH",
        "PLAYER_API_KEY"
    ]

    env_dict = {}
    for e in env_vars:
        v = os.getenv(e)
        if v:
            env_dict[e] = v
        else:
            raise ValueError(f"Environmental variable {e} not set")

    data = {
        "functionId": "d4eb6dlgru00e0rmato3",
        "runtime": "python312",
        "description": "Latest dev version",
        "entrypoint": "index.handler",
        "resources": {
            "memory": "268435456"
        },
        "executionTimeout": "10s",
        "serviceAccountId": "aje6u9bhleude8c1l6sv",
        "environment": env_dict,
        "tag": [
            "dev"
        ],
        "connectivity": {
            "networkId": "enptndrgdorv9dvns6gd"
        },
        "logOptions": {
            "disabled": False,
            "logGroupId": "e23jc1ns9nefsq07opqe"
        },
        "concurrency": "16"
    }

    if to_prod:
        data["versionId"] = version_to_copy
        data["environment"] = {**data["environment"], "CONTOUR": "prod"}
        data["tag"] = ["prod"]
    else:
        data["content"] = base64.b64encode(version_content).decode("utf-8")

    print(data)

    r = requests.post("https://serverless-functions.api.cloud.yandex.net/functions/v1/versions", json=data,
                      headers=headers)
    print(r.text)


if __name__ == '__main__':
    yia = YandexIamAuth()
    headers = yia.get_headers()

    do_deploy = True
    to_prod = False

    if do_deploy:
        if to_prod:
            r = requests.get("https://serverless-functions.api.cloud.yandex.net/functions/v1/versions:byTag",
                             headers=headers, params={"functionId": "d4eb6dlgru00e0rmato3", "tag": "dev"})
            version_to_copy = r.json()["id"]
            deploy_new_cloud_function_version(headers, version_to_copy=version_to_copy, to_prod=True)
        else:
            version_content = get_new_version_content()
            deploy_new_cloud_function_version(headers, version_content=version_content, to_prod=False)

    else:
        r = requests.get("https://serverless-functions.api.cloud.yandex.net/functions/v1/versions:byTag",
                         headers=headers, params={"functionId": "d4eb6dlgru00e0rmato3", "tag": "$dev"})
        print(r.text)
