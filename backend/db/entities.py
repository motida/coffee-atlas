"""Canonical map of content entity types to their DuckDB tables.

Every entity the app models as a graph vertex is also something a user can
favorite, so both concerns resolve an opaque ``entity_type`` (``"variety"``,
``"shop"``, …) to the same set of read-only DuckDB tables. Keeping the mapping
here — rather than duplicating it in ``routers/graph.py`` and
``routers/_activity_entities.py`` — means a new entity type is added in one
place and can never drift between the graph explorer and the favorites API.

The keys must match ``frontend/lib/entity-config.ts`` ``ENTITY_CONFIG`` so the
frontend can build detail-page hrefs from an ``entity_type`` with no remapping.
"""

CONTENT_ENTITY_TABLES: dict[str, str] = {
    "variety": "var_varieties",
    "country": "org_countries",
    "region": "org_regions",
    "farm": "org_farms",
    "processing": "proc_methods",
    "roast_profile": "roast_profiles",
    "roaster": "roast_roasters",
    "product": "prod_products",
    "shop": "shop_shops",
    "flavor": "flav_attributes",
}
