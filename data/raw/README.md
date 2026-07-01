# data/raw

Source files used by the ingest pipeline. Most files in this directory are
gitignored; the ones committed here are small reference datasets needed for a
clean-room bootstrap.

## Committed files

Reference datasets and curation inputs:

- `wcr_varieties.json` — World Coffee Research varieties catalog snapshot.
  Source: `varieties.worldcoffeeresearch.org` (CC BY-NC-ND 4.0).
- `scaa_2016_flavor_wheel.json` — SCAA 2016 / WCR Sensory Lexicon hierarchy
  extracted from the interactive wheel at `notbadcoffee.com/flavor-wheel-en/`.
- `country_centroids.json` — country centroid coordinates used by the
  geocoding stage as a fallback when a region has no resolved coordinates,
  and to expand Overture ISO country codes to full names in
  `roaster_locations`.
- `cqi_arabica.csv`, `cqi_robusta.csv` — CQI cupping data via the Kaggle
  dataset `volpatto/coffee-quality-database-from-cqi`, originally from
  coffeeinstitute.org.
- `distribution_seed.json` — hand-curated certifications, importers, and trade
  routes for the `distribution` stage.
- `roasting_seed.json` — hand-curated roast profiles and notable roasters for
  the `roasting` stage.
- `processing_flavor_seed.json` — hand-mapped ProcessingMethod → FlavorAttribute
  table for the `processing_flavor` stage.

Roaster / shop scraper inputs:

- `roaster_sites.txt` — the crawl frontier for the `products` scrape: one
  storefront root per line (Shopify `/products.json` or WooCommerce Store API).
  Seeded by hand and grown via the `roaster_discovery` stage, which probes
  specialty shops for public catalogs and stages confirmed hits for review
  before they are promoted here.
- `roaster_locations.json` — curated `roaster name → "City, Country"` map
  (authoritative source for the `roaster_locations` stage, applied before the
  shop-website auto-derive fallback).
- `scrape_cities.txt` — city list for the `descriptions` stage (shop-homepage
  scrape that feeds the `specialty` heuristic). No-op when empty.
