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
    "id, name, roaster_id, roast_level, process, is_blend, price, "
    "net_weight_grams, url, description, created_at, updated_at"
)
