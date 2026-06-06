# Coffee Atlas

A full-stack geospatial platform that maps the global coffee ecosystem — from
bean genetics and farm origins to roasting science, distribution networks,
and specialty coffee shops.

Built as a knowledge-graph-backed application where every entity (variety,
farm, roaster, shop, flavor profile) is a node in a connected graph,
enabling discovery through relationships rather than flat search.

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
- **[Development](docs/DEVELOPMENT.md)** — project structure, testing, Docker

## License

The code in this repository is licensed under the [MIT License](LICENSE).

Source **data** retains its own terms, independent of the code license: the WCR
Varieties Catalog is CC BY-NC-ND 4.0; CQI cupping data and Overture Maps POI
carry their respective licenses. See [docs/DATA.md](docs/DATA.md) for details.
