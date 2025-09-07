import typing

from common import ResourceProcessor, permission_required, APIPermission, api_view
from resources.progression_store import ProgressionStoreProcessor
from resources.daily_activity import DailyActivityProcessor


class CombinedCharacterDetailsProcessor(ResourceProcessor):
    """Combined data getter for character details (instead of sending multiple requests)"""

    def __init__(self, logger, contour, user, yc, s3):
        super(CombinedCharacterDetailsProcessor, self).__init__(logger, contour, user, yc, s3)

        self.progression_processor = ProgressionStoreProcessor(self.logger, self.contour, self.user, self.yc, self.s3)
        self.dailies_processor = DailyActivityProcessor(self.logger, self.contour, self.user, self.yc, self.s3)

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all required data about character for character menu: progression and daily tasks"""

        r1, s1 = self.progression_processor.API_GET(request_body)
        if s1 == 200:
            r2, s2 = self.dailies_processor.API_GET(request_body)
            if s2 == 200:
                return {"success": True, "data": {"progression": r1.get("data"), "dailies": r2.get("data")}}, 200
            else:
                return r2, s2
        else:
            return r1, s1


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector

    player = 4

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    cdp = CombinedCharacterDetailsProcessor(logging.getLogger(__name__), "dev", player, yc, s3)
    r, s = cdp.API_GET({"player": 4, "char": 2})
    print(s, r)
