from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import CatalogDep, EditorDep, KeitaroDep, SettingsDep
from app.api.schemas import CampaignListItem, CampaignOut
from app.api.views import campaign_out
from app.db import SessionDep

router = APIRouter(prefix="/campaigns", tags=["campaigns"])

CampaignId = Annotated[int, Path(gt=0)]


@router.get("", response_model=list[CampaignListItem])
async def list_campaigns(keitaro: KeitaroDep):
    """Campaigns straight from Keitaro, newest first."""
    campaigns = await keitaro.list_campaigns()
    return [CampaignListItem.model_validate(c, from_attributes=True) for c in campaigns]


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: CampaignId,
    session: SessionDep,
    editor: EditorDep,
    catalog: CatalogDep,
    settings: SettingsDep,
):
    campaign = await editor.get_campaign(session, campaign_id)
    return await campaign_out(campaign, catalog, settings)


@router.post("/{campaign_id}/fetch", response_model=CampaignOut)
async def fetch_campaign(
    campaign_id: CampaignId,
    session: SessionDep,
    editor: EditorDep,
    catalog: CatalogDep,
    settings: SettingsDep,
):
    """Load the campaign from Keitaro again. Unpublished changes are dropped."""
    campaign = await editor.fetch_campaign(session, campaign_id)
    return await campaign_out(campaign, catalog, settings)
