from pydantic import BaseModel

from backend.models._base import ReadModel


class RoastProfileBase(BaseModel):
    name: str
    roast_level: str | None = None
    first_crack_temp: float | None = None
    development_time_ratio: float | None = None
    charge_temp: float | None = None
    total_roast_time: int | None = None
    description: str | None = None


class RoastProfileRead(RoastProfileBase, ReadModel):
    pass


class RoasterBase(BaseModel):
    name: str
    location: str | None = None
    website: str | None = None


class RoasterRead(RoasterBase, ReadModel):
    pass
