from datetime import datetime
from typing import Annotated

import pycountry
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, StringConstraints, field_validator

from app.models import OfferState

# ISO 3166-1 alpha-2, the codes Keitaro's country filter uses
COUNTRY_CODES = sorted(country.alpha_2 for country in pycountry.countries)


def is_country_code(code: str) -> bool:
    return code in COUNTRY_CODES


class CampaignCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    geo: Annotated[list[str], Field(min_length=1, max_length=20)]
    offer_id: PositiveInt
    domain_id: PositiveInt
    group_id: PositiveInt
    traffic_source_id: PositiveInt

    @field_validator("geo")
    @classmethod
    def _normalize_geo(cls, codes: list[str]) -> list[str]:
        result: list[str] = []
        for raw in codes:
            code = raw.strip().upper()
            if not is_country_code(code):
                raise ValueError(f"Неизвестный код страны: {code or raw!r}")
            if code not in result:
                result.append(code)
        return result


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    countries: list[str]


class NamedOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CampaignFormOut(BaseModel):
    prefix: str
    countries: list[str]
    domains: list[NamedOut]
    groups: list[NamedOut]
    traffic_sources: list[NamedOut]


class AddOffer(BaseModel):
    offer_id: PositiveInt


class PinOffer(BaseModel):
    pinned: bool


class CampaignListItem(BaseModel):
    id: int
    name: str
    alias: str
    state: str
    updated_at: str | None


class StreamOfferOut(BaseModel):
    offer_id: int
    name: str
    countries: list[str]
    state: OfferState
    share: int
    pinned: bool
    published_state: OfferState | None
    published_share: int | None


class StreamOut(BaseModel):
    id: int
    name: str
    position: int
    type: str
    state: str
    has_offers: bool
    dirty: bool
    active_total: int
    offers: list[StreamOfferOut]


class CampaignOut(BaseModel):
    id: int
    name: str
    alias: str
    state: str
    domain: NamedOut | None
    group: NamedOut | None
    traffic_source: NamedOut | None
    keitaro_url: str
    synced_at: datetime
    streams: list[StreamOut]
