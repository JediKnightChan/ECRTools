import json
import string
import os
import logging
import requests

# Bot credentials and channel for handling posts
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CURRENT_ONLINE_CHANNEL_ID = os.getenv("CURRENT_ONLINE_CHANNEL_ID", "")
CURRENT_ONLINE_ROLE_ID = os.getenv("CURRENT_ONLINE_ROLE_ID", "")

def json_response(dict_, status_code=200):
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(dict_)
    }

# Method to add a ping (or not) depending on the player count
def get_ping(player_count):
    if (player_count  > 8):
        return "<@&{}>".format(CURRENT_ONLINE_ROLE_ID)
    else:
        return ""

# Method to build an embed object from a player count
def build_embed(player_count):
    return {
          "type": "rich",
          "title": "ECR Match",
          "description": "",
          "color": 0xbfa300,
          "fields": [
            {
              "name": "Players",
              "value": str(player_count)
            }
          ]
        }

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
    except Exception as e:
        logging.warning(f"Couldn't parse body of event")
        return json_response({"error": "Couldn't parse body"}, status_code=400)

    try:
        # TODO? - Check authorisation?
        return command_handler(body)
    except Exception as e:
        logging.error(f"Error: {e}")
        return json_response({"error": "Internal error"}, status_code=500)

def command_handler(body):
    type = body['type']
    # Header for bot exchange
    headers = { "Authorization":"Bot {}".format(BOT_TOKEN),
        "User-Agent":"myBotThing (http://some.url, v0.1)",
        "Content-Type":"application/json", }
        
    # Create message
    if (type == 1):
        player_count = body['player_count']
    
        baseURL = "https://discordapp.com/api/channels/{}/messages".format(CURRENT_ONLINE_CHANNEL_ID)
        
        POSTedJSON =  json.dumps ( { "content": get_ping(player_count),
                                "embeds": [build_embed(player_count)]
                                } )
        
        response = requests.post(baseURL, headers = headers, data = POSTedJSON)
        
        if (response.status_code == 200):
            return json_response({"id": response.json()['id']}, 200)
        else:
            return json_response({"error": "Message could not be created"}, 500)
    
    # Update message
    elif (type == 2):
        message_id = body['message_id']
        player_count = body['player_count']
        
        POSTedJSON =  json.dumps ( { "content": get_ping(player_count),
                                "embeds": [build_embed(player_count)]
                                } )
        
        response = requests.patch("https://discordapp.com/api/channels/{}/messages/{}".format(CURRENT_ONLINE_CHANNEL_ID, message_id), headers=headers, data = POSTedJSON)

        if (response.status_code == 200):
            return json_response({"message": "Message updated succesfully"}, 200)
        else:
            return json_response({"error": "Message could not be updated"}, 500)
    
    # Delete message
    elif (type == 3):
        message_id = body['message_id']
        
        response = requests.delete("https://discordapp.com/api/channels/{}/messages/{}".format(CURRENT_ONLINE_CHANNEL_ID, message_id), headers=headers)
        
        if (response.status_code == 204):
            return json_response({"message": "Message deleted succesfully"}, 204)
        else:
            return json_response({"error": "Message could not be deleted"}, 500)
                
    else:
        logging.error(f"Unknown type {type}")
        return json_response({"error": "unhandled type"}, status_code=400)
