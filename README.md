# Coffee Atlas

A full-stack geospatial platform that maps the global coffee ecosystem — from bean genetics and farm origins to roasting science, distribution networks, and specialty coffee shops.

Built as a knowledge-graph-backed application where every entity (bean variety, farm, roaster, shop, flavor profile) is a node in a connected graph, enabling discovery through relationships rather than flat search.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.13) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind CSS) |
| Database | DuckDB with Parquet storage (Hive-partitioned) |
| Graph | DuckPGQ extension for graph traversal |
| Vector Search | DuckDB VSS with HNSW indexing (OpenAI `text-embedding-3-small`) |
| Maps | Mapbox GL JS (react-map-gl) |
| Ontology | OWL 2 via Owlready2, validated with HermiT reasoner |

## Prerequisites

- [Python 3.11+](https://www.python.org/) (3.13.7 pinned via `.python-version`)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js 20+](https://nodejs.org/)
- [pyenv](https://github.com/pyenv/pyenv) (recommended for Python version management)

## Getting Started

### 1. Clone and install

```bash
git clone <repo-url>
cd coffee-atlas

# Backend
uv venv
uv sync --extra dev

# Frontend
cd frontend && npm install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   OPENAI_API_KEY    — for embeddings and semantic search
#   MAPBOX_ACCESS_TOKEN — for map rendering
```

### 3. Initialize the database

```bash
uv run python -m backend.db.schema
```

### 4. Run

```bash
# Terminal 1 — Backend (port 8000)
uv run uvicorn backend.main:app --reload

# Terminal 2 — Frontend (port 3000)
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

## Project Structure

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

## API

The backend exposes a REST API at `/api/v1/`:

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/varieties` | List/filter coffee varieties |
| `GET /api/v1/origins` | List origin countries/regions |
| `GET /api/v1/origins/geo` | GeoJSON feature collection |
| `GET /api/v1/roasting/profiles` | List roast profiles |
| `GET /api/v1/flavor/wheel` | Flavor wheel hierarchy |
| `GET /api/v1/shops` | List/filter shops |
| `GET /api/v1/shops/geo` | Shop locations as GeoJSON |
| `GET /api/v1/shops/nearby` | Nearby shops (lat/lng + radius) |
| `GET /api/v1/graph/traverse` | Graph traversal from a node |
| `GET /api/v1/graph/path` | Shortest path between nodes |
| `GET /api/v1/search/semantic` | Semantic similarity search |
| `GET /api/v1/search/text` | Full-text search |

Interactive docs available at [http://localhost:8000/docs](http://localhost:8000/docs) when the backend is running.

## Data Sources

| Source | Coverage |
|--------|----------|
| [WCR Varieties Catalog](https://varieties.worldcoffeeresearch.org) | 100+ varieties with agronomic data |
| [WCR Sensory Lexicon 2.0](https://worldcoffeeresearch.org/resources/sensory-lexicon) | 110 flavor attributes |
| [CQI Database](https://www.kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi) | ~1,300 cupping reviews |
| [ICO Market Reports](https://ico.org) | Trade and production statistics |
| [FAOSTAT](https://www.fao.org/faostat) | Country-level trade flows |
| [Overture Maps](https://overturemaps.org) | Coffee shop POI data |

## Data Pipeline

Run ingest stages individually or all at once:

```bash
uv run python -m backend.ingest.pipeline --stage lexicon     # Flavor taxonomy
uv run python -m backend.ingest.pipeline --stage varieties    # WCR varieties
uv run python -m backend.ingest.pipeline --stage cqi          # CQI cupping data
uv run python -m backend.ingest.pipeline --stage geocode      # Geocode origins
uv run python -m backend.ingest.pipeline --stage embeddings   # Vector embeddings
uv run python -m backend.ingest.pipeline --stage graph        # Build graph edges
uv run python -m backend.ingest.pipeline --all                # Run all stages
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

## License

TBD
