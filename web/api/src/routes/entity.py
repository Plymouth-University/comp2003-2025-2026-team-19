import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import read_all_entities, read_entity_by_id
from ..database import get_db_session

router = APIRouter()


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db_session)):
    """Get an entity by its ID."""
    entity = await read_entity_by_id(db, uuid.UUID(entity_id))
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.get("/entities")
async def list_entities(db: AsyncSession = Depends(get_db_session)):
    """List all entities."""
    result = await read_all_entities(db)
    return result
