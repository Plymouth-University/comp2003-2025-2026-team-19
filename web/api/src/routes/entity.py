import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import read_all_active_entities, read_entity_by_id
from ..database import get_db_session

router = APIRouter()


@router.get("/entities/{entity_id}")
async def get_entity(
    entity_id: str, db: AsyncSession = Depends(get_db_session)
) -> dict:
    """Get an entity by its ID."""
    entity = await read_entity_by_id(db, uuid.UUID(entity_id))

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return {
        "id": str(entity.id),
        "name": entity.name,
        "description": entity.description,
        "type": entity.type,
        "image_url": entity.image_url,
        "attributes": [
            {
                "key": attr.key,
                "value": attr.value,
                "value_type": attr.value_type,
            }
            for attr in entity.attributes
        ],
    }


@router.get("/entities")
async def get_entities(db: AsyncSession = Depends(get_db_session)):
    """List all active entities.

    An entity is considered active if its 'active' attribute is set to True.
    Active entities may have an associated route attached to them, indicated by the presence of a non-null 'route_id' attribute.
    """
    result = await read_all_active_entities(db)
    result = [
        {"id": str(entity.id), "name": entity.name, "type": entity.type}
        for entity in result
    ]
    return result
