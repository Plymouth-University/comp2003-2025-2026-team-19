import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Attribute, Entity


async def read_entity_by_id(db: AsyncSession, entity_id: uuid.UUID) -> Entity | None:
    """Read an entity by its ID."""
    result = await db.execute(
        select(Entity)
        .where(Entity.id == entity_id)
        .join(Entity.attributes)
        .options(selectinload(Entity.attributes))
    )
    entity = result.scalars().first()

    if not entity:
        return None

    return entity


async def read_all_entities(db: AsyncSession) -> list[Entity]:
    """Read all entities."""
    result = await db.execute(select(Entity))
    return result.scalars().all()  # type: ignore


async def read_all_active_entities(db: AsyncSession) -> list[Entity]:
    """Read all active entities."""
    result = await db.execute(select(Entity).where(Entity.active == True))
    return result.scalars().all()  # type: ignore
