# Coffee Atlas — CLAUDE.md

## Project Identity

Coffee Atlas is a full-stack geospatial application that maps the global coffee ecosystem — from bean genetics and farm origins to roasting science, distribution networks, and specialty coffee shops. It is built as a knowledge-graph-backed platform where every entity (bean variety, farm, roaster, shop, flavor profile) is a node in a connected graph, enabling discovery through relationships rather than flat search.

---

## Architecture

### Stack

- **Backend:** FastAPI (Python 3.14+)
- **Frontend:** Next.js 14+ (App Router, TypeScript, Tailwind CSS)
- **Database:** DuckDB with Parquet storage (Hive-partitioned by domain)
- **Graph Layer:** DuckPGQ extension for graph traversal queries
- **Vector Search:** DuckDB VSS extension with HNSW indexing (Gemini `gemini-embedding-001`, 3072 dims)
- **Maps:** MapLibre GL JS (react-map-gl wrapper) with OpenFreeMap tiles
- **Ontology (design-time):** OWL 2 via Owlready2, validated with HermiT reasoner

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
│   │   └── shops.ttl
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
│   │   ├── roasting.py
│   │   ├── flavor.py
│   │   ├── shops.py
│   │   ├── graph.py                    # Graph traversal endpoints
│   │   └── search.py                   # Semantic similarity search
│   ├── services/
│   │   ├── embeddings.py               # Gemini embedding generation
│   │   ├── enrichment.py               # LLM-based entity extraction
│   │   └── geocoding.py                # Geocoding service (provider TBD)
│   └── ingest/
│       ├── cqi_loader.py               # Coffee Quality Institute data
│       ├── wcr_varieties_loader.py     # World Coffee Research catalog
│       ├── wcr_lexicon_loader.py       # WCR Sensory Lexicon
│       ├── shop_scrapers/              # Specialty shop data collection
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

### Ontology Validation Workflow
1. Edit `.ttl` modules in Protégé or by hand
2. Run `validate_ontology.py` — loads with Owlready2, runs HermiT reasoner, checks consistency
3. Run `export_triples.py` — exports T-Box + inferred A-Box triples to DuckDB tables
4. Report triple count, class count, property count after each edit

---

## Data Pipeline

### Ingest Order
1. **WCR Sensory Lexicon** → parse PDF, populate `flavor_attributes` table (T-Box stable)
2. **WCR Varieties Catalog** → scrape web catalog, populate `varieties` table
3. **CQI Database** → download CSV from Kaggle, clean + normalize, populate `coffee_samples`, `origins`, `processing_methods`
4. **Geocoding** → batch geocode origins (country + region + altitude) via chosen provider, store coordinates
5. **Shops** → POI data load, filter specialty coffee, geocode, populate `shops`
6. **Embeddings** → generate Gemini embeddings for variety descriptions, flavor profiles, shop descriptions → store in DuckDB VSS index
7. **Graph edges** → compute and store edges for DuckPGQ property graph

### DuckDB Schema Conventions
- All tables prefixed by domain: `var_`, `org_`, `proc_`, `roast_`, `flav_`, `dist_`, `shop_`
- `_id` columns are UUIDs (text)
- `_embedding` columns are `FLOAT[3072]` for Gemini `gemini-embedding-001` embeddings
- `created_at` and `updated_at` timestamps on all tables
- Parquet export: Hive partitioned by domain under `data/parquet/domain=xxx/`

### DuckPGQ Property Graph
Define a property graph over the relational tables:

```sql
CREATE PROPERTY GRAPH coffee_graph
VERTEX TABLES (
    var_varieties,
    org_countries,
    org_regions,
    org_farms,
    proc_methods,
    roast_profiles,
    flav_attributes,
    shop_shops
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
GET  /api/v1/varieties/{id}              # Variety detail + connected graph
GET  /api/v1/varieties/{id}/flavor       # Flavor profile for a variety
GET  /api/v1/origins                     # List origins (countries/regions)
GET  /api/v1/origins/{id}                # Origin detail + farms + varieties grown
GET  /api/v1/origins/geo                 # GeoJSON feature collection for map
GET  /api/v1/roasting/profiles           # List roast profiles
GET  /api/v1/roasting/profiles/{id}      # Roast profile detail
GET  /api/v1/flavor/wheel                # Full flavor wheel hierarchy (JSON tree)
GET  /api/v1/flavor/attributes/{id}      # Attribute detail + linked varieties
GET  /api/v1/shops                       # List/filter shops
GET  /api/v1/shops/geo                   # GeoJSON for map layer
GET  /api/v1/shops/{id}                  # Shop detail + what they serve/source
GET  /api/v1/shops/nearby                # Nearby shops (lat/lng + radius)
GET  /api/v1/graph/traverse              # Graph traversal (start_node, depth, edge_types)
GET  /api/v1/graph/path                  # Shortest path between two entities
GET  /api/v1/search/semantic             # Semantic similarity search across all entities
GET  /api/v1/search/text                 # Full-text search
```

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
# Database
DUCKDB_PATH=./data/coffee_atlas.duckdb

# APIs
GEMINI_API_KEY=...
GOOGLE_PLACES_API_KEY=...          # Optional, for shop data

# Server
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Feature flags
ENABLE_EMBEDDINGS=true
ENABLE_GRAPH=true
```

---

## Bootstrap Sequence

When starting fresh, execute in this order:

1. `cd ontology && python scripts/validate_ontology.py` — confirm ontology consistency
2. `cd backend && python -m db.schema` — create DuckDB tables
3. `cd backend && python -m ingest.pipeline --stage lexicon` — load flavor taxonomy
4. `cd backend && python -m ingest.pipeline --stage varieties` — load WCR varieties
5. `cd backend && python -m ingest.pipeline --stage cqi` — load CQI cupping data
6. `cd backend && python -m ingest.pipeline --stage geocode` — geocode all origins
7. `cd backend && python -m ingest.pipeline --stage embeddings` — generate vector embeddings
8. `cd backend && python -m ingest.pipeline --stage graph` — build DuckPGQ edges
9. `uvicorn backend.main:app --reload` — start API
10. `cd frontend && npm run dev` — start Next.js

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
