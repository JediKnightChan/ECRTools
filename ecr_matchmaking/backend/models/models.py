from pydantic import BaseModel, Field, constr, validator
from typing import Optional, Literal, List, Tuple

GAME_FACTIONS: Tuple[str, ...] = (
    'LoyalSpaceMarines',
    'ChaosSpaceMarines'
)


class ReenterMatchmakingRequest(BaseModel):
    player_id: str
    region: str
    pool_name: Literal['pvp_casual', 'pvp_duels', 'pvp_casual_instant', 'pve', 'pve_instant']
    game_version: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    game_contour: Literal['prod', 'dev']

    desired_match_group: Optional[
        Literal['PoolAlpha', 'PoolBeta', 'PoolGamma', 'Vein', 'Inferno', 'Abyss']] = None  # Optional field
    faction: Optional[str] = None
    party_members: Optional[List[str]] = None

    @validator('faction')
    def validate_faction(cls, v):
        if v is None:
            return v
        if v not in GAME_FACTIONS:
            raise ValueError(f"Invalid faction: {v}")
        return v

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
