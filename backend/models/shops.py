from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


class ShopRead(ShopBase):
    id: str
    created_at: datetime
    updated_at: datetime


class ShopGeoFeature(BaseModel):
    type: str = "Feature"
    geometry: dict[str, Any]
    properties: ShopRead
