from pydantic import BaseModel, Field, constr
from typing import Optional, Literal, List


class ReenterMatchmakingRequest(BaseModel):
    player_id: str
    region: str
    pool_name: Literal['pvp_casual', 'pvp_duels', 'pve', 'pve_instant']
    game_version: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}$')
    game_contour: Literal['prod', 'dev']

    desired_match_group: Optional[
        Literal['PoolAlpha', 'PoolBeta', 'PoolGamma', 'Vein', 'Inferno', 'Abyss']] = None  # Optional field
    faction: Optional[Literal['LoyalSpaceMarines', 'ChaosSpaceMarines']] = None  # Optional field
    party_members: Optional[List[str]] = None


class LeaveMatchmakingRequest(BaseModel):
    player_id: str


class RegisterGameServerRequest(BaseModel):
    region: str
    resource_units: int
    free_resource_units: int
    free_instances_amount: int


class RegisterGameServerStats(BaseModel):
    region: str
    match_id: str
    stats: dict
