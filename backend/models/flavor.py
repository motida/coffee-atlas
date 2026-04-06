from datetime import datetime

from pydantic import BaseModel


class FlavorAttributeBase(BaseModel):
    name: str
    category: str | None = None
    subcategory: str | None = None
    description: str | None = None
    intensity_reference: str | None = None
    sensory_reference: str | None = None
    parent_id: str | None = None


class FlavorAttributeRead(FlavorAttributeBase):
    id: str
    created_at: datetime
    updated_at: datetime
