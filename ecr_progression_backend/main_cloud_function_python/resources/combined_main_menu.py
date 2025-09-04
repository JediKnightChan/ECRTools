import typing

from common import ResourceProcessor, permission_required, APIPermission, api_view
from resources.character import CharacterProcessor
from resources.player import PlayerProcessor


class CombinedMainMenuProcessor(ResourceProcessor):
    """Combined data getter for main menu (instead of sending multiple requests)"""

    def __init__(self, logger, contour, user, yc, s3):
        super(CombinedMainMenuProcessor, self).__init__(logger, contour, user, yc, s3)

        self.player_processor = PlayerProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        self.character_processor = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)

    @api_view
    @permission_required(APIPermission.SERVER_OR_OWNING_PLAYER, player_arg_name="id")
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all required data about player for main menu: basic player data, list of characters"""

        r1, s1 = self.player_processor.API_GET(request_body)
        if s1 == 200:
            r2, s2 = self.character_processor.API_LIST({"player": request_body.get("id")})
            if s2 == 200:
                return {"success": True, "data": {"player": r1.get("data"), "characters": r2.get("data")}}, 200
            else:
                return r2, s2
        else:
            return r1, s1

    @api_view
    def API_GET_FOR_SELF(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Same, but doesn't require to specify internal user id, will take it from current user"""

        player = self.user
        if not player or self.is_user_server_or_backend():
            raise ValueError(f"Can't get self player data for user {player}")
        return self.API_GET({"id": player})

    def API_CUSTOM_ACTION(self, action: str, request_body: dict) -> typing.Tuple[dict, int]:
        if action == "get_for_self":
            return self.API_GET_FOR_SELF(request_body)
        else:
            raise NotImplementedError


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector

    player = 4

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    lsp = CombinedMainMenuProcessor(logging.getLogger(__name__), "dev", player, yc, s3)
    # r, s = lsp.API_GET({"id": player})
    r, s = lsp.API_GET_FOR_SELF({})
    print(s, r)
