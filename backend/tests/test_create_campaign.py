import pytest
from sqlalchemy import text

VALID = {
    "name": "campaign1",
    "geo": ["au"],
    "offer_id": 18001,
    "domain_id": 1813,
    "group_id": 10332,
    "traffic_source_id": 836,
}


async def test_campaign_is_created_with_two_streams(client, fake_keitaro):
    response = await client.post("/api/campaigns", json=VALID)

    assert response.status_code == 201
    campaign_id = response.json()["id"]
    assert response.json()["name"] == "test_karaf_campaign1"

    [create_call] = fake_keitaro.requests("POST", "/campaigns")
    assert create_call.body == {
        "name": "test_karaf_campaign1",
        "type": "position",
        "state": "active",
        "cost_type": "CPC",
        "cost_value": 0,
        "cost_currency": "USD",
        "cost_auto": True,
        "domain_id": 1813,
        "group_id": 10332,
        "traffic_source_id": 836,
    }
    geo_call, offers_call = fake_keitaro.requests("POST", "/streams")
    assert geo_call.body == {
        "campaign_id": campaign_id,
        "name": "Geo AU",
        "type": "regular",
        "schema": "redirect",
        "action_type": "http",
        "action_payload": "https://google.com",
        "filters": [{"name": "country", "mode": "accept", "payload": ["AU"]}],
    }
    assert offers_call.body == {
        "campaign_id": campaign_id,
        "name": "Offers",
        "type": "default",
        "schema": "landings",
        "action_type": "http",
        "offers": [{"offer_id": 18001, "share": 100, "state": "active"}],
    }


async def test_created_campaign_is_ready_for_the_editor(client, fake_keitaro):
    response = await client.post("/api/campaigns", json=VALID)

    geo, offers = response.json()["streams"]
    assert (geo["name"], geo["has_offers"]) == ("Geo AU", False)
    assert offers["dirty"] is False
    assert [(o["offer_id"], o["share"], o["published_state"]) for o in offers["offers"]] == [
        (18001, 100, "active")
    ]

    calls_before = len(fake_keitaro.calls)
    editor = await client.get(f"/api/campaigns/{response.json()['id']}")
    assert editor.status_code == 200
    assert len(fake_keitaro.calls) == calls_before


async def test_prefix_is_not_added_twice(client):
    response = await client.post("/api/campaigns", json={**VALID, "name": "test_karaf_promo"})

    assert response.json()["name"] == "test_karaf_promo"


async def test_several_countries_go_into_one_filter(client, fake_keitaro):
    await client.post("/api/campaigns", json={**VALID, "geo": ["mx", " AU ", "MX"]})

    geo_call = fake_keitaro.requests("POST", "/streams")[0]
    assert geo_call.body["name"] == "Geo MX, AU"
    assert geo_call.body["filters"][0]["payload"] == ["MX", "AU"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("geo", ["XX"]), ("geo", []), ("name", "   "), ("offer_id", 0), ("group_id", "abc")],
)
async def test_invalid_input_is_rejected_before_calling_keitaro(client, fake_keitaro, field, value):
    response = await client.post("/api/campaigns", json={**VALID, field: value})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"].startswith(field)
    assert fake_keitaro.requests("POST") == []


async def test_unknown_country_code_is_named_in_the_error(client):
    response = await client.post("/api/campaigns", json={**VALID, "geo": ["AU", "UK"]})

    assert "UK" in response.json()["error"]["details"][0]["message"]


async def test_unknown_offer_is_rejected(client, fake_keitaro):
    response = await client.post("/api/campaigns", json={**VALID, "offer_id": 55555})

    assert response.status_code == 422
    assert response.json()["error"]["details"] == [
        {"field": "offer_id", "message": "Оффер 55555 не найден в Keitaro"}
    ]
    assert fake_keitaro.requests("POST") == []


async def test_unknown_group_is_rejected(client, fake_keitaro):
    response = await client.post("/api/campaigns", json={**VALID, "group_id": 1})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "group_id"
    assert fake_keitaro.requests("POST") == []


async def test_duplicate_name_is_rejected(client, fake_keitaro):
    fake_keitaro.add_campaign("test_karaf_campaign1")

    response = await client.post("/api/campaigns", json=VALID)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_name"
    assert fake_keitaro.requests("POST", "/campaigns") == []


async def test_campaign_is_deleted_when_a_stream_fails(client, fake_keitaro, db_engine):
    fake_keitaro.fail("POST", "/streams", status=500, skip=1)

    response = await client.post("/api/campaigns", json=VALID)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "campaign_not_created"
    assert len(fake_keitaro.requests("DELETE")) == 1
    assert fake_keitaro.campaigns == {}
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM campaigns")) == 0


async def test_failed_rollback_tells_which_campaign_to_delete(client, fake_keitaro):
    campaign_id = fake_keitaro.next_id + 1
    fake_keitaro.fail("POST", "/streams", status=500)
    fake_keitaro.fail("DELETE", f"/campaigns/{campaign_id}", status=503, times=3)

    response = await client.post("/api/campaigns", json=VALID)

    assert response.status_code == 502
    error = response.json()["error"]
    assert error["code"] == "campaign_partially_created"
    assert f"#{campaign_id}" in error["message"]


async def test_campaign_rejected_by_keitaro_needs_no_rollback(client, fake_keitaro):
    fake_keitaro.fail("POST", "/campaigns", status=406, error="name: too long")

    response = await client.post("/api/campaigns", json=VALID)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "keitaro_rejected"
    assert "too long" in response.json()["error"]["message"]
    assert fake_keitaro.requests("DELETE") == []
