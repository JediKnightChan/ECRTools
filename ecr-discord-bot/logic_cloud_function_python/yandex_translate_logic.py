import os
from itertools import zip_longest

import requests


class YandexTranslator:
    def __init__(self):
        self.api_key = os.getenv("YT_API_KEY", "")
        self.folder_id = os.getenv("YT_FOLDER_ID", "")
        if not self.api_key:
            raise ValueError("YT_API_KEY not set")
        if not self.folder_id:
            raise ValueError("YT_FOLDER_ID not set")

    def translate_texts(self, texts, target_lang="en"):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': 'Api-Key ' + self.api_key,
        }

        data = {
            "folderId": self.folder_id,
            "texts": texts,
            "targetLanguageCode": target_lang
        }

        r = requests.post('https://translate.api.cloud.yandex.net/translate/v2/translate', headers=headers,
                          json=data)
        print(r.text)
        translations = r.json().get("translations", [])

        result_texts = []
        for original_text, translation_piece in zip_longest(texts, translations, fillvalue=None):
            if translation_piece and translation_piece.get("detectedLanguageCode") != target_lang:
                result_texts.append(translation_piece["text"])
            else:
                result_texts.append(original_text)
        return result_texts


if __name__ == '__main__':
    yt = YandexTranslator()
    r = yt.translate_texts(["Привет", "Космодесантники захватили точку Б!"])
    print(r)
