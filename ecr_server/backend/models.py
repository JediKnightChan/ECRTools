from pydantic import BaseModel, Field, constr
from typing import Optional, Literal, List


# Pydantic model for the request body
class StartServerRequest(BaseModel):
    game_version: str = Field(pattern=r'^\d{1,3}\.\d{1,3}\.\d{1,3}$')
    game_contour: Literal['prod', 'dev']
    game_map: str
    game_mode: str
    game_mission: str
    resource_units: int
    match_unique_id: str
    faction_setup: str
    max_team_size: int

# Pydantic model for the request body
class DownloadUpdateRequest(BaseModel):
    new_image: str
    images_to_remove: List[str]
