from datetime import datetime

from pydantic import BaseModel


class ProcessingMethodBase(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None
    fermentation_duration: float | None = None
    drying_duration: float | None = None


class ProcessingMethodRead(ProcessingMethodBase):
    id: str
    created_at: datetime
    updated_at: datetime
