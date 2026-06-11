# Coffee Atlas — command runner
# Run `just` to see all available recipes

set dotenv-load

default:
    @just --list

# --- Development ---

# Start the FastAPI backend with hot reload
dev-backend:
    uv run uvicorn backend.main:app --reload --port ${BACKEND_PORT:-8000}

# Start the Next.js frontend dev server
dev-frontend:
    cd frontend && npm run dev

# Start both backend and frontend (requires two terminals — use with `just dev-backend &`)
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    just dev-backend &
    just dev-frontend &
    wait

# --- Database ---

# Create DuckDB tables
db-create:
    uv run python -m backend.db.schema

# --- Ontology ---

# Validate OWL ontology with HermiT reasoner
ontology-validate:
    cd ontology && uv run python scripts/validate_ontology.py

# Export inferred triples to DuckDB
ontology-export:
    cd ontology && uv run python scripts/export_triples.py

# --- Ingest Pipeline ---

# Run a specific ingest stage (lexicon, varieties, cqi, geocode, shops, distribution, roasting, embeddings, graph)
ingest stage:
    uv run python -m backend.ingest.pipeline --stage {{ stage }}

# Run the full ingest pipeline in order (shops excluded: network-heavy, see docs/DATA.md)
ingest-all:
    just ingest lexicon
    just ingest varieties
    just ingest cqi
    just ingest geocode
    just ingest distribution
    just ingest roasting
    just ingest embeddings
    just ingest graph

# --- Testing ---

# Run backend tests
test-backend *args:
    uv run pytest {{ args }}

# Run frontend tests
test-frontend *args:
    cd frontend && npm test -- {{ args }}

# Run all tests
test:
    just test-backend
    just test-frontend

# --- Linting & Formatting ---

# Lint and format backend code
lint-backend:
    uv run ruff check backend/ tests/
    uv run ruff format --check backend/ tests/

# Fix backend lint issues
lint-backend-fix:
    uv run ruff check --fix backend/ tests/
    uv run ruff format backend/ tests/

# Lint frontend code
lint-frontend:
    cd frontend && npm run lint

# Type-check backend code with ty
typecheck:
    uv run ty check

# Lint everything
lint:
    just lint-backend
    just lint-frontend
    just typecheck

# --- Dependencies ---

# Install backend dependencies
install-backend:
    uv sync --all-extras

# Install frontend dependencies
install-frontend:
    cd frontend && npm install

# Install everything
install:
    just install-backend
    just install-frontend

# --- Docker ---

# Build and start all services
docker-up *args:
    docker compose up --build {{ args }}

# Stop all services
docker-down:
    docker compose down

# --- Bootstrap ---

# Full bootstrap: install deps, validate ontology, create DB, export ontology, run ingest
bootstrap:
    just install
    just ontology-validate
    just db-create
    just ontology-export
    just ingest-all
