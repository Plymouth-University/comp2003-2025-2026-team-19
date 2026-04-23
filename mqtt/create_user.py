import secrets
import uuid

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.models import Entity, Sensor, SensorACL
from core.settings import settings


async def create_sensor(
    db: AsyncSession,
    entity_uuid: uuid.UUID,
    label: str | None = None,
) -> tuple[Sensor, str]:
    """
    Creates a Sensor with MQTT credentials scoped to its entity's topics.
    Returns the Sensor and the plaintext password (shown once, not stored).
    """
    password = secrets.token_urlsafe(32)
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=10)).decode()

    query = select(Entity).where(Entity.uuid == entity_uuid)

    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if entity is None:
        raise ValueError(f"No Entity found with UUID: {entity_uuid}")

    sensor_uuid = f"sensor-{entity_uuid}"

    sensor = Sensor(
        entity_id=entity.id,
        label=label or sensor_uuid,
        mqtt_username=sensor_uuid,
        mqtt_password_hash=password_hash,
    )
    db.add(sensor)
    try:
        await db.flush()  # populate sensor.id before inserting ACLs
    except Exception as e:
        await db.rollback()
        raise ValueError(f"Failed to create Sensor: {e}")

    acls = [
        # Can only publish to its own entity's telemetry topic
        SensorACL(sensor_id=sensor.id, topic=f"entity/{entity_uuid}/telemetry", rw=2),
        # Can only subscribe to its own entity's command topic
        SensorACL(sensor_id=sensor.id, topic=f"entity/{entity_uuid}/commands", rw=1),
    ]
    db.add_all(acls)
    await db.commit()

    return sensor, password


if __name__ == "__main__":
    import asyncio

    uuid_ = input("Enter Entity UUID: ")

    async def main():
        async with AsyncSessionLocal() as db:  # type: ignore
            details = await create_sensor(
                db,
                entity_uuid=uuid.UUID(uuid_) if uuid_ else uuid.uuid4(),
            )

            print(f"Created Sensor with MQTT username: {details[0].mqtt_username}")
            print(f"Generated password: {details[1]}")

    asyncio.run(main())
