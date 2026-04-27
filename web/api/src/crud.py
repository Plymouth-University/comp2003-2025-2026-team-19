import logging
from typing import Literal
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import aliased, selectinload

from core.database import AsyncSession
from core.models import Entity, EntityOnRoute, GPSTelemetry, Location, Point, Route

from .exceptions import EntityNotFoundError
from .schema.entity import ReadEntity

logger = logging.getLogger("uvicorn")


async def get_entity_by_uuid(db: AsyncSession, entity_id: UUID) -> ReadEntity:
    stmt = (
        select(Entity)
        .options(
            selectinload(Entity.attributes),
            selectinload(Entity.current_route).selectinload(EntityOnRoute.route),
        )
        .where(Entity.uuid == entity_id)
    )

    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()

    if entity is not None:
        return ReadEntity.model_validate(entity)
    raise EntityNotFoundError("Entity not found")


async def list_entities(db: AsyncSession) -> list[ReadEntity]:
    stmt = select(Entity).options(
        selectinload(Entity.attributes),
        selectinload(Entity.current_route).selectinload(EntityOnRoute.route),
    )
    result = await db.execute(stmt)
    entities = result.scalars().all()
    return [ReadEntity.model_validate(entity) for entity in entities]


async def get_entities_info(
    db: AsyncSession, entity_uuids: list[UUID] | Literal["all"]
) -> dict[str, dict]:
    StartLoc = aliased(Location)
    EndLoc = aliased(Location)

    if entity_uuids == "all":
        entity_uuids = list(
            map(str, (await db.execute(select(Entity.uuid))).scalars().all())
        )  # type: ignore

        logger.info(f"Subscribing to all entities: {entity_uuids}")

    stmt = (
        select(
            Entity,
            GPSTelemetry,
            Route.uuid.label("route_uuid"),
            StartLoc.name.label("origin"),
            EndLoc.name.label("destination"),
            func.ST_X(GPSTelemetry.geom).label("lng"),
            func.ST_Y(GPSTelemetry.geom).label("lat"),
        )
        .distinct(Entity.id)
        .outerjoin(GPSTelemetry, Entity.id == GPSTelemetry.entity_id)
        .outerjoin(EntityOnRoute, EntityOnRoute.entity_id == Entity.id)
        .outerjoin(Route, Route.id == EntityOnRoute.route_id)
        .outerjoin(StartLoc, StartLoc.id == Route.start_location_id)
        .outerjoin(EndLoc, EndLoc.id == Route.end_location_id)
        .where(Entity.uuid.in_(entity_uuids))
        .order_by(Entity.id, desc(GPSTelemetry.timestamp))
    )

    result = await db.execute(stmt)
    rows = result.all()

    return {
        str(row.Entity.uuid): {
            "name": row.Entity.name,
            "route": {
                "uuid": str(row.route_uuid) if row.route_uuid else None,
                "origin": row.origin,
                "destination": row.destination,
            },
            # Handle None values for entities without telemetry
            "last_location": (
                {
                    "lat": row.lat,
                    "lng": row.lng,
                    "ts": (
                        row.GPSTelemetry.timestamp.isoformat()
                        if row.GPSTelemetry
                        else None
                    ),
                }
                if row.GPSTelemetry
                else None
            ),
        }
        for row in rows
    }


async def get_route_trajectory_geojson(
    db: AsyncSession, route_uuid: UUID
) -> dict | None:
    """
    Fetches ordered points for a route and formats them as a GeoJSON FeatureCollection.
    """
    stmt = (
        select(func.ST_X(Point.geom).label("lng"), func.ST_Y(Point.geom).label("lat"))
        .join(Route, Route.id == Point.route_id)
        .where(Route.uuid == route_uuid)
        .order_by(Point.sequence)
    )

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return None

    # Format exactly as MapLibre expects
    coordinates = [[row.lng, row.lat] for row in rows]

    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coordinates},
                "properties": {
                    "route_uuid": str(route_uuid),
                    "point_count": len(coordinates),
                },
            }
        ],
    }
