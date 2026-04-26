FROM python:3.14-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev postgresql-dev

WORKDIR /build
RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --with dev --no-interaction --no-ansi --no-root

FROM python:3.14-alpine
WORKDIR /app

RUN apk add --no-cache libpq

COPY --from=builder /build/.venv /app/.venv
COPY ./alembic.ini /app/alembic.ini
COPY ./database/migrations /app/database/migrations
COPY ./core /app/core

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

CMD ["sh", "-c", "python -m alembic upgrade head && python database/migrations/seed.py"]