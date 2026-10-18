# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

RUN apt-get update \
    && apt-get install --no-install-recommends --yes libcairo2 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.lock.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --disable-pip-version-check --requirement requirements.lock.txt

COPY pyproject.toml ./
COPY src ./src
RUN pip install --disable-pip-version-check --no-deps --no-build-isolation .

COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
