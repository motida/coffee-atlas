from pydantic import BaseModel

from backend.models._base import ReadModel


class VarietyBase(BaseModel):
    name: str
    species: str | None = None
    genetic_group: str | None = None
    description: str | None = None
    yield_potential: str | None = None
    optimal_altitude_min: int | None = None
    optimal_altitude_max: int | None = None
    bean_size: str | None = None
    cherry_color: str | None = None
    stature: str | None = None
    disease_resistance: str | None = None


class VarietyCreate(VarietyBase):
    pass


class VarietyRead(VarietyBase, ReadModel):
    pass
