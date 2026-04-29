import json
import uuid as uuid_lib

import redis.asyncio as redis
import shapely
from fastapi import Depends, Response
from fastapi.routing import APIRouter
from geoalchemy2.shape import to_shape

from core.database import AsyncSession, get_db_session
from core.models import APIKey
from core.settings import settings

from .. import crud
from ..schema.gpstelemetry import GPSTelemetryCreate
from ..security import get_api_key

router = APIRouter(tags=["entity"], prefix="/entities")

redis_client = redis.from_url(f"redis://{settings.REDIS_HOST}:6379")


@router.post("/{entity_id}/telemetry")
async def add_telemetry(
    entity_id: uuid_lib.UUID,
    telemetry_data: GPSTelemetryCreate,
    api_key: APIKey = Depends(get_api_key),
    db: AsyncSession = Depends(get_db_session),
):
    if api_key.allowed_entity_id is not None:
        pass

    new_point = await crud.ingest_telemetry(db, entity_id, telemetry_data)

    if new_point:
        shape: shapely.Point = to_shape(new_point.geom)  # type: ignore
        lat, lon = shape.y, shape.x
        payload = {
            "entity_id": str(entity_id),
            "timestamp": new_point.timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
        }
        await redis_client.publish("location_updates", json.dumps(payload))
    return Response(status_code=202)
