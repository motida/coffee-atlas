# Adding a Country / City of Shops & Roasters

How to expand the map into a new region — load its coffee shops, scrape shop
descriptions, add its roasters, and flag the specialty ones.

This is a runbook for the **network-heavy ingest stages** that `just bootstrap`
deliberately skips. Each stage is idempotent and resumable, so re-running is
safe. For the full pipeline overview see [DATA.md](DATA.md); for the data-store
split (read-only DuckDB content vs. Postgres user data) see
[ARCHITECTURE.md](ARCHITECTURE.md).

> **Where data lives.** Shops and roasters are content, so they go into the
> read-only DuckDB store (`shop_shops`, `roast_roasters`, `prod_products`,
> `edges_*`). None of this touches Postgres. After ingesting locally you ship
> the rebuilt DB by uploading it to the Hugging Face dataset
> `motidav/coffee-atlas-db` and rebuilding the Render image (see "Shipping a
> new DB" in [deploy/render/README.md](../deploy/render/README.md)) — code
> changes auto-deploy, but **data changes do not**.

---

## TL;DR — the order

For a brand-new region, run the stages in this order. Steps 3–7 are optional
depending on whether you're also adding roasters.

```bash
# 1. Load the region's coffee POIs (set a bounding box)
OVERTURE_BBOX=<xmin,ymin,xmax,ymax> just ingest shops

# 2. Scrape shop homepage descriptions (the main specialty signal)
#    First append the region's cities to data/raw/scrape_cities.txt
just ingest descriptions

# 3. (optional) Add roasters — append site URLs to data/raw/roaster_sites.txt
just ingest products

# 4. Backfill roaster location labels (curated map + derive-from-shops)
just ingest roaster_locations

# 5. (Re)build graph edges, incl. edges_shop_roaster
just ingest graph

# 6. Flag specialty shops (reads edges_shop_roaster, so must follow graph)
just ingest specialty

# 7. (optional) Stage new candidate roaster sites for review
just ingest roaster_discovery
```

**Hard ordering constraints** (don't reshuffle these):

- `descriptions` needs `shops` to have run first.
- `roaster_locations` *derive* source needs both `shops` **and** `products`.
- `graph` needs `products` **and** `shops`.
- `specialty` needs `graph` (it reads `edges_shop_roaster`).
- `roaster_discovery` needs `specialty` (it reads `is_specialty`).

> `just ingest-all` / `just bootstrap` run only the **local** stages and skip
> every stage on this page. Run these explicitly. `python -m
> backend.ingest.pipeline --all` *does* run all 16, network stages included.

---

## Step 1 — Load shops for the region (`shops` stage)

The `shops` stage pulls coffee POIs (`coffee_shop`, `cafe`) from the
[Overture Maps](https://overturemaps.org) `places` theme straight off public S3
via DuckDB `httpfs` + `spatial`. No API key — it's ODbL open data. It
upserts `shop_shops` idempotently (source fields refresh; curated enrichment
like `rating`/`description`/`is_specialty` and `created_at` are preserved).

**Scope by bounding box, not country name.** Overture is ~10 GB of GeoParquet;
scanning it globally is impractical, so you pass a bounding box and DuckDB pushes
the predicate into parquet row-group statistics to read only the matching slice.
Set `OVERTURE_BBOX` as **`xmin,ymin,xmax,ymax`** (longitude,latitude — exactly
four floats, comma-separated):

```bash
OVERTURE_BBOX=-10,35,30,60     just ingest shops   # Western Europe
OVERTURE_BBOX=128,30,146,46    just ingest shops   # Japan
OVERTURE_BBOX=139.55,35.55,139.90,35.80 just ingest shops   # just Tokyo
```

The default (when `OVERTURE_BBOX` is unset) is the contiguous US:
`-125.0,24.0,-66.0,50.0` (~150K coffee shops, ~2 min over a residential
connection). Pick a box with a tool like [bboxfinder.com](http://bboxfinder.com)
— a tight box keeps the scan fast.

`OVERTURE_BBOX` / `OVERTURE_RELEASE` are read from the **environment** by the
loader (`backend/ingest/overture_shops_loader.py`), not from `backend/config.py`.
The `justfile` has `set dotenv-load`, so you can either prefix the command (as
above) or add the line to `.env`.

**If the stage errors with "No parquet files found"**, the pinned Overture
release has aged out of S3. Check the
[release history](https://docs.overturemaps.org/release/) and bump it:

```bash
OVERTURE_RELEASE=2026-06-17.0 OVERTURE_BBOX=<box> just ingest shops
```

### What you get

Each shop row carries Overture's own `locality` as `city` and an **ISO alpha-2
country code** as `country` (e.g. `US`, `GB`, `IL`, `JP`). You need that exact
spelling for the next step — note that non-Latin localities are stored in the
local script (Israeli cities are in Hebrew).

---

## Step 2 — Scrape shop descriptions (`descriptions` stage)

A shop's homepage `<meta>` / Open Graph / Twitter description is the **main
signal** the `specialty` stage uses. This stage fetches it for shops in the
cities you list.

### Edit `data/raw/scrape_cities.txt`

One `City,CC` per line (`CC` = ISO alpha-2 country code). `#` comments and blank
lines are ignored. **The city string must match `shop_shops.city` (Overture's
`locality`) verbatim** — including local-script spellings and odd spacing.

```
London,GB
New York,US
Tel Aviv,IL
תל אביב - יפו,IL          # Israeli localities are stored in Hebrew in Overture
Tokyo,JP                  # no-op until the shops bbox covers JP
```

> A city line that doesn't match any loaded shop is simply a no-op — the
> `descriptions` stage only touches rows where `description IS NULL AND website
> IS NOT NULL`, and skips known non-specialty chains. If nothing scrapes, double
> check the city spelling against what `shops` actually loaded.

### Run it

```bash
just ingest descriptions
```

The scrape is resumable (JSONL logs under `data/cache/shop_scrape/`). It only
keeps descriptions that contain a coffee keyword (the keyword list includes
Hebrew/Japanese/Thai terms). An empty city list makes the stage a no-op.

---

## Step 3 — Add roasters (`products` stage) *(optional)*

Roasters enter the DB by scraping their **product catalogs**. The scraper reads
a Shopify storefront (`/products.json`), else the WooCommerce Store API, else
embedded JSON-LD; drops non-coffee items (tea, merch, gear); attributes each
site's roaster as the modal Shopify `vendor`; and upserts `roast_roasters` +
inserts `prod_products`.

### Edit `data/raw/roaster_sites.txt`

One site root URL per line. `#` comments and blanks ignored. This is the crawl
frontier.

```
https://www.blackwhiteroasters.com
https://onyxcoffeelab.com
https://sey.coffee
```

### Run it

```bash
just ingest products
```

Resumable (JSONL under `data/cache/product_scrape/`). **Product graph edges are
not built here** — the `graph` stage (step 5) resolves them.

> **Naming gotcha.** Merch-heavy or WooCommerce-no-vendor sites can mis-name a
> roaster (e.g. an origin-country name like "Peru", or a bare domain). Fix with
> `_SITE_ROASTER_OVERRIDES` / `_VENDOR_ALIASES` in the product loader, re-load,
> then delete the orphaned roaster. See the project memory note on roaster
> vendor overrides.
>
> **Reload hazard.** Re-running `products` clear+reinserts `prod_products` and
> can wipe `description_embedding`s; roaster ids are FK-referenced, so don't
> blindly re-run the `roasting` stage on a populated DB. For a small additive
> change prefer adding roasters by name and re-running `graph`, rather than a
> full re-scrape. See the related memory notes before doing a large reload.

---

## Step 4 — Backfill roaster locations (`roaster_locations` stage)

Roasters added by the scrape arrive with **no location**. This stage fills
`roast_roasters.location` from two sources, curated-first. Both only `UPDATE`
(never insert/delete), fill blanks only, and are idempotent.

1. **Curated map (authoritative).** `data/raw/roaster_locations.json` —
   `name → "City, Country"`. Keys must match `roast_roasters.name` **verbatim**;
   use full country names (not ISO codes). The **last comma segment (country) is
   the grouping key** on the frontend Roasters page; city is display-only.

   ```json
   {
     "_meta": { "description": "...", "source": "..." },
     "locations": {
       "Assembly Coffee London": "London, United Kingdom",
       "Onyx Coffee Lab": "Rogers, United States",
       "Subtext Coffee Roasters": "Toronto, Canada"
     }
   }
   ```

2. **Derive from shops (automatic fallback).** For roasters still blank, the
   loader matches the roaster's `website` host to a `shop_shops.website` (the
   roaster's own Overture cafe), takes that shop's city + ISO country,
   normalizes the ISO code to a full country name via
   `data/raw/country_centroids.json`, and writes `"City, Country"`. This is why
   the derive source needs **both** `shops` and `products` to have run.

```bash
just ingest roaster_locations
```

Unmatched curated names are reported in the output — add them to the JSON or let
the derive step catch them.

---

## Step 5 — Rebuild graph edges (`graph` stage)

Resolves product → variety/flavor/country/region/roast-profile content edges and
roaster → product, shop → roaster, shop → product → variety structural edges
(including `edges_shop_roaster`, which the next step depends on).

```bash
just ingest graph
```

Run this any time you've changed shops, products, or roasters.

---

## Step 6 — Flag specialty shops (`specialty` stage)

The app surfaces **only specialty shops**. This stage sets
`shop_shops.is_specialty` + `specialty_score` from a multi-signal heuristic
(`backend/ingest/shop_specialty.py`):

```
score = 0.6  curated-roaster match (row in edges_shop_roaster)
      + 0.3  scraper-vetted coffee description present
      + 0.2  roasts_in_house = TRUE
      + 0.2  rating >= 4.0
      + 0.1  has its own website
is_specialty = specialty_chain (allowlist → always true)
            OR (NOT nonspecialty_chain AND score >= 0.2)
```

Chain allow/block lists live in `backend/ingest/shop_scrapers/chains.py`
(keeps Blue Bottle / Stumptown; drops big non-specialty chains). It reads
`edges_shop_roaster`, so **it must run after `graph`**.

```bash
just ingest specialty
```

A non-US region with no scraped descriptions and no curated-roaster matches may
score everything below threshold — meaning shops load but none show on the map.
The fix is coverage: scrape descriptions (step 2) and/or add roasters whose cafes
are in that region.

---

## Step 7 — Grow the roaster frontier (`roaster_discovery` stage) *(optional)*

Finds new roasters without hand-curation. It probes the websites of specialty /
`roasts_in_house` shops in `shop_shops` for a public catalog (Shopify or
WooCommerce), skipping any host already in `roaster_sites.txt` or already a
`roast_roasters.website`.

```bash
just ingest roaster_discovery
```

It writes **no DB rows**. Confirmed hits go to a review staging file,
`data/processed/roaster_site_candidates.txt`, in the same format as
`roaster_sites.txt` (a `#` annotation line + the bare URL):

```
# Some Roaster — Portland, United States — shopify (42 products)
https://someroaster.com
```

**Review → promote workflow:** a person vets the candidates, then **manually
moves approved URLs into `data/raw/roaster_sites.txt`**. Then loop back to
**step 3** (`products` → `roaster_locations` → `graph`) to ingest them.

---

## Quick reference — what to edit for what

| To add… | Edit | Then run |
|---------|------|----------|
| A region's **shops** | `OVERTURE_BBOX=xmin,ymin,xmax,ymax` (env / inline) | `OVERTURE_BBOX=… just ingest shops` |
| A city's **descriptions** | `data/raw/scrape_cities.txt` — append `City,CC` (exact Overture spelling) | `just ingest descriptions` |
| A **roaster** | `data/raw/roaster_sites.txt` — append site URL | `just ingest products` |
| A roaster's **location label** | `data/raw/roaster_locations.json` — add `"Name": "City, Country"` | `just ingest roaster_locations` |

After any of these, re-run `graph` (and `specialty` if shops changed), then ship
the rebuilt DB: compact it (`backend/db/compact.py`), upload it to the
`motidav/coffee-atlas-db` HF dataset, and rebuild the Render image (see
"Shipping a new DB" in [deploy/render/README.md](../deploy/render/README.md)).

---

## Embeddings (optional, for search/recommendations)

New shops/products won't appear in semantic search or recommendations until
they're embedded. `shop_shops` is **skipped by default** (hundreds of thousands
of rows, far beyond the Gemini free tier). Embed a freshly loaded domain
explicitly:

```bash
uv run python -m backend.ingest.pipeline --stage embeddings --tables prod_products
uv run python -m backend.ingest.pipeline --stage embeddings --tables shop_shops   # large — opt in
```

Requires `GEMINI_API_KEY` and `ENABLE_EMBEDDINGS=true`.
