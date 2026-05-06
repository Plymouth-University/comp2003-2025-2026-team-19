"""
GPS Telemetry Replay Service

Reads GPSTelemetry rows from PostGIS within a configured time window and
re-publishes them to the Redis `location_updates` channel, preserving the
original timing gaps between points (scaled by REPLAY_SPEED).

Loops continuously once the end of the time range is reached.

Environment variables:
    DATABASE_URL   - SQLAlchemy-compatible PostgreSQL URL (required)
    REDIS_HOST     - Redis hostname (default: redis)
    REPLAY_START   - ISO-8601 start of the replay window (required)
    REPLAY_END     - ISO-8601 end   of the replay window (required)
    REPLAY_SPEED   - Speed multiplier, e.g. 2.0 = twice real-time (default: 1.0)
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

import redis.asyncio as redis
from shapely import wkb
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("replay")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        logger.error(f"Required environment variable '{name}' is not set.")
        sys.exit(1)
    return value


DATABASE_URL: str = _require_env("DATABASE_URL")
REDIS_HOST: str = os.environ.get("REDIS_HOST", "redis")
REPLAY_SPEED: float = float(os.environ.get("REPLAY_SPEED", "1.0"))

_start_raw = _require_env("REPLAY_START")
_end_raw = _require_env("REPLAY_END")

try:
    REPLAY_START = datetime.fromisoformat(_start_raw).astimezone(timezone.utc)
    REPLAY_END = datetime.fromisoformat(_end_raw).astimezone(timezone.utc)
except ValueError as exc:
    logger.error(f"Invalid REPLAY_START or REPLAY_END: {exc}")
    sys.exit(1)

if REPLAY_START >= REPLAY_END:
    logger.error("REPLAY_START must be before REPLAY_END.")
    sys.exit(1)

if REPLAY_SPEED <= 0:
    logger.error("REPLAY_SPEED must be a positive number.")
    sys.exit(1)

# SQLAlchemy requires the async driver prefix
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

CHANNEL = "location_updates"

QUERY = text("""
    SELECT
        g.entity_id,
        g.timestamp,
        ST_AsBinary(g.geom) AS geom_wkb
    FROM "GPSTelemetry" g
    WHERE g.timestamp >= :start
      AND g.timestamp <= :end
    ORDER BY g.timestamp, g.entity_id
""")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def decode_point(wkb_bytes: bytes) -> tuple[float, float]:
    """Return (latitude, longitude) from a PostGIS WKB point."""
    point = wkb.loads(wkb_bytes)
    # PostGIS POINT(lon lat) — x=longitude, y=latitude
    return point.y, point.x


def build_payload(entity_id: int, timestamp: datetime, lat: float, lon: float) -> str:
    return json.dumps(
        {
            "entity_id": str(entity_id),
            "timestamp": timestamp.isoformat(),
            "latitude": lat,
            "longitude": lon,
        }
    )


# ---------------------------------------------------------------------------
# Core replay loop
# ---------------------------------------------------------------------------


async def fetch_telemetry(engine) -> list[dict]:
    """Load all telemetry rows for the configured window, ordered by timestamp."""
    async with engine.connect() as conn:
        result = await conn.execute(QUERY, {"start": REPLAY_START, "end": REPLAY_END})
        rows = result.fetchall()

    points = []
    for row in rows:
        lat, lon = decode_point(bytes(row.geom_wkb))
        points.append(
            {
                "entity_id": row.entity_id,
                "timestamp": row.timestamp.astimezone(timezone.utc),
                "latitude": lat,
                "longitude": lon,
            }
        )

    return points


async def replay_once(points: list[dict], r: redis.Redis) -> None:
    """Publish all points in order, sleeping to preserve original timing gaps."""
    logger.info(f"Starting replay of {len(points)} points at {REPLAY_SPEED}x speed.")

    for i, point in enumerate(points):
        payload = build_payload(
            point["entity_id"],
            point["timestamp"],
            point["latitude"],
            point["longitude"],
        )
        await r.publish(CHANNEL, payload)
        logger.debug(
            f"Published entity={point['entity_id']} "
            f"t={point['timestamp'].isoformat()} "
            f"lat={point['latitude']:.5f} lon={point['longitude']:.5f}"
        )

        # Sleep until the next point, scaled by REPLAY_SPEED
        if i < len(points) - 1:
            gap = (points[i + 1]["timestamp"] - point["timestamp"]).total_seconds()
            sleep_time = gap / REPLAY_SPEED
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    logger.info("Replay loop complete — restarting from the beginning.")


async def run() -> None:
    logger.info(
        f"Replay service starting | "
        f"window=[{REPLAY_START.isoformat()} → {REPLAY_END.isoformat()}] | "
        f"speed={REPLAY_SPEED}x | "
        f"redis={REDIS_HOST} | "
        f"channel={CHANNEL}"
    )

    engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)

    # Fetch once — the dataset is fixed for a given time window
    logger.info("Fetching telemetry from database...")
    points = await fetch_telemetry(engine)

    if not points:
        logger.error(
            f"No GPSTelemetry rows found between "
            f"{REPLAY_START.isoformat()} and {REPLAY_END.isoformat()}. Exiting."
        )
        await engine.dispose()
        sys.exit(1)

    logger.info(f"Loaded {len(points)} telemetry points.")

    # Redis connection with exponential backoff
    retry_delay = 1
    max_delay = 60

    while True:
        try:
            r = redis.from_url(
                f"redis://{REDIS_HOST}:6379/0",
                decode_responses=True,
            )
            logger.info(f"Connected to Redis at {REDIS_HOST}.")
            retry_delay = 1

            while True:
                await replay_once(points, r)

        except (ConnectionError, TimeoutError, OSError) as exc:
            logger.warning(
                f"Redis connection failed: {exc}. Retrying in {retry_delay}s..."
            )
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, max_delay)

        except asyncio.CancelledError:
            logger.info("Replay service cancelled.")
            break

        except Exception as exc:
            logger.error(f"Unexpected error: {exc}", exc_info=True)
            await asyncio.sleep(5)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
