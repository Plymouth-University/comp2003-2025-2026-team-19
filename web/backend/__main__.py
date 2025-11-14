import fastapi
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates/")
app = fastapi.FastAPI(
    title="ferrytracker Web Backend",
    description="Backend API for ferrytracker web application, \
serving html pages and static assets.",
    version="0.1.0",
)


@app.get("/")
async def get_root():
    return {"message": "Welcome to the ferrytracker Web Backend!"}

    # TODO: Return index.html template
    # return templates.TemplateResponse("index.html", {"request": request})


@app.get("/status/{entity_id}")
async def get_status(entity_id: str):
    return {"entity_id": entity_id, "status": "active"}

    # TODO: Return status.html template with entity status
    # return templates.TemplateResponse("status.html", {"request": request, "entity_id": entity_id})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
