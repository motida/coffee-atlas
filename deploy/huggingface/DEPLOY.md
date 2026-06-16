# Deploying Coffee Atlas to Hugging Face Spaces

Two free Docker Spaces, one per service:

| Space | Role | Port | Persistent? |
|-------|------|------|-------------|
| `coffee-atlas-api` | FastAPI backend | 7860 | No (DB bundled in image) |
| `coffee-atlas-web` | Next.js frontend | 7860 | No (stateless) |

DuckDB is read-only at runtime, so the lack of persistent disk on the free tier
is fine: the database file is built locally, committed via git-lfs, and shipped
inside the image.

---

## One-time setup

### 1. Build the database locally

```sh
uv run -m backend.ingest.pipeline --all
ls -lh data/coffee_atlas.duckdb     # confirm the file exists
```

### 2. Install git-lfs and the HF CLI

```sh
brew install git-lfs
git lfs install
pip install -U "huggingface_hub[cli]"   # provides the `hf` CLI
hf auth login                            # paste a write token from https://huggingface.co/settings/tokens
hf auth whoami                           # confirms the login
```

The modern CLI is `hf`; `huggingface-cli` is removed.

### 3. Create both Spaces on huggingface.co

For each Space (`coffee-atlas-api` and `coffee-atlas-web`):

1. Visit <https://huggingface.co/new-space>
2. **Owner:** your username
3. **Space name:** `coffee-atlas-api` (or `coffee-atlas-web`)
4. **License:** your choice (MIT works)
5. **SDK:** Docker → blank template
6. **Hardware:** CPU basic — free
7. **Visibility:** public (private requires Pro)

### 4. Configure Space variables and secrets

**`coffee-atlas-api`** → Settings → Variables and secrets:

- `GEMINI_API_KEY` (secret) — required at runtime for `/api/v1/search/semantic`.
  The endpoint embeds the incoming query and ranks rows by cosine similarity;
  without the key it silently falls back to plain text (LIKE) search. The
  bundled DB already holds the entity embeddings — this key is for embedding the
  query, not the stored rows — so it's also needed if you ever re-run the
  embeddings stage inside the Space.

**`coffee-atlas-web`** → Settings → Variables and secrets:

- `BACKEND_URL` (variable) =
  `https://<your-username>-coffee-atlas-api.hf.space`

  Variables — not secrets — are exposed at build time, which is what Next.js
  needs. Each rebuild bakes this URL into `next.config.js`.

---

## Deploy

From the repo root:

```sh
HF_USER=your-username ./deploy/huggingface/deploy.sh
```

The script clones each Space, syncs the relevant source tree, copies the
HF-specific `Dockerfile` + `README.md` + `.gitattributes`, copies the
DuckDB file with LFS, commits, and pushes. HF rebuilds automatically on push;
follow the build logs at:

- `https://huggingface.co/spaces/<your-username>/coffee-atlas-api`
- `https://huggingface.co/spaces/<your-username>/coffee-atlas-web`

Targeted deploys:

```sh
HF_USER=... ./deploy/huggingface/deploy.sh api      # backend only
HF_USER=... ./deploy/huggingface/deploy.sh web      # frontend only
```

Staging clones live under `deploy/huggingface/.staging/` and are reused on
subsequent runs (incremental rsync + git push).

---

## Updating data only

If only the DuckDB file changed:

```sh
uv run -m backend.ingest.pipeline --all
HF_USER=... ./deploy/huggingface/deploy.sh api
```

The git-lfs delta is pushed and HF rebuilds the api Space.

---

## Gotchas

- **48-hour idle sleep.** Free Spaces sleep after 48h with no traffic. First
  request after sleep takes ~30s for a Docker Space. Acceptable for a
  portfolio app.
- **Backend URL is build-time, not runtime.** Changing the api Space's URL
  (e.g. renaming) means the web Space must be rebuilt. This is a Next.js
  rewrites limitation (see `frontend/next.config.js`), not an HF one.
- **Repo size limit: 5 GB per Space.** The DB is currently ~25 MB so there's
  plenty of headroom.
- **Files >10 MB must be LFS-tracked.** `.gitattributes` in the api Space
  handles `*.duckdb` and `*.parquet`.
- **Container runs as UID 1000** (`user`). The Dockerfile `chown`s `/app` to
  this user so DuckDB can open the bundled file (DuckDB writes a `.wal` even
  for read-only opens in some configurations).
- **No persistent disk.** Anything the running app writes — including DuckDB
  WAL — is lost on rebuild. That's fine; the DB is the artifact, and we ship
  a fresh copy on every deploy.
- **Custom domains are paid only.** Free Spaces stay at `*.hf.space`.

---

## Pre-flight check

Before pushing, smoke-test the HF Dockerfiles locally:

```sh
# Backend
docker build -f deploy/huggingface/api/Dockerfile -t coffee-atlas-api:hf .
docker run --rm -p 7860:7860 coffee-atlas-api:hf
curl http://localhost:7860/health

# Frontend (point to local backend on host)
docker build -f deploy/huggingface/web/Dockerfile \
  --build-arg BACKEND_URL=http://host.docker.internal:7860 \
  -t coffee-atlas-web:hf .
docker run --rm -p 7861:7860 coffee-atlas-web:hf
open http://localhost:7861
```

If both come up, the Space build will too.
