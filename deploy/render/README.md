# Deploying the Coffee Atlas API to Render

The API moved off Hugging Face Spaces after HF began requiring a PRO
subscription to host Docker Spaces on free `cpu-basic`. This directory hosts the
API on **Render's free tier** instead (Docker web service, no credit card).

## How it's wired

- **Compute:** a Render Docker web service built from `deploy/render/Dockerfile`.
- **Content DB:** the ~350 MB DuckDB file is **not** in the git repo (it's
  gitignored). It lives in a public Hugging Face **dataset** repo,
  [`motidav/coffee-atlas-db`](https://huggingface.co/datasets/motidav/coffee-atlas-db)
  (datasets are free — only Docker/Gradio *Spaces* are paywalled). The Dockerfile
  `curl`s it at **build time**, so it's baked into the image and cold starts stay
  fast.
- **Frontend:** unchanged on Vercel. After the first deploy, point the frontend's
  `BACKEND_URL` at the new Render URL (see step 4).

## First-time deploy

1. **Create the Render service.** On [render.com](https://render.com) → **New** →
   **Blueprint** → connect the `motida/coffee-atlas` GitHub repo. Render reads
   `deploy/render/render.yaml` and creates the `coffee-atlas-api` service.
2. **Set the three secrets** when prompted (all marked `sync: false`, so Render
   asks for them):
   - `GEMINI_API_KEY` — for real semantic search (else it falls back to text search)
   - `DATABASE_URL` — Postgres user-data store (else `/auth/*` + `/account/*` 503)
   - `JWT_SECRET` — signs the session cookie; required whenever `DATABASE_URL` is set
3. **Deploy.** Render builds the image (pulling the DB from the dataset) and
   starts it. Watch the build log; the Dockerfile self-checks the DB
   (`DB OK: <n> products`) and fails the build if the download is bad.
4. **Repoint the frontend.** In the Vercel project settings, set
   `BACKEND_URL=https://coffee-atlas-api.onrender.com` (use the actual URL Render
   assigns) and redeploy the frontend — Next.js bakes the rewrite target at build
   time, so a redeploy is required (see the root `CLAUDE.md`).

Verify: `https://<render-url>/health` → `{"status":"ok","accounts":"enabled"}`.

## Shipping a new DB

The DB is a build artifact of the ingest pipeline; ship changes by re-uploading
it to the dataset, then rebuilding the image:

```bash
# 1. Build a compacted, deploy-ready copy locally (drops non-specialty shops,
#    reclaims free space, keeps PK/FK constraints — see backend/db/compact.py):
uv run python -m backend.db.compact data/coffee_atlas.duckdb /tmp/deploy.duckdb

# 2. Upload it to the dataset (needs `hf auth login` with a write token):
hf upload motidav/coffee-atlas-db /tmp/deploy.duckdb coffee_atlas.duckdb \
    --repo-type dataset --commit-message "Deploy $(date -u +%FT%TZ)"

# 3. Trigger a Render rebuild (Manual Deploy → Clear build cache & deploy, so the
#    curl layer re-fetches). Backend *code* changes auto-deploy on push to main.
```

> **Why a rebuild, not a runtime fetch?** Baking the DB into the image keeps free-
> tier cold starts fast (no ~350 MB download on every wake-up) and lets the build
> fail loudly on a corrupt/incomplete DB instead of crash-looping at runtime.

## Portability

The Dockerfile is host-agnostic — it binds to `$PORT` and pulls the DB from a
public URL, so the same image runs on **Fly.io**, **Koyeb**, **Railway**, or a
plain `docker run` (defaults to port 8000). Only `render.yaml` is Render-specific.
