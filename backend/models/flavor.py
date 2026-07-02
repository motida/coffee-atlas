from pydantic import BaseModel

from backend.models._base import ReadModel


class FlavorAttributeBase(BaseModel):
    name: str
    category: str | None = None
    subcategory: str | None = None
    description: str | None = None
    intensity_reference: str | None = None
    sensory_reference: str | None = None
    parent_id: str | None = None


class FlavorAttributeRead(FlavorAttributeBase, ReadModel):
    pass


class FlavorStrengthRead(FlavorAttributeBase):
    """Flavor leaf plus the linking edge's strength — the shape
    /varieties/{id}/flavor returns (no timestamps, never the embedding)."""

    id: str
    strength: float | None = None
