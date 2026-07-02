FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY ontology/ ./ontology/

# Dependencies come pinned from uv.lock — `uv pip install .` re-resolves from
# pyproject ranges on every build, so a Space rebuild could silently bump
# duckdb/fastapi past the CI-tested versions. --frozen also fails the build
# if the lockfile drifts from pyproject.toml.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    uv pip install --system --no-cache --no-deps . && \
    rm /tmp/requirements.txt

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
