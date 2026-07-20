# Coffee Atlas — Database ERD

> Source of truth: [`backend/db/schema.py`](../backend/db/schema.py) (raw DuckDB DDL, no ORM).
> 33 tables total: **14 entity tables**, **18 graph edge tables**, and **1 ontology triple store**.
>
> Conventions (apply to every table unless noted):
> - `id TEXT PRIMARY KEY` holds a UUID string.
> - Every table carries `created_at` / `updated_at TIMESTAMP DEFAULT current_timestamp` (omitted below to reduce noise).
> - `*_embedding` columns are `FLOAT[3072]` Gemini `gemini-embedding-001` vectors.
> - Tables are prefixed by domain: `var_`, `org_`, `proc_`, `roast_`, `flav_`, `dist_`, `shop_`, `prod_`, `edges_`.

GitHub renders the Mermaid block below as a diagram automatically. Pre-rendered
images are also committed alongside this file:
[`database-erd.svg`](./database-erd.svg) (vector) and
[`database-erd.png`](./database-erd.png) (raster).

![Coffee Atlas database ERD](./database-erd.png)

## Conceptual ERD (entities + relationships)

The 18 `edges_*` tables are the join layer of the knowledge graph. To keep the
map readable they are drawn here as **labeled many-to-many lines** rather than as
boxes; each one is a real table whose columns are listed in the appendix.

- **Solid line** (`||--o{`) = enforced foreign key (`REFERENCES` in the DDL).
- **Dotted line** (`||..o{`) = logical FK stored as a plain `TEXT` column (not enforced).
- **`}o--o{`** = many-to-many realized by an `edges_*` table (label = table name).

```mermaid
erDiagram
    %% ---------- enforced FK hierarchy ----------
    org_countries  ||--o{ org_regions   : "FK country_id"
    org_regions    ||--o{ org_farms     : "FK region_id"
    roast_roasters ||--o{ prod_products : "FK roaster_id"
    flav_attributes ||--o{ flav_attributes : "parent_id (hierarchy, unenforced)"

    %% ---------- logical (unenforced) FKs in the distribution domain ----------
    org_countries ||..o{ dist_importers    : "country_id (logical)"
    org_countries ||..o{ dist_trade_routes : "exporter/importer (logical)"

    %% ---------- graph edge tables (many-to-many) ----------
    var_varieties   }o--o{ flav_attributes : "edges_variety_flavor (strength)"
    org_countries   }o--o{ var_varieties   : "edges_country_variety"
    org_regions     }o--o{ var_varieties   : "edges_region_variety"
    org_farms       }o--o{ var_varieties   : "edges_farm_variety"
    shop_shops      }o--o{ var_varieties   : "edges_shop_variety"
    var_varieties   }o--o{ proc_methods    : "edges_variety_processing"
    roast_profiles  }o--o{ var_varieties   : "edges_roast_variety"
    proc_methods    }o--o{ flav_attributes : "edges_processing_flavor (effect)"
    org_countries   }o--o{ org_regions     : "edges_country_region"
    org_regions     }o--o{ org_farms       : "edges_region_farm"
    prod_products   }o--o{ var_varieties   : "edges_product_variety (share)"
    prod_products   }o--o{ org_regions     : "edges_product_region"
    prod_products   }o--o{ org_countries   : "edges_product_country"
    prod_products   }o--o{ flav_attributes : "edges_product_flavor (strength)"
    prod_products   }o--o{ roast_profiles  : "edges_product_roast"
    shop_shops      }o--o{ prod_products   : "edges_shop_product"
    roast_roasters  }o--o{ prod_products   : "edges_roaster_product"
    shop_shops      }o--o{ roast_roasters  : "edges_shop_roaster"

    %% ---------- entity tables ----------
    var_varieties {
        TEXT id PK
        TEXT name
        TEXT species
        TEXT genetic_group
        TEXT description
        TEXT yield_potential
        INTEGER optimal_altitude_min
        INTEGER optimal_altitude_max
        TEXT bean_size
        TEXT cherry_color
        TEXT stature
        TEXT disease_resistance
        FLOAT name_embedding "[3072]"
    }
    org_countries {
        TEXT id PK
        TEXT name
        TEXT iso_code
        DOUBLE latitude
        DOUBLE longitude
        DOUBLE production_volume
    }
    org_regions {
        TEXT id PK
        TEXT name
        TEXT country_id FK
        DOUBLE latitude
        DOUBLE longitude
        INTEGER altitude_min
        INTEGER altitude_max
    }
    org_farms {
        TEXT id PK
        TEXT name
        TEXT region_id FK
        DOUBLE latitude
        DOUBLE longitude
        INTEGER altitude
        TEXT soil_type
        TEXT owner
    }
    proc_methods {
        TEXT id PK
        TEXT name
        TEXT category
        TEXT description
        DOUBLE fermentation_duration
        DOUBLE drying_duration
        FLOAT description_embedding "[3072]"
    }
    roast_profiles {
        TEXT id PK
        TEXT name
        TEXT roast_level
        DOUBLE first_crack_temp
        DOUBLE development_time_ratio
        DOUBLE charge_temp
        INTEGER total_roast_time
        TEXT description
        FLOAT description_embedding "[3072]"
    }
    roast_roasters {
        TEXT id PK
        TEXT name
        TEXT location
        TEXT website
    }
    flav_attributes {
        TEXT id PK
        TEXT name
        TEXT category
        TEXT subcategory
        TEXT description
        TEXT intensity_reference
        TEXT sensory_reference
        TEXT parent_id FK "self → hierarchy (unenforced)"
        FLOAT name_embedding "[3072]"
    }
    dist_importers {
        TEXT id PK
        TEXT name
        TEXT country_id "logical → org_countries"
        TEXT website
    }
    dist_trade_routes {
        TEXT id PK
        TEXT exporter_country_id "logical → org_countries"
        TEXT importer_country_id "logical → org_countries"
        DOUBLE annual_volume
        INTEGER year
    }
    dist_certifications {
        TEXT id PK
        TEXT name
        TEXT description
    }
    shop_shops {
        TEXT id PK
        TEXT name
        DOUBLE latitude
        DOUBLE longitude
        TEXT address
        TEXT city
        TEXT country
        TEXT website
        DOUBLE rating
        BOOLEAN roasts_in_house
        TEXT description
        FLOAT description_embedding "[3072]"
    }
    prod_products {
        TEXT id PK
        TEXT name
        TEXT roaster_id FK
        TEXT roast_level
        TEXT process
        BOOLEAN is_blend
        DOUBLE price
        TEXT currency
        INTEGER net_weight_grams
        TEXT url
        TEXT description
        FLOAT description_embedding "[3072]"
    }
    ontology_triples {
        TEXT subject
        TEXT predicate
        TEXT object_value
        TEXT object_kind
        TEXT object_datatype
        TEXT object_lang
        TEXT graph_iri
    }
```

