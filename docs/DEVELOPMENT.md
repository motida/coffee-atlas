# Development

## Project structure

```
coffee-atlas/
├── ontology/              # OWL 2 domain ontology (7 modules)
│   ├── modules/           # varieties, origins, processing, roasting,
│   │                      # flavor, distribution, shops
│   └── scripts/           # validate + export scripts
├── backend/               # FastAPI application
│   ├── main.py            # App entry point
│   ├── config.py          # Settings (pydantic-settings)
│   ├── db/                # DuckDB connection, schema, seeds
│   ├── models/            # Pydantic models (one per domain)
│   ├── routers/           # API routes (one per domain)
│   ├── services/          # Embeddings, geocoding, enrichment
│   └── ingest/            # Data loaders (CQI, WCR, shops)
├── frontend/              # Next.js 14 application
│   ├── app/               # App Router pages
│   ├── components/        # Map, graph, flavor wheel components
│   └── lib/               # API client + TypeScript types
├── tests/                 # pytest (backend) + vitest (frontend)
├── data/                  # Raw, processed, and Parquet data files
├── pyproject.toml         # Python deps (uv/hatchling)
├── Dockerfile             # Multi-stage build
└── docker-compose.yml     # Backend + frontend services
```

## Testing

```bash
# Backend
uv run pytest tests/backend/ -v

# Frontend
cd frontend && npm test
```

## Docker

```bash
docker compose up --build
```

Backend at `localhost:8000`, frontend at `localhost:3000`.
