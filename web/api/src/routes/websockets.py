import json
from contextlib import suppress

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websockets"])


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


@router.websocket("/entities/ws")
async def entities_websocket(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            message: dict = await websocket.receive_json()
            if message.get("action") == "subscribe":
                await ws_manager.subscribe(
                    websocket,
                    message.get("entity_ids", []),
                )
                await websocket.send_json(
                    {
                        "status": "subscribed",
                        "entity_ids": message.get("entity_ids", []),
                    }
                )
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


async def redis_listener():
    r = redis.from_url("redis://redis:6379/0")
    pubsub = r.pubsub()
    await pubsub.subscribe("location_updates")
    try:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                data: dict = json.loads(message["data"])
                entity_id = data.get("entity_id")
                if entity_id is not None:
                    await ws_manager.broadcast(entity_id, data)
    finally:
        await pubsub.unsubscribe("location_updates")
        await r.close()
