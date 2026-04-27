from uuid import UUID

from .. import crud
from fastapi import APIRouter, Depends, HTTPException

from core.database import AsyncSession, get_db_session


router = APIRouter(prefix="/routes", tags=["routes"])


@router.get("/{route_uuid}/trajectory")
async def get_route_trajectory(
    route_uuid: UUID, db: AsyncSession = Depends(get_db_session)
):
    geojson = await crud.get_route_trajectory_geojson(db, route_uuid)

    if not geojson:
        raise HTTPException(status_code=404, detail="Route trajectory not found")

    return geojson
