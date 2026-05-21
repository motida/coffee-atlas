---
title: Coffee Atlas
emoji: ☕
colorFrom: yellow
colorTo: red
sdk: docker
app_port: 7860
pinned: false
---

# Coffee Atlas — Web

Next.js 14 frontend for [Coffee Atlas](https://github.com/motida/coffee-atlas):
an interactive map of the global coffee ecosystem — varieties, origins,
processing, roasting, flavor, and specialty shops — backed by an OWL ontology
and a DuckDB knowledge graph.

The API Space at `coffee-atlas-api` serves all `/api/v1/*` routes.

## Build-time coupling

The backend URL is **baked into the build** via the `BACKEND_URL` Docker `ARG`.
If the API Space's URL changes, this Space must be rebuilt.

In the HF Space UI, configure under **Settings → Variables and secrets**:

- `BACKEND_URL` (variable, not secret) = `https://<your-username>-coffee-atlas-api.hf.space`
