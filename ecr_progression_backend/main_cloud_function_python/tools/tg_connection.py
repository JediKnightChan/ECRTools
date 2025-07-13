import os
import logging
import traceback

import requests

logger = logging.getLogger('Telegram')


def send_telegram_message(message):
    bot_token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not bot_token or not chat_id:
        raise ValueError("Env variables TG_BOT_TOKEN and TG_CHAT_ID must be set")

    try:
        url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
        payload = {
            'chat_id': chat_id,
            'text': message
        }

        response = requests.post(url, data=payload)
        if response.status_code != 200:
            raise ValueError(f"Telegram Error {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Telegram Error {e}")
        logger.error(traceback.format_exc())


if __name__ == '__main__':
    send_telegram_message("Hello")
