"""Orchestrates the full data ingest pipeline. Run with: python -m backend.ingest.pipeline"""

import argparse
import sys
from collections.abc import Callable

from backend.config import settings


def _run_lexicon(tables: list[str] | None = None) -> None:
    from backend.ingest.wcr_lexicon_loader import load_wcr_lexicon

    count = load_wcr_lexicon(settings.DUCKDB_PATH)
    print(f"Loaded {count} flavor attributes")


def _run_varieties(tables: list[str] | None = None) -> None:
    from backend.ingest.wcr_varieties_loader import load_wcr_varieties

    count = load_wcr_varieties(settings.DUCKDB_PATH)
    print(f"Loaded {count} varieties")


def _run_cqi(tables: list[str] | None = None) -> None:
    from backend.ingest.cqi_loader import load_cqi_data

    counts = load_cqi_data(settings.DUCKDB_PATH)
    print(
        f"Loaded {counts.countries} countries, {counts.regions} regions, "
        f"{counts.farms} farms, {counts.methods} processing methods"
    )
    print(
        f"Variety edges → country: {counts.country_variety_edges}, "
        f"region: {counts.region_variety_edges}, farm: {counts.farm_variety_edges}, "
        f"processing: {counts.variety_processing_edges} "
        f"({counts.unmatched_varieties} unmatched)"
    )


def _run_processing_descriptions(tables: list[str] | None = None) -> None:
    from backend.ingest.processing_descriptions_loader import load_processing_descriptions

    counts = load_processing_descriptions(settings.DUCKDB_PATH)
    print(
        f"Described {counts.methods_updated} processing methods "
        f"across {counts.categories_applied} categories"
    )
    if counts.skipped_categories:
        print(f"  Skipped categories (no method present): {counts.skipped_categories}")


def _run_processing_flavor(tables: list[str] | None = None) -> None:
    from backend.ingest.processing_flavor_loader import load_processing_flavor

    counts = load_processing_flavor(settings.DUCKDB_PATH)
    print(f"Seeded {counts.edges} processing→flavor edges across {counts.methods_matched} methods")
    if counts.skipped_methods:
        print(f"  Skipped method categories (not found): {counts.skipped_methods}")
    if counts.skipped_flavors:
        print(f"  Skipped flavors (not found): {counts.skipped_flavors}")


def _run_geocode(tables: list[str] | None = None) -> None:
    from backend.ingest.geocode_stage import run_geocode

    counts = run_geocode(settings.DUCKDB_PATH)
    print(
        f"Countries: {counts.countries_resolved} resolved, "
        f"{counts.countries_unresolved} unresolved | "
        f"Regions: {counts.regions_resolved} resolved, "
        f"{counts.regions_unresolved} unresolved"
    )


def _run_shops(tables: list[str] | None = None) -> None:
    from backend.ingest.overture_shops_loader import load_overture_shops

    counts = load_overture_shops(settings.DUCKDB_PATH)
    print(f"Inserted {counts.inserted} shops from {counts.fetched} Overture candidates")


def _run_descriptions(tables: list[str] | None = None) -> None:
    import asyncio

    from backend.ingest.shop_scrapers.website_scraper import read_cities, run

    cities = read_cities()
    if not cities:
        print("Skipped: no cities configured (data/raw/scrape_cities.txt empty/absent)")
        return
    print(f"Scraping shop descriptions across {len(cities)} cities (resumable)...")
    asyncio.run(run(cities, concurrency=16, limit=None, dry_run=False))


def _run_distribution(tables: list[str] | None = None) -> None:
    from backend.ingest.distribution_loader import load_distribution

    counts = load_distribution(settings.DUCKDB_PATH)
    print(
        f"Loaded {counts.certifications} certifications, "
        f"{counts.importers} importers, {counts.trade_routes} trade routes "
        f"(+{counts.countries_added} new countries)"
    )
    if counts.unresolved:
        print(f"  Unresolved: {len(counts.unresolved)} entries")


def _run_roasting(tables: list[str] | None = None) -> None:
    from backend.ingest.roasting_loader import load_roasting

    counts = load_roasting(settings.DUCKDB_PATH)
    print(
        f"Loaded {counts.profiles} roast profiles, {counts.roasters} roasters, "
        f"{counts.roast_variety_edges} roast→variety edges"
    )


