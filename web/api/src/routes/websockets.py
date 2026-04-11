import asyncio
import json
import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from geoalchemy2.shape import to_shape

from core.database import AsyncSession, get_db_session, AsyncSessionLocal
from core.models import GPSTelemetry
from core.settings import settings

from .. import crud

router = APIRouter(tags=["websockets"])

logger = logging.getLogger("uvicorn")


class TrackingWebSocketManager:
    def __init__(self):
        self.subscriptions: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()

    async def subscribe(self, websocket: WebSocket, entity_ids: list[str]):
        for eid in entity_ids:
            if eid not in self.subscriptions:
                self.subscriptions[eid] = set()
            self.subscriptions[eid].add(websocket)

    def disconnect(self, websocket: WebSocket):
        for eid in self.subscriptions:
            self.subscriptions[eid].discard(websocket)

    async def broadcast(self, entity_id: str, data: dict):
        if entity_id in self.subscriptions:
            for connection in self.subscriptions[entity_id]:
                payload = {"type": "update", "data": data}
                await connection.send_json(payload)


ws_manager = TrackingWebSocketManager()

async def get_latest_telemetry_timestamp(entity_id: str) -> str | None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(GPSTelemetry.timestamp)
            .where(GPSTelemetry.entity_id == int(entity_id))
            .order_by(GPSTelemetry.timestamp.desc())
            .limit(1)
        )

        row = result.scalar_one_or_none()
        return row.isoformat() if row else None

@router.websocket("api/v1/entities/ws")
async def entities_websocket(
    websocket: WebSocket, db: AsyncSession = Depends(get_db_session)
):
    await ws_manager.connect(websocket)
    try:
        while True:
            message: dict = await websocket.receive_json()
            if message.get("action") == "subscribe":
                entity_info = await crud.get_entities_info(
                    db, message.get("entity_ids", [])
                )

                await ws_manager.subscribe(websocket, list(entity_info.keys()))

                await websocket.send_json(
                    {
                        "status": "subscribed",
                        "entities": entity_info,
                    }
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


async def redis_listener():
    retry_delay = 1
    max_delay = 60

    while True:
        try:
            logger.info(f"Connecting to Redis at {settings.REDIS_HOST}...")
            r = redis.from_url(
                f"redis://{settings.REDIS_HOST}:6379/0",
                decode_responses=True,
            )

            async with r.pubsub() as pubsub:
                await pubsub.subscribe("location_updates")
                logger.info("Subscribed to 'location_updates' channel")
                retry_delay = 1

                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            entity_id = data.get("entity_id")
                            if entity_id:
                                timestamp = await get_latest_telemetry_timestamp(
                                    str(entity_id)
                                )
                                if timestamp:
                                    data["timestamp"] = timestamp
                                
                                await ws_manager.broadcast(str(entity_id), data)
                        except json.JSONDecodeError:
                            logger.error(f"Malformed JSON received: {message['data']}")
                        except Exception as e:
                            logger.error(f"Error broadcasting message: {e}")
        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"Redis connection failed: {e}. Retrying in {retry_delays}s...")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)
        
        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled.")
            break
        
        except Exception as e:
            logger.error(f"Unexpected error in Redis Listener: {e}")
            await asyncio.sleep(5)