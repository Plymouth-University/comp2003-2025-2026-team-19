FROM python:3.14-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

RUN pip install poetry

WORKDIR /build
COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true \
    && poetry install --only main --no-interaction --no-ansi --no-root

FROM python:3.14-alpine
WORKDIR /app

COPY --from=builder /build/.venv /app/.venv

COPY ./mqtt/auth /app
COPY ./core /app/core

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]