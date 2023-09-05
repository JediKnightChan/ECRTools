# To use this tool you require an Oauth2 client id and its associated secret
# You may generate such a pair for any google cloud project
# At : https://console.cloud.google.com/apis/credentials
# Once you have it you need to put it in the corresponding settings.yaml fields
# You will also need to authorise the google account that will be used to log in
# At : https://console.cloud.google.com/apis/credentials/consent
# The first time you will try to upload with this pair
# You will be required to login to google and authorise the app
# The following times login will be done automatically with a newly generated credentials.json file

# Arguments are :
# 1 : Google drive folder name
# 2 : File to upload relative path

import sys
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

def gdrive_upload(google_drive_folder, file_path):
    gauth = GoogleAuth('google_settings.yaml')
    drive = GoogleDrive(gauth)

    gfile = drive.CreateFile({'parents': [{'id': google_drive_folder}]})
    gfile.SetContentFile(file_path)
    gfile.Upload()

    # Saw somewhere it might cause a memory leak otherwise
    gfile = None
