class DiscordPermissions:
    def __init__(self, user_data):
        self.user_data = user_data

    def has_role(self, role_id):
        return str(role_id) in self.user_data["roles"]

    def is_user_creator(self):
        return self.user_data["user"]["id"] == "234402941224747010"

    def is_user_admin(self):
        return self.has_role("897042700392615966")

    def is_user_project_developer(self):
        return self.has_role("901564733298212884")

    def is_user_community_manager(self):
        return self.has_role("1114968943048802376")
