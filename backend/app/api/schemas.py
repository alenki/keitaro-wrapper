from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import OfferState


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
    domains: list[NamedOut]
    groups: list[NamedOut]
    traffic_sources: list[NamedOut]


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
