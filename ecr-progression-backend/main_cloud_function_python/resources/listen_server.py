import json
import logging
import traceback
import typing

from common import ResourceProcessor, permission_required, APIPermission
from resources.cosmetic_store import CosmeticStoreProcessor
from resources.player import PlayerProcessor


class ListenServerProcessor(ResourceProcessor):
    """Combined data getter for listen server (instead of sending multiple requests)"""

    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        """Get all required data about player for listen server: basic player data, character cosmetics"""

        player_processor = PlayerProcessor(self.logger, self.contour, self.user)
        cosmetic_store_processor = CosmeticStoreProcessor(self.logger, self.contour, self.user)

        r1, s1 = player_processor.API_GET(request_body)
        r2, s2 = cosmetic_store_processor.API_GET(request_body)

        if s1 == 200 and s2 == 200:
            return {"success": True, "data": {"player": r1.get("data"), "cosmetics": r2.get("data")}}, 200
        else:
            return {"success": False}, max([s1, s2])


if __name__ == '__main__':
    player_id = "earlydevtestplayerid"
    char_id = "68f2381b653656b7a5bf9a52e0cd2ca9"
    item_id = "test_cosmetic_item"

    lsp = ListenServerProcessor(logging.getLogger(__name__), "dev", player_id)
    r, s = lsp.API_GET({"player_id": player_id, "id": char_id})
    print(s, r)
