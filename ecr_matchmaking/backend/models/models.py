from pydantic import BaseModel, Field, constr, validator
from typing import Optional, Literal, List, Tuple

GAME_FACTIONS: Tuple[str, ...] = (
    'LoyalSpaceMarines',
    'ChaosSpaceMarines'
)

ALLOWED_POOLS = [
    "pvp_casual",
    "pvp_duels",
    "pve"
]

MAX_PARTY_SIZE = 4


class ReenterMatchmakingRequest(BaseModel):
    player_id: str
    region: str
    # pool_name: Literal['pvp_casual', 'pvp_duels', 'pve']
    pools: List[str]
    game_version: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$')
    game_contour: Literal['prod', 'dev']

    faction: Optional[str] = None
    party_members: Optional[List[str]] = None

    @validator('faction')
    def validate_faction(cls, v):
        if v is None:
            return v
        if v not in GAME_FACTIONS:
            raise ValueError(f"Invalid faction: {v}")
        return v

    @validator('party_members')
    def validate_party_members(cls, v):
        if v is None:
            return v
        if len(v) > MAX_PARTY_SIZE:
            raise ValueError(f"Party size exceeds maximum: {len(v)} > {MAX_PARTY_SIZE}")
        return v

    @validator('pools')
    def validate_pools(cls, v):
        if v is None:
            return v

        if len(v) == 0:
            raise ValueError(f"At least 1 pool must be specified")
        if len(v) > len(ALLOWED_POOLS):
            raise ValueError(f"Max pool amount: {len(ALLOWED_POOLS)}")

        for el in v:
            if el not in ALLOWED_POOLS:
                raise ValueError(f"Invalid pool: {el}")
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


class UpdateOngoingMatchRequest(BaseModel):
    match_id: str
    pool_id: str
    faction_free_spots: dict
    mission: str
