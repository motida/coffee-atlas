from fastapi import APIRouter, Depends
import duckdb

from backend.db.connection import get_db
from backend.models.flavor import FlavorAttributeRead

router = APIRouter(prefix="/api/v1/flavor", tags=["flavor"])


@router.get("/wheel")
def get_flavor_wheel(db: duckdb.DuckDBPyConnection = Depends(get_db)):
    """Return the full flavor wheel as a hierarchical JSON tree."""
    rows = db.execute(
        "SELECT * FROM flav_attributes ORDER BY category, subcategory, name"
    ).fetchdf()
    tree: dict = {}
    for _, row in rows.iterrows():
        cat = row.get("category", "Other")
        sub = row.get("subcategory", "Other")
        tree.setdefault(cat, {}).setdefault(sub, []).append(row.to_dict())
    return tree


@router.get("/attributes/{attribute_id}", response_model=FlavorAttributeRead)
def get_flavor_attribute(attribute_id: str, db: duckdb.DuckDBPyConnection = Depends(get_db)):
    row = db.execute("SELECT * FROM flav_attributes WHERE id = ?", [attribute_id]).fetchone()
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Flavor attribute not found")
    columns = [desc[0] for desc in db.description]
    return dict(zip(columns, row))
