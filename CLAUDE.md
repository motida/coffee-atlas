# Coffee Atlas — CLAUDE.md

## Project Identity

Coffee Atlas is a full-stack geospatial application that maps the global coffee ecosystem — from bean genetics and farm origins to roasting science, distribution networks, and specialty coffee shops. It is built as a knowledge-graph-backed platform where every entity (bean variety, farm, roaster, shop, flavor profile) is a node in a connected graph, enabling discovery through relationships rather than flat search.

---

## Architecture

### Stack

- **Backend:** FastAPI (Python 3.14+)
- **Frontend:** Next.js 14+ (App Router, TypeScript, Tailwind CSS)
- **Database:** DuckDB (single-file today; Hive-partitioned Parquet export planned) — the **read-only content store**
- **User data store:** managed **Postgres** (provider-agnostic via `DATABASE_URL`) for everything user-owned (accounts, favorites, cupping notes). Separate from DuckDB because the content DB ships read-only into an ephemeral Space and can't take request-time writes. Accessed with psycopg 3 (sync) + a connection pool; raw SQL, no ORM. See `backend/db/pg.py` and `backend/db/pg_schema.py` (`usr_*` tables).
- **Auth:** custom in FastAPI — bcrypt password hashing + signed JWT in an **httpOnly cookie** (`backend/services/auth.py`). No third-party provider.
- **Graph Layer:** DuckPGQ extension is the target; **parked** on the current DuckDB build (the community `duckpgq` extension fails to load), so graph endpoints run BFS over relational edge tables
- **Vector Search:** DuckDB VSS extension with HNSW indexing planned; semantic search runs an exact cosine scan over stored Gemini embeddings today (`gemini-embedding-001`, 3072 dims)
- **Maps:** MapLibre GL JS (react-map-gl wrapper) with OpenFreeMap tiles
- **Ontology (design-time):** OWL 2 via rdflib (parse + structure validation, triple export); HermiT DL reasoning planned

> **Status note.** This file is the design spec; several pieces above are intentionally scoped for later (DuckPGQ, HNSW/VSS, HermiT, Parquet export). See `docs/ARCHITECTURE.md` for the live-vs-planned breakdown.

### Project Structure

