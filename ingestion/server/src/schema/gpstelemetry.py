import datetime

from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    class Config:
        from_attributes = True


class GPSTelemetryCreate(BaseSchema):
    latitude: float = Field(..., alias="lat")
    longitude: float = Field(..., alias="lon")
    timestamp: datetime.datetime | None = None
