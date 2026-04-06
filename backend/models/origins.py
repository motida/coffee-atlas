from datetime import datetime

from pydantic import BaseModel


class CountryBase(BaseModel):
    name: str
    iso_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    production_volume: float | None = None


class CountryRead(CountryBase):
    id: str
    created_at: datetime
    updated_at: datetime


class RegionBase(BaseModel):
    name: str
    country_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_min: int | None = None
    altitude_max: int | None = None


class RegionRead(RegionBase):
    id: str
    created_at: datetime
    updated_at: datetime


class FarmBase(BaseModel):
    name: str
    region_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: int | None = None
    soil_type: str | None = None
    owner: str | None = None


class FarmRead(FarmBase):
    id: str
    created_at: datetime
    updated_at: datetime
