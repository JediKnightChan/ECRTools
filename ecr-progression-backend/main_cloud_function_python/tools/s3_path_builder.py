

class S3PathBuilder:
    """Class that defines S3 Path Building for our API"""

    def __init__(self, contour):
        self.contour = contour

    def get_char_folder_s3_path(self, player_id, character_id):
        return f"{self.contour}/player_data/{player_id}/{character_id}/"

    def get_char_folder_file_s3_path(self, player_id, character_id, filename):
        return f"{self.get_char_folder_s3_path(player_id, character_id)}{filename}"

    def get_character_existence_s3_path(self, player_id, character_id):
        return self.get_char_folder_file_s3_path(player_id, character_id, "creation_data.json")

    def get_currency_s3_path(self, player_id, character_id):
        return self.get_char_folder_file_s3_path(player_id, character_id, "currencies.json")

    def get_currency_history_s3_path(self, player_id, character_id, ts_rel_path):
        return self.get_char_folder_file_s3_path(player_id, character_id, f"currency_history/{ts_rel_path}")

    def get_unlocked_cosmetics_s3_path(self, player_id, character_id):
        return self.get_char_folder_file_s3_path(player_id, character_id, "unlocked_cosmetics.json")
