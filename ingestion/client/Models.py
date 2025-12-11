from pydantic import BaseModel, Field
from typing import Optional


class GPSPayload(BaseModel):
    entity_id: int = Field(..., example=1)
    lat: float = Field(..., example=50.36312)
    lon: float = Field(..., example=-4.15122)
    time: str = Field(..., example="2025-11-27T12:34:56Z")
    auth_key: str = Field(..., example="supersecretkey123")
