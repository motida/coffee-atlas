# Deploying Coffee Atlas to Hugging Face Spaces

Two free Docker Spaces, one per service:

| Space | Role | Port | Persistent? |
|-------|------|------|-------------|
| `coffee-atlas-api` | FastAPI backend | 7860 | No (DB bundled in image) |
| `coffee-atlas-web` | Next.js frontend | 7860 | No (stateless) |

DuckDB is read-only at runtime, so the lack of persistent disk on the free tier
is fine: the database file is built locally, committed via git-lfs, and shipped
inside the image. User-owned data (accounts, favorites, cupping notes) needs a
concurrent-write, persistent store, so it lives in an external managed Postgres
instead — see [User accounts & data](#user-accounts--data-postgres).

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
- `DATABASE_URL` (secret) — Postgres connection string for user accounts and
  activity (see [User accounts & data](#user-accounts--data-postgres) below).
  Leave unset to run the API content-only (auth/account routes disabled).
- `JWT_SECRET` (secret) — signing key for session tokens. Generate with
  `python -c "import secrets;print(secrets.token_urlsafe(48))"`. Required
  whenever `DATABASE_URL` is set.
- `COOKIE_SECURE` (variable, optional) — defaults to `true`. Keep `true` in
  production (cookies only sent over HTTPS); the `*.hf.space` domain is HTTPS.

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
HF-specific `Dockerfile` + `README.md` + `.gitattributes`, ships a **compacted**
DuckDB file with LFS, commits, and pushes. HF rebuilds automatically on push;
follow the build logs at:

> **DB compaction.** Rather than `cp` the full local DB, the api deploy runs
> `python -m backend.db.compact` to build the shipped copy: it drops the
> non-specialty shops (~98% of `shop_shops`, which the app never serves) and
> reclaims DuckDB's free blocks via a CTAS rebuild. This takes the LFS blob from
> ~190 MB to ~34 MB (≈5× more deploys before the LFS-quota reset below). Your
> local DB is left untouched, so you can still re-tune the specialty heuristic
> and re-run stages against the full POI set. The shipped DB drops PK/FK
> constraints (no value for a read-only store) and the `?include_non_specialty`
> escape hatch on `/shops` returns nothing against it.


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

## User accounts & data (Postgres)

User-owned data (accounts, saved favorites, cupping notes) **cannot** live in
the DuckDB file: that file ships read-only inside the image and is rebuilt on
every deploy, so any request-time write would be lost. Instead it lives in a
**managed Postgres** reached at runtime via `DATABASE_URL` — entirely
independent of `deploy.sh` and the git-lfs flow.

1. **Provision Postgres.** Any provider works (the code is provider-agnostic):
   - [Neon](https://neon.tech) — pairs tightest with a Vercel frontend; use the
     pooled (`-pooler`) connection string.
   - [Supabase](https://supabase.com) — use the connection string from
     Project Settings → Database.
2. **Set the two secrets** on the api Space (above): `DATABASE_URL` and
   `JWT_SECRET`. They're runtime secrets — *not* build-time variables.
3. **Tables auto-create on boot.** The app's lifespan runs `create_pg_tables`
   (idempotent `CREATE TABLE IF NOT EXISTS` for the `usr_*` tables) on startup,
   so there's no separate migration step for V1.

The same `DATABASE_URL` + `JWT_SECRET` go in your local `.env` for development
(with `COOKIE_SECURE=false` for local http). A local Postgres works too:

```sh
docker run -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16
# DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres
```

> **CORS note.** Because the browser talks only to the frontend (which proxies
> `/api/v1/*` to the API server-side), the session cookie is first-party and
> `SameSite=Lax` suffices. If you ever point the browser directly at the API
> host, add that exact origin to `allow_origins` in `backend/main.py` and switch
> the cookie to `SameSite=None; Secure` — never use `"*"` with credentials.

---

## Updating data only

If only the DuckDB file changed:

```sh
uv run -m backend.ingest.pipeline --all
HF_USER=... ./deploy/huggingface/deploy.sh api
```

The git-lfs delta is pushed and HF rebuilds the api Space.

---

## Resetting the LFS storage quota (recreating the api Space)

Each `deploy.sh api` run pushes a **fresh DB blob** through git-LFS (now ~34 MB
after compaction, down from ~190 MB), and old LFS versions aren't freed promptly
(squashing history doesn't reclaim them quickly either). After enough data
deploys the api Space still drifts toward the free tier's **~1 GB LFS storage
cap** and pushes start failing — compaction just buys ~5× more deploys first. The
reliable fix is to **delete and recreate** the Space so its storage resets:

1. Delete the api Space (Settings → bottom → *Delete this Space*).
2. Recreate it per [Create both Spaces](#3-create-both-spaces-on-huggingfaceco)
   above (same name, Docker SDK).
3. Re-run `HF_USER=... ./deploy/huggingface/deploy.sh api` to push code + DB.

> **Recreating wipes every secret — re-add all THREE on the api Space.**
> A fresh Space starts with no variables or secrets. It's easy to remember the
> obvious one (`GEMINI_API_KEY`) and forget the auth pair. Re-add **all** of
> `GEMINI_API_KEY`, `DATABASE_URL`, and `JWT_SECRET` (see
> [Configure Space variables and secrets](#4-configure-space-variables-and-secrets)).
>
> Missing `DATABASE_URL`/`JWT_SECRET` fails **silently and partially**: the
> content endpoints (`/varieties`, `/shops`, …) keep returning 200, so the
> Space looks healthy, while every `/auth/*` and `/account/*` route returns
> `503 "User accounts are unavailable"` (raised by `db/pg.get_pg` when the pool
> was never initialized). Symptom in the UI: registration/login fails with
> "Could not create your account."

---

## Gotchas

- **48-hour idle sleep.** Free Spaces sleep after 48h with no traffic. First
  request after sleep takes ~30s for a Docker Space. Acceptable for a
  portfolio app.
- **Backend URL is build-time, not runtime.** Changing the api Space's URL
  (e.g. renaming) means the web Space must be rebuilt. This is a Next.js
  rewrites limitation (see `frontend/next.config.js`), not an HF one.
- **Repo size limit: 5 GB per Space.** The shipped (compacted) DB is ~34 MB so
  there's plenty of headroom.
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
