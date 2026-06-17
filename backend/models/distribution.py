from pydantic import BaseModel

from backend.models._base import ReadModel


class ImporterBase(BaseModel):
    name: str
    country_id: str | None = None
    website: str | None = None


class ImporterRead(ImporterBase, ReadModel):
    country_name: str | None = None  # joined from org_countries


class TradeRouteBase(BaseModel):
    exporter_country_id: str | None = None
    importer_country_id: str | None = None
    annual_volume: float | None = None
    year: int | None = None


class TradeRouteRead(TradeRouteBase, ReadModel):
    exporter_name: str | None = None  # joined from org_countries
    importer_name: str | None = None


class CertificationBase(BaseModel):
    name: str
    description: str | None = None


class CertificationRead(CertificationBase, ReadModel):
    pass
