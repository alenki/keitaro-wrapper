import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import NotFoundError
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import KeitaroNotFound
from app.keitaro.schemas import KtCampaign, KtStream, KtStreamOffer
from app.models import Campaign, OfferState, Stream, StreamOffer
from app.services.catalog import Catalog

logger = logging.getLogger(__name__)


class Editor:
    """Offers editor: keeps a copy of a campaign's streams and a draft of their offers."""

    def __init__(self, keitaro: KeitaroClient, catalog: Catalog) -> None:
        self._keitaro = keitaro
        self._catalog = catalog

    async def get_campaign(self, session: AsyncSession, campaign_id: int) -> Campaign:
        """The local copy, fetched from Keitaro the first time the campaign is opened."""
        if await session.get(Campaign, campaign_id) is None:
            return await self.fetch_campaign(session, campaign_id)
        return await load_campaign(session, campaign_id)

    async def fetch_campaign(self, session: AsyncSession, campaign_id: int) -> Campaign:
        """Replace the local copy with what Keitaro has now. Unpublished drafts are dropped."""
        try:
            kt_campaign = await self._keitaro.get_campaign(campaign_id)
            kt_streams = await self._keitaro.list_streams(campaign_id)
        except KeitaroNotFound:
            await session.execute(delete(Campaign).where(Campaign.id == campaign_id))
            await session.commit()
            raise NotFoundError(
                f"Кампания #{campaign_id} не найдена в Keitaro", code="campaign_not_found"
            ) from None

        await store_campaign(session, self._catalog, kt_campaign, kt_streams)
        await session.commit()
        logger.info(
            "campaign fetched from keitaro",
            extra={"campaign_id": campaign_id, "streams": len(kt_streams)},
        )
        return await load_campaign(session, campaign_id)


async def load_campaign(session: AsyncSession, campaign_id: int) -> Campaign:
    """Campaign with streams, offers and offer names loaded (no lazy loading under asyncio)."""
    campaign = await session.scalar(
        select(Campaign).where(Campaign.id == campaign_id).execution_options(populate_existing=True)
    )
    if campaign is None:
        raise NotFoundError(f"Кампания #{campaign_id} не найдена", code="campaign_not_found")
    return campaign


async def store_campaign(
    session: AsyncSession,
    catalog: Catalog,
    kt_campaign: KtCampaign,
    kt_streams: Sequence[KtStream],
) -> None:
    """Make the local copy match Keitaro. The caller commits."""
    now = datetime.now(UTC)
    # Stream offers reference the offers table, so the rows have to exist first
    await catalog.ensure_offers({offer.offer_id for s in kt_streams for offer in s.offers})

    fields = {
        "name": kt_campaign.name,
        "alias": kt_campaign.alias,
        "state": kt_campaign.state,
        "domain_id": kt_campaign.domain_id,
        "group_id": kt_campaign.group_id,
        "traffic_source_id": kt_campaign.traffic_source_id,
        "synced_at": now,
    }
    # The upsert also locks the campaign row, so two fetches of one campaign take turns
    await session.execute(
        insert(Campaign)
        .values(id=kt_campaign.id, **fields)
        .on_conflict_do_update(index_elements=[Campaign.id], set_=fields)
    )
    campaign = await load_campaign(session, kt_campaign.id)

    local = {stream.id: stream for stream in campaign.streams}
    for kt_stream in kt_streams:
        stream = local.pop(kt_stream.id, None)
        if stream is None:
            stream = Stream(id=kt_stream.id)
            campaign.streams.append(stream)
        stream.name = kt_stream.name
        stream.position = kt_stream.position
        stream.type = kt_stream.type
        stream.schema_name = kt_stream.schema_name
        stream.state = kt_stream.state
        stream.synced_at = now
        sync_offers(stream, kt_stream.offers)
    for gone in local.values():
        campaign.streams.remove(gone)
    await session.flush()


def sync_offers(stream: Stream, kt_offers: Sequence[KtStreamOffer]) -> None:
    """Make the offers of a stream match Keitaro, as the video shows.

    Offers we knew about that are gone from Keitaro stay in the list as removed, so they can
    be brought back. Offers added in an unpublished draft are dropped.
    """
    remaining = {offer.offer_id: offer for offer in kt_offers}
    for binding in list(stream.offers):
        kt_offer = remaining.pop(binding.offer_id, None)
        if kt_offer is not None:
            state = _state_from_keitaro(kt_offer.state)
            binding.state = binding.published_state = state
            binding.share = binding.published_share = kt_offer.share
        elif binding.published_state is None:
            stream.offers.remove(binding)
        else:
            binding.state = binding.published_state = OfferState.REMOVED
            binding.share = binding.published_share = 0
            binding.pinned = False

    position = max((binding.position for binding in stream.offers), default=0)
    for kt_offer in kt_offers:
        if kt_offer.offer_id not in remaining:
            continue
        position += 1
        state = _state_from_keitaro(kt_offer.state)
        stream.offers.append(
            StreamOffer(
                offer_id=kt_offer.offer_id,
                position=position,
                state=state,
                share=kt_offer.share,
                pinned=False,
                published_state=state,
                published_share=kt_offer.share,
            )
        )


def is_dirty(stream: Stream) -> bool:
    """True when the draft differs from Keitaro, the "yellow" stream from the video."""
    return any(
        binding.published_state is None
        or binding.state != binding.published_state
        or binding.share != binding.published_share
        for binding in stream.offers
    )


def _state_from_keitaro(state: str) -> OfferState:
    if state == "active":
        return OfferState.ACTIVE
    if state != "disabled":
        logger.warning(
            "unknown offer state in keitaro, treated as disabled", extra={"state": state}
        )
    return OfferState.DISABLED
