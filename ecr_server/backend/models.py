from pydantic import BaseModel, Field, constr
from typing import Optional, Literal, List


# Pydantic model for the request body
class StartServerRequest(BaseModel):
    game_map: str
    game_mode: str
    game_mission: str
    resource_units: int
    match_unique_id: str
    faction_setup: str



# Pydantic model for the request body
class LeaveMatchmakingRequest(BaseModel):
    player_id: str
