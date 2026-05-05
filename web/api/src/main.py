import asyncio
import logging
import os
from contextlib import asynccontextmanager

import sentry_sdk
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import Base, engine, get_db_session
from core.logging import EndpointFilter
from core.settings import settings

from .routes import (
    entity_router,
    health_router,
    websocket_router,
    admin_router,
    routes_router,
    icon_router,
)
from .routes.websockets import redis_listener

load_dotenv()

sentry_sdk.init(
    dsn=settings.SENTRY_DSN_API,
    environment=settings.ENVIRONMENT,
    send_default_pii=True,
    enable_logs=False,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)

logging.getLogger("uvicorn.access").addFilter(
    EndpointFilter(exclude_endpoints=["/api/v1/health"])
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to handle startup and shutdown events."""
    task = asyncio.create_task(redis_listener())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan, root_path="/api/v1")

app.include_router(health_router)
app.include_router(websocket_router)
app.include_router(entity_router)
app.include_router(icon_router)
app.include_router(routes_router)
app.include_router(admin_router)
