import logging
import os

import fastapi
import sentry_sdk
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.logging import EndpointFilter
from core.settings import settings

load_dotenv()

templates = Jinja2Templates(directory="static/")
static = StaticFiles(directory="static/")

sentry_sdk.init(
    dsn=settings.SENTRY_DSN_FRONTEND_SERVER,
    environment=settings.ENVIRONMENT,
    send_default_pii=True,
    enable_logs=False,
    traces_sample_rate=1.0,
    profile_session_sample_rate=1.0,
    profile_lifecycle="trace",
)

logging.getLogger("uvicorn.access").addFilter(
    EndpointFilter(exclude_endpoints=["/health"])
)

app = fastapi.FastAPI(
    title="ferrytracker Web Frontend",
    description="Frontend for ferrytracker web application, serving html pages and static assets.",
    version="0.1.0",
    docs_url=None,
)

app.mount("/static", static, name="static")


@app.get("/status")
@app.get("/")
async def get_status(
    request: fastapi.Request, entity_id: str | None = None
) -> fastapi.responses.HTMLResponse:
    """Returns the status page for a given entity_id.
    Args:
        request (fastapi.Request): The incoming request object.
        entity_id (str): The entity ID to fetch the status for.

    Returns:
        fastapi.responses.HTMLResponse: The rendered status HTML page.
    """
    # TODO: Check if entity_id exists and fetch its status

    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "entity_id": entity_id,
            "env": settings.ENVIRONMENT,
            "sentry_script_url": settings.SENTRY_SCRIPT_URL,
        },
    )


@app.get("/health")
async def get_health():
    """Return a health check message.
    Returns:
        dict: A message indicating the service is healthy.
    """
    return {"message": "Service is healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
