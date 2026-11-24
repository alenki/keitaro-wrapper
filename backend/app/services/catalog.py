import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import String, cast, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.keitaro.client import KeitaroClient
from app.keitaro.schemas import KtNamed
from app.models import Offer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CampaignFormOptions:
    domains: list[KtNamed]
    groups: list[KtNamed]
    traffic_sources: list[KtNamed]


class Catalog:
    """Read-only part of Keitaro: offers, domains, campaign groups and traffic sources.

    Offers are copied into Postgres because stream offers reference them and search runs in
    SQL. The other lists are tiny, so they are only cached in memory. Both are reloaded from
    Keitaro when older than the TTL, which keeps the number of calls to Keitaro low.
    """

    def __init__(
        self,
        keitaro: KeitaroClient,
        session_factory: async_sessionmaker[AsyncSession],
        ttl_seconds: int,
    ) -> None:
        self._keitaro = keitaro
        self._session_factory = session_factory
        self._ttl = ttl_seconds
        self._offers_loaded_at: float | None = None
        self._offers_lock = asyncio.Lock()
        self._lists: dict[str, tuple[float, list[KtNamed]]] = {}

    async def search_offers(self, query: str, limit: int) -> list[Offer]:
        """Active offers whose id starts with the query or whose name contains it."""
        await self._refresh_offers_if_stale()
        stmt = select(Offer).where(Offer.state == "active").order_by(Offer.id).limit(limit)
        query = query.strip()
        if query:
            escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            stmt = stmt.where(
                or_(
                    Offer.name.ilike(f"%{escaped}%", escape="\\"),
                    cast(Offer.id, String).like(f"{escaped}%", escape="\\"),
                )
            )
        async with self._session_factory() as session:
            return list(await session.scalars(stmt))

    async def find_offer(self, offer_id: int) -> Offer | None:
        await self._refresh_offers_if_stale()
        async with self._session_factory() as session:
            return await session.get(Offer, offer_id)

    async def ensure_offers(self, offer_ids: Iterable[int]) -> None:
        """Make sure every id has a row, because stream offers point to the offers table."""
        missing = set(offer_ids) - await self._existing_ids(set(offer_ids))
        if not missing:
            return
        await self.refresh_offers()
        missing -= await self._existing_ids(missing)
        if missing:
            # A stream still uses an offer that the catalog no longer returns
            logger.warning("offers missing from the catalog", extra={"offer_ids": sorted(missing)})
            await self._upsert(
                [
                    {
                        "id": offer_id,
                        "name": f"Оффер #{offer_id}",
                        "state": "unknown",
                        "countries": [],
                    }
                    for offer_id in missing
                ],
                update=False,
            )

    async def refresh_offers(self) -> None:
        offers = await self._keitaro.list_offers()
        await self._upsert(
            [{"id": o.id, "name": o.name, "state": o.state, "countries": o.country} for o in offers]
        )
        self._offers_loaded_at = time.monotonic()
        logger.info("offers catalog refreshed", extra={"count": len(offers)})

    async def campaign_form_options(self) -> CampaignFormOptions:
        domains, groups, sources = await asyncio.gather(
            self._cached("domains", self._keitaro.list_domains),
            self._cached("groups", self._keitaro.list_groups),
            self._cached("traffic_sources", self._keitaro.list_traffic_sources),
        )
        return CampaignFormOptions(domains=domains, groups=groups, traffic_sources=sources)

    def _offers_are_fresh(self) -> bool:
        loaded_at = self._offers_loaded_at
        return loaded_at is not None and time.monotonic() - loaded_at < self._ttl

    async def _refresh_offers_if_stale(self) -> None:
        if self._offers_are_fresh():
            return
        async with self._offers_lock:
            # Another request may have refreshed the catalog while this one waited
            if not self._offers_are_fresh():
                await self.refresh_offers()

    async def _existing_ids(self, offer_ids: set[int]) -> set[int]:
        if not offer_ids:
            return set()
        async with self._session_factory() as session:
            return set(await session.scalars(select(Offer.id).where(Offer.id.in_(offer_ids))))

    async def _upsert(self, rows: list[dict], *, update: bool = True) -> None:
        if not rows:
            return
        now = datetime.now(UTC)
        stmt = insert(Offer).values([{**row, "synced_at": now} for row in rows])
        if update:
            excluded = stmt.excluded
            stmt = stmt.on_conflict_do_update(
                index_elements=[Offer.id],
                set_={
                    "name": excluded.name,
                    "state": excluded.state,
                    "countries": excluded.countries,
                    "synced_at": excluded.synced_at,
                },
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=[Offer.id])
        async with self._session_factory() as session:
            await session.execute(stmt)
            await session.commit()

    async def _cached(
        self, key: str, load: Callable[[], Awaitable[list[KtNamed]]]
    ) -> list[KtNamed]:
        cached = self._lists.get(key)
        if cached and time.monotonic() - cached[0] < self._ttl:
            return cached[1]
        value = await load()
        self._lists[key] = (time.monotonic(), value)
        return value
