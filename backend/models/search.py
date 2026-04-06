from pydantic import BaseModel


class SearchQuery(BaseModel):
    query: str
    entity_types: list[str] | None = None
    limit: int = 20


class SearchResult(BaseModel):
    id: str
    entity_type: str
    label: str
    description: str | None = None
    similarity: float | None = None
