FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY ontology/ ./ontology/

RUN uv pip install --system --no-cache .

RUN useradd -m -u 1000 user && \
    mkdir -p /app/data && \
    chown -R user:user /app

USER user

COPY --chown=user data/coffee_atlas.duckdb /app/data/coffee_atlas.duckdb

ENV DUCKDB_PATH=/app/data/coffee_atlas.duckdb \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user

EXPOSE 7860

CMD ["sh", "-c", "python -m backend.db.bootstrap && exec uvicorn backend.main:app --host 0.0.0.0 --port 7860"]
