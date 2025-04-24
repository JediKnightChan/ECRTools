

class S3PathBuilder:
    """Class that defines S3 Path Building for our API"""

    def __init__(self, contour):
        self.contour = contour

    def get_player_folder_s3_path(self, player_id):
        """Player folder"""
        return f"{self.contour}/player_data/{player_id}/"

    def get_player_folder_file_s3_path(self, player, filename):
        """Filename in player folder"""
        return f"{self.get_player_folder_s3_path(player)}{filename}"

    def get_char_folder_s3_path(self, player_id, character_id):
        """Character folder"""
        return f"{self.contour}/player_data/{player_id}/{character_id}/"

    def get_char_folder_file_s3_path(self, player_id, character_id, filename):
        """Filename in character folder"""
        return f"{self.get_char_folder_s3_path(player_id, character_id)}{filename}"

    def get_player_currency_history_s3_path(self, player, ts_rel_path):
        """Currency history file (for given timestamp) in the player folder"""
        return self.get_player_folder_file_s3_path(player, f"currency_history/{ts_rel_path}")

    def get_character_currency_history_s3_path(self, player, char, ts_rel_path):
        """Currency history file (for given timestamp) in the player folder"""
        return self.get_char_folder_file_s3_path(player, char, f"currency_history/{ts_rel_path}")

    def get_unlocked_progression_s3_path(self, player_id, character_id):
        """Unlocked cosmetics file in character folder"""
        return self.get_char_folder_file_s3_path(player_id, character_id, "unlocked_progression.json")
