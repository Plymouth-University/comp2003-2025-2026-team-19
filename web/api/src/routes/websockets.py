import asyncio
import json
import logging
from typing import Annotated, Literal, Union
from uuid import UUID

import redis.asyncio as redis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from geoalchemy2.shape import to_shape
from pydantic import BaseModel, BeforeValidator, Field, ValidationError

from core.database import AsyncSession, get_db_session
from core.helpers import filter_uuids
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


SafeUUIDList = Annotated[list[UUID], BeforeValidator(filter_uuids)]


class SubscribeAction(BaseModel):
    action: Literal["subscribe"]
    entity_ids: SafeUUIDList | Literal["all"] | None = None


WSAction = Union[SubscribeAction]


class WSRequest(BaseModel):
    data: WSAction = Field(..., discriminator="action")


@router.websocket("/entities/ws")
async def entities_websocket(
    websocket: WebSocket, db: AsyncSession = Depends(get_db_session)
):
    await ws_manager.connect(websocket)
    try:
        while True:
            try:
                raw_data: dict = await websocket.receive_json()
                request = WSRequest(data=raw_data)  # type: ignore
                data = request.data
            except json.JSONDecodeError:
                await websocket.close(code=1007, reason="Invalid JSON")
                ws_manager.disconnect(websocket)
                break
            except ValidationError as e:
                # Catch missing fields or invalid action names
                errors = e.errors()
                if errors[0]["type"] == "union_tag_invalid":
                    await websocket.close(code=1008, reason="Invalid action")
                elif errors[0]["type"] == "union_tag_not_found":
                    await websocket.close(code=1007, reason="Missing action")
                else:
                    await websocket.close(code=1008, reason=str(errors))
                ws_manager.disconnect(websocket)
                break
            if data.action == "subscribe":
                if data.entity_ids is not None:
                    entity_ids = (
                        [e for e in data.entity_ids if type(e) == UUID]
                        if type(data.entity_ids) == list
                        else data.entity_ids
                    )
                    entity_info = await crud.get_entities_info(db, entity_ids)

                    await ws_manager.subscribe(websocket, list(entity_info.keys()))
                else:
                    entity_info = {}

                await websocket.send_json(
                    {
                        "status": "subscribed",
                        "entities": entity_info,
                    }
                )
            else:
                await websocket.close(code=1008, reason="Invalid action")
                ws_manager.disconnect(websocket)
                break
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


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
                                await ws_manager.broadcast(str(entity_id), data)
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
