from fastapi import FastAPI

from .routes.entity import router as entity_router
from .routes.health import router as health_router

app = FastAPI(title="ingestion", root_path="/api/v1")
app.include_router(entity_router)
app.include_router(health_router)
