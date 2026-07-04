from datetime import datetime

from pydantic import BaseModel, Field, field_validator

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
    # Display name resolved from the entity's DuckDB table at read time (not
    # stored in Postgres). None when the entity no longer exists after a
    # content reload.
    name: str | None = None
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

    @field_validator("notes")
    @classmethod
    def _notes_not_null(cls, v: str | None) -> str | None:
        # None here is only ever an explicit null in the payload (the validator
        # doesn't run for the unset default). The column is NOT NULL, so reject
        # with a 422 instead of letting Postgres raise into a 500.
        if v is None:
            raise ValueError("notes cannot be null; omit the field to leave it unchanged")
        return v


class CuppingNoteRead(CuppingNoteBase, ReadModel):
    user_id: str
