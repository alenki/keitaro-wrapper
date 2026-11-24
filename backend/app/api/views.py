"""Turn database objects into API responses."""

import logging

from app.api.schemas import CampaignOut, NamedOut, StreamOfferOut, StreamOut
from app.config import Settings
from app.keitaro.errors import KeitaroError
from app.keitaro.schemas import KtNamed
from app.models import Campaign, Stream
from app.services.catalog import CampaignFormOptions, Catalog
from app.services.editor import is_dirty
from app.services.shares import active_total

logger = logging.getLogger(__name__)


def stream_out(stream: Stream) -> StreamOut:
    offers = sorted(stream.offers, key=lambda binding: binding.position)
    return StreamOut(
        id=stream.id,
        name=stream.name,
        position=stream.position,
        type=stream.type,
        state=stream.state,
        has_offers=stream.has_offers,
        dirty=is_dirty(stream),
        active_total=active_total(offers),
        offers=[
            StreamOfferOut(
                offer_id=binding.offer_id,
                name=binding.offer.name,
                countries=binding.offer.countries,
                state=binding.state,
                share=binding.share,
                pinned=binding.pinned,
                published_state=binding.published_state,
                published_share=binding.published_share,
            )
            for binding in offers
        ],
    )


async def campaign_out(campaign: Campaign, catalog: Catalog, settings: Settings) -> CampaignOut:
    try:
        options = await catalog.campaign_form_options()
    except KeitaroError:
        # The editor works from the local copy; without Keitaro the names fall back to ids
        logger.warning("keitaro lists unavailable, showing ids", extra={"campaign_id": campaign.id})
        options = CampaignFormOptions(domains=[], groups=[], traffic_sources=[])
    return CampaignOut(
        id=campaign.id,
        name=campaign.name,
        alias=campaign.alias,
        state=campaign.state,
        domain=_named(options.domains, campaign.domain_id),
        group=_named(options.groups, campaign.group_id),
        traffic_source=_named(options.traffic_sources, campaign.traffic_source_id),
        keitaro_url=settings.campaign_url(campaign.id),
        synced_at=campaign.synced_at,
        streams=[stream_out(s) for s in sorted(campaign.streams, key=lambda s: s.position)],
    )


def _named(items: list[KtNamed], item_id: int | None) -> NamedOut | None:
    if item_id is None:
        return None
    name = next((item.name for item in items if item.id == item_id), f"#{item_id}")
    return NamedOut(id=item_id, name=name)
