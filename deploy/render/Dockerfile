FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY backend/ ./backend/
COPY ontology/ ./ontology/

# Dependencies come pinned from uv.lock — `uv pip install .` re-resolves from
# pyproject ranges on every build, so a rebuild could silently bump
# duckdb/fastapi past the CI-tested versions. --frozen also fails the build if
# the lockfile drifts from pyproject.toml.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt && \
    uv pip install --system --no-cache --no-deps . && \
    rm /tmp/requirements.txt

RUN useradd -m -u 1000 user && \
    mkdir -p /app/data && \
    chown -R user:user /app

# The content DB is NOT in the git repo (it is ~350 MB, gitignored). Unlike the
# Hugging Face Space (which committed the DB into the Space repo via LFS), a host
# that builds from GitHub has no DB to COPY. So we pull it from the public HF
# *dataset* repo at BUILD time — baking it into the image means fast, reliable
# cold starts (no ~350 MB download on every free-tier wake-up). To ship a new DB:
# re-upload it to the dataset and trigger a rebuild (see deploy/render/README.md).
# Override DB_URL at build time to pin a revision or point at a fork.
ARG DB_URL="https://huggingface.co/datasets/motidav/coffee-atlas-db/resolve/main/coffee_atlas.duckdb"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -fL --retry 5 --retry-delay 3 "$DB_URL" -o /app/data/coffee_atlas.duckdb && \
    chown user:user /app/data/coffee_atlas.duckdb && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Fail the build early if the download produced something that is not a DuckDB
# file (e.g. an HTML error page from a bad URL) — a silent bad DB would only
# surface as a crash loop at runtime.
RUN python -c "import duckdb; n=duckdb.connect('/app/data/coffee_atlas.duckdb', read_only=True).execute('SELECT count(*) FROM prod_products').fetchone()[0]; print(f'DB OK: {n} products'); assert n > 0"

USER user

ENV DUCKDB_PATH=/app/data/coffee_atlas.duckdb \
    PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    COOKIE_SECURE=true \
    ENABLE_EMBEDDINGS=true

# Render (and most PaaS hosts) inject the listen port via $PORT. Fall back to
# 8000 for a plain `docker run`. bootstrap runs create_tables against the shipped
# DB (idempotent; verifies PK/FK constraints survive) before the server starts.
EXPOSE 8000
CMD ["sh", "-c", "python -m backend.db.bootstrap && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
