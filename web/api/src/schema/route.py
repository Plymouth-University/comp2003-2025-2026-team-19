from .base import BaseSchema
from pydantic import Field


class TrajectoryPayload(BaseSchema):
    route_id: int
    coordinates: list[list[float]] = Field(..., description="Array of [lng, lat]")


class RouteCreatePayload(BaseSchema):
    start_location_id: int
    end_location_id: int
    color: str = Field(
        default="#5aa7ff", description="Hex color code for the route line"
    )


class RouteEntitiesPayload(BaseSchema):
    entity_ids: list[int] = Field(
        ..., description="List of Entity IDs to assign to the route"
    )
