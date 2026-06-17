# Coffee Atlas — Technical Deep Dive

> A geospatial knowledge graph platform that combines semantic web standards, hybrid relational-graph design, and vector search in a single coherent system — mapping the global coffee ecosystem from bean genetics to specialty shops.

> **Implementation status.** This document describes the target architecture; some
> pieces are deliberately scoped for later. **Live today:** the FastAPI + DuckDB
> backend with all eight domain routers (varieties, origins, processing, roasting,
> flavor, distribution, shops, products) plus graph and search, the ingest pipeline,
> Gemini embeddings with cosine semantic search over varieties + flavor attributes,
> the Next.js frontend (map, graph, flavor wheel, explore), and rdflib-based
> ontology validation + triple export. **Planned:** DuckPGQ property-graph queries
> (currently BFS over relational edge tables), the HNSW/VSS index (currently a
> full-table cosine scan), HermiT DL reasoning, and Hive-partitioned Parquet
> export. Sections below flag the gap inline where it matters.

---

## Why This Project

Most data platforms treat entities as rows in isolated tables. Coffee Atlas treats them as **nodes in a knowledge graph** — a coffee variety is connected to the farms that grow it, the processing methods that transform it, the flavor attributes it exhibits, the roast profiles that suit it, and the shops that serve it.

This architecture enables queries that flat databases cannot express naturally:

- *"Which Ethiopian natural-process varieties produce blueberry flavor notes?"*
- *"What's the shortest supply chain path from a Gesha farm to a specialty shop in Tel Aviv?"*
- *"Find shops serving varieties similar to what I described in natural language."*

