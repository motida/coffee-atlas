"""DDL definitions for all Coffee Atlas tables. Run with: python -m backend.db.schema"""

import duckdb

TABLES: list[str] = [
    # --- Varieties domain ---
    """
    CREATE TABLE IF NOT EXISTS var_varieties (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        species TEXT,
        genetic_group TEXT,
        description TEXT,
        yield_potential TEXT,
        optimal_altitude_min INTEGER,
        optimal_altitude_max INTEGER,
        bean_size TEXT,
        cherry_color TEXT,
        stature TEXT,
        disease_resistance TEXT,
        name_embedding FLOAT[768],
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Origins domain ---
    """
    CREATE TABLE IF NOT EXISTS org_countries (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        iso_code TEXT,
        latitude DOUBLE,
        longitude DOUBLE,
        production_volume DOUBLE,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS org_regions (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        country_id TEXT REFERENCES org_countries(id),
        latitude DOUBLE,
        longitude DOUBLE,
        altitude_min INTEGER,
        altitude_max INTEGER,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS org_farms (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        region_id TEXT REFERENCES org_regions(id),
        latitude DOUBLE,
        longitude DOUBLE,
        altitude INTEGER,
        soil_type TEXT,
        owner TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Processing domain ---
    """
    CREATE TABLE IF NOT EXISTS proc_methods (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        description TEXT,
        fermentation_duration DOUBLE,
        drying_duration DOUBLE,
        description_embedding FLOAT[768],
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Roasting domain ---
    """
    CREATE TABLE IF NOT EXISTS roast_profiles (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        roast_level TEXT,
        first_crack_temp DOUBLE,
        development_time_ratio DOUBLE,
        charge_temp DOUBLE,
        total_roast_time INTEGER,
        description TEXT,
        description_embedding FLOAT[768],
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS roast_roasters (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        location TEXT,
        website TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Flavor domain ---
    """
    CREATE TABLE IF NOT EXISTS flav_attributes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        subcategory TEXT,
        description TEXT,
        intensity_reference TEXT,
        sensory_reference TEXT,
        parent_id TEXT,
        name_embedding FLOAT[768],
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Distribution domain ---
    """
    CREATE TABLE IF NOT EXISTS dist_importers (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        country_id TEXT,
        website TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dist_trade_routes (
        id TEXT PRIMARY KEY,
        exporter_country_id TEXT,
        importer_country_id TEXT,
        annual_volume DOUBLE,
        year INTEGER,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dist_certifications (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Shops domain ---
    """
    CREATE TABLE IF NOT EXISTS shop_shops (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        latitude DOUBLE,
        longitude DOUBLE,
        address TEXT,
        city TEXT,
        country TEXT,
        website TEXT,
        rating DOUBLE,
        roasts_in_house BOOLEAN,
        description TEXT,
        description_embedding FLOAT[768],
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    # --- Edge tables (for DuckPGQ property graph) ---
    """
    CREATE TABLE IF NOT EXISTS edges_variety_flavor (
        id TEXT PRIMARY KEY,
        variety_id TEXT REFERENCES var_varieties(id),
        flavor_id TEXT REFERENCES flav_attributes(id),
        strength DOUBLE,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges_origin_variety (
        id TEXT PRIMARY KEY,
        origin_id TEXT,
        variety_id TEXT REFERENCES var_varieties(id),
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges_shop_variety (
        id TEXT PRIMARY KEY,
        shop_id TEXT REFERENCES shop_shops(id),
        variety_id TEXT REFERENCES var_varieties(id),
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges_variety_processing (
        id TEXT PRIMARY KEY,
        variety_id TEXT REFERENCES var_varieties(id),
        method_id TEXT REFERENCES proc_methods(id),
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges_roast_variety (
        id TEXT PRIMARY KEY,
        profile_id TEXT REFERENCES roast_profiles(id),
        variety_id TEXT REFERENCES var_varieties(id),
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS edges_processing_flavor (
        id TEXT PRIMARY KEY,
        method_id TEXT REFERENCES proc_methods(id),
        flavor_id TEXT REFERENCES flav_attributes(id),
        effect TEXT,
        created_at TIMESTAMP DEFAULT current_timestamp,
        updated_at TIMESTAMP DEFAULT current_timestamp
    )
    """,
]


def create_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create all tables in the database."""
    for ddl in TABLES:
        conn.execute(ddl)


if __name__ == "__main__":
    from backend.db.connection import get_connection

    conn = get_connection()
    create_tables(conn)
    tables = conn.execute("SHOW TABLES").fetchall()
    print(f"Created {len(tables)} tables:")
    for (name,) in tables:
        print(f"  - {name}")
    conn.close()
