import asyncio
from math import e

import anyio
import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from core import models
from tests.utils import create_test_entity
from web.api.src.main import app


def test_websocket_subscription(db_session, client: TestClient):
    entity = create_test_entity(db_session)

    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json({"action": "subscribe", "entity_ids": [str(entity.uuid)]})

        msg = websocket.receive_json()
        assert msg["status"] == "subscribed"
        assert str(entity.uuid) in msg["entities"]
        assert msg["entities"][str(entity.uuid)]["name"] == entity.name


def test_websocket_subscription_invalid_entity(db_session, client: TestClient):
    create_test_entity(db_session)
    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json(
            {
                "action": "subscribe",
                "entity_ids": ["00000000-0000-0000-0000-000000000000"],
            }
        )

        msg = websocket.receive_json()
        assert msg["status"] == "subscribed"
        assert "00000000-0000-0000-0000-000000000000" not in msg["entities"]


def test_websocket_subscription_all(db_session, client: TestClient):
    entity_ids = [
        create_test_entity(db_session, f"Test entity {n}").uuid for n in range(2)
    ]
    with client.websocket_connect("/entities/ws") as websocket:
        websocket.send_json({"action": "subscribe", "entity_ids": "all"})

        msg = websocket.receive_json()

        assert len(msg["entities"]) == len(entity_ids)
        assert set(map(str, entity_ids)).intersection(
            set(map(str, msg["entities"]))
        ) == set(map(str, entity_ids))


@pytest.mark.anyio
async def test_websocket_subscription_no_entity_ids(db_override):
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with aconnect_ws("/entities/ws", client) as websocket:
            await websocket.send_json({"action": "subscribe"})
            msg = await websocket.receive_json(timeout=5)
            assert msg["status"] == "subscribed"
            assert msg["entities"] == {}


@pytest.mark.anyio
async def test_websocket_subscription_mixed_uuids(db_session, db_override):
    entity = create_test_entity(db_session)
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with aconnect_ws("/entities/ws", client) as websocket:
            await websocket.send_json(
                {
                    "action": "subscribe",
                    "entity_ids": [str(entity.uuid), "not-a-uuid", 12345],
                }
            )
            msg = await websocket.receive_json()
            # Valid uuid works, others are ignored
            assert str(entity.uuid) in msg["entities"]
            assert len(msg["entities"]) == 1


@pytest.mark.anyio
async def test_websocket_subscription_invalid_action(db_override):
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            async with aconnect_ws("/entities/ws", client) as websocket:
                await websocket.send_json({"action": "invalid"})
                await websocket.receive_json(timeout=5)
        except* WebSocketDisconnect as eg:
            assert eg.exceptions[0].code == 1008  # type: ignore
        else:
            pytest.fail("Expected WebSocketDisconnect")


@pytest.mark.anyio
async def test_websocket_subscription_malformed_message(db_override):
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            async with aconnect_ws("/entities/ws", client) as websocket:
                await websocket.send_text("This is not a valid JSON message")
                await websocket.receive_json(timeout=5)
        except* WebSocketDisconnect as eg:
            assert eg.exceptions[0].code in [1003, 1007]  # type: ignore
            assert "Invalid JSON" in eg.exceptions[0].reason  # type: ignore
        else:
            pytest.fail("Expected WebSocketDisconnect")


@pytest.mark.anyio
async def test_websocket_subscription_missing_action(db_override):
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            async with aconnect_ws("/entities/ws", client) as websocket:
                await websocket.send_json({"entity_ids": ["some-entity-id"]})
                await websocket.receive_json(timeout=5)
        except* WebSocketDisconnect as eg:
            assert eg.exceptions[0].code == 1007  # type: ignore
        else:
            pytest.fail("Expected WebSocketDisconnect")


@pytest.mark.anyio
async def test_websocket_subscription_invalid_entity_format(db_override):
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            async with aconnect_ws("/entities/ws", client) as websocket:
                await websocket.send_json({"action": "subscribe", "entity_ids": 12345})
                await websocket.receive_json(timeout=5)
        except* WebSocketDisconnect as eg:
            assert eg.exceptions[0].code == 1008  # type: ignore
        else:
            pytest.fail("Expected WebSocketDisconnect")
