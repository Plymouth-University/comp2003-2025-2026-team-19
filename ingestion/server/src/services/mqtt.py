import asyncio
import json
import logging
import ssl
import uuid

import aiomqtt
from redis.asyncio import Redis
import shapely
from geoalchemy2.shape import to_shape

from core.database import AsyncSessionLocal
from core.settings import settings

from .. import crud
from ..schema.gpstelemetry import GPSTelemetryCreate

logger = logging.getLogger(__name__)

# Matches entity/{entity_id}/telemetry
TOPIC_FILTER = "entity/+/telemetry"


def _parse_entity_id(topic: str) -> uuid.UUID | None:
    """Extract and validate the entity UUID from the topic string."""
    try:
        parts = topic.split("/")
        # entity / {entity_id} / telemetry
        if len(parts) != 3:
            return None
        return uuid.UUID(parts[1])
    except (ValueError, IndexError):
        logger.warning("Could not parse entity_id from topic: %s", topic)
        return None


def _build_telemetry(payload: dict) -> GPSTelemetryCreate | None:
    """Map the ESP32 payload keys to the GPSTelemetryCreate schema."""
    try:
        return GPSTelemetryCreate(
            lat=payload["lat"],
            lon=payload["lng"],
        )
    except (KeyError, ValueError) as e:
        logger.warning("Invalid telemetry payload: %s — %s", payload, e)
        return None


async def _handle_message(
    topic: str,
    raw: bytes,
    redis_client: Redis,
) -> None:
    entity_id = _parse_entity_id(topic)
    if entity_id is None:
        return

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Non-JSON payload on topic %s: %s", topic, raw)
        return

    telemetry = _build_telemetry(payload)
    if telemetry is None:
        return

    # Use a fresh DB session per message — mirrors the per-request
    # session lifecycle of the HTTP endpoint
    async with AsyncSessionLocal() as db:  # type: ignore
        try:
            new_point = await crud.ingest_telemetry(db, entity_id, telemetry)
        except Exception:
            logger.exception("DB error ingesting telemetry for %s", entity_id)
            return

    if new_point:
        shape: shapely.Point = to_shape(new_point.geom)  # type: ignore
        lat, lon = shape.y, shape.x
        redis_payload = {
            "entity_id": str(entity_id),
            "timestamp": new_point.timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
        }
        await redis_client.publish("location_updates", json.dumps(redis_payload))
        logger.debug("Published location update for entity %s", entity_id)


async def mqtt_listener(redis_client: Redis) -> None:
    """
    Long-running coroutine that subscribes to MQTT and processes telemetry.
    Intended to be run as a background task from the FastAPI lifespan.
    Reconnects automatically on connection loss.
    """
    tls_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    # tls_context.load_verify_locations(cafile=settings.MQTT_CA_CERT_PATH)

    # Uncomment for mTLS:
    # tls_context.load_cert_chain(
    #     certfile=settings.MQTT_CLIENT_CERT_PATH,
    #     keyfile=settings.MQTT_CLIENT_KEY_PATH,
    # )

    while True:
        try:
            logger.info(
                "Connecting to MQTT broker %s:%s",
                settings.MQTT_BROKER,
                settings.MQTT_PORT,
            )
            async with aiomqtt.Client(
                hostname=settings.MQTT_BROKER,
                port=settings.MQTT_PORT,
                username=settings.MQTT_LISTENER_USERNAME,
                password=settings.MQTT_LISTENER_PASSWORD,
                identifier=f"ferry_mqtt_listener",
            ) as client:
                await client.subscribe(TOPIC_FILTER, qos=1)
                logger.info("Subscribed to %s", TOPIC_FILTER)

                async for message in client.messages:
                    await _handle_message(
                        topic=str(message.topic),
                        raw=message.payload,  # type: ignore
                        redis_client=redis_client,
                    )

        except aiomqtt.MqttError as e:
            logger.warning("MQTT connection lost: %s — reconnecting in 5s", e)
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("MQTT listener shutting down")
            raise
        except Exception:
            logger.exception("Unexpected error in MQTT listener — reconnecting in 5s")
            await asyncio.sleep(5)