## Entity summary

Coffee Atlas models the coffee supply chain as a knowledge graph. Entity tables
are the **nodes**; `edges_*` tables are the **edges**. Because the DuckPGQ
extension is unavailable on the current build, traversal endpoints BFS over these
edge tables directly instead of using a property graph.

| Domain | Table | Represents |
|--------|-------|------------|
| Varieties | `var_varieties` | Coffee varieties (genetics, agronomy, flavor seed). 55 Arabica + 47 Robusta from WCR. |
| Origins | `org_countries` | Producing countries (geo + production volume). |
| Origins | `org_regions` | Growing regions within a country (FK → country). |
| Origins | `org_farms` | Individual farms/estates within a region (FK → region). |
| Processing | `proc_methods` | Processing methods (washed, natural, honey, anaerobic…). |
| Roasting | `roast_profiles` | Roast profiles (temp curves, development ratio, level). |
| Roasting | `roast_roasters` | Roasting companies. Parent of `prod_products` (FK). |
| Flavor | `flav_attributes` | WCR Sensory Lexicon attributes; self-referencing `parent_id` builds the 3-tier flavor-wheel hierarchy. |
| Distribution | `dist_importers` | Green-coffee importers (logical FK → country). |
| Distribution | `dist_trade_routes` | Export→import trade flows with annual volume. |
| Distribution | `dist_certifications` | Certifications (FairTrade, Organic…). Standalone reference table. |
| Shops | `shop_shops` | Specialty coffee shops (geo, rating, roasts-in-house). |
| Products | `prod_products` | Scraped roaster products/SKUs (FK → roaster). |
| Ontology | `ontology_triples` | RDF subject/predicate/object triples exported from the OWL ontology. No `id`/FKs; not connected to the relational graph. |

### Enforced vs. logical foreign keys

Only four relationships are enforced with `REFERENCES` on the entity tables:

- `org_regions.country_id → org_countries.id`
- `org_farms.region_id → org_regions.id`
- `prod_products.roaster_id → roast_roasters.id`
- (every `edges_*` table also declares `REFERENCES` on both of its endpoint columns)

These are stored as plain `TEXT` and **not** enforced:

- `flav_attributes.parent_id` (self-reference, builds the flavor hierarchy)
- `dist_importers.country_id`
- `dist_trade_routes.exporter_country_id`, `dist_trade_routes.importer_country_id`

## Edge tables (physical join layer)

Every edge table has `id TEXT PK`, the two endpoint FK columns (both
`REFERENCES` their entity table), `created_at`/`updated_at`, and — for some — a
payload column.

| Edge table | Source → Destination | Payload |
|------------|----------------------|---------|
| `edges_variety_flavor` | `var_varieties` → `flav_attributes` | `strength DOUBLE` |
| `edges_country_variety` | `org_countries` → `var_varieties` | — |
| `edges_region_variety` | `org_regions` → `var_varieties` | — |
| `edges_farm_variety` | `org_farms` → `var_varieties` | — |
| `edges_shop_variety` | `shop_shops` → `var_varieties` | — |
| `edges_variety_processing` | `var_varieties` → `proc_methods` | — |
| `edges_roast_variety` | `roast_profiles` → `var_varieties` | — |
| `edges_processing_flavor` | `proc_methods` → `flav_attributes` | `effect TEXT` |
| `edges_country_region` | `org_countries` → `org_regions` | — |
| `edges_region_farm` | `org_regions` → `org_farms` | — |
| `edges_product_variety` | `prod_products` → `var_varieties` | `share DOUBLE` |
| `edges_product_region` | `prod_products` → `org_regions` | — |
| `edges_product_country` | `prod_products` → `org_countries` | — |
| `edges_product_flavor` | `prod_products` → `flav_attributes` | `strength DOUBLE` |
| `edges_product_roast` | `prod_products` → `roast_profiles` | — |
| `edges_shop_product` | `shop_shops` → `prod_products` | — |
| `edges_roaster_product` | `roast_roasters` → `prod_products` | — |
| `edges_shop_roaster` | `shop_shops` → `roast_roasters` | — |

> Note: `edges_country_region` and `edges_region_farm` duplicate the enforced
> `org_*` FK hierarchy as explicit graph edges so traversal queries can walk
> origin geography the same way they walk every other relationship.
