from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def get_health():
    return {"message": "Service is healthy"}
