from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CatalogDep, SettingsDep
from app.api.schemas import COUNTRY_CODES, CampaignFormOut, NamedOut, OfferOut

router = APIRouter(tags=["catalog"])


@router.get("/offers", response_model=list[OfferOut])
async def search_offers(
    catalog: CatalogDep,
    q: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    return await catalog.search_offers(q, limit)


@router.get("/campaign-form", response_model=CampaignFormOut)
async def campaign_form(catalog: CatalogDep, settings: SettingsDep):
    """What the new campaign form needs: the name prefix, country codes and Keitaro lists."""
    options = await catalog.campaign_form_options()
    return CampaignFormOut(
        prefix=settings.campaign_prefix,
        countries=COUNTRY_CODES,
        domains=[NamedOut.model_validate(d) for d in options.domains],
        groups=[NamedOut.model_validate(g) for g in options.groups],
        traffic_sources=[NamedOut.model_validate(s) for s in options.traffic_sources],
    )
