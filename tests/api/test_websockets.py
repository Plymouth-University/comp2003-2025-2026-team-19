import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient
from httpx_ws import WebSocketDisconnect, aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport

from tests.utils import create_test_entity
from web.api.src.main import app


@asynccontextmanager
async def ws_client():
    """
    Async HTTP client with WebSocket support.
    """
    transport = ASGIWebSocketTransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def assert_disconnects_with(
    payload, code: int, reason_contains: str | None = None
):
    """Assert that sending *payload* causes the server to close with *code*."""
    with pytest.raises(ExceptionGroup) as exc_info:
        async with ws_client() as client:
            async with aconnect_ws("/entities/ws", client) as ws:
                if isinstance(payload, str):
                    await ws.send_text(payload)
                else:
                    await ws.send_json(payload)
                await ws.receive_json(timeout=5)

    # Unwrap nested ExceptionGroups (httpx_ws raises from an internal task group)
    exc = exc_info.value.exceptions[0]
    while isinstance(exc, ExceptionGroup):
        exc = exc.exceptions[0]

    assert isinstance(exc, WebSocketDisconnect)
    assert exc.code == code, f"Expected close code {code}, got {exc.code}"
    if reason_contains is not None:
        assert (
            reason_contains in exc.reason
        ), f"Expected '{reason_contains}' in reason, got: {exc.reason!r}"


@pytest.mark.anyio
async def test_subscribe_single_entity(db_session, db_override):
    entity = create_test_entity(db_session)

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json(
                {"action": "subscribe", "entity_ids": [str(entity.uuid)]}
            )
            msg = await ws.receive_json(timeout=5)

    assert msg["status"] == "subscribed"
    assert str(entity.uuid) in msg["entities"]
    assert msg["entities"][str(entity.uuid)]["name"] == entity.name


@pytest.mark.anyio
async def test_subscribe_all_entities(db_session, db_override):
    entity_ids = {
        str(create_test_entity(db_session, f"Test entity {n}").uuid) for n in range(3)
    }

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json({"action": "subscribe", "entity_ids": "all"})
            msg = await ws.receive_json(timeout=5)

    # Exact match — no extra or missing entities
    assert set(msg["entities"].keys()) == entity_ids


@pytest.mark.anyio
async def test_subscribe_no_entity_ids_defaults_to_empty(db_override):
    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json({"action": "subscribe"})
            msg = await ws.receive_json(timeout=5)

    assert msg["status"] == "subscribed"
    assert msg["entities"] == {}


@pytest.mark.anyio
async def test_subscribe_idempotent(db_session, db_override):
    """Subscribing to the same entity twice should not duplicate it."""
    entity = create_test_entity(db_session)
    entity_id = str(entity.uuid)

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            for _ in range(2):
                await ws.send_json({"action": "subscribe", "entity_ids": [entity_id]})
                msg = await ws.receive_json(timeout=5)

    assert list(msg["entities"].keys()).count(entity_id) == 1  # type: ignore


@pytest.mark.anyio
async def test_subscribe_mixed_valid_and_invalid_uuids(db_session, db_override):
    """Valid UUIDs are subscribed; malformed values are silently ignored."""
    entity = create_test_entity(db_session)

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json(
                {
                    "action": "subscribe",
                    "entity_ids": [str(entity.uuid), "not-a-uuid", 12345],
                }
            )
            msg = await ws.receive_json(timeout=5)

    assert str(entity.uuid) in msg["entities"]
    assert len(msg["entities"]) == 1


@pytest.mark.anyio
async def test_subscribe_nonexistent_entity_excluded(db_override):
    """A well-formed UUID that doesn't match any entity is omitted from the response."""
    missing_id = str(uuid.uuid4())

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json({"action": "subscribe", "entity_ids": [missing_id]})
            msg = await ws.receive_json(timeout=5)

    assert missing_id not in msg["entities"]


@pytest.mark.anyio
async def test_multiple_sequential_subscriptions(db_session, db_override):
    """A single connection can subscribe to multiple entities in separate messages."""
    entity_a = create_test_entity(db_session, "Entity A")
    entity_b = create_test_entity(db_session, "Entity B")

    async with ws_client() as client:
        async with aconnect_ws("/entities/ws", client) as ws:
            await ws.send_json(
                {"action": "subscribe", "entity_ids": [str(entity_a.uuid)]}
            )
            msg_a = await ws.receive_json(timeout=5)

            await ws.send_json(
                {"action": "subscribe", "entity_ids": [str(entity_b.uuid)]}
            )
            msg_b = await ws.receive_json(timeout=5)

    assert str(entity_a.uuid) in msg_a["entities"]
    assert str(entity_b.uuid) in msg_b["entities"]


@pytest.mark.anyio
async def test_invalid_action_closes_with_1008(db_override):
    await assert_disconnects_with(
        {"action": "invalid"},
        code=1008,
    )


@pytest.mark.anyio
async def test_malformed_json_closes_with_1003_or_1007(db_override):
    await assert_disconnects_with(
        "This is not valid JSON",  # sent as raw text
        code=1007,
        reason_contains="Invalid JSON",
    )


@pytest.mark.anyio
async def test_missing_action_field_closes_with_1007(db_override):
    await assert_disconnects_with(
        {"entity_ids": ["some-entity-id"]},
        code=1007,
    )


@pytest.mark.anyio
async def test_entity_ids_wrong_type_closes_with_1008(db_override):
    """entity_ids must be a list or 'all', not a bare integer."""
    await assert_disconnects_with(
        {"action": "subscribe", "entity_ids": 12345},
        code=1008,
    )
