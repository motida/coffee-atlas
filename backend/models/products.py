from datetime import datetime

from pydantic import BaseModel


class ProductBase(BaseModel):
    name: str
    roaster_id: str | None = None
    roast_level: str | None = None
    process: str | None = None
    is_blend: bool | None = None
    price: float | None = None
    net_weight_grams: int | None = None
    url: str | None = None
    description: str | None = None


class ProductRead(ProductBase):
    id: str
    roaster_name: str | None = None  # joined from roast_roasters
    created_at: datetime
    updated_at: datetime
