"""Shared SELECT column lists.

These name every client-facing column *except* the 3072-float ``*_embedding``
vectors, which must never be shipped over the API. Kept here so the lists that
are used by more than one router stay in sync with the schema in one edit.
"""

VARIETY_COLS = (
    "id, name, species, genetic_group, description, yield_potential, "
    "optimal_altitude_min, optimal_altitude_max, bean_size, cherry_color, "
    "stature, disease_resistance, created_at, updated_at"
)

PRODUCT_COLS = (
    "id, name, roaster_id, roast_level, process, is_blend, price, currency, "
    "net_weight_grams, url, description, created_at, updated_at"
)

# Core flavor-attribute columns shared by the endpoints that return attributes
# without their audit timestamps (the flavor wheel and the variety/processing
# join views). Endpoints that serialize a ``FlavorAttributeRead`` add
# ``created_at, updated_at`` on top of these.
FLAVOR_COLS = (
    "id, name, category, subcategory, description, "
    "intensity_reference, sensory_reference, parent_id"
)


def prefixed(cols: str, alias: str) -> str:
    """Prefix each column in a comma-separated list with ``alias.``.

    Turns a shared column constant into a table-qualified select list for use in
    JOIN queries, e.g. ``prefixed(VARIETY_COLS, "v")`` → ``"v.id, v.name, ..."``.
    """
    return ", ".join(f"{alias}.{col}" for col in cols.split(", "))