def _run_products(tables: list[str] | None = None) -> None:
    import asyncio

    from backend.ingest.products_loader import load_from_file
    from backend.ingest.shop_scrapers.product_scraper import read_sites, scrape

    sites = read_sites()
    print(f"Scraping {len(sites)} roaster sites (resumable)...")
    asyncio.run(scrape(sites, concurrency=4, max_products=250, run_id="pipeline", dry_run=False))
    counts = load_from_file()
    print(
        f"Loaded {counts.products} products from {counts.roasters} roasters "
        f"({counts.dropped_non_coffee} non-coffee dropped). "
        f"Product edges are built in the graph stage."
    )


def _run_embeddings(tables: list[str] | None = None) -> None:
    if not settings.ENABLE_EMBEDDINGS:
        print("Embeddings disabled (ENABLE_EMBEDDINGS=false)")
        return
    if not settings.GEMINI_API_KEY:
        print("Skipped: GEMINI_API_KEY not set")
        return
    from backend.ingest.embeddings_stage import TARGETS, run_embeddings

    results = run_embeddings(tables=tables)
    for table, count in results.items():
        print(f"  {table}: {count} rows embedded")
    if tables is None:
        for t in TARGETS:
            if not t.embed_by_default:
                print(f"  {t.table}: skipped by default (run with --tables {t.table})")
    total = sum(results.values())
    print(f"Total: {total} rows embedded")


def _run_graph(tables: list[str] | None = None) -> None:
    from backend.ingest.graph_stage import run_graph_stage

    counts = run_graph_stage(settings.DUCKDB_PATH)
    print(
        f"country->region: {counts.country_region}, "
        f"region->farm: {counts.region_farm}, "
        f"variety<->flavor: {counts.variety_flavor}, "
        f"product_edges: {counts.product_edges}, "
        f"property_graph: {'ok' if counts.property_graph_ok else 'skipped'}"
    )


def _run_specialty(tables: list[str] | None = None) -> None:
    from backend.ingest.shop_specialty import compute_specialty

    counts = compute_specialty(settings.DUCKDB_PATH)
    print(f"Specialty shops: {counts.specialty}/{counts.total} flagged")


# Stage name → handler, in pipeline execution order. STAGES is derived from this
# mapping, so the CLI choices and the dispatch can never drift apart. Adding a
# stage means writing one handler and adding one entry here.
STAGE_REGISTRY: dict[str, Callable[[list[str] | None], None]] = {
    "lexicon": _run_lexicon,
    "varieties": _run_varieties,
    "cqi": _run_cqi,
    "processing_descriptions": _run_processing_descriptions,
    "processing_flavor": _run_processing_flavor,
    "geocode": _run_geocode,
    "shops": _run_shops,
    "descriptions": _run_descriptions,
    "distribution": _run_distribution,
    "roasting": _run_roasting,
    "products": _run_products,
    "embeddings": _run_embeddings,
    "graph": _run_graph,
    "specialty": _run_specialty,
}

STAGES = list(STAGE_REGISTRY)


def run_stage(stage: str, tables: list[str] | None = None) -> None:
    handler = STAGE_REGISTRY.get(stage)
    if handler is None:
        print(f"Unknown stage: {stage}")
        sys.exit(1)
    handler(tables)


def main() -> None:
    parser = argparse.ArgumentParser(description="Coffee Atlas data ingest pipeline")
    parser.add_argument("--stage", choices=STAGES, help="Run a specific ingest stage")
    parser.add_argument("--all", action="store_true", help="Run all stages in order")
    parser.add_argument(
        "--tables",
        nargs="+",
        metavar="TABLE",
        help="Embeddings stage only: restrict to these target tables "
        "(e.g. --tables roast_profiles)",
    )
    args = parser.parse_args()

    if args.tables and args.stage != "embeddings":
        parser.error("--tables only applies to --stage embeddings")

    if args.all:
        for stage in STAGES:
            print(f"\n--- Running stage: {stage} ---")
            try:
                run_stage(stage)
            except NotImplementedError as e:
                print(f"  Skipped: {e}")
    elif args.stage:
        run_stage(args.stage, tables=args.tables)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
