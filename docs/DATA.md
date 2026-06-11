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

## Ingest pipeline

Run stages individually or all at once. Order matters: the flavor taxonomy
must exist before varieties can link to it; coordinates must exist before
the map can render; embeddings require text fields to be populated.

```bash
uv run python -m backend.ingest.pipeline --stage lexicon     # Flavor taxonomy
uv run python -m backend.ingest.pipeline --stage varieties   # WCR varieties
uv run python -m backend.ingest.pipeline --stage cqi         # CQI cupping data
uv run python -m backend.ingest.pipeline --stage geocode     # Geocode origins
uv run python -m backend.ingest.pipeline --stage shops       # Coffee shops (Overture, S3)
uv run python -m backend.ingest.pipeline --stage distribution # Certifications, importers, trade routes
uv run python -m backend.ingest.pipeline --stage roasting    # Roast profiles + suitability edges
uv run python -m backend.ingest.pipeline --stage embeddings  # Vector embeddings
uv run python -m backend.ingest.pipeline --stage graph       # Build graph edges
uv run python -m backend.ingest.pipeline --all               # Run all stages
```

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
OVERTURE_RELEASE=2026-04-15.0 just ingest shops
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
