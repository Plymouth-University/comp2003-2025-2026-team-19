from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/status")
async def get_status():
    return {"status": "ok"}
