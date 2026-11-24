from pydantic import BaseModel, ConfigDict


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
