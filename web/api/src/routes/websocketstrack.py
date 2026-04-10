import asyncio
import json
import logging

import redis.asyncio as redis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from geoalchemy2.shape import to_shape

from core.database import AsyncSession, get_db_session
from core.settings import settings

from .. import crud

router = APIRouter(tags=["websockets"])

logger = logging.getLogger("uvicorn")


class TrackerWebSocketManager:
    def __init__(self):
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.connections.discard(websocket)
    
    async def broadcast(self, data: dict):
        for connection in self.connections:
            await connection.send_json(data)
            
tracker_ws_manager = TrackerWebSocketManager()

@router.websocket("/tracker/ws")
async def trackers_websocket(websocket: WebSocket):
    await tracker_ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        tracker_ws_manager.disconnect(websocket)

async def redis_listener():
    retry_delay = 1  # Start with 1 second delay
    max_delay = 60  # Cap the delay at 1 minute

    while True:
        try:
            logger.info(f"Connecting to Redis at {settings.REDIS_HOST}...")
            # Added decode_responses=True so message["data"] is a string, not bytes
            r = redis.from_url(
                f"redis://{settings.REDIS_HOST}:6379/0",
                decode_responses=True,
            )

            async with r.pubsub() as pubsub:
                await pubsub.subscribe("location_updates")
                logger.info("Subscribed to 'location_updates' channel")

                # Reset retry delay on successful connection
                retry_delay = 1

                async for message in pubsub.listen():
                    if message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            entity_id = data.get("entity_id")
                            if entity_id:

                                await tracker_ws_manager.broadcast({
                                    "type": "update",
                                    "data": {
                                        "entity_id": entity_id,
                                        "timestamp": data.get("timestamp")
                                    }
                                })
                        except json.JSONDecodeError:
                            logger.error(f"Malformed JSON received: {message['data']}")
                        except Exception as e:
                            logger.error(f"Error broadcasting message: {e}")

        except (ConnectionError, TimeoutError, OSError) as e:
            logger.warning(
                f"Redis connection failed: {e}. Retrying in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            # Exponential backoff
            retry_delay = min(retry_delay * 2, max_delay)

        except asyncio.CancelledError:
            logger.info("Redis listener task cancelled.")
            break  # Exit the while loop gracefully

        except Exception as e:
            logger.error(f"Unexpected error in Redis listener: {e}")
            await asyncio.sleep(5)  # Avoid tight-looping on logic errors
