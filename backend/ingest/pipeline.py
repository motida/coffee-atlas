"""Orchestrates the full data ingest pipeline. Run with: python -m backend.ingest.pipeline"""

import argparse
import sys

from backend.config import settings

STAGES = ["lexicon", "varieties", "cqi", "geocode", "shops", "embeddings", "graph"]


def run_stage(stage: str) -> None:
    if stage == "lexicon":
        from backend.ingest.wcr_lexicon_loader import load_wcr_lexicon

        count = load_wcr_lexicon(settings.DUCKDB_PATH)
        print(f"Loaded {count} flavor attributes")

    elif stage == "varieties":
        from backend.ingest.wcr_varieties_loader import load_wcr_varieties

        count = load_wcr_varieties(settings.DUCKDB_PATH)
        print(f"Loaded {count} varieties")

    elif stage == "cqi":
        from backend.ingest.cqi_loader import load_cqi_data

        counts = load_cqi_data(settings.DUCKDB_PATH)
        print(
            f"Loaded {counts.countries} countries, {counts.regions} regions, "
            f"{counts.farms} farms, {counts.methods} processing methods"
        )

    elif stage == "geocode":
        from backend.ingest.geocode_stage import run_geocode

        counts = run_geocode(settings.DUCKDB_PATH)
        print(
            f"Countries: {counts.countries_resolved} resolved, "
            f"{counts.countries_unresolved} unresolved | "
            f"Regions: {counts.regions_resolved} resolved, "
            f"{counts.regions_unresolved} unresolved"
        )

    elif stage == "shops":
        from backend.ingest.overture_shops_loader import load_overture_shops

        counts = load_overture_shops(settings.DUCKDB_PATH)
        print(f"Inserted {counts.inserted} shops from {counts.fetched} Overture candidates")

    elif stage == "embeddings":
        if not settings.ENABLE_EMBEDDINGS:
            print("Embeddings disabled (ENABLE_EMBEDDINGS=false)")
            return
        if not settings.GEMINI_API_KEY:
            print("Skipped: GEMINI_API_KEY not set")
            return
        from backend.ingest.embeddings_stage import run_embeddings

        results = run_embeddings()
        for table, count in results.items():
            print(f"  {table}: {count} rows embedded")
        total = sum(results.values())
        print(f"Total: {total} rows embedded")

    elif stage == "graph":
        from backend.ingest.graph_stage import run_graph_stage

        counts = run_graph_stage(settings.DUCKDB_PATH)
        print(
            f"country->region: {counts.country_region}, "
            f"region->farm: {counts.region_farm}, "
            f"variety<->flavor: {counts.variety_flavor}, "
            f"property_graph: {'ok' if counts.property_graph_ok else 'skipped'}"
        )

    else:
        print(f"Unknown stage: {stage}")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coffee Atlas data ingest pipeline")
    parser.add_argument("--stage", choices=STAGES, help="Run a specific ingest stage")
    parser.add_argument("--all", action="store_true", help="Run all stages in order")
    args = parser.parse_args()

    if args.all:
        for stage in STAGES:
            print(f"\n--- Running stage: {stage} ---")
            try:
                run_stage(stage)
            except NotImplementedError as e:
                print(f"  Skipped: {e}")
    elif args.stage:
        run_stage(args.stage)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
