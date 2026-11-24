import json
import logging

import httpx
import pytest

from app.keitaro.client import KeitaroClient
from app.keitaro.errors import (
    KeitaroAuthError,
    KeitaroError,
    KeitaroNotFound,
    KeitaroRejected,
    KeitaroUnavailable,
)

STREAM = {
    "id": 61,
    "name": "Offers",
    "campaign_id": 34,
    "position": 2,
    "state": "active",
    "type": "default",
    "schema": "landings",
    "action_type": "http",
    "filters": [],
    "offers": [
        {"id": 79, "stream_id": 61, "offer_id": 18001, "state": "active", "share": 50},
        {"id": 80, "stream_id": 61, "offer_id": 18002, "state": "active", "share": 50},
    ],
}


def keitaro(handler) -> KeitaroClient:
    return KeitaroClient(
        "http://kt.test",
        "secret-key",
        transport=httpx.MockTransport(handler),
        retry_delays=(0, 0),
    )


def replies(*responses):
    """Handler that returns the given responses in order and remembers the requests."""
    queue = list(responses)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    handler.seen = seen
    return handler


async def test_requests_carry_api_key_and_user_agent():
    handler = replies(httpx.Response(200, json=[{"id": 1813, "name": "kt-emulator.test"}]))

    async with keitaro(handler) as kt:
        domains = await kt.list_domains()

    assert domains[0].id == 1813
    request = handler.seen[0]
    assert str(request.url) == "http://kt.test/admin_api/v1/domains"
    assert request.headers["Api-Key"] == "secret-key"
    assert request.headers["User-Agent"].startswith("keitaro-wrapper/")


async def test_groups_are_requested_for_campaigns():
    handler = replies(httpx.Response(200, json=[{"id": 10332, "name": "FORTESTS"}]))

    async with keitaro(handler) as kt:
        await kt.list_groups()

    assert handler.seen[0].url.params["type"] == "campaigns"


async def test_stream_is_parsed_with_offers():
    handler = replies(httpx.Response(200, json=STREAM))

    async with keitaro(handler) as kt:
        stream = await kt.get_stream(61)

    assert stream.schema_name == "landings"
    assert [(o.offer_id, o.share, o.state) for o in stream.offers] == [
        (18001, 50, "active"),
        (18002, 50, "active"),
    ]


async def test_update_stream_offers_sends_only_the_offers():
    handler = replies(httpx.Response(200, json=STREAM))
    offers = [{"offer_id": 18001, "share": 100, "state": "active"}]

    async with keitaro(handler) as kt:
        await kt.update_stream_offers(61, offers)

    request = handler.seen[0]
    assert request.method == "PUT"
    assert request.url.path == "/admin_api/v1/streams/61"
    assert json.loads(request.content) == {"offers": offers}


async def test_not_found_keeps_keitaro_message():
    handler = replies(httpx.Response(404, json={"error": "Campaign not found"}))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroNotFound, match="Campaign not found"):
            await kt.get_campaign(999)


async def test_rejected_api_key_is_an_auth_error():
    handler = replies(httpx.Response(401, json={"error": "Unauthorized"}))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroAuthError):
            await kt.list_offers()


async def test_validation_error_keeps_keitaro_message_and_status():
    handler = replies(httpx.Response(406, json={"error": "offers: offer 1 does not exist"}))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroRejected, match="offer 1 does not exist") as error:
            await kt.update_stream_offers(61, [])

    assert error.value.status == 406


async def test_unexpected_response_shape_is_a_keitaro_error():
    handler = replies(httpx.Response(200, json={"unexpected": True}))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroError):
            await kt.get_stream(61)


async def test_get_is_retried_after_service_unavailable():
    handler = replies(httpx.Response(503), httpx.Response(200, json=[]))

    async with keitaro(handler) as kt:
        assert await kt.list_offers() == []

    assert len(handler.seen) == 2


async def test_get_gives_up_after_three_attempts():
    handler = replies(httpx.Response(503))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroUnavailable):
            await kt.list_offers()

    assert len(handler.seen) == 3


async def test_read_timeout_on_get_is_retried():
    handler = replies(httpx.ReadTimeout("slow"), httpx.Response(200, json=[]))

    async with keitaro(handler) as kt:
        assert await kt.list_offers() == []

    assert len(handler.seen) == 2


async def test_post_is_not_retried_after_server_error():
    handler = replies(httpx.Response(500, json={"error": "boom"}))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroUnavailable):
            await kt.create_campaign({"name": "test_karaf_x"})

    assert len(handler.seen) == 1


async def test_post_is_not_retried_after_read_timeout():
    handler = replies(httpx.ReadTimeout("slow"))

    async with keitaro(handler) as kt:
        with pytest.raises(KeitaroUnavailable):
            await kt.create_campaign({"name": "test_karaf_x"})

    assert len(handler.seen) == 1


async def test_post_is_retried_when_the_connection_failed():
    created = {"id": 34, "name": "test_karaf_x", "alias": "dd01567f", "state": "active"}
    handler = replies(httpx.ConnectError("refused"), httpx.Response(200, json=created))

    async with keitaro(handler) as kt:
        campaign = await kt.create_campaign({"name": "test_karaf_x"})

    assert campaign.id == 34
    assert len(handler.seen) == 2


async def test_calls_are_logged_without_the_api_key(caplog):
    caplog.set_level(logging.INFO, logger="app.keitaro")
    handler = replies(httpx.Response(503), httpx.Response(200, json=[]))

    async with keitaro(handler) as kt:
        await kt.list_offers()

    records = [r for r in caplog.records if r.name.startswith("app.keitaro")]
    assert [(r.method, r.path, r.status, r.attempt) for r in records] == [
        ("GET", "/offers", 503, 1),
        ("GET", "/offers", 200, 2),
    ]
    assert all(r.duration_ms >= 0 for r in records)
    assert "secret-key" not in caplog.text
    assert all("secret-key" not in str(vars(r)) for r in records)
