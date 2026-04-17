import logging
import os

import sentry_sdk
from dotenv import load_dotenv
from fastapi import FastAPI

from core.logging import EndpointFilter
from core.settings import settings

from .routes.entity import router as entity_router
from .routes.health import router as health_router

load_dotenv()

sentry_sdk.init(
    dsn="https://e803558910d4259c6092d510d3d268df@o4510404857757696.ingest.de.sentry.io/4511198016110672",
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
app.include_router(entity_router)
app.include_router(health_router)
