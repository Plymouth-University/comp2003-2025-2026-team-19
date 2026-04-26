import json

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse
from pydantic import RootModel, ValidationError
from pydantic_core import PydanticCustomError
from pydantic_extra_types import Color

from ..services.icon_service import colour_svg

router = APIRouter(prefix="/icon", tags=["icons"])


class ColorMap(RootModel):
    root: dict[str, Color]


@router.get("")
async def get_icon(
    request: Request, type_: str = Query(alias="type"), refresh: bool = False
):
    try:
        colour_map = ColorMap.model_validate(
            {
                k: v
                for k, v in request.query_params.items()
                if k not in ["type", "refresh"]
            }
        )
    except ValidationError as e:
        return {"type": "error", "errors": e.errors()}

    try:
        return Response(
            colour_svg(type_, colour_map.root, refresh=refresh),
            media_type="image/svg+xml",
        )
    except FileNotFoundError:
        return Response(
            status_code=404,
            content=json.dumps({"type": "error", "msg": "Icon type not found"}),
            media_type="application/json",
        )
