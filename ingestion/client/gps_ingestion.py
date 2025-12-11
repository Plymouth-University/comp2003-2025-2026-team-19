from fastapi import FastAPI, HTTPException
from models import GPSPayload
from config import AUTH_KEY
from database import get_connection
import logging

app = FastAPI(title="Ferry GPS Ingestion API")


@app.post("/ingest")
def ingest_gps(payload: GPSPayload):
    """
    Accepts JSON with entity_id, lat, lon, time, auth_key.
    """

    # 1. Validate authentication
    if payload.auth_key != AUTH_KEY:
        logging.warning("Invalid auth key")
        raise HTTPException(status_code=401, detail="Invalid authentication key")

    # 2. Validate latitude / longitude ranges
    if not (-90 <= payload.lat <= 90):
        raise HTTPException(status_code=422, detail="Invalid latitude")

    if not (-180 <= payload.lon <= 180):
        raise HTTPException(status_code=422, detail="Invalid longitude")

    # 3. Insert into database
    try:
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO gps_data (entity_id, latitude, longitude, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (payload.entity_id, payload.lat, payload.lon, payload.time)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f"Database error: {e}")
        raise HTTPException(status_code=500, detail="Database insert failed")

    # 4. Response
    return {
        "status": "success",
        "entity_id": payload.entity_id,
        "lat": payload.lat,
        "lon": payload.lon,
        "timestamp": payload.time
    }
