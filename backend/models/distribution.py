from datetime import datetime

from pydantic import BaseModel


class ImporterBase(BaseModel):
    name: str
    country_id: str | None = None
    website: str | None = None


class ImporterRead(ImporterBase):
    id: str
    created_at: datetime
    updated_at: datetime


class TradeRouteBase(BaseModel):
    exporter_country_id: str | None = None
    importer_country_id: str | None = None
    annual_volume: float | None = None
    year: int | None = None


class TradeRouteRead(TradeRouteBase):
    id: str
    created_at: datetime
    updated_at: datetime


class CertificationBase(BaseModel):
    name: str
    description: str | None = None


class CertificationRead(CertificationBase):
    id: str
    created_at: datetime
    updated_at: datetime
