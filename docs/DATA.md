# Data Sources & Ingest Pipeline

## Data sources

| Source | Coverage |
|--------|----------|
| [WCR Varieties Catalog](https://varieties.worldcoffeeresearch.org) | 100+ varieties with agronomic data |
| [WCR Sensory Lexicon 2.0](https://worldcoffeeresearch.org/resources/sensory-lexicon) | 110 flavor attributes |
| [CQI Database](https://www.kaggle.com/datasets/volpatto/coffee-quality-database-from-cqi) | ~1,300 cupping reviews |
| [ICO Market Reports](https://ico.org) | Trade and production statistics |
| [FAOSTAT](https://www.fao.org/faostat) | Country-level trade flows |
| [Overture Maps](https://overturemaps.org) | Coffee shop POI data |
| Hand-curated roasting seed (`data/raw/roasting_seed.json`) | 11 canonical roast profiles + 10 notable roasters |
| Roaster product catalogs (Shopify storefront JSON + JSON-LD) | Coffee product listings with tasting notes, scraped from the roaster frontier (`data/raw/roaster_sites.txt`) — hand-seeded and grown by the `roaster_discovery` stage |

## Ingest pipeline

Run stages individually or all at once. Order matters: the flavor taxonomy
must exist before varieties can link to it; coordinates must exist before
the map can render; embeddings require text fields to be populated.

```bash
uv run python -m backend.ingest.pipeline --stage lexicon                 # Flavor taxonomy
uv run python -m backend.ingest.pipeline --stage varieties               # WCR varieties
uv run python -m backend.ingest.pipeline --stage cqi                     # CQI cupping data
uv run python -m backend.ingest.pipeline --stage processing_descriptions # Curated method descriptions
uv run python -m backend.ingest.pipeline --stage processing_flavor       # Processing→flavor edges
uv run python -m backend.ingest.pipeline --stage geocode                 # Geocode origins
uv run python -m backend.ingest.pipeline --stage shops                   # Coffee shops (Overture, S3) [network]
uv run python -m backend.ingest.pipeline --stage descriptions            # Scrape shop homepages for descriptions [network]
uv run python -m backend.ingest.pipeline --stage distribution            # Certifications, importers, trade routes
uv run python -m backend.ingest.pipeline --stage roasting                # Roast profiles + suitability edges
uv run python -m backend.ingest.pipeline --stage products                # Scrape roaster product catalogs [network]
uv run python -m backend.ingest.pipeline --stage roaster_locations       # Backfill roaster locations (curated + shop-derived)
uv run python -m backend.ingest.pipeline --stage embeddings              # Vector embeddings
uv run python -m backend.ingest.pipeline --stage graph                   # Build graph edges
uv run python -m backend.ingest.pipeline --stage specialty               # Flag specialty shops (reads graph)
uv run python -m backend.ingest.pipeline --stage roaster_discovery       # Discover new roaster storefronts [network]
uv run python -m backend.ingest.pipeline --all                           # Run all stages in order
```

`pipeline --all` runs every stage in order. `just bootstrap` / `just ingest-all`
run only the local stages — they **exclude** the network-heavy ones (`shops`,
`descriptions`, `products`, `roaster_discovery`) and the stages that are a no-op
without shop/product data (`roaster_locations`, `specialty`). Run those
explicitly; see [Roaster frontier](#roaster-frontier--discovery) below for the
products/roaster flow.

The embeddings stage accepts `--tables` to restrict the run to specific
target tables — useful for embedding one freshly loaded domain:

```bash
uv run python -m backend.ingest.pipeline --stage embeddings --tables roast_profiles
```

`shop_shops` is **skipped by default** (~215K rows, far beyond the Gemini
free tier's ~1K requests/day) and only runs when named explicitly:

```bash
uv run python -m backend.ingest.pipeline --stage embeddings --tables shop_shops
```

## Overture shops stage

The `shops` stage is **not** part of `just bootstrap` — it queries the
Overture Maps `places` theme directly from public S3 (~10 GB across 16
GeoParquet files) via DuckDB's `httpfs` + `spatial` extensions.

A bbox filter pushes predicates into parquet row-group statistics so we
read only the matching slice. The default bbox covers the contiguous US
(~150K coffee shops, ~2 minutes over a residential connection).

To scope to a different region, set `OVERTURE_BBOX` (`xmin,ymin,xmax,ymax`):

```bash
OVERTURE_BBOX=-10,35,30,60 just ingest shops      # Western Europe
OVERTURE_BBOX=128,30,146,46 just ingest shops     # Japan
```

Overture deletes older releases from S3, so `OVERTURE_RELEASE` may need a
bump if the pinned default disappears. Check
[overture release history](https://docs.overturemaps.org/release/) and set:

```bash
OVERTURE_RELEASE=2026-06-17.0 just ingest shops
```

## Roasting stage

The `roasting` stage loads `data/raw/roasting_seed.json` — a hand-curated
reference set of 11 canonical roast profiles (Cinnamon through Italian,
plus Nordic Light, Omni, and Classic Espresso) and 10 notable specialty
roasters. Values are representative midpoints from public roasting
literature, not any roaster's proprietary curve.

Each profile carries a `suitable_for` rule (species list + optional
`min_optimal_altitude`) that the loader resolves against `var_varieties`
to derive `edges_roast_variety` (RoastProfile → suitableFor → Variety),
so run the `varieties` stage first.

## Processing stages

Two small curation stages enrich the processing methods loaded by `cqi`:

- `processing_descriptions` attaches curated prose to each `proc_methods` row.
- `processing_flavor` seeds `edges_processing_flavor` (ProcessingMethod →
  enhances/diminishes → FlavorAttribute) from a hand-mapped table, so it must
  run after `lexicon` and `cqi`.

Both are local and fast, and run as part of `just ingest-all` / `just bootstrap`.

## Products stage

The `products` stage scrapes coffee product catalogs from the roaster frontier
in `data/raw/roaster_sites.txt` (Shopify storefront JSON + embedded JSON-LD),
drops non-coffee items, and loads the result into `prod_products`. Like `shops`,
it is **network-heavy and excluded from `just bootstrap`** — run it explicitly:

```bash
uv run python -m backend.ingest.pipeline --stage products
```

The scrape is resumable. Product graph edges are **not** built here — the
`graph` stage resolves them: content edges (product → variety / flavor /
country / region / roast profile, matched conservatively against the loaded
entity tables) and structural edges (roaster → product, shop → roaster, and
shop → product → variety, which finally populates `edges_shop_variety`). Run
`graph` after both `products` and `shops`.

Roasters scraped here arrive with no location, so run `roaster_locations` after
`products` to backfill `roast_roasters.location` (curated map first, then derive
from each roaster's own Overture shop), and re-run `embeddings --tables
prod_products` (the product reload clears `description_embedding`) before `graph`.

## Roaster frontier & discovery

The `products` scrape only crawls hosts listed in `data/raw/roaster_sites.txt`.
That frontier started as a small hand-curated seed; the `roaster_discovery`
stage grows it without per-URL curation:

```bash
uv run python -m backend.ingest.pipeline --stage roaster_discovery
```

It reads specialty (or `roasts_in_house`) shops from `shop_shops` that have a
website, drops any host already in the frontier or already a
`roast_roasters.website`, de-duplicates by host, and probes each remaining host
for a public catalog (reusing the products scraper's Shopify/WooCommerce
fetchers + coffee filter). Confirmed hits are written to a **review staging
file**, `data/processed/roaster_site_candidates.txt` (same format as
`roaster_sites.txt`) — it writes **no** DB rows and does not edit the frontier.
A person vets the candidates and moves approved URLs into `roaster_sites.txt`,
after which the normal `products` → `roaster_locations` → `embeddings` → `graph`
flow ingests them.
