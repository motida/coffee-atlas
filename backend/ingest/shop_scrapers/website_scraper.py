"""Scrape shop websites for description text.

Fetches each shop's homepage, extracts the first usable description from
<meta>/<og:>/<twitter:> tags, and writes it back to shop_shops.description.

Resumable via a JSONL log at data/cache/shop_scrape/<run_id>.jsonl — re-runs
skip shop_ids already in any prior log for the same scope.

Run:
    uv run -m backend.ingest.shop_scrapers.website_scraper \
        --city "New York,US" --city "Brooklyn,US" \
        --concurrency 10 --limit 50 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Iterable

import duckdb
import httpx

from backend.db.connection import get_connection
from backend.ingest.shop_scrapers.chains import is_nonspecialty_chain

USER_AGENT = "coffee-atlas-bot/0.1 (+https://huggingface.co/spaces/motidav/coffee-atlas-web)"
REQUEST_TIMEOUT = 10.0
MIN_DESCRIPTION_LEN = 30
MAX_DESCRIPTION_LEN = 1200
# Keep the scope slug (and thus the log filename) well under the 255-byte
# filename limit; long city lists fall back to a deterministic hash.
MAX_SCOPE_SLUG_BYTES = 150
CACHE_DIR = Path("data/cache/shop_scrape")
# Curated city frontier for the `descriptions` ingest stage (see read_cities).
CITIES_FILE = Path("data/raw/scrape_cities.txt")

# Generic CMS boilerplate that we treat as no-signal
JUNK_PATTERNS = [
    re.compile(r"^just another wordpress site\.?$", re.I),
    re.compile(r"^welcome to (your new|wix|squarespace)", re.I),
    re.compile(r"^this is an? example (page|description)", re.I),
    re.compile(r"^my (wordpress|wix|blog) site$", re.I),
]

# Description must contain at least one of these — filters squatted domains,
# parked pages, and content that drifted to non-coffee businesses.
# Latin terms use \b word boundaries; non-Latin scripts (Hebrew/Japanese/Thai)
# have no usable word boundary here, so they're a separate boundary-free
# alternation. Without these, non-English coffee pages (Tel Aviv, Tokyo,
# Bangkok…) get a meta description but fail this filter and are dropped as junk.
COFFEE_KEYWORDS = re.compile(
    r"\b(coffee|cafe|café|caffè|espresso|roast(?:ed|er|ing|ery)?|"
    r"latte|cappuccino|cortado|macchiato|americano|mocha|brew(?:ed|ing)?|"
    r"barista|drip|pour\s*over|cold\s*brew|beans?|cup(?:ping)?|"
    r"bakery|pastry|pastries|tea\s*shop|tea\s*house|"
    r"breakfast|brunch|deli)\b"
    r"|(?:קפה|אספרסו|"  # Hebrew: coffee, espresso
    r"コーヒー|珈琲|カフェ|エスプレッソ|焙煎|"  # Japanese: coffee, coffee, cafe, espresso, roast
    r"กาแฟ|คาเฟ่|เอสเพรสโซ)",  # Thai: coffee, cafe, espresso
    re.I,
)

META_PATTERNS = [
    re.compile(
        r'<meta[^>]+(?:name|property)\s*=\s*["\']\s*(?:og:description|twitter:description|description)\s*["\'][^>]*?content\s*=\s*["\']([^"\']{10,2000})["\']',
        re.I | re.S,
    ),
    re.compile(
        r'<meta[^>]+content\s*=\s*["\']([^"\']{10,2000})["\'][^>]*?(?:name|property)\s*=\s*["\']\s*(?:og:description|twitter:description|description)\s*["\']',
        re.I | re.S,
    ),
]


@dataclass
class ScrapeResult:
    shop_id: str
    url: str
    status: str  # "ok" | "empty" | "junk" | "http_error" | "fetch_error" | "skip"
    http_status: int | None
    description: str | None
    duration_ms: int
    error: str | None = None


def _normalize_url(url: str) -> str | None:
    url = url.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def extract_description(html: str, shop_name: str) -> str | None:
    """Pull the first usable description tag. Returns None if nothing usable."""
    for pat in META_PATTERNS:
        m = pat.search(html)
        if not m:
            continue
        text = unescape(m.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) < MIN_DESCRIPTION_LEN:
            continue
        if text.lower() == shop_name.lower():
            continue
        if any(p.search(text) for p in JUNK_PATTERNS):
            continue
        if not COFFEE_KEYWORDS.search(text):
            continue
        return text[:MAX_DESCRIPTION_LEN]
    return None


async def scrape_one(
    client: httpx.AsyncClient,
    shop_id: str,
    shop_name: str,
    url: str,
    sem: asyncio.Semaphore,
) -> ScrapeResult:
    started = time.monotonic()
    normalized = _normalize_url(url)
    if normalized is None:
        return ScrapeResult(shop_id, url, "skip", None, None, 0, "empty url")

    async with sem:
        try:
            r = await client.get(normalized, timeout=REQUEST_TIMEOUT, follow_redirects=True)
        except (httpx.HTTPError, OSError) as e:
            return ScrapeResult(
                shop_id,
                normalized,
                "fetch_error",
                None,
                None,
                int((time.monotonic() - started) * 1000),
                f"{type(e).__name__}: {e}"[:200],
            )

    duration_ms = int((time.monotonic() - started) * 1000)
    if r.status_code >= 400:
        return ScrapeResult(shop_id, normalized, "http_error", r.status_code, None, duration_ms)

    body = r.text[:200_000]  # cap HTML size we inspect
    desc = extract_description(body, shop_name)
    if desc is None:
        # Distinguish "empty" (no tag) from "junk" (tag but filtered)
        had_tag = any(p.search(body) for p in META_PATTERNS)
        status = "junk" if had_tag else "empty"
        return ScrapeResult(shop_id, normalized, status, r.status_code, None, duration_ms)

    return ScrapeResult(shop_id, normalized, "ok", r.status_code, desc, duration_ms)


def select_shops(
    conn: duckdb.DuckDBPyConnection,
    cities: list[tuple[str, str]],
    limit: int | None,
    already_done: set[str],
) -> list[tuple[str, str, str]]:
    """Return list of (shop_id, name, website) for the given (city, country) pairs.

    Non-specialty chains are skipped (they yield no useful description); specialty
    chains are kept, so the filtering happens in Python via ``is_nonspecialty_chain``
    rather than a SQL name blocklist.
    """
    if not cities:
        raise ValueError("at least one --city required")
    city_clauses = " OR ".join("(city = ? AND country = ?)" for _ in cities)
    params: list[object] = []
    for city, country in cities:
        params.extend([city, country])

    sql = f"""
        SELECT id, name, website
        FROM shop_shops
        WHERE description IS NULL
          AND website IS NOT NULL AND TRIM(website) != ''
          AND ({city_clauses})
        ORDER BY id
    """
    rows = conn.execute(sql, params).fetchall()
    rows = [r for r in rows if r[0] not in already_done and not is_nonspecialty_chain(r[1])]
    if limit is not None:
        rows = rows[:limit]
    return rows


def read_cities(path: str | Path = CITIES_FILE) -> list[tuple[str, str]]:
    """(city, country) pairs from the city-frontier file; the `descriptions` stage
    reads this. Blank lines and ``#`` comments are ignored; a missing file yields
    an empty list (the stage then no-ops). Each line is ``City,CC`` (e.g.
    ``New York,US``)."""
    p = Path(path)
    if not p.exists():
        return []
    cities: list[tuple[str, str]] = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        city, sep, country = line.partition(",")
        city, country = city.strip(), country.strip()
        if not sep or not city or not country:
            raise ValueError(f"scrape_cities line must be 'City,CC', got: {raw!r}")
        cities.append((city, country))
    return cities


def _scope_slug(cities: list[tuple[str, str]]) -> str:
    """A filesystem-safe, deterministic key for this city set.

    The slug names the resumable JSONL log. The readable form (city names joined
    by ``_``) is used as-is while it fits; longer lists (the filename overflows
    the 255-byte limit past ~8 cities) collapse to ``<firstcity>-and<N>more-<hash>``.
    The hash is stable for a given city set, so re-runs still resume.
    """
    raw = "_".join(f"{c}-{co}".replace(" ", "") for c, co in cities)
    if len(raw.encode("utf-8")) <= MAX_SCOPE_SLUG_BYTES:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    first = f"{cities[0][0]}-{cities[0][1]}".replace(" ", "")[:40]
    return f"{first}-and{len(cities) - 1}more-{digest}"


def load_done_ids(scope_key: str) -> set[str]:
    """Read every JSONL log matching this scope and collect already-processed ids."""
    done: set[str] = set()
    for path in CACHE_DIR.glob(f"{scope_key}__*.jsonl"):
        with path.open() as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                shop_id = record.get("shop_id")
                if shop_id is not None:
                    done.add(shop_id)
    return done


async def run(
    cities: list[tuple[str, str]],
    concurrency: int,
    limit: int | None,
    dry_run: bool,
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    scope_key = _scope_slug(cities)
    log_path = CACHE_DIR / f"{scope_key}__{int(time.time())}.jsonl"

    conn = get_connection()
    try:
        done = load_done_ids(scope_key)
        shops = select_shops(conn, cities, limit, done)
        if not shops:
            print("Nothing to scrape (all already done or no matches).")
            return

        print(f"Scope:        {cities}")
        print(f"Already done: {len(done):,}")
        print(f"To process:   {len(shops):,}")
        print(f"Concurrency:  {concurrency}")
        print(f"Log:          {log_path}")
        print(f"Dry run:      {dry_run}")
        print()

        if dry_run:
            print("Sample of shops that would be scraped:")
            for sid, name, url in shops[:10]:
                print(f"  {name[:40]:<40}  {url}")
            return

        sem = asyncio.Semaphore(concurrency)
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            http2=False,
            limits=httpx.Limits(max_connections=concurrency * 2),
        ) as client:
            tasks = [scrape_one(client, sid, name, url, sem) for sid, name, url in shops]

            counts: dict[str, int] = {}
            written = 0
            with log_path.open("w") as logf:
                for fut in asyncio.as_completed(tasks):
                    res = await fut
                    counts[res.status] = counts.get(res.status, 0) + 1
                    logf.write(json.dumps(res.__dict__) + "\n")
                    if res.status == "ok" and res.description is not None:
                        conn.execute(
                            "UPDATE shop_shops SET description = ?, updated_at = NOW() WHERE id = ?",
                            [res.description, res.shop_id],
                        )
                        written += 1
                    total = sum(counts.values())
                    if total % 50 == 0:
                        print(f"  {total:>5}/{len(shops)}  {counts}  wrote={written}")

        print()
        print(f"Done. {written:,} descriptions written.")
        print(f"Breakdown: {counts}")
    finally:
        conn.close()


def _parse_city(spec: str) -> tuple[str, str]:
    city, _, country = spec.partition(",")
    if not city or not country:
        raise argparse.ArgumentTypeError(f"--city must be 'City,CC' (got {spec!r})")
    return city.strip(), country.strip()


def main(argv: Iterable[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--city",
        action="append",
        type=_parse_city,
        required=True,
        help="City,Country pair. Repeatable. E.g. --city 'New York,US'",
    )
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--limit", type=int, default=None, help="Cap total shops processed")
    p.add_argument("--dry-run", action="store_true", help="Print scope, don't fetch")
    args = p.parse_args(list(argv) if argv is not None else None)
    asyncio.run(run(args.city, args.concurrency, args.limit, args.dry_run))


if __name__ == "__main__":
    main()
