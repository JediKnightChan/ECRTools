

class S3PathBuilder:
    """Class that defines S3 Path Building for our API"""

    def __init__(self, contour):
        self.contour = contour

    def get_player_folder_s3_path(self, player_id):
        """Player folder"""
        return f"{self.contour}/player_data/{player_id}/"

    def get_player_folder_file_s3_path(self, player_id, filename):
        """Filename in player folder"""
        return f"{self.get_player_folder_s3_path(player_id)}{filename}"

    def get_char_folder_s3_path(self, player_id, character_id):
        """Character folder"""
        return f"{self.contour}/player_data/{player_id}/{character_id}/"

    def get_char_folder_file_s3_path(self, player_id, character_id, filename):
        """Filename in character folder"""
        return f"{self.get_char_folder_s3_path(player_id, character_id)}{filename}"

    def get_character_existence_s3_path(self, player_id, character_id):
        """Character existence file"""
        return self.get_char_folder_file_s3_path(player_id, character_id, "creation_data.json")

    def get_currency_history_s3_path(self, player_id, ts_rel_path):
        """Currency history file (for given timestamp) in the player folder"""
        return self.get_player_folder_file_s3_path(player_id, f"currency_history/{ts_rel_path}")

    def get_unlocked_cosmetics_s3_path(self, player_id, character_id):
        """Unlocked cosmetics file in character folder"""
        return self.get_char_folder_file_s3_path(player_id, character_id, "unlocked_cosmetics.json")
