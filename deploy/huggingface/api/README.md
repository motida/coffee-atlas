---
title: Coffee Atlas API
emoji: ☕
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Coffee Atlas — API

FastAPI backend for [Coffee Atlas](https://github.com/motida/coffee-atlas).
Serves the knowledge-graph-backed coffee ontology over HTTP, reading from a
pre-built DuckDB file bundled into the image.

The companion frontend Space lives at `coffee-atlas-web`.

## Endpoints

- `GET /health` — liveness probe
- `GET /api/v1/varieties` — list/filter coffee varieties
- `GET /api/v1/origins/geo` — GeoJSON of producing countries/regions
- `GET /api/v1/flavor/wheel` — full SCA flavor wheel hierarchy
- `GET /api/v1/graph/traverse` — BFS traversal over the property graph
- See `/docs` for the full OpenAPI schema.

## How it's deployed

The DuckDB file (`data/coffee_atlas.duckdb`) is pre-built locally with the
ingest pipeline and committed via git-lfs. Container start runs an idempotent
bootstrap, then launches Uvicorn on port 7860.
