import asyncio
import os

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.models import Sensor, SensorACL


async def seed_mqtt_listener() -> None:
    username = os.environ["MQTT_LISTENER_USERNAME"]
    password = os.environ["MQTT_LISTENER_PASSWORD"]

    async with AsyncSessionLocal() as db:  # type: ignore
        existing = await db.execute(
            select(Sensor).where(Sensor.mqtt_username == username)
        )
        if existing.scalar_one_or_none():
            print(f"Listener account '{username}' already exists — skipping.")
            return

        password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt(rounds=10)
        ).decode()

        sensor = Sensor(
            entity_id=None,
            label="API Listener Service Account",
            mqtt_username=username,
            mqtt_password_hash=password_hash,
            is_active=True,
        )
        db.add(sensor)
        await db.flush()

        db.add(
            SensorACL(
                sensor_id=sensor.id,
                topic="entity/+/telemetry",
                rw=1,  # subscribe only
            )
        )

        await db.commit()
        print(f"Listener account '{username}' created successfully.")


if __name__ == "__main__":
    asyncio.run(seed_mqtt_listener())
