FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock* ./
RUN if [ -f uv.lock ]; then uv sync --locked --no-dev; else uv sync --no-dev; fi

COPY app app
COPY alembic.ini .
COPY migrations migrations
