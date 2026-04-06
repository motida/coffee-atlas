from datetime import datetime

from pydantic import BaseModel


class RoastProfileBase(BaseModel):
    name: str
    roast_level: str | None = None
    first_crack_temp: float | None = None
    development_time_ratio: float | None = None
    charge_temp: float | None = None
    total_roast_time: int | None = None
    description: str | None = None


class RoastProfileRead(RoastProfileBase):
    id: str
    created_at: datetime
    updated_at: datetime


class RoasterBase(BaseModel):
    name: str
    location: str | None = None
    website: str | None = None


class RoasterRead(RoasterBase):
    id: str
    created_at: datetime
    updated_at: datetime