The project demonstrates how formal ontology design, graph databases, and vector search can work together in a production-grade full-stack application — without the operational overhead of separate graph and vector databases.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14)                      │
│  ┌──────────┐  ┌───────────┐  ┌────────┐  ┌──────────────┐  │
│  │ MapLibre │  │ d3-force  │  │ Flavor │  │  Explore /   │  │
│  │  Map     │  │ Graph Viz │  │ Wheel  │  │  Search UI   │  │
│  └────┬─────┘  └─────┬─────┘  └───┬────┘  └──────┬───────┘  │
│       └───────────────┴────────────┴──────────────┘          │
│                           │ fetch()                          │
└───────────────────────────┼──────────────────────────────────┘
                            │ /api/v1/*
┌───────────────────────────┼──────────────────────────────────┐
│                    Backend (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  Routers: varieties · origins · processing · roasting│    │
│  │           flavor · distribution · shops · products   │    │
│  │           graph · search                             │    │
│  └──────────────────────┬───────────────────────────────┘    │
│  ┌──────────┐  ┌────────┴───────┐  ┌────────────────────┐   │
│  │Embedding │  │  DuckDB Conn   │  │  Geocoding Service │   │
│  │ Service  │  │  Manager       │  │  (Nominatim + ISO  │   │
│  │(Gemini)  │  │  + Extensions  │  │   centroids)       │   │
│  └──────────┘  └────────┬───────┘  └────────────────────┘   │
└──────────────────────────┼───────────────────────────────────┘
                           │
┌──────────────────────────┼───────────────────────────────────┐
│                    DuckDB (Single Process)                    │
│  ┌─────────────┐  ┌─────┴──────┐  ┌─────────────────────┐   │
│  │ Relational  │  │  DuckPGQ   │  │  DuckDB VSS         │   │
│  │ Tables (31) │  │ Property   │  │  Cosine scan today  │   │
│  │ 8 domains   │  │ Graph      │  │  3072-dim embeddings│   │
│  │ 13 + 18 edge│  │ (parked)   │  │  (HNSW planned)     │   │
│  └─────────────┘  └────────────┘  └─────────────────────┘   │
│                           │                                   │
│              Parquet (Hive-partitioned by domain)             │
└──────────────────────────────────────────────────────────────┘
                           ▲
                           │ design-time validation
┌──────────────────────────┼───────────────────────────────────┐
│                    Ontology Layer (OWL 2 DL)                 │
│  ┌──────────┐ ┌────────┐ ┌──────────┐ ┌─────────┐           │
│  │varieties │ │origins │ │processing│ │roasting │           │
│  ├──────────┤ ├────────┤ ├──────────┤ ├─────────┤           │
│  │ flavor   │ │distrib.│ │  shops   │ │products │           │
│  └──────────┘ └────────┘ └──────────┘ └─────────┘           │
│              Owlready2 + HermiT Reasoner                     │
└──────────────────────────────────────────────────────────────┘
```

---

## Ontology-First Design

Most projects start with a database schema. Coffee Atlas starts with a **formal OWL 2 DL ontology** — a machine-readable specification of every concept, relationship, and constraint in the coffee domain.

### Why Ontology-First?

An ontology is not documentation. It's designed to be executable (the reasoning
layer is the main planned extension — see status note above):

- **HermiT reasoner** (planned) would check logical consistency — if a class hierarchy is contradictory, the build fails before any data enters the system. Today `validate_ontology.py` does an rdflib parse/structure check; DL reasoning is parked.
- **Inferred relationships** (planned) — e.g. if Gesha `belongsToSpecies` Arabica and Arabica `hasProperty` "self-fertile", Gesha inherits that property
- **Cross-domain constraints** are formally declared — a `ProcessingMethod` can only `impactOnFlavor` a `FlavorAttribute`, not a `Farm`

### Modular Architecture

Eight domain ontologies are developed independently and composed via `owl:imports`:

```turtle
# coffee-atlas-ontology.ttl (master)
<http://coffeeatlas.org/ontology> a owl:Ontology ;
    owl:imports <http://coffeeatlas.org/ontology/varieties> ,
                <http://coffeeatlas.org/ontology/origins> ,
                <http://coffeeatlas.org/ontology/processing> ,
                <http://coffeeatlas.org/ontology/roasting> ,
                <http://coffeeatlas.org/ontology/flavor> ,
                <http://coffeeatlas.org/ontology/distribution> ,
                <http://coffeeatlas.org/ontology/shops> ,
                <http://coffeeatlas.org/ontology/products> .
```

Each module defines its own class hierarchy, properties, and constraints. Cross-domain relationships (e.g., `ProcessingMethod → enhances → FlavorAttribute`) reference other modules by IRI.

### Design → Runtime Flow

```
Edit .ttl modules
    → validate_ontology.py (Owlready2 + HermiT)
    → export_triples.py → DuckDB tables
    → Pydantic models mirror OWL classes
    → TypeScript interfaces mirror Pydantic models
```

Type safety propagates from the ontology through every layer.

---

## Domain Model

Eight interconnected domains, each with its own database table prefix, router, and Pydantic model:

### Entity Domains

| Domain | Prefix | Key Entities | Data Source |
|--------|--------|-------------|-------------|
| **Varieties** | `var_` | CoffeeSpecies, CoffeeVariety, GeneticLineage | WCR Catalog (100+ varieties) |
| **Origins** | `org_` | Country, Region, Farm, Mill | CQI Database (~1,300 samples) |
| **Processing** | `proc_` | ProcessingMethod, FermentationType | CQI + manual curation |
| **Roasting** | `roast_` | RoastProfile, RoastLevel, Roaster | Hand-curated seed (`roasting_seed.json`) |
| **Flavor** | `flav_` | FlavorAttribute, FlavorCategory | WCR Sensory Lexicon (110 attributes) |
| **Distribution** | `dist_` | Importer, TradeRoute, Certification | ICO, FAOSTAT |
| **Shops** | `shop_` | CoffeeShop, Roastery, BrewMethod | Overture Maps POI |
| **Products** | `prod_` | CoffeeProduct (single-origin / blend) | Scraped roaster catalogs (Shopify + JSON-LD) |

### Relationship Graph

```
Variety ──hasFlavor──▶ FlavorAttribute
   ▲                        ▲
   │                        │
   grows                  enhances
   │                        │
Farm ──locatedIn──▶ Region ──partOf──▶ Country
                                         │
                                     exportsTo
                                         │
CoffeeShop ──servesVariety──▶ Variety    ▼
     │                               Country
     └──sourcesFrom──▶ Farm | Importer
     └──usesRoastProfile──▶ RoastProfile ──enhances/diminishes──▶ FlavorAttribute
```

Eighteen edge tables materialize these relationships for graph traversal, built by a handful of loaders:

- **Geographic hierarchy & semantics** (graph stage): `edges_country_region` and `edges_region_farm` from foreign keys; `edges_variety_flavor` from top-K embedding similarity.
- **Cupping co-occurrence** (CQI loader): `edges_country_variety`, `edges_region_variety`, `edges_farm_variety`, and `edges_variety_processing`. Origin → Variety is split per origin level so each edge keeps a real foreign key (no polymorphic IDs).
- **Curated seeds**: `edges_roast_variety` (roasting loader, from each profile's species/altitude suitability rule) and `edges_processing_flavor` (processing_flavor stage, from a hand-mapped table).
- **Products domain** (graph stage, after the `products` and `shops` stages run): *content* edges match scraped product text against the loaded entities (`edges_product_variety`, `edges_product_flavor`, `edges_product_country`, `edges_product_region`, `edges_product_roast`); *structural* edges follow the website graph (`edges_roaster_product`, `edges_shop_roaster`, `edges_shop_product`). The last chain, shop → product → variety, finally populates the previously-empty `edges_shop_variety`.

Because origin → variety and the product/shop chains bridge the geographic hierarchy to the variety/flavor/processing/roasting clusters, traversal spans a **single connected component** rather than disconnected islands.

| Edge Table | From | To |
|-----------|------|-----|
| `edges_variety_flavor` | Variety | FlavorAttribute |
| `edges_country_variety` | Country | Variety |
| `edges_region_variety` | Region | Variety |
| `edges_farm_variety` | Farm | Variety |
| `edges_variety_processing` | Variety | ProcessingMethod |
| `edges_processing_flavor` | ProcessingMethod | FlavorAttribute |
| `edges_roast_variety` | RoastProfile | Variety |
| `edges_country_region` | Country | Region |
| `edges_region_farm` | Region | Farm |
| `edges_product_variety` | CoffeeProduct | Variety |
| `edges_product_flavor` | CoffeeProduct | FlavorAttribute |
| `edges_product_country` | CoffeeProduct | Country |
| `edges_product_region` | CoffeeProduct | Region |
| `edges_product_roast` | CoffeeProduct | RoastProfile |
| `edges_roaster_product` | Roaster | CoffeeProduct |
| `edges_shop_product` | Shop | CoffeeProduct |
| `edges_shop_roaster` | Shop | Roaster |
| `edges_shop_variety` | Shop | Variety |

---

## Database Architecture

### Why DuckDB?

DuckDB is an in-process columnar analytical database. Choosing it over PostgreSQL or SQLite was deliberate:

| Capability | DuckDB | PostgreSQL | SQLite |
|-----------|--------|-----------|--------|
| Columnar compression | 50-90% smaller | Row-oriented | Row-oriented |
| Analytical queries | 10-100x faster | Requires tuning | Slow |
| Property graph (PGQ) | Native extension | Requires Apache AGE | Not available |
| Vector search (VSS) | Native extension | Requires pgvector | Not available |
| Parquet I/O | Native, zero-copy | Foreign data wrapper | Not available |
| Operational overhead | Zero (embedded) | Server process | Zero (embedded) |

The trade-off is intentional: DuckDB is single-node and optimized for analytical workloads. For a knowledge graph platform where reads dominate and the dataset fits in memory, this is the right fit.

### Schema Conventions

Every table follows consistent conventions:
- `id TEXT PRIMARY KEY` — UUIDs as text
- `created_at TIMESTAMP DEFAULT current_timestamp`
- `updated_at TIMESTAMP DEFAULT current_timestamp`
- `*_embedding FLOAT[3072]` — Gemini `gemini-embedding-001` vectors where applicable

### DuckPGQ Property Graph

DuckDB's `pgq` extension is designed to overlay a property graph on relational tables — no data duplication, the graph is a **view** over existing tables. The target definition is below. On the current DuckDB build the community `duckpgq` extension fails to load, so this step is **parked** and the graph endpoints run BFS over the same edge tables instead (`property_graph_ok` is reported as skipped by the graph stage):

```sql
CREATE PROPERTY GRAPH coffee_graph
VERTEX TABLES (
    var_varieties, org_countries, org_regions, org_farms,
    proc_methods, roast_profiles, roast_roasters,
    flav_attributes, shop_shops, prod_products
)
EDGE TABLES (
    edges_variety_flavor   (source REFERENCES var_varieties,
                            destination REFERENCES flav_attributes),
    edges_country_variety  (source REFERENCES org_countries,
                            destination REFERENCES var_varieties),
    edges_region_variety   (source REFERENCES org_regions,
                            destination REFERENCES var_varieties),
    edges_farm_variety     (source REFERENCES org_farms,
                            destination REFERENCES var_varieties),
    -- ... 14 more edge tables, including the products domain
);
```

Once the extension is available, graph queries run inside DuckDB's SQL engine — no network roundtrips to a separate graph database, with ACID guarantees on graph mutations.

### Vector Search with HNSW

The `vss` extension builds HNSW (Hierarchical Navigable Small World) indexes on embedding columns:

- **What's embedded**: variety descriptions and flavor attribute names today (shop bios and processing descriptions are schema-ready)
- **Model**: Gemini `gemini-embedding-001` (3072 dimensions)
- **Index**: exact cosine scan today via `array_cosine_similarity`; an HNSW index (the `vss` extension) is the planned upgrade for approximate k-NN at scale
- **Query flow**: natural language → embed with Gemini → cosine ranking over embedded entity types → ranked results with similarity scores. When no Gemini key is configured (e.g. the public demo), `/search/semantic` degrades transparently to text search.

This enables semantic search like *"fruity Ethiopian natural process light roast"* returning relevant varieties and flavor attributes ranked by semantic similarity.

---

## Backend Architecture

### Dependency Injection

FastAPI's `Depends` system decouples routers from infrastructure:

```python
# Connection manager yields and cleans up
def get_db() -> Generator[duckdb.DuckDBPyConnection, None, None]:
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

# Router receives injected connection
@router.get("/{variety_id}")
def get_variety(variety_id: str, db = Depends(get_db)):
    row = db.execute("SELECT * FROM var_varieties WHERE id = ?", [variety_id])
    ...
```

This makes testing trivial — swap `get_db` with an in-memory DuckDB fixture:

```python
@pytest.fixture
def db():
    conn = duckdb.connect(":memory:")
    create_tables(conn)
    yield conn
    conn.close()
```

### Router-Per-Domain (SOLID)

Each domain has exactly one router with a dedicated prefix:

| Router | Prefix | Responsibilities |
|--------|--------|-----------------|
| `varieties.py` | `/api/v1/varieties` | List, detail, flavor profile |
| `origins.py` | `/api/v1/origins` | List, detail, GeoJSON export (countries + regions) |
| `processing.py` | `/api/v1/processing` | Methods list/detail, linked varieties + flavors |
| `roasting.py` | `/api/v1/roasting` | Profiles list and detail |
| `flavor.py` | `/api/v1/flavor` | Wheel hierarchy, attribute detail |
| `distribution.py` | `/api/v1/distribution` | Importers, certifications, trade routes + GeoJSON arcs |
| `shops.py` | `/api/v1/shops` | List, detail, GeoJSON, nearby (Haversine), products |
| `products.py` | `/api/v1/products` | List/detail, varieties, flavors, origin |
| `graph.py` | `/api/v1/graph` | Traverse, shortest path |
| `search.py` | `/api/v1/search` | Semantic similarity, full-text |

### Geospatial Queries

The shops router implements proximity search using the Haversine formula directly in SQL:

```python
@router.get("/nearby")
def get_nearby_shops(lat: float, lng: float, radius_km: float = 5.0):
    db.execute("""
        SELECT *, (
            6371 * acos(
                cos(radians(?)) * cos(radians(latitude))
                * cos(radians(longitude) - radians(?))
                + sin(radians(?)) * sin(radians(latitude))
            )
        ) AS distance_km
        FROM shop_shops
        HAVING distance_km <= ?
        ORDER BY distance_km
    """, [lat, lng, lat, radius_km])
```

GeoJSON endpoints return standard `FeatureCollection` objects, ready for MapLibre layers.

### Type Safety Pipeline

Types flow from the ontology through every layer:

```
OWL 2 Class (varieties.ttl)
    → DuckDB DDL (schema.py: var_varieties)
    → Pydantic BaseModel (models/varieties.py: VarietyRead)
    → FastAPI response_model (auto-validates output)
    → TypeScript interface (lib/types.ts: Variety)
    → React component props
```

If a field is added to the ontology, the change propagates: schema migration → Pydantic model → API contract → TypeScript type → compile-time error in the frontend.

---

## Frontend Architecture

### Next.js 14 App Router

The frontend uses Next.js 14's App Router with server components by default and client components where interactivity is required:

| Page | Route | Rendering |
|------|-------|-----------|
| Global Map | `/` | Client (MapLibre GL requires DOM) |
| Explore | `/explore` | Server (search form, results) |
| Entity Detail | `/explore/[entity]` | Dynamic (per-entity SSR) |
| Graph Explorer | `/graph` | Client (d3-force requires DOM) |

Client components are loaded with `next/dynamic` and `ssr: false` for libraries that require browser APIs (MapLibre, d3).

### Map Layer Architecture

The map component renders multiple toggleable layers:

- **Origins layer** — coffee-producing countries/regions colored by production volume
- **Shops layer** — clustered markers for specialty coffee shops
- **Trade routes layer** — animated arcs showing green coffee trade flows

Each layer consumes GeoJSON from the corresponding API endpoint (`/origins/geo`, `/shops/geo`).

### API Proxy

The Next.js config proxies `/api/v1/*` to the FastAPI backend, avoiding CORS in development:

```javascript
async rewrites() {
    return [{
        source: "/api/v1/:path*",
        destination: "http://localhost:8000/api/v1/:path*",
    }];
}
```

### API Client

A typed fetch wrapper ensures all API calls are type-safe:

```typescript
async function fetchAPI<T>(endpoint: string): Promise<T> {
    const res = await fetch(`${API_BASE}/api/v1${endpoint}`);
    return res.json();
}

export const getVarieties = () => fetchAPI<Variety[]>("/varieties");
export const getShopsGeo = () => fetchAPI<GeoJSONFeatureCollection>("/shops/geo");
```

---

## Data Pipeline

The ingest pipeline runs in stages, each independently re-runnable:

```
Stage  1: lexicon                 ─ WCR Sensory Lexicon PDF ─▶ flav_attributes (110 rows)
Stage  2: varieties               ─ WCR Web Catalog ─────────▶ var_varieties (100+ rows)
Stage  3: cqi                     ─ Kaggle CSV ──────────────▶ org_*, proc_methods (~1,300 rows)
Stage  4: processing_descriptions ─ Curated prose ──────────▶ proc_methods.description
Stage  5: processing_flavor       ─ Hand-mapped table ──────▶ edges_processing_flavor
Stage  6: geocode                 ─ Nominatim + ISO centroids ▶ lat/lng on org_countries/regions
Stage  7: shops                   ─ Overture Maps POI ───────▶ shop_shops   (network; skipped in bootstrap)
Stage  8: distribution            ─ ICO / FAOSTAT seed ──────▶ dist_*
Stage  9: roasting                ─ Curated seed JSON ───────▶ roast_profiles, roast_roasters
Stage 10: products                ─ Roaster catalog scrape ──▶ prod_products (network; skipped in bootstrap)
Stage 11: embeddings              ─ Gemini API ──────────────▶ *_embedding columns
Stage 12: graph                   ─ Computed ─────────────────▶ edges_* tables
```

Order matters: the flavor taxonomy must exist before varieties can link to it; coordinates must exist before the map can render; embeddings require text fields to be populated.

```bash
uv run python -m backend.ingest.pipeline --all     # Run all stages
uv run python -m backend.ingest.pipeline --stage cqi  # Run one stage
```

---

## Key Technical Decisions

| Decision | Chosen | Alternative | Rationale |
|----------|--------|-------------|-----------|
| Database | DuckDB (embedded) | PostgreSQL | Zero ops, columnar compression, native PGQ + VSS extensions |
| Graph | DuckPGQ (in-process; BFS fallback today) | Neo4j | No separate server, ACID, SQL joins with relational data |
| Vector search | DuckDB VSS | Pinecone / Weaviate | Self-contained, no external service dependency |
| Ontology | OWL 2 DL + HermiT | JSON Schema | Formal reasoning, inferred relationships, consistency proofs |
| Embeddings | Gemini `gemini-embedding-001` | OpenAI / open-source (e5, BGE) | Generous free tier, 3072 dims, high-quality retrieval |
| Package manager | uv | pip + setuptools | 10-100x faster installs, lockfile, built-in venv management |
| Frontend | Next.js 14 App Router | Vite + React SPA | Server components, API proxy, ISR for static pages |
| Maps | MapLibre GL JS + OpenFreeMap | Mapbox / Leaflet / deck.gl | Open-source, no API key, same vector-tile capabilities as Mapbox (forked from Mapbox GL v1) |

---

## What Makes This Architecturally Interesting

**Three specialized query engines in one database.** Most platforms deploy separate systems for relational queries (Postgres), graph traversal (Neo4j), and vector search (Pinecone). Coffee Atlas runs all three inside DuckDB — reducing operational complexity from three services to zero.

**Ontology-driven development.** The OWL ontology isn't documentation — it's the source of truth that drives schema design, API contracts, and type definitions. Changes propagate through the stack via formal semantics, not convention.

**Cross-domain discovery.** The graph structure enables queries that span domains: *"Show me all shops in Berlin that serve washed Ethiopian varieties with citrus flavor notes, roasted light."* This traverses shops → varieties → origins → processing → flavor → roasting in a single query path.

**Geospatial + semantic + graph.** The platform combines three specialized capabilities (map rendering, natural language search, relationship traversal) in a unified interface — not as separate features, but as complementary views of the same knowledge graph.
