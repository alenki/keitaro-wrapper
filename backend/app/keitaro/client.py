import asyncio
import logging
import time
from collections.abc import Sequence
from functools import lru_cache
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError

from app import __version__
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroError,
    KeitaroNotFound,
    KeitaroRejected,
    KeitaroUnavailable,
)
from app.keitaro.schemas import KtCampaign, KtNamed, KtOffer, KtStream

logger = logging.getLogger("app.keitaro")

IDEMPOTENT_METHODS = {"GET", "PUT", "DELETE"}
RETRYABLE_STATUSES = {502, 503, 504}
# The request never left this machine, so even a POST can be sent again
NOT_SENT_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout)


class KeitaroClient:
    """Typed client for the part of the Keitaro Admin API the wrapper uses."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_delays: Sequence[float] = (0.3, 0.9),
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=f"{base_url}/admin_api/v1",
            headers={"Api-Key": api_key, "User-Agent": f"keitaro-wrapper/{__version__}"},
            timeout=timeout,
            transport=transport,
        )
        self._retry_delays = tuple(retry_delays)

    async def __aenter__(self) -> "KeitaroClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    # Catalog (read-only in the emulator)

    async def list_offers(self) -> list[KtOffer]:
        return _parse(list[KtOffer], await self._request("GET", "/offers"))

    async def list_domains(self) -> list[KtNamed]:
        return _parse(list[KtNamed], await self._request("GET", "/domains"))

    async def list_groups(self) -> list[KtNamed]:
        data = await self._request("GET", "/groups", params={"type": "campaigns"})
        return _parse(list[KtNamed], data)

    async def list_traffic_sources(self) -> list[KtNamed]:
        return _parse(list[KtNamed], await self._request("GET", "/traffic_sources"))

    # Campaigns

    async def list_campaigns(self) -> list[KtCampaign]:
        return _parse(list[KtCampaign], await self._request("GET", "/campaigns"))

    async def get_campaign(self, campaign_id: int) -> KtCampaign:
        return _parse(KtCampaign, await self._request("GET", f"/campaigns/{campaign_id}"))

    async def create_campaign(self, payload: dict[str, Any]) -> KtCampaign:
        return _parse(KtCampaign, await self._request("POST", "/campaigns", json=payload))

    async def delete_campaign(self, campaign_id: int) -> None:
        await self._request("DELETE", f"/campaigns/{campaign_id}")

    # Streams

    async def list_streams(self, campaign_id: int) -> list[KtStream]:
        data = await self._request("GET", f"/campaigns/{campaign_id}/streams")
        return _parse(list[KtStream], data)

    async def get_stream(self, stream_id: int) -> KtStream:
        return _parse(KtStream, await self._request("GET", f"/streams/{stream_id}"))

    async def create_stream(self, payload: dict[str, Any]) -> KtStream:
        return _parse(KtStream, await self._request("POST", "/streams", json=payload))

    async def update_stream_offers(self, stream_id: int, offers: list[dict[str, Any]]) -> KtStream:
        """Replace the whole offer list of a stream (that is how Keitaro treats `offers`)."""
        data = await self._request("PUT", f"/streams/{stream_id}", json={"offers": offers})
        return _parse(KtStream, data)

    async def _request(
        self, method: str, path: str, *, json: Any = None, params: dict | None = None
    ) -> Any:
        attempt = 0
        while True:
            attempt += 1
            started = time.perf_counter()
            try:
                response = await self._http.request(method, path, json=json, params=params)
            except httpx.TransportError as exc:
                _log(logging.WARNING, method, path, None, started, attempt, type(exc).__name__)
                if self._can_retry(method, attempt, exc):
                    await asyncio.sleep(self._retry_delays[attempt - 1])
                    continue
                raise KeitaroUnavailable(f"Keitaro не отвечает ({type(exc).__name__})") from exc

            status = response.status_code
            if status >= 400:
                _log(logging.WARNING, method, path, status, started, attempt, _error_text(response))
                if status in RETRYABLE_STATUSES and self._can_retry(method, attempt):
                    await asyncio.sleep(self._retry_delays[attempt - 1])
                    continue
                raise _error_for(response)

            _log(logging.INFO, method, path, status, started, attempt)
            try:
                return response.json()
            except ValueError as exc:
                raise KeitaroError("Keitaro вернул ответ не в формате JSON") from exc

    def _can_retry(self, method: str, attempt: int, exc: Exception | None = None) -> bool:
        if attempt > len(self._retry_delays):
            return False
        return method in IDEMPOTENT_METHODS or isinstance(exc, NOT_SENT_ERRORS)


def _log(level, method, path, status, started, attempt, error: str | None = None) -> None:
    extra = {
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": round((time.perf_counter() - started) * 1000),
        "attempt": attempt,
    }
    if error:
        extra["error"] = error
    logger.log(level, "keitaro call", extra=extra)


def _error_text(response: httpx.Response) -> str:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        error = None
    return str(error) if error else (response.text[:300] or f"HTTP {response.status_code}")


def _error_for(response: httpx.Response) -> KeitaroError:
    status = response.status_code
    message = _error_text(response)
    if status in (401, 403):
        return KeitaroAuthError(message, status=status)
    if status == 404:
        return KeitaroNotFound(message, status=status)
    if status >= 500:
        return KeitaroUnavailable(message, status=status)
    return KeitaroRejected(message, status=status)


@lru_cache
def _adapter(model_type: Any) -> TypeAdapter:
    return TypeAdapter(model_type)


def _parse(model_type: Any, data: Any) -> Any:
    try:
        return _adapter(model_type).validate_python(data)
    except ValidationError as exc:
        logger.error("unexpected keitaro response", extra={"error": str(exc)[:500]})
        raise KeitaroError("Keitaro вернул ответ в неожиданном формате") from exc
