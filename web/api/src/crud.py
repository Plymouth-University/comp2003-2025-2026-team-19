from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from core.database import AsyncSession
from core.models import Entity, EntityOnRoute

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
