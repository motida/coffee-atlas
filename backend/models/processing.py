from pydantic import BaseModel

from backend.models._base import ReadModel


class ProcessingMethodBase(BaseModel):
    name: str
    category: str | None = None
    description: str | None = None
    fermentation_duration: float | None = None
    drying_duration: float | None = None


class ProcessingMethodRead(ProcessingMethodBase, ReadModel):
    pass
