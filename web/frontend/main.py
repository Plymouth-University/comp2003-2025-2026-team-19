import fastapi
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="static/")
static = StaticFiles(directory="static/")
app = fastapi.FastAPI(
    title="ferrytracker Web Backend",
    description="Backend API for ferrytracker web application, \
serving html pages and static assets.",
    version="0.1.0",
    docs_url=None,
)

app.mount("/static", static, name="static")


@app.get("/")
async def get_root(
     request: fastapi.Request):
    """Returns a welcome message or the index page.
    Returns:
        dict: A welcome message.
    """
    return templates.TemplateResponse(
        "entity_list.html", {"request": request}
    )
    
    # TODO: Return index.html template
    # return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status/{entity_id}")
async def get_status(
    request: fastapi.Request, entity_id: str
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
        "status.html", {"request": request, "entity_id": entity_id}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
