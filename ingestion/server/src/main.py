from fastapi import FastAPI

from .routes.entity import router as entity_router

app = FastAPI(title="ingestion", root_path="/api/v1")
app.include_router(entity_router)
