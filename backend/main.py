"""Coffee Atlas API — FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.connection import get_connection
from backend.db.pg import close_pool, init_pool
from backend.db.pg_schema import create_pg_tables
from backend.db.schema import create_tables
from backend.routers import (
    account,
    auth,
    varieties,
    origins,
    processing,
    roasting,
    flavor,
    distribution,
    shops,
    products,
    graph,
    search,
    recommend,
)
from backend.services.auth import validate_jwt_secret


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Content store (DuckDB) — always created.
    conn = get_connection()
    create_tables(conn)
    conn.close()

    # User-data store (Postgres) — opt-in via DATABASE_URL. When unset, the app
    # still boots (content-only) and auth/account routes return a clean 503
    # ("accounts unavailable") on use — see db/pg.get_pg.
    pg_enabled = bool(settings.DATABASE_URL)
    if pg_enabled:
        # Refuse to boot with a forgeable (empty/weak) JWT secret.
        validate_jwt_secret()
        pool = init_pool()
        with pool.connection() as pg:
            create_pg_tables(pg)
    try:
        yield
    finally:
        if pg_enabled:
            close_pool()


app = FastAPI(
    title="Coffee Atlas API",
    description="Geospatial coffee knowledge graph platform",
    version="0.1.0",
    lifespan=lifespan,
)

# With credentialed requests, origins must be listed explicitly (never "*").
# The primary path is same-origin (browser → frontend, which proxies /api/v1/*
# server-side), so these matter only if a browser hits the backend directly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://motidav-coffee-atlas-web.hf.space",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(account.router)
app.include_router(varieties.router)
app.include_router(origins.router)
app.include_router(processing.router)
app.include_router(roasting.router)
app.include_router(flavor.router)
app.include_router(distribution.router)
app.include_router(shops.router)
app.include_router(products.router)
app.include_router(graph.router)
app.include_router(search.router)
app.include_router(recommend.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
