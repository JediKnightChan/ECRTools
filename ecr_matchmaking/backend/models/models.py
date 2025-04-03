from pydantic import BaseModel, Field, constr
from typing import Optional, Literal, List


# Pydantic model for the request body
class ReenterMatchmakingRequest(BaseModel):
    player_id: str
    pool_name: Literal['pvp_casual', 'pvp_duels', 'pve', 'pve_instant']
    game_version: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}$')
    game_contour: Literal['prod', 'dev']

    desired_match_group: Optional[Literal['PoolAlpha', 'PoolBeta', 'PoolGamma', 'Vein', 'Inferno', 'Abyss']] = None  # Optional field
    faction: Optional[Literal['LoyalSpaceMarines', 'ChaosSpaceMarines']] = None  # Optional field
    party_members: Optional[List[str]] = None

# Pydantic model for the request body
class LeaveMatchmakingRequest(BaseModel):
    player_id: str