```
coffee-atlas/
├── CLAUDE.md
├── ontology/
│   ├── coffee-atlas-ontology.ttl      # OWL 2 Turtle file
│   ├── modules/                        # Modular domain ontologies
│   │   ├── varieties.ttl
│   │   ├── origins.ttl
│   │   ├── processing.ttl
│   │   ├── roasting.ttl
│   │   ├── flavor.ttl
│   │   ├── distribution.ttl
│   │   ├── shops.ttl
│   │   └── products.ttl
│   └── scripts/
│       ├── validate_ontology.py        # Owlready2 + HermiT consistency check
│       └── export_triples.py           # Export inferred triples to DuckDB
├── backend/
│   ├── main.py                         # FastAPI app entry
│   ├── config.py                       # Settings, env vars, DB paths
│   ├── db/
│   │   ├── connection.py               # DuckDB connection manager
│   │   ├── schema.py                   # DDL for all tables
│   │   ├── seeds/                      # Seed scripts per domain
│   │   └── parquet/                    # Hive-partitioned Parquet files
│   ├── models/                         # Pydantic models per domain
│   ├── routers/
│   │   ├── varieties.py
│   │   ├── origins.py
│   │   ├── processing.py
│   │   ├── roasting.py
│   │   ├── flavor.py
│   │   ├── distribution.py
│   │   ├── shops.py
│   │   ├── products.py
│   │   ├── graph.py                    # Graph traversal endpoints (BFS)
│   │   └── search.py                   # Semantic similarity search
│   ├── services/
│   │   ├── embeddings.py               # Gemini embedding generation
│   │   ├── enrichment.py               # LLM-based entity extraction
│   │   └── geocoding.py                # Geocoding service (provider TBD)
│   └── ingest/
│       ├── cqi_loader.py               # Coffee Quality Institute data
│       ├── wcr_varieties_loader.py     # World Coffee Research catalog
│       ├── wcr_lexicon_loader.py       # WCR Sensory Lexicon
│       ├── processing_descriptions_loader.py  # Curated method prose
│       ├── processing_flavor_loader.py # Processing→flavor edge seed
│       ├── distribution_loader.py      # Certifications, importers, trade routes
│       ├── roasting_loader.py          # Roast profiles + roasters seed
│       ├── overture_shops_loader.py    # Overture Maps POI (S3)
│       ├── products_loader.py          # Load scraped roaster products
│       ├── product_edges.py            # Resolve product/shop/roaster edges
│       ├── geocode_stage.py            # Geocode origins
│       ├── embeddings_stage.py         # Gemini embeddings
│       ├── graph_stage.py              # Build edge tables (BFS-ready)
│       ├── shop_scrapers/              # Roaster catalog scrapers (Shopify/JSON-LD)
│       └── pipeline.py                 # Orchestrates full ingest
├── frontend/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # Landing / global map view
│   │   ├── explore/
│   │   │   ├── page.tsx                # Search + filter interface
│   │   │   └── [entity]/page.tsx       # Entity detail view
│   │   ├── graph/
│   │   │   └── page.tsx                # Knowledge graph explorer
│   │   └── api/                        # Next.js API routes (proxy to FastAPI)
│   ├── components/
│   │   ├── map/
│   │   │   ├── CoffeeMap.tsx           # Main MapLibre map component
│   │   │   ├── layers/                 # Map layer configs per entity type
│   │   │   └── popups/                 # Entity popup cards
│   │   ├── graph/
│   │   │   └── GraphViewer.tsx         # Force-directed graph viz (d3)
│   │   ├── flavor/
│   │   │   └── FlavorWheel.tsx         # Interactive SCA flavor wheel
│   │   └── ui/                         # Shared UI primitives
│   ├── lib/
│   │   ├── api.ts                      # API client
│   │   └── types.ts                    # TypeScript types (mirror Pydantic)
│   └── public/
├── data/
│   ├── raw/                            # Downloaded source files
│   │   ├── cqi_arabica.csv
│   │   ├── cqi_robusta.csv
│   │   ├── wcr_sensory_lexicon.pdf
│   │   └── wcr_varieties/
│   └── processed/                      # Cleaned, normalized data
├── tests/
│   ├── backend/
│   └── frontend/
├── deploy/
│   └── huggingface/                    # HF Space scaffold (api + web) + deploy.sh
├── justfile                            # Task runner (just bootstrap, just dev, ...)
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

---

## Ontology Design

The ontology follows OWL 2 DL profile. Design modules independently, import into a master ontology file. Use `owl:imports` between modules where cross-domain relationships exist.

### Domain Modules

#### 1. Varieties (`varieties.ttl`)
Classes: `CoffeeSpecies`, `CoffeeVariety`, `GeneticLineage`, `BreedingProgram`
Key properties: `hasParentVariety`, `resistantTo` (diseases/pests), `yieldPotential`, `optimalAltitudeRange`, `beanSize`, `cherryColor`, `stature`
Seed data: **WCR Varieties Catalog** — 55 Arabica + 47 Robusta varieties with 20+ agronomic variables. Scrape from `varieties.worldcoffeeresearch.org`. Creative Commons licensed.

#### 2. Origins (`origins.ttl`)
Classes: `Country`, `Region`, `Farm`, `Cooperative`, `Mill`, `GrowingConditions`
Key properties: `locatedIn`, `altitudeRange`, `soilType`, `annualRainfall`, `harvestSeason`, `producesVariety`
Seed data: **CQI Database** (Kaggle) — ~1,300 reviewed samples with country, region, altitude, farm name, mill, producer. Enrich coordinates via a geocoding service (provider TBD — candidates: Nominatim/OSM, Pelias, or a paid API).

#### 3. Processing (`processing.ttl`)
Classes: `ProcessingMethod`, `DryingMethod`, `FermentationType`
Individuals: `Washed`, `Natural`, `Honey`, `SemiWashed`, `WetHulled`, `Anaerobic`, `CarbonMaceration`
Key properties: `usesMethod`, `fermentationDuration`, `dryingDuration`, `impactOnFlavor`
Seed data: CQI processing method column + manual curation of modern specialty methods.

#### 4. Roasting (`roasting.ttl`)
Classes: `RoastProfile`, `RoastLevel`, `RoastingMethod`, `Roaster` (company/person)
Key properties: `firstCrackTemp`, `developmentTimeRatio`, `roastDegree` (light/medium/dark), `chargeTemp`, `totalRoastTime`, `enhancesFlavor`, `diminishesFlavor`
Seed data: Community-sourced profiles. Consider scraping Cropster public profiles, Sweet Maria's roast recommendations, or structured data from roasting forums. Model as individuals with datatype properties for temp curves.

#### 5. Flavor (`flavor.ttl`)
Classes: `FlavorAttribute`, `FlavorCategory`, `AromaAttribute`, `TextureAttribute`, `TasteAttribute`
Key properties: `belongsToCategory`, `intensityReference`, `sensoryReference`, `adjacentTo` (flavor wheel proximity)
Seed data: **WCR Sensory Lexicon 2.0** — 110 attributes organized hierarchically. Free PDF download from worldcoffeeresearch.org. Parse into a 3-tier taxonomy (category → subcategory → specific attribute). The interactive wheel at `notbadcoffee.com/flavor-wheel-en/` has the hierarchy in client-side JS — extract the JSON structure.

#### 6. Distribution (`distribution.ttl`)
Classes: `Importer`, `Exporter`, `TradeRoute`, `CoffeeGrade`, `Certification`
Key properties: `exportsTo`, `importsFrom`, `annualVolume`, `certifiedBy` (FairTrade, RainforestAlliance, Organic, etc.)
Seed data: **ICO Coffee Market Reports** (free monthly PDFs). For trade flow data, FAO FAOSTAT has open coffee trade statistics by country. Green coffee importers like Genuine Origin, Olam, Volcafe publish origin lists.

#### 7. Shops (`shops.ttl`)
Classes: `CoffeeShop`, `Roastery`, `CafeChain`, `BrewMethod`
Key properties: `locatedAt` (coordinates), `servesVariety`, `roastsInHouse`, `offersBrewMethod`, `sourcesFrom`, `rating`
Seed data: Google Places API, Yelp Fusion API, or Overture Maps Foundation open data for POI. Filter by coffee-related categories. For specialty focus, consider scraping European Coffee Trip, Sprudge city guides, or specialty coffee directories.

#### 8. Products (`products.ttl`)
Classes: `CoffeeProduct` (single-origin or blend)
Key properties: `roastedBy` (→ Roaster), `roastLevel`, `process`, `isBlend`, `price`, `netWeightGrams`, `consistsOf` (→ Variety), `hasFlavor` (→ FlavorAttribute), `fromOrigin` (→ Country/Region)
Seed data: scraped roaster product catalogs (Shopify storefront JSON + embedded JSON-LD) from a curated roaster list. The scraper drops non-coffee items; the `products` ingest stage is network-heavy and excluded from `just bootstrap` (run explicitly, like `shops`).

### Cross-Domain Object Properties
- `Variety → hasFlavor → FlavorAttribute`
- `Farm → grows → Variety`
- `Farm → locatedIn → Region → partOf → Country`
- `ProcessingMethod → enhances → FlavorAttribute`
- `RoastProfile → suitableFor → Variety`
- `RoastProfile → enhances / diminishes → FlavorAttribute`
- `CoffeeShop → sourcesFrom → Farm | Importer`
- `CoffeeShop → servesVariety → Variety`
- `CoffeeShop → usesRoastProfile → RoastProfile`
- `Country → exportsTo → Country` (via TradeRoute)
- `CoffeeProduct → consistsOf → Variety`
- `CoffeeProduct → hasFlavor → FlavorAttribute`
- `CoffeeProduct → fromOrigin → Country | Region`
- `CoffeeProduct → hasRoastLevel → RoastProfile`
- `Roaster → produces → CoffeeProduct`
- `CoffeeShop → sells → CoffeeProduct` (resolved via shop ↔ roaster domain match)

### Ontology Validation Workflow
1. Edit `.ttl` modules in Protégé or by hand
2. Run `validate_ontology.py` — loads with Owlready2, runs HermiT reasoner, checks consistency
3. Run `export_triples.py` — exports T-Box + inferred A-Box triples to DuckDB tables
4. Report triple count, class count, property count after each edit

---

## Data Pipeline

### Ingest Order

The `backend.ingest.pipeline` module runs these stages in order (run all with
`--all`, or one at a time with `--stage <name>`). `just bootstrap` runs the
local stages; the network-heavy `shops` and `products` stages are run explicitly.

1. `lexicon` — parse WCR Sensory Lexicon, populate `flav_attributes` (T-Box stable)
2. `varieties` — load WCR Varieties Catalog into `var_varieties`
3. `cqi` — clean + normalize CQI CSV → `org_*`, `proc_methods`, + cupping-derived edges
4. `processing_descriptions` — attach curated prose to `proc_methods`
5. `processing_flavor` — seed `edges_processing_flavor` from a hand-mapped table
6. `geocode` — batch-geocode origins (Nominatim + ISO centroids), store coordinates
7. `shops` — Overture Maps POI load → `shop_shops` *(network; skipped in bootstrap)*
8. `distribution` — certifications, importers, trade routes → `dist_*`
9. `roasting` — roast profiles + roasters seed → `roast_profiles`, `roast_roasters`, `edges_roast_variety`
10. `products` — scrape roaster catalogs → `prod_products` *(network; skipped in bootstrap)*
11. `embeddings` — generate Gemini embeddings → `*_embedding` columns (cosine scan today)
12. `graph` — compute and store all `edges_*` tables (incl. product/shop edges; DuckPGQ graph parked)

### DuckDB Schema Conventions
- All tables prefixed by domain: `var_`, `org_`, `proc_`, `roast_`, `flav_`, `dist_`, `shop_`, `prod_` (plus `edges_*` join tables)
- `_id` columns are UUIDs (text)
- `_embedding` columns are `FLOAT[3072]` for Gemini `gemini-embedding-001` embeddings
- `created_at` and `updated_at` timestamps on all tables
- Parquet export: Hive partitioned by domain under `data/parquet/domain=xxx/`

### DuckPGQ Property Graph

> **Parked.** The community `duckpgq` extension fails to load on the current
> DuckDB build, so this property graph is the design target, not the live path.
> The graph stage attempts it and reports `property_graph_ok` as skipped; graph
> endpoints traverse the `edges_*` tables with BFS in SQL instead.

Target definition over the relational tables:

```sql
CREATE PROPERTY GRAPH coffee_graph
VERTEX TABLES (
    var_varieties,
    org_countries,
    org_regions,
    org_farms,
    proc_methods,
    roast_profiles,
    roast_roasters,
    flav_attributes,
    shop_shops,
    prod_products
)
EDGE TABLES (
    edges_variety_flavor  (source KEY (variety_id) REFERENCES var_varieties (id),
                           destination KEY (flavor_id) REFERENCES flav_attributes (id)),
    edges_country_variety (source KEY (country_id) REFERENCES org_countries (id),
                           destination KEY (variety_id) REFERENCES var_varieties (id)),
    edges_region_variety  (source KEY (region_id) REFERENCES org_regions (id),
                           destination KEY (variety_id) REFERENCES var_varieties (id)),
    edges_farm_variety    (source KEY (farm_id) REFERENCES org_farms (id),
                           destination KEY (variety_id) REFERENCES var_varieties (id)),
    edges_shop_variety    (source KEY (shop_id) REFERENCES shop_shops (id),
                           destination KEY (variety_id) REFERENCES var_varieties (id)),
    -- ... additional edge tables
);
```

---

## API Design

### Core Endpoints

```
GET  /api/v1/varieties                   # List/filter varieties
GET  /api/v1/varieties/{id}              # Variety detail
GET  /api/v1/varieties/{id}/flavor       # Flavor profile for a variety
GET  /api/v1/origins                     # List origin countries
GET  /api/v1/origins/{id}                # Country detail
GET  /api/v1/origins/geo                 # Countries GeoJSON for map
GET  /api/v1/origins/regions/geo         # Regions GeoJSON for map
GET  /api/v1/origins/regions/{id}        # Region detail
GET  /api/v1/processing/methods          # List/filter processing methods
GET  /api/v1/processing/methods/{id}     # Processing method detail
GET  /api/v1/processing/methods/{id}/varieties  # Varieties prepared with a method
GET  /api/v1/processing/methods/{id}/flavor     # Flavors a method enhances/diminishes
GET  /api/v1/roasting/profiles           # List roast profiles
GET  /api/v1/roasting/profiles/{id}      # Roast profile detail
GET  /api/v1/flavor/wheel                # Full flavor wheel hierarchy (JSON tree)
GET  /api/v1/flavor/attributes/{id}      # Attribute detail
GET  /api/v1/distribution/importers      # List green-coffee importers
GET  /api/v1/distribution/certifications # List certifications
GET  /api/v1/distribution/trade-routes   # List trade routes
GET  /api/v1/distribution/trade-routes/geo  # Trade routes as GeoJSON LineStrings
GET  /api/v1/shops                       # List/filter shops
GET  /api/v1/shops/geo                   # GeoJSON for map layer
GET  /api/v1/shops/{id}                  # Shop detail
GET  /api/v1/shops/nearby                # Nearby shops (lat/lng + radius)
GET  /api/v1/shops/{id}/products         # Products the shop's roaster sells
GET  /api/v1/products                    # List products (filter: roaster_id, is_blend)
GET  /api/v1/products/{id}               # Product detail (with roaster name)
GET  /api/v1/products/{id}/varieties     # Varieties a product consists of
GET  /api/v1/products/{id}/flavors       # Flavor attributes in the tasting notes
GET  /api/v1/products/{id}/origin        # Origin countries and regions named
GET  /api/v1/graph/traverse              # Graph traversal (start_id, max_depth, edge_types)
GET  /api/v1/graph/path                  # Shortest path between two entities
GET  /api/v1/search/semantic             # Semantic similarity search across all entities
GET  /api/v1/search/text                 # Full-text search
POST /api/v1/auth/register               # Create account, set session cookie
POST /api/v1/auth/login                  # Log in, set session cookie
POST /api/v1/auth/logout                 # Clear session cookie
GET  /api/v1/auth/me                     # Current user (401 if not signed in)
GET  /api/v1/account/favorites           # User's saved entities (?entity_type=)
POST /api/v1/account/favorites           # Save an entity (idempotent; validates vs DuckDB)
DELETE /api/v1/account/favorites/{id}    # Remove a saved entity (ownership-scoped)
GET  /api/v1/account/notes               # User's cupping notes (?entity_type=&entity_id=)
POST /api/v1/account/notes               # Add a cupping note (product/variety only)
PATCH /api/v1/account/notes/{id}         # Update a cupping note (ownership-scoped)
DELETE /api/v1/account/notes/{id}        # Delete a cupping note (ownership-scoped)
```

> **Auth + activity (Postgres-backed).** `/auth/*` and `/account/*` live in
> Postgres, not DuckDB. `/account/*` routes require the session cookie
> (`get_current_user`) and are scoped `WHERE user_id = %s`. Write routes validate
> the referenced `entity_id` exists in DuckDB (`require_entity`) before writing —
> `entity_type` is resolved to a DuckDB table via the whitelists in
> `backend/routers/_activity_entities.py`.

### Query Patterns
- All list endpoints support `?limit=`, `?offset=`, `?sort=`, `?filter[field]=value`
- Geo endpoints return GeoJSON FeatureCollections
- Graph endpoints accept `start_id`, `max_depth`, `edge_types[]`, return adjacency lists
- Semantic search accepts `query` (natural language), returns ranked results with similarity scores

---

## Frontend Features

### 1. Global Map View (Landing Page)
- MapLibre GL map (OpenFreeMap tiles) with multiple toggleable layers:
  - **Origins layer:** coffee-producing countries/regions colored by production volume
  - **Shops layer:** clustered markers for specialty coffee shops worldwide
  - **Trade routes layer:** animated arcs showing green coffee trade flows
- Click any entity to open a detail sidebar
- Layer controls in top-right corner

### 2. Explore Interface
- Faceted search across all entity types
- Filter by: variety, origin country, processing method, flavor attributes, roast level
- Results displayed as cards with map pins highlighted
- Semantic search bar: "fruity Ethiopian natural process light roast" → ranked results

### 3. Entity Detail Views
- **Variety page:** genetics/lineage tree, where it's grown (map), flavor radar chart, suitable roast profiles, shops serving it
- **Origin page:** region map, altitude profile, varieties grown, processing methods used, seasonal calendar
- **Shop page:** location map, varieties served, brew methods, sourcing info, flavor profiles available
- **Flavor attribute page:** position on flavor wheel, varieties that exhibit it, processing methods that enhance it

### 4. Knowledge Graph Explorer
- Force-directed graph visualization (d3-force)
- Click a node to expand its connections
- Filter edges by relationship type
- Color nodes by entity type
- Hover for preview cards

### 5. Interactive Flavor Wheel
- SVG-based concentric ring visualization
- Click segments to filter varieties/shops by flavor
- Highlight segments based on selected variety or origin
- Link to WCR Lexicon references

---

## Development Principles

- **SOLID principles** — especially Single Responsibility (one router per domain) and Dependency Inversion (services injected into routers)
- **Type safety** — Pydantic models on backend, TypeScript types on frontend, kept in sync
- **Incremental buildout** — get one vertical working end-to-end (e.g., Varieties → Origin → Flavor) before expanding
- **Ontology-first** — design the OWL module before writing DB schema or API for any new domain
- **Test coverage** — pytest for backend (unit + integration), Vitest for frontend components
- **CLAUDE.md is the living spec** — update this file as architecture decisions are made

---

## Environment Variables

```env
# Database (read-only content store)
DUCKDB_PATH=./data/coffee_atlas.duckdb

# User data store (Postgres). Empty → content-only (auth/account disabled).
DATABASE_URL=                      # postgresql://user:pass@host:5432/dbname

# Auth (custom JWT-in-cookie). JWT_SECRET required when DATABASE_URL is set.
JWT_SECRET=                        # python -c "import secrets;print(secrets.token_urlsafe(48))"
COOKIE_SECURE=true                 # false for local http dev
# JWT_ALGORITHM=HS256, ACCESS_TOKEN_TTL_MINUTES=10080, COOKIE_NAME=ca_session, COOKIE_SAMESITE=lax

# APIs
GEMINI_API_KEY=...
GOOGLE_PLACES_API_KEY=...          # Optional, for shop data

# Server
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Feature flags
ENABLE_EMBEDDINGS=true
ENABLE_GRAPH=true

# Ingest options (read at ingest time; optional)
OVERTURE_RELEASE=2026-04-15.0      # Overture release for the shops stage
OVERTURE_BBOX=                     # xmin,ymin,xmax,ymax to scope the shops scrape
```

### Deployment

The hosted demo is split across two providers (not the local `docker-compose`):

- **Frontend → Vercel**, auto-deployed from `main` (root directory `frontend/`).
- **API → Hugging Face Space** (`motidav-coffee-atlas-api`). Backend *code*
  auto-deploys on push to `main` via CI; *data/DB* changes ship via
  `deploy/huggingface/deploy.sh`. Both frontends proxy `/api/v1/*` to the Space.

Next.js rewrites are baked at build time, so the backend URL is passed via the
Dockerfile `BACKEND_URL` ARG (a runtime env var won't override the built
manifest). See `deploy/huggingface/DEPLOY.md`.

---

## Bootstrap Sequence

The fastest path is `just bootstrap` (install → validate ontology → create
tables → export triples → `just ingest-all`). To run it by hand:

1. `just ontology-validate` — confirm ontology parses (rdflib structure check)
2. `just db-create` — create DuckDB tables (`python -m backend.db.schema`)
3. `just ontology-export` — export T-Box triples into `ontology_triples`
4. `just ingest-all` — runs the local stages in order: `lexicon`, `varieties`,
   `cqi`, `processing_descriptions`, `processing_flavor`, `geocode`,
   `distribution`, `roasting`, `embeddings`, `graph`
5. The network-heavy stages stay out of `ingest-all` — run them explicitly:
   `just ingest shops` then `just ingest products`, followed by a
   `just ingest graph` re-run to resolve the product/shop/roaster edges
6. `just dev-backend` — start the API (`uvicorn backend.main:app --reload`)
7. `just dev-frontend` — start Next.js (`cd frontend && npm run dev`)

> Note: `just ingest-all` runs every stage except the two network-heavy ones
> (`shops`, `products`). `python -m backend.ingest.pipeline --all` runs all 12,
> including those two.

---

## Data Sources Reference

| Source | URL | License | Domain Coverage |
|--------|-----|---------|-----------------|
| WCR Varieties Catalog | varieties.worldcoffeeresearch.org | CC BY-NC-ND 4.0 | Varieties, genetics, agronomy |
| WCR Sensory Lexicon 2.0 | worldcoffeeresearch.org/resources/sensory-lexicon | Free download | Flavor taxonomy (110 attributes) |
| CQI Database | kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi | Public | Cupping scores, origins, processing |
| ICO Market Reports | ico.org/resources/coffee-market-report-statistics-section | Free | Trade, prices, production |
| FAOSTAT Coffee | fao.org/faostat | Open | Trade flows, production by country |
| Overture Maps POI | overturemaps.org | ODbL | Coffee shop locations |
| notbadcoffee.com Flavor Wheel | notbadcoffee.com/flavor-wheel-en | Reference | Flavor wheel hierarchy (JS) |
| WCR SNP Markers | worldcoffeeresearch.org/resources/arabica-ldp-snp-marker-panel | Open access | Genetic fingerprints |

---

## Notes

- This project is also a portfolio piece demonstrating full-stack + knowledge graph + geospatial skills
- The ontology + DuckDB + DuckPGQ architecture mirrors the Sentinel pattern but in a self-contained, publicly demonstrable domain
- Future expansion: user accounts for cupping logs, recommendation engine ("if you like X, try Y" via graph similarity), roaster/shop owner portal for self-listing
