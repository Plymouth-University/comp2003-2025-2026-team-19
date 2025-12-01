import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Entity


async def read_entity_by_id(db: AsyncSession, entity_id: uuid.UUID) -> Entity | None:
    """Read an entity by its ID."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    return result.scalars().first()


async def read_all_entities(db: AsyncSession) -> list[Entity]:
    """Read all entities."""
    result = await db.execute(select(Entity))
    return result.scalars().all()  # type: ignore
