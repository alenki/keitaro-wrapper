import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, InvalidInputError, NotFoundError
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import KeitaroNotFound
from app.keitaro.schemas import KtCampaign, KtStream, KtStreamOffer
from app.models import Campaign, OfferState, Stream, StreamOffer
from app.services.catalog import Catalog
from app.services.shares import TOTAL, active_total, rebalance

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

    # Draft actions change only the local copy. Keitaro is untouched until push.

    async def add_offer(self, session: AsyncSession, stream_id: int, offer_id: int) -> Stream:
        stream = await lock_stream(session, stream_id)
        binding = _find_binding(stream, offer_id)
        if binding is not None:
            if binding.state != OfferState.REMOVED:
                raise ConflictError("Этот оффер уже есть в потоке", code="offer_already_added")
            _bring_back(binding)
        else:
            offer = await self._catalog.find_offer(offer_id)
            if offer is None or offer.state != "active":
                message = f"Оффер {offer_id} не найден в Keitaro"
                raise InvalidInputError(
                    message, details=[{"field": "offer_id", "message": message}]
                )
            stream.offers.append(
                StreamOffer(
                    offer_id=offer_id,
                    position=_next_position(stream),
                    state=OfferState.ACTIVE,
                    share=0,
                    pinned=False,
                )
            )
        return await self._save(session, stream, "offer added to draft", offer_id)

    async def remove_offer(self, session: AsyncSession, stream_id: int, offer_id: int) -> Stream:
        stream = await lock_stream(session, stream_id)
        binding = _get_binding(stream, offer_id)
        if binding.state == OfferState.REMOVED:
            raise ConflictError("Оффер уже удалён из потока", code="offer_already_removed")
        active = [b for b in stream.offers if b.state == OfferState.ACTIVE]
        if active == [binding]:
            raise ConflictError(
                "Последний активный оффер удалить нельзя: поток останется без офферов",
                code="last_active_offer",
            )
        if binding.published_state is None:
            # It never reached Keitaro, so removing it just undoes the add
            stream.offers.remove(binding)
        else:
            binding.state = OfferState.REMOVED
            binding.pinned = False
        return await self._save(session, stream, "offer removed in draft", offer_id)

    async def restore_offer(self, session: AsyncSession, stream_id: int, offer_id: int) -> Stream:
        stream = await lock_stream(session, stream_id)
        binding = _get_binding(stream, offer_id)
        if binding.state != OfferState.REMOVED:
            raise ConflictError("Вернуть можно только удалённый оффер", code="offer_not_removed")
        _bring_back(binding)
        return await self._save(session, stream, "offer brought back in draft", offer_id)

    async def set_pinned(
        self, session: AsyncSession, stream_id: int, offer_id: int, pinned: bool
    ) -> Stream:
        stream = await lock_stream(session, stream_id)
        binding = _get_binding(stream, offer_id)
        if binding.state != OfferState.ACTIVE:
            raise ConflictError("Закрепить можно только активный оффер", code="offer_not_active")
        binding.pinned = pinned
        # Pinning keeps the current number; an unpinned offer joins the even split again
        action = "offer pinned" if pinned else "offer unpinned"
        return await self._save(session, stream, action, offer_id, rebalance=not pinned)

    async def cancel(self, session: AsyncSession, stream_id: int) -> Stream:
        """Throw the draft away: back to what Keitaro has."""
        stream = await lock_stream(session, stream_id)
        for binding in list(stream.offers):
            if binding.published_state is None:
                stream.offers.remove(binding)
            else:
                binding.state = binding.published_state
                binding.share = binding.published_share or 0
        await session.commit()
        logger.info("draft cancelled", extra={"stream_id": stream_id})
        return await load_stream(session, stream_id)

    async def push(self, session: AsyncSession, stream_id: int) -> Stream:
        """Send the draft to Keitaro.

        The stream row stays locked while Keitaro is called (at most the client timeout), so
        two pushes of one stream can't interleave.
        """
        stream = await lock_stream(session, stream_id)
        if not is_dirty(stream):
            return stream

        offers = sorted(stream.offers, key=lambda binding: binding.position)
        if not any(b.state == OfferState.ACTIVE for b in offers):
            raise ConflictError("В потоке нет активных офферов", code="no_active_offers")
        total = active_total(offers)
        if total != TOTAL:
            raise ConflictError(
                f"Сумма долей активных офферов {total}%, а должна быть 100%. "
                "Открепите оффер или измените состав потока",
                code="shares_not_100",
            )

        try:
            current = await self._keitaro.get_stream(stream_id)
        except KeitaroNotFound:
            raise NotFoundError(
                "Поток удалён в Keitaro, загрузите кампанию заново", code="stream_not_found"
            ) from None
        in_keitaro = {(o.offer_id, o.share, _state_from_keitaro(o.state)) for o in current.offers}
        draft = {(b.offer_id, b.share, b.state) for b in offers if b.state != OfferState.REMOVED}
        last_seen = {
            (b.offer_id, b.published_share, b.published_state)
            for b in offers
            if b.published_state in (OfferState.ACTIVE, OfferState.DISABLED)
        }

        if in_keitaro == draft:
            # An earlier push got through but its answer was lost: nothing left to send
            kt_offers = current.offers
        elif in_keitaro != last_seen:
            # Keitaro has no versions, so this is how a change made elsewhere is noticed
            raise ConflictError(
                "Поток изменили в Keitaro после загрузки. Загрузите кампанию из Keitaro "
                "заново и повторите изменения",
                code="stream_changed_in_keitaro",
            )
        else:
            payload = [
                {"offer_id": b.offer_id, "share": b.share, "state": b.state.value}
                for b in offers
                if b.state != OfferState.REMOVED
            ]
            kt_offers = (await self._keitaro.update_stream_offers(stream_id, payload)).offers

        # Keitaro's answer becomes the published state; removed offers stay in the archive
        sync_offers(stream, kt_offers)
        stream.synced_at = datetime.now(UTC)
        await session.commit()
        logger.info(
            "stream pushed to keitaro", extra={"stream_id": stream_id, "shares": _shares(stream)}
        )
        return await load_stream(session, stream_id)

    async def _save(
        self,
        session: AsyncSession,
        stream: Stream,
        action: str,
        offer_id: int,
        *,
        rebalance: bool = True,
    ) -> Stream:
        if rebalance:
            _rebalance(stream)
        await session.commit()
        logger.info(
            action,
            extra={"stream_id": stream.id, "offer_id": offer_id, "shares": _shares(stream)},
        )
        return await load_stream(session, stream.id)


