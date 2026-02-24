import datetime
import uuid

import geoalchemy2
from fastapi import HTTPException
from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError

from core.database import AsyncSession
from core.models import Entity, GPSTelemetry

from .logging import logger
from .schema.gpstelemetry import GPSTelemetryCreate


async def ingest_telemetry(
    db: AsyncSession, entity_id: uuid.UUID, data: GPSTelemetryCreate
):
    if data.latitude is None or data.longitude is None:
        # Skip telemetry with missing coordinates
        logger.debug(
            f"Skipping telemetry for entity {entity_id} due to missing coordinates"
        )
        return

    # construct geometry from lat/lon

    entity_id_subquery = (
        select(Entity.id).where(Entity.uuid == entity_id).scalar_subquery()
    )

    new_point = GPSTelemetry(
        entity_id=entity_id_subquery,
        geom=func.ST_SetSRID(func.ST_MakePoint(data.longitude, data.latitude), 4326),
    )

    db.add(new_point)
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        if "fk_GPSTelemetry_entity_id" in str(e.orig):  # type: ignore
            raise HTTPException(
                status_code=404, detail=f"Entity with ID {entity_id} not found"
            )
        if "not-null constraint" in str(e.orig):  # type: ignore
            raise HTTPException(
                status_code=404, detail=f"Entity with ID {entity_id} not found"
            )
        print(type(e))
        raise e  # Re-raise other integrity errors
    await db.refresh(new_point)
    return new_point
