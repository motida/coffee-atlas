from datetime import datetime

from pydantic import BaseModel, Field

from backend.models._base import ReadModel


# --- Favorites ---
class FavoriteCreate(BaseModel):
    entity_type: str
    entity_id: str


class FavoriteRead(BaseModel):
    """Declared explicitly (not via ReadModel): favorites carry no updated_at."""

    id: str
    user_id: str
    entity_type: str
    entity_id: str
    created_at: datetime


# --- Cupping notes ---
class CuppingNoteBase(BaseModel):
    entity_type: str
    entity_id: str
    notes: str
    score: float | None = Field(default=None, ge=0, le=100)
    brew_method: str | None = None


class CuppingNoteCreate(CuppingNoteBase):
    pass


class CuppingNoteUpdate(BaseModel):
    """Partial update (PATCH): every field optional."""

    notes: str | None = None
    score: float | None = Field(default=None, ge=0, le=100)
    brew_method: str | None = None


class CuppingNoteRead(CuppingNoteBase, ReadModel):
    user_id: str
