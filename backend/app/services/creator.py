import logging
from typing import Any, NoReturn

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import ConflictError, CreationFailed, InvalidInputError
from app.keitaro.client import KeitaroClient
from app.keitaro.errors import KeitaroError
from app.models import Campaign
from app.services.catalog import Catalog
from app.services.editor import load_campaign, store_campaign

logger = logging.getLogger(__name__)

GOOGLE_URL = "https://google.com"
# Key for pg_advisory_xact_lock: campaigns are created one at a time across all app processes
CREATE_LOCK_ID = 7_301_001


def full_name(name: str, prefix: str) -> str:
    name = name.strip()
    return name if name.startswith(prefix) else prefix + name


def campaign_payload(
    name: str, *, domain_id: int, group_id: int, traffic_source_id: int
) -> dict[str, Any]:
    # Same settings as the campaign in the task screenshot
    return {
        "name": name,
        "type": "position",
        "state": "active",
        "cost_type": "CPC",
        "cost_value": 0,
        "cost_currency": "USD",
        "cost_auto": True,
        "domain_id": domain_id,
        "group_id": group_id,
        "traffic_source_id": traffic_source_id,
    }


def geo_stream_payload(campaign_id: int, geo: list[str]) -> dict[str, Any]:
    """Visitors from these countries go to Google."""
    return {
        "campaign_id": campaign_id,
        "name": f"Geo {', '.join(geo)}",
        "type": "regular",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": GOOGLE_URL,
        "filters": [{"name": "country", "mode": "accept", "payload": geo}],
    }


def offers_stream_payload(campaign_id: int, offer_id: int) -> dict[str, Any]:
    """Everyone the geo stream didn't take goes to the offer.

    "default" is Keitaro's closing stream type: it only gets visitors no other stream took,
    whatever the rotation type of the campaign.
    """
    return {
        "campaign_id": campaign_id,
        "name": "Offers",
        "type": "default",
        "schema": "landings",
        "action_type": "http",
        "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
    }


class CampaignCreator:
    def __init__(self, keitaro: KeitaroClient, catalog: Catalog, prefix: str) -> None:
        self._keitaro = keitaro
        self._catalog = catalog
        self._prefix = prefix

    async def create(
        self,
        session: AsyncSession,
        *,
        name: str,
        geo: list[str],
        offer_id: int,
        domain_id: int,
        group_id: int,
        traffic_source_id: int,
    ) -> Campaign:
        name = full_name(name, self._prefix)
        await self._check_references(offer_id, domain_id, group_id, traffic_source_id)

        # Held until the transaction ends, so a double click can't pass the check below twice
        await session.execute(select(func.pg_advisory_xact_lock(CREATE_LOCK_ID)))
        if any(campaign.name == name for campaign in await self._keitaro.list_campaigns()):
            raise ConflictError(f'Кампания "{name}" уже есть в Keitaro', code="duplicate_name")

        campaign = await self._keitaro.create_campaign(
            campaign_payload(
                name, domain_id=domain_id, group_id=group_id, traffic_source_id=traffic_source_id
            )
        )
        try:
            geo_stream = await self._keitaro.create_stream(geo_stream_payload(campaign.id, geo))
            offers_stream = await self._keitaro.create_stream(
                offers_stream_payload(campaign.id, offer_id)
            )
        except KeitaroError as exc:
            await self._roll_back(campaign.id, exc)

        await store_campaign(session, self._catalog, campaign, [geo_stream, offers_stream])
        await session.commit()
        logger.info(
            "campaign created",
            extra={
                "campaign_id": campaign.id,
                "campaign_name": name,
                "geo": geo,
                "offer_id": offer_id,
            },
        )
        return await load_campaign(session, campaign.id)

    async def _check_references(
        self, offer_id: int, domain_id: int, group_id: int, traffic_source_id: int
    ) -> None:
        problems = []
        offer = await self._catalog.find_offer(offer_id)
        if offer is None or offer.state != "active":
            problems.append(
                {"field": "offer_id", "message": f"Оффер {offer_id} не найден в Keitaro"}
            )

        options = await self._catalog.campaign_form_options()
        checks = [
            ("domain_id", domain_id, options.domains, f"Домен #{domain_id} не найден в Keitaro"),
            ("group_id", group_id, options.groups, f"Группа #{group_id} не найдена в Keitaro"),
            (
                "traffic_source_id",
                traffic_source_id,
                options.traffic_sources,
                f"Источник #{traffic_source_id} не найден в Keitaro",
            ),
        ]
        for field, value, items, message in checks:
            if value not in {item.id for item in items}:
                problems.append({"field": field, "message": message})

        if problems:
            raise InvalidInputError("Проверьте введённые данные", details=problems)

    async def _roll_back(self, campaign_id: int, cause: KeitaroError) -> NoReturn:
        """Delete a campaign whose streams could not be created, then report the failure."""
        try:
            await self._keitaro.delete_campaign(campaign_id)
        except KeitaroError as exc:
            logger.error(
                "rollback failed, campaign left in keitaro",
                extra={"campaign_id": campaign_id, "error": exc.message},
            )
            raise CreationFailed(
                f"Не удалось создать потоки, и кампанию #{campaign_id} не получилось удалить. "
                f"Удалите её в Keitaro вручную. Причина: {cause.message}",
                code="campaign_partially_created",
            ) from cause

        logger.warning(
            "campaign creation rolled back",
            extra={"campaign_id": campaign_id, "error": cause.message},
        )
        raise CreationFailed(
            f"Не удалось создать потоки, кампания удалена. Причина: {cause.message}"
        ) from cause
