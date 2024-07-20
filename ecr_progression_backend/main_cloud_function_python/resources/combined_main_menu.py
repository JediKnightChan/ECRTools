import typing

from common import ResourceProcessor, permission_required, APIPermission
from resources.character import CharacterProcessor
from resources.player import PlayerProcessor


class CombinedMainMenuProcessor(ResourceProcessor):
    """Combined data getter for main menu (instead of sending multiple requests)"""

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all required data about player for main menu: basic player data, list of characters"""

        player_processor = PlayerProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        character_processor = CharacterProcessor(self.logger, self.contour, self.user, self.yc, self.s3)

        r1, s1 = player_processor.API_GET(request_body)
        r2, s2 = character_processor.API_LIST(request_body)

        if s1 == 200 and s2 == 200:
            return {"success": True, "data": {"player": r1.get("data"), "characters": r2.get("data")}}, 200
        else:
            return {"success": False}, max([s1, s2])


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector

    player_id = "earlydevtestplayerid"

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    lsp = CombinedMainMenuProcessor(logging.getLogger(__name__), "dev", player_id, yc, s3)
    r, s = lsp.API_GET({"player_id": player_id})
    print(s, r)
