import logging

import bcrypt
from fastapi import Depends, FastAPI, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db_session
from core.logging import EndpointFilter
from core.models import Sensor

app = FastAPI()

logging.getLogger("uvicorn.access").addFilter(
    EndpointFilter(exclude_endpoints=["/health"])
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/auth/register")
async def auth_on_register(
    request: Request, session: AsyncSession = Depends(get_db_session)
):
    body = await request.json()
    username = body.get("username")
    password = body.get("password")
    sensor = await session.scalar(
        select(Sensor).where(Sensor.mqtt_username == username, Sensor.is_active == True)
    )
    if sensor and bcrypt.checkpw(password.encode(), sensor.mqtt_password_hash.encode()):
        return {"result": "ok"}
    return {"result": {"error": "not allowed"}}


@app.post("/auth/subscribe")
async def auth_on_subscribe(
    request: Request, session: AsyncSession = Depends(get_db_session)
):
    body = await request.json()
    username = body.get("username")
    topics = body.get("topics")
    sensor = await session.scalar(
        select(Sensor)
        .options(selectinload(Sensor.acls))
        .where(Sensor.mqtt_username == username)
    )
    if not sensor:
        return {"result": {"error": "not allowed"}}
    if sensor.entity_id is None:
        return {
            "result": "ok",
            "topics": [{"topic": t["topic"], "qos": t["qos"]} for t in topics],
        }
    allowed = []
    for t in topics:
        acl = next(
            (a for a in sensor.acls if a.topic == t["topic"] and a.rw in (1, 3)),
            None,
        )
        allowed.append({"topic": t["topic"], "qos": t["qos"] if acl else 128})
    return {"result": "ok", "topics": allowed}


@app.post("/auth/publish")
async def auth_on_publish(
    request: Request, session: AsyncSession = Depends(get_db_session)
):
    body = await request.json()
    username = body.get("username")
    topic = body.get("topic")
    sensor = await session.scalar(
        select(Sensor)
        .options(selectinload(Sensor.acls))
        .where(Sensor.mqtt_username == username)
    )
    if not sensor:
        return {"result": {"error": "not allowed"}}
    if sensor.entity_id is None:
        return {"result": "ok"}
    acl = next(
        (a for a in sensor.acls if a.topic == topic and a.rw in (2, 3)),
        None,
    )
    return {"result": "ok"} if acl else {"result": {"error": "not allowed"}}
    return {"result": "ok"} if acl else {"result": {"error": "not allowed"}}
