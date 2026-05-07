# data/raw

Source files used by the ingest pipeline. Most files in this directory are
gitignored; the ones committed here are small reference datasets needed for a
clean-room bootstrap.

## Committed files

- `wcr_varieties.json` — World Coffee Research varieties catalog snapshot.
  Source: `varieties.worldcoffeeresearch.org` (CC BY-NC-ND 4.0).
- `scaa_2016_flavor_wheel.json` — SCAA 2016 / WCR Sensory Lexicon hierarchy
  extracted from the interactive wheel at `notbadcoffee.com/flavor-wheel-en/`.
- `country_centroids.json` — country centroid coordinates used by the
  geocoding stage as a fallback when a region has no resolved coordinates.
- `cqi_arabica.csv`, `cqi_robusta.csv` — CQI cupping data via the Kaggle
  dataset `volpatto/coffee-quality-database-from-cqi`, originally from
  coffeeinstitute.org.
