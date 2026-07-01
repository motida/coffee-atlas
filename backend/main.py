"""Coffee Atlas API — FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.config import settings
from backend.db.connection import get_connection
from backend.db.pg import close_pool, init_pool, pool_ready
from backend.db.pg_schema import create_pg_tables
from backend.db.schema import create_tables
from backend.routers import (
    account,
    auth,
    distribution,
    flavor,
    graph,
    meta,
    origins,
    processing,
    products,
    recommend,
    roasting,
    search,
    shops,
    varieties,
)
from backend.services.auth import validate_jwt_secret

logger = logging.getLogger(__name__)


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
        logger.info("User-data store enabled: /auth/* and /account/* are active.")
    else:
        # Loud, because the failure is otherwise silent: content endpoints keep
        # returning 200 while every /auth/* and /account/* route 503s. The usual
        # cause is the hosted api Space losing its DATABASE_URL/JWT_SECRET secrets
        # on a recreate — see deploy/huggingface/DEPLOY.md.
        logger.warning(
            "DATABASE_URL is not set — the Postgres user-data store is DISABLED. "
            "All /api/v1/auth/* and /api/v1/account/* routes will return 503 "
            '("User accounts are unavailable"). If this is the hosted api Space, '
            "re-add the DATABASE_URL and JWT_SECRET secrets and reboot."
        )
    try:
        yield
    finally:
        if pg_enabled:
            close_pool()


app = FastAPI(
    title="Coffee Atlas API",
    description="Geospatial coffee knowledge graph platform",
    version=__version__,
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
app.include_router(meta.router)


@app.get("/health")
def health_check() -> dict[str, str]:
    # `accounts` surfaces whether the Postgres user-data store came up, so a
    # missing DATABASE_URL is visible from a probe rather than only when a user
    # tries to log in (where it shows as a 503). "disabled" == auth/account 503.
    return {"status": "ok", "accounts": "enabled" if pool_ready() else "disabled"}
