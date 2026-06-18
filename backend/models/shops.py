from typing import Any

from pydantic import BaseModel

from backend.models._base import ReadModel


class ShopBase(BaseModel):
    name: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    rating: float | None = None
    roasts_in_house: bool | None = None
    description: str | None = None
    is_specialty: bool | None = None


class ShopRead(ShopBase, ReadModel):
    pass


class ShopGeoFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: ShopRead
