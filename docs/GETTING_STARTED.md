# Getting Started

## Prerequisites

- [Python 3.14+](https://www.python.org/) (3.14.6 pinned via `.python-version`)
- [uv](https://docs.astral.sh/uv/) — Python package manager
- [Node.js 20+](https://nodejs.org/)
- [pyenv](https://github.com/pyenv/pyenv) (recommended for Python version management)

## 1. Clone and install

```bash
git clone <repo-url>
cd coffee-atlas

# Backend
uv venv
uv sync --extra dev

# Frontend
cd frontend && npm install
```

## 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your API keys:
#   GEMINI_API_KEY — for embeddings and semantic search
```

## 3. Initialize and seed the database

The fastest path is the one-shot bootstrap — it installs deps, validates the
ontology, creates the tables, exports triples, and runs the ingest pipeline:

```bash
just bootstrap
```

To only create the (empty) tables without loading any data:

```bash
uv run python -m backend.db.schema   # or: just db-create
```

Bootstrap runs only the local stages — it excludes the network-heavy ones
(`shops`, `descriptions`, `products`, `roaster_discovery`) and the stages that
are a no-op without that data (`roaster_locations`, `specialty`); see
[Data Sources & Pipeline](DATA.md) for running those individually.

## 4. Run

```bash
# Terminal 1 — Backend (port 8000)
uv run uvicorn backend.main:app --reload

# Terminal 2 — Frontend (port 3000)
cd frontend && npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

Interactive API docs are at [http://localhost:8000/docs](http://localhost:8000/docs).
