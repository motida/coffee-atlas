from pydantic import BaseModel


class Recommendation(BaseModel):
    """A single recommended entity.

    Shaped like ``SearchResult`` (id/entity_type/label/description) so the
    frontend reuses the same card rendering, plus a blended ``score`` and a
    human-readable ``reason`` explaining the graph overlap that boosted it.
    """

    id: str
    entity_type: str
    label: str
    description: str | None = None
    score: float
    reason: str | None = None
