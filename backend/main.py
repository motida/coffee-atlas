"""Coffee Atlas API — FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.connection import get_connection
from backend.db.schema import create_tables
from backend.routers import varieties, origins, roasting, flavor, shops, graph, search


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = get_connection()
    create_tables(conn)
    conn.close()
    yield


app = FastAPI(
    title="Coffee Atlas API",
    description="Geospatial coffee knowledge graph platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(varieties.router)
app.include_router(origins.router)
app.include_router(roasting.router)
app.include_router(flavor.router)
app.include_router(shops.router)
app.include_router(graph.router)
app.include_router(search.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
