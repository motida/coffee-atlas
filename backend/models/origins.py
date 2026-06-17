from pydantic import BaseModel

from backend.models._base import ReadModel


class CountryBase(BaseModel):
    name: str
    iso_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    production_volume: float | None = None


class CountryRead(CountryBase, ReadModel):
    pass


class RegionBase(BaseModel):
    name: str
    country_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude_min: int | None = None
    altitude_max: int | None = None


class RegionRead(RegionBase, ReadModel):
    pass


class FarmBase(BaseModel):
    name: str
    region_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: int | None = None
    soil_type: str | None = None
    owner: str | None = None


class FarmRead(FarmBase, ReadModel):
    pass
