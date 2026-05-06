FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    sqlalchemy[asyncio]==2.0.* \
    asyncpg==0.29.* \
    redis[hiredis]==5.* \
    geoalchemy2==0.15.* \
    shapely==2.* \
    python-dotenv==1.*

COPY main.py .

CMD ["python", "main.py"]