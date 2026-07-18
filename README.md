# Coffee Atlas

A full-stack geospatial platform that maps the global coffee ecosystem — from
bean genetics and farm origins to roasting science, distribution networks,
and specialty coffee shops.

Built as a knowledge-graph-backed application where every entity (variety,
farm, roaster, shop, flavor profile) is a node in a connected graph,
enabling discovery through relationships rather than flat search.

## Live Demo

- **App:** <https://coffee-atlas-tau.vercel.app>
- **API docs:** <https://coffee-atlas-api.onrender.com/docs>

> The frontend is hosted on Vercel (auto-deployed from `main`). The API runs on
> Render's free tier, which sleeps after ~15 min of inactivity — the first
> request may take ~1 min to wake the container. The content DB is hosted in the
> public Hugging Face dataset
> [`motidav/coffee-atlas-db`](https://huggingface.co/datasets/motidav/coffee-atlas-db)
> and baked into the API image at build time (see `deploy/render/README.md`).

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.14) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind CSS) |
| Database | DuckDB (single-file; Parquet/Hive export planned) |
| Graph | BFS traversal over relational edge tables (DuckPGQ planned) |
| Vector Search | DuckDB VSS — cosine over stored Gemini embeddings (HNSW index planned) |
| Maps | MapLibre GL JS with OpenFreeMap tiles |
| Ontology | OWL 2 (Turtle), parsed & exported to DuckDB via rdflib (HermiT DL reasoning planned) |

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** — prerequisites, install, run
- **[Architecture](docs/ARCHITECTURE.md)** — design rationale and deep dive
- **[API Reference](docs/API.md)** — REST endpoints
- **[Data Sources & Pipeline](docs/DATA.md)** — ingest stages and sources
- **[Adding Shops & Roasters](docs/ADDING_SHOPS_AND_ROASTERS.md)** — runbook for expanding the map into a new country/city
- **[Development](docs/DEVELOPMENT.md)** — project structure, testing, Docker

## License

The code in this repository is licensed under the [MIT License](LICENSE).

Source **data** retains its own terms, independent of the code license: the WCR
Varieties Catalog is CC BY-NC-ND 4.0; CQI cupping data and Overture Maps POI
carry their respective licenses. See [docs/DATA.md](docs/DATA.md) for details.
