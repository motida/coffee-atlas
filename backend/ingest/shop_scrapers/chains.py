"""Coffee-shop chain lists, shared across the scraper and specialty scoring.

Two lists, deliberately separate:

- ``NONSPECIALTY_CHAINS`` — mass-market chains we *exclude* from the specialty
  map (and skip when scraping descriptions, since they yield no useful copy).
- ``SPECIALTY_CHAINS`` — multi-location *specialty* chains we *force-include*.
  A shop being a chain does not make it non-specialty: Blue Bottle, Stumptown,
  Intelligentsia et al. are chains we want to keep. This allowlist overrides the
  blocklist.

Matching is normalized and prefix-aware (word-boundary), so "Blue Bottle",
"Blue Bottle Coffee" and "Starbucks Reserve" all match their brand key, while
"Costa Rica Coffee Roasters" does *not* match "Costa Coffee". Both lists are
curation surfaces — extend them as coverage grows, especially outside the US.
"""

from __future__ import annotations

import re
import unicodedata

# Distinctive brand *cores*, normalized into match sets at import time. Matching
# is "name equals core, or name starts with core + space", so a short core like
# "blue bottle" matches "Blue Bottle" and "Blue Bottle Coffee" while "costa
# coffee" does NOT match "Costa Rica Coffee Roasters".
_NONSPECIALTY_CHAIN_NAMES: tuple[str, ...] = (
    "Starbucks",
    "Tim Hortons",
    "Dunkin",
    "Dutch Bros",
    "McCafe",
    "Panera",
    "Caribou Coffee",
    "Scooter's Coffee",
    "7 Brew",
    "Costa Coffee",
    "Peets",
    "Coffee Bean & Tea Leaf",
    "Caffe Nero",
    "Pret A Manger",
    "Greggs",
    "Gloria Jean's",
    "Second Cup",
    "Tully's",
)

_SPECIALTY_CHAIN_NAMES: tuple[str, ...] = (
    "Blue Bottle",
    "Stumptown",
    "Intelligentsia",
    "Verve Coffee",
    "La Colombe",
    "Onyx Coffee",
    "Philz",
    "Gregorys Coffee",
    "Bluestone Lane",
    "Joe Coffee",
    "Devocion",
    "Sightglass",
    "Ritual Coffee",
    "George Howell",
    "Coava",
    "Heart Coffee",
    "Sey Coffee",
    "Partners Coffee",
    "Counter Culture",
)


def _norm(name: str) -> str:
    """Fold accents, lowercase, drop apostrophes, reduce other punctuation to spaces.

    "Caffè Nero" -> "caffe nero"; "Peet's Coffee & Tea" -> "peets coffee tea";
    "Blue Bottle" -> "blue bottle". Accent folding matters: without it an accented
    chain name (Caffè Nero) wouldn't match its ASCII key and would slip the filter.
    """
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.casefold().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


NONSPECIALTY_CHAINS: frozenset[str] = frozenset(_norm(n) for n in _NONSPECIALTY_CHAIN_NAMES)
SPECIALTY_CHAINS: frozenset[str] = frozenset(_norm(n) for n in _SPECIALTY_CHAIN_NAMES)


def _matches(name: str, keys: frozenset[str]) -> bool:
    """True if `name`, normalized, equals or starts with (word-boundary) a key."""
    norm = _norm(name)
    if not norm:
        return False
    return any(norm == key or norm.startswith(key + " ") for key in keys)


def is_specialty_chain(name: str) -> bool:
    """A known multi-location specialty chain (kept on the map)."""
    return _matches(name, SPECIALTY_CHAINS)


def is_nonspecialty_chain(name: str) -> bool:
    """A mass-market chain (excluded), unless also a specialty chain."""
    return _matches(name, NONSPECIALTY_CHAINS) and not is_specialty_chain(name)
