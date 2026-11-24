"""The fields of Keitaro responses that the wrapper reads. Everything else is ignored."""

from pydantic import BaseModel, ConfigDict, Field


class KeitaroModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class KtNamed(KeitaroModel):
    """Domain, campaign group or traffic source."""

    id: int
    name: str


class KtOffer(KeitaroModel):
    id: int
    name: str
    state: str = "active"
    country: list[str] = Field(default_factory=list)


class KtCampaign(KeitaroModel):
    id: int
    name: str
    alias: str = ""
    state: str = "active"
    domain_id: int | None = None
    group_id: int | None = None
    traffic_source_id: int | None = None
    updated_at: str | None = None


class KtStreamOffer(KeitaroModel):
    offer_id: int
    share: int
    state: str = "active"


class KtStream(KeitaroModel):
    id: int
    campaign_id: int
    name: str
    position: int = 0
    type: str = "regular"
    schema_name: str = Field(default="landings", alias="schema")
    state: str = "active"
    offers: list[KtStreamOffer] = Field(default_factory=list)