async def lock_stream(session: AsyncSession, stream_id: int) -> Stream:
    """Stream row locked until the transaction ends, so changes to one stream take turns."""
    stream = await session.scalar(
        select(Stream)
        .where(Stream.id == stream_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if stream is None:
        raise NotFoundError(
            "Поток не найден, загрузите кампанию из Keitaro заново", code="stream_not_found"
        )
    if not stream.has_offers:
        raise ConflictError(
            "В этом потоке нет офферов, его нельзя редактировать", code="stream_without_offers"
        )
    return stream


async def load_stream(session: AsyncSession, stream_id: int) -> Stream:
    stream = await session.scalar(
        select(Stream).where(Stream.id == stream_id).execution_options(populate_existing=True)
    )
    if stream is None:
        raise NotFoundError("Поток не найден", code="stream_not_found")
    return stream


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


def _find_binding(stream: Stream, offer_id: int) -> StreamOffer | None:
    return next((b for b in stream.offers if b.offer_id == offer_id), None)


def _get_binding(stream: Stream, offer_id: int) -> StreamOffer:
    binding = _find_binding(stream, offer_id)
    if binding is None:
        raise NotFoundError(f"Оффера {offer_id} нет в этом потоке", code="offer_not_in_stream")
    return binding


def _bring_back(binding: StreamOffer) -> None:
    binding.state = OfferState.ACTIVE
    binding.pinned = False


def _next_position(stream: Stream) -> int:
    return max((binding.position for binding in stream.offers), default=0) + 1


def _rebalance(stream: Stream) -> None:
    offers = sorted(stream.offers, key=lambda binding: binding.position)
    for binding, share in zip(offers, rebalance(offers), strict=True):
        binding.share = share


def _shares(stream: Stream) -> list[list[int]]:
    """[offer_id, share] pairs for the log line."""
    offers = sorted(stream.offers, key=lambda binding: binding.position)
    return [[b.offer_id, b.share] for b in offers if b.state != OfferState.REMOVED]


def _state_from_keitaro(state: str) -> OfferState:
    if state == "active":
        return OfferState.ACTIVE
    if state != "disabled":
        logger.warning(
            "unknown offer state in keitaro, treated as disabled", extra={"state": state}
        )
    return OfferState.DISABLED
