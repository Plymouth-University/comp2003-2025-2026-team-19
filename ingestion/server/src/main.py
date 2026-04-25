import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI
from redis.asyncio import Redis

from core.logging import EndpointFilter
from core.settings import settings

from .routes.entity import router as entity_router
from .routes.health import router as health_router
from .services.mqtt import mqtt_listener

load_dotenv()

sentry_sdk.init(
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

app = FastAPI(title="ingestion", root_path="/api/v1")
redis_client = Redis.from_url(f"redis://{settings.REDIS_HOST}:6379")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(mqtt_listener(redis_client))
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    await redis_client.close()


app = FastAPI(title="ingestion", lifespan=lifespan, root_path="/api/v1")
app.include_router(entity_router)
app.include_router(health_router)
