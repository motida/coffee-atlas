# Development

## Project structure

```
coffee-atlas/
├── ontology/              # OWL 2 domain ontology (8 modules)
│   ├── modules/           # varieties, origins, processing, roasting, flavor,
│   │                      # distribution, shops, products
│   └── scripts/           # validate + export scripts
├── backend/               # FastAPI application
│   ├── main.py            # App entry point
│   ├── config.py          # Settings (pydantic-settings)
│   ├── db/                # DuckDB connection, schema, seeds
│   ├── models/            # Pydantic models (one per domain)
│   ├── routers/           # API routes (one per domain)
│   ├── services/          # Embeddings, geocoding, enrichment
│   └── ingest/            # Data loaders (CQI, WCR, Overture shops,
│                          # roaster product scrapers) + pipeline
├── frontend/              # Next.js 14 application
│   ├── app/               # App Router pages
│   ├── components/        # Map, graph, flavor wheel components
│   └── lib/               # API client + TypeScript types
├── deploy/                # Hugging Face Space scaffold (api + web)
├── tests/                 # pytest (backend) + vitest (frontend)
├── data/                  # Raw, processed, and Parquet data files
├── justfile               # Task runner (just bootstrap, just dev, ...)
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

## Deployment

The hosted demo runs as two independently deployed pieces:

- **Frontend** → **Vercel**, auto-deployed from `main` (project root directory
  `frontend/`).
- **API** → a free **Hugging Face Space** (`motidav-coffee-atlas-api`).
  Backend *code* auto-deploys on push to `main` via CI; *data/DB* changes are
  shipped separately with `deploy/huggingface/deploy.sh`.

Both frontends proxy `/api/v1/*` to the HF Space. See
`deploy/huggingface/DEPLOY.md` for the full procedure.
