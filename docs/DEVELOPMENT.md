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
│   ├── services/          # Embeddings, geocoding, recommendations, auth
│   └── ingest/            # Data loaders (CQI, WCR, Overture shops,
│                          # roaster product scrapers) + pipeline
├── frontend/              # Next.js 14 application
│   ├── app/               # App Router pages
│   ├── components/        # Map, graph, flavor wheel components
│   └── lib/               # API client + TypeScript types
├── deploy/                # render/ (live API service) + huggingface/ (retired)
├── tests/                 # pytest (backend) + vitest (frontend)
├── data/                  # Raw seed data (processed/ + parquet/ are generated)
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
- **API** → **Render** free tier (Docker web service, `coffee-atlas-api`).
  Backend *code* auto-deploys on push to `main` (Render watches the repo);
  *data/DB* changes are shipped separately — the ~350 MB content DB lives in
  the public Hugging Face dataset `motidav/coffee-atlas-db` and is baked into
  the image at build time, so shipping a new DB means re-uploading it there
  and rebuilding with a cleared build cache.

The frontend proxies `/api/v1/*` to the Render URL via `BACKEND_URL` (baked at
build time). See `deploy/render/README.md` for the full procedure.

> The API originally ran on a free Hugging Face Docker Space, retired in
> 2026-07 when HF began requiring a PRO subscription for Docker Spaces. The
> `deploy/huggingface/` scaffold is kept for historical reference only — do not
> run its scripts (see the deprecation note in `deploy/huggingface/DEPLOY.md`).
