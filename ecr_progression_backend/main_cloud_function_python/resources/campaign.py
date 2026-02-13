import json
import math
import os
import typing
import datetime

from common import CURRENT_CAMPAIGN_NAME, ResourceProcessor, api_view, permission_required, APIPermission
from tools.common_schemas import ExcludeSchema, ECR_FACTIONS
from marshmallow import fields


class FactionCampaignResultSchema(ExcludeSchema):
    campaign = fields.Str()
    faction = fields.Str()
    won_matches = fields.Int()
    played_matches = fields.Int()


class CampaignProcessor(ResourceProcessor):
    """Retrieve current campaign status"""

    def __init__(self, logger, contour, user, yc, s3):
        super(CampaignProcessor, self).__init__(logger, contour, user, yc, s3)

        self.table_name = self.get_table_name_for_contour("ecr_campaign_results")

    @api_view
    @permission_required(APIPermission.ANYONE)
    def API_GET(self, request_body: dict) -> typing.Tuple[dict, int]:
        if CURRENT_CAMPAIGN_NAME and CURRENT_CAMPAIGN_NAME in self.campaigns_data:
            # Active campaign is ongoing or ending
            faction_res = self._get_factions_results()
            campaign_data = self._get_campaign_data(CURRENT_CAMPAIGN_NAME)
            end_ts = datetime.datetime.fromisoformat(campaign_data["end_time_iso"]).timestamp()

            return {
                "success": True,
                "data": {
                    "is_active": True,
                    "campaign": CURRENT_CAMPAIGN_NAME,
                    "end_ts": end_ts,
                    "scores": faction_res,
                    **campaign_data
                }
            }, 200
        else:
            # No active campaign
            return {
                "success": True,
                "data": {
                    "is_active": False,
                }
            }, 200

    def _get_campaign_data(self, campaign) -> dict:
        """Retrieves campaign data from JSON file"""
        return self.campaigns_data.get(campaign, None)

    def _get_factions_results(self) -> dict[str, int]:
        """Retrieves campaign results for active factions from DB"""

        query = f"""
            DECLARE $CAMPAIGN AS Utf8;

            SELECT * FROM {self.table_name}
            WHERE
                campaign = $CAMPAIGN
            ;
        """

        query_params = {
            '$CAMPAIGN': CURRENT_CAMPAIGN_NAME,
        }

        result, code = self.yc.process_query(query, query_params)
        if code != 0 or len(result) == 0:
            raise Exception("Couldn't retrieve campaign results")

        dump_schema = FactionCampaignResultSchema()
        records = [dump_schema.dump(r) for r in result[0].rows]

        play_amounts = {r["faction"]: r["played_matches"] for r in records}
        win_amounts = {r["faction"]: r["won_matches"] for r in records}

        return self.calculate_faction_scores(play_amounts, win_amounts, ECR_FACTIONS)

    @staticmethod
    def calculate_faction_scores(
            plays: dict[str, int],
            wins: dict[str, int],
            factions: list[str],
            alpha: float = 10.0,
            beta: float = 0.5
    ) -> dict[str, int]:
        """
        Calculate faction scores that sum to 100, based on win/play amounts.

        Args:
            plays: dict of {faction: played_matches}
            wins: dict of {faction: won_matches}
            factions: list of all factions (ensures missing ones are included)
            alpha: prior strength for regularizing win rate on small samples
            beta: exponent for activity scaling

        Returns:
            dict of factions to scores, summing to 100
        """

        # Ensure all factions are present
        records = []
        total_wins = sum(wins.get(f, 0) for f in factions)
        total_plays = sum(plays.get(f, 0) for f in factions)

        if total_plays > 0:
            p0 = total_wins / total_plays
        else:
            p0 = 1.0 / len(factions)

        for f in factions:
            w = float(wins.get(f, 1))
            p = float(plays.get(f, 1))
            # regularized win rate
            p_hat = (w + alpha * p0) / (p + alpha) if (p + alpha) > 0 else p0
            # activity adjustment
            act = p ** beta if p > 0 else 0.0
            score_raw = p_hat * act
            records.append((f, score_raw))

        total_score = sum(s for _, s in records) or 1.0

        # normalize to percentages
        scores_float = {f: 100.0 * s / total_score for f, s in records}

        # round to integers, keep sum = 100
        rounded = {f: int(round(val)) for f, val in scores_float.items()}
        diff = 100 - sum(rounded.values())
        if diff != 0:
            # fix rounding by adjusting largest faction(s)
            sorted_f = sorted(scores_float.items(), key=lambda x: -x[1])
            for f, _ in sorted_f:
                rounded[f] += int(math.copysign(1, diff))
                diff -= int(math.copysign(1, diff))
                if diff == 0:
                    break

        return rounded


if __name__ == '__main__':
    import logging
    from tools.s3_connection import S3Connector
    from tools.ydb_connection import YDBConnector

    logger = logging.getLogger(__name__)
    yc = YDBConnector(logger)
    s3 = S3Connector()

    player = 4
    campaign_proc = CampaignProcessor(logger, "dev", player, yc, s3)
    r, s = campaign_proc.API_GET({})
    print(r, s)
