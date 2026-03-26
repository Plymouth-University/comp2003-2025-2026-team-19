from cProfile import label
from os import name
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import aliased, selectinload

from core.database import AsyncSession
from core.models import Entity, EntityOnRoute, GPSTelemetry, Location, Route

from .exceptions import EntityNotFoundError
from .schema.entity import ReadEntity


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
    db: AsyncSession, entity_uuids: list[str]
) -> dict[str, dict]:
    StartLoc = aliased(Location)
    EndLoc = aliased(Location)

    stmt = (
        select(
            GPSTelemetry,
            Entity,
            Route.uuid.label("route_uuid"),
            StartLoc.name.label("origin"),
            EndLoc.name.label("destination"),
            func.ST_X(GPSTelemetry.geom).label("lng"),
            func.ST_Y(GPSTelemetry.geom).label("lat"),
        )
        .distinct(GPSTelemetry.entity_id)
        .join(Entity, Entity.id == GPSTelemetry.entity_id)
        .outerjoin(EntityOnRoute, EntityOnRoute.entity_id == Entity.id)
        .outerjoin(Route, Route.id == EntityOnRoute.route_id)
        .outerjoin(StartLoc, StartLoc.id == Route.start_location_id)
        .outerjoin(EndLoc, EndLoc.id == Route.end_location_id)
        .where(Entity.uuid.in_(entity_uuids))
        .order_by(GPSTelemetry.entity_id, desc(GPSTelemetry.timestamp))
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
            "last_location": {
                "lat": row.lat,
                "lng": row.lng,
                "ts": row.GPSTelemetry.timestamp.isoformat(),
            },
        }
        for row in rows
    }
