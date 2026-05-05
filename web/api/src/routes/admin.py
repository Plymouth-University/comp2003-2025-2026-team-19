import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import func, select, delete
from sqlalchemy.orm import aliased
from ..schema.route import RouteCreatePayload, TrajectoryPayload

from core.database import AsyncSession, get_db_session
from core.models import Route, Point, Location, EntityOnRoute, RouteAttribute
from core.settings import settings

router = APIRouter(prefix="/admin", tags=["admin"])
security = HTTPBasic()


# --- Auth Dependency ---
def verify_admin(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = settings.ADMIN_USER.encode("utf8")
    correct_password = settings.ADMIN_PASSWORD.encode("utf8")

    if not (
        secrets.compare_digest(credentials.username.encode("utf8"), correct_username)
        and secrets.compare_digest(
            credentials.password.encode("utf8"), correct_password
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    return credentials.username


@router.get("/locations")
async def get_locations(
    username: str = Depends(verify_admin), db: AsyncSession = Depends(get_db_session)
):
    """Fetch locations to populate frontend dropdowns"""
    stmt = select(Location.id, Location.name).order_by(Location.name)
    result = await db.execute(stmt)
    return [{"id": row.id, "name": row.name} for row in result.all()]


@router.get("/routes")
async def get_routes(
    username: str = Depends(verify_admin), db: AsyncSession = Depends(get_db_session)
):
    """List routes, active entities, and the route colour"""
    StartLoc = aliased(Location)
    EndLoc = aliased(Location)
    ColorAttr = aliased(
        RouteAttribute
    )  # Alias the attribute table to join specifically for colour

    stmt = (
        select(
            Route.id,
            Route.uuid,
            StartLoc.name.label("start_name"),
            EndLoc.name.label("end_name"),
            ColorAttr.value.label("color"),  # Extract the color
            func.count(EntityOnRoute.id).label("active_entities"),
            func.count(Point.id).label("point_count"),
        )
        .join(StartLoc, Route.start_location_id == StartLoc.id)
        .join(EndLoc, Route.end_location_id == EndLoc.id)
        .outerjoin(
            ColorAttr, (ColorAttr.parent_id == Route.id) & (ColorAttr.key == "color")
        )
        .outerjoin(EntityOnRoute, Route.id == EntityOnRoute.route_id)
        .outerjoin(Point, Route.id == Point.route_id)
        .group_by(Route.id, StartLoc.name, EndLoc.name, ColorAttr.value)
        .order_by(Route.id)
    )

    result = await db.execute(stmt)
    return [
        {
            "id": row.id,
            "uuid": str(row.uuid),
            "start": row.start_name,
            "end": row.end_name,
            "color": row.color or "#5aa7ff",  # Fallback if no attribute exists
            "active_entities": row.active_entities,
            "point_count": row.point_count,
        }
        for row in result.all()
    ]


@router.post("/routes")
async def create_route(
    payload: RouteCreatePayload,
    username: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new route with a colour attribute"""
    if payload.start_location_id == payload.end_location_id:
        raise HTTPException(
            status_code=400, detail="Start and End locations must be different."
        )

    new_route = Route(
        start_location_id=payload.start_location_id,
        end_location_id=payload.end_location_id,
    )

    # Save the color via the attributes relationship
    new_route.attributes = [
        RouteAttribute(key="color", value=payload.color, datatype="string")  # type: ignore
    ]

    db.add(new_route)
    await db.commit()
    return {
        "status": "success",
        "message": f"Route created successfully with ID {new_route.id}",
    }


@router.delete("/routes/{route_id}")
async def delete_route(
    route_id: int,
    username: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Delete a route. DB CASCADE automatically handles EntityOnRoute and Points."""
    route = await db.get(Route, route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found.")

    await db.delete(route)
    await db.commit()
    return {"status": "success", "message": f"Route {route_id} deleted."}


@router.post("/trajectory")
async def import_trajectory(
    payload: TrajectoryPayload,
    username: str = Depends(verify_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Attach geometry points to an existing route"""
    for coord in payload.coordinates:
        if len(coord) != 2:
            raise HTTPException(
                status_code=422, detail="Coordinates must be [longitude, latitude]."
            )

    route = await db.get(Route, payload.route_id)
    if not route:
        raise HTTPException(status_code=404, detail="Route not found.")

    points_to_insert = [
        Point(
            route_id=payload.route_id,
            sequence=seq,
            geom=func.ST_SetSRID(func.ST_MakePoint(lng, lat), 4326),
        )
        for seq, (lng, lat) in enumerate(payload.coordinates)
    ]

    try:

        await db.execute(
            delete(Point).where(Point.route_id == payload.route_id)
        )  # Clear old points
        db.add_all(points_to_insert)
        await db.commit()
        return {
            "status": "success",
            "message": f"Inserted {len(points_to_insert)} points.",
        }
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
