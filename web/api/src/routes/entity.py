import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from core import models
from core.database import AsyncSession, get_db_session

from .. import crud

router = APIRouter(tags=["entity"], prefix="/entities")


def validate_entity_uuid(entity_id: str) -> UUID:
    try:
        obj_uuid = uuid.UUID(entity_id)
    except ValueError:
        # Treat malformed UUID as 404
        raise HTTPException(status_code=404, detail="Entity not found")
    return obj_uuid


@router.get("")
async def list_entities(db: AsyncSession = Depends(get_db_session)):
    return await crud.list_entities(db)


@router.get("/{entity_id}")
async def get_entity(
    entity_id: UUID = Depends(validate_entity_uuid),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        return await crud.get_entity_by_uuid(db, entity_id)
    except crud.EntityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
