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
| Backend | FastAPI (Python 3.13) |
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind CSS) |
| Database | DuckDB with Parquet storage (Hive-partitioned) |
| Graph | DuckPGQ extension for graph traversal |
| Vector Search | DuckDB VSS with HNSW indexing |
| Maps | MapLibre GL JS with OpenFreeMap tiles |
| Ontology | OWL 2 via Owlready2, validated with HermiT |

## Documentation

- **[Getting Started](docs/GETTING_STARTED.md)** — prerequisites, install, run
- **[Architecture](docs/ARCHITECTURE.md)** — design rationale and deep dive
- **[API Reference](docs/API.md)** — REST endpoints
- **[Data Sources & Pipeline](docs/DATA.md)** — ingest stages and sources
- **[Development](docs/DEVELOPMENT.md)** — project structure, testing, Docker

## License

TBD
