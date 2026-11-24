async def test_offers_are_found_by_name(client):
    response = await client.get("/api/offers", params={"q": "detox"})

    assert response.status_code == 200
    assert response.json() == [
        {"id": 18001, "name": "18001 Detoxin [HAIR-CL] [vsl es -] CPAHUB v2", "countries": ["CL"]}
    ]


async def test_offers_are_found_by_id_prefix(client):
    response = await client.get("/api/offers", params={"q": "1810"})

    assert [offer["id"] for offer in response.json()] == [18100]


async def test_like_wildcards_in_the_query_are_literal(client):
    response = await client.get("/api/offers", params={"q": "%"})

    assert response.json() == []


async def test_empty_query_returns_the_first_offers_by_id(client):
    response = await client.get("/api/offers", params={"limit": 2})

    assert [offer["id"] for offer in response.json()] == [18001, 18002]


async def test_offer_limit_is_validated(client):
    response = await client.get("/api/offers", params={"limit": 500})

    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "limit"


async def test_offers_catalog_is_loaded_once_within_ttl(client, fake_keitaro):
    await client.get("/api/offers", params={"q": "a"})
    await client.get("/api/offers", params={"q": "b"})

    assert len(fake_keitaro.requests("GET", "/offers")) == 1


async def test_offers_catalog_is_reloaded_after_ttl(make_client, fake_keitaro):
    async with make_client(catalog_ttl_seconds=0) as client:
        await client.get("/api/offers")
        await client.get("/api/offers")

    assert len(fake_keitaro.requests("GET", "/offers")) == 2


async def test_campaign_form_has_prefix_and_catalog_lists(client):
    response = await client.get("/api/campaign-form")

    assert response.status_code == 200
    body = response.json()
    countries = body.pop("countries")
    assert body == {
        "prefix": "test_karaf_",
        "domains": [{"id": 1813, "name": "kt-emulator.test"}],
        "groups": [{"id": 10332, "name": "FORTESTS"}],
        "traffic_sources": [{"id": 836, "name": "FORTESTS"}],
    }
    # The same ISO 3166-1 list the backend validates with, so the form can check codes too
    assert len(countries) == 249
    assert {"AU", "GB", "MX", "RO"} <= set(countries)
    assert not {"UK", "EU", "XK"} & set(countries)


async def test_campaign_form_lists_are_cached(client, fake_keitaro):
    await client.get("/api/campaign-form")
    await client.get("/api/campaign-form")

    assert len(fake_keitaro.requests("GET", "/domains")) == 1
    assert len(fake_keitaro.requests("GET", "/groups")) == 1
    assert len(fake_keitaro.requests("GET", "/traffic_sources")) == 1


async def test_rejected_api_key_is_reported_as_bad_gateway(make_client):
    async with make_client(keitaro_api_key="wrong-key") as client:
        response = await client.get("/api/campaign-form")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "keitaro_auth"


async def test_keitaro_outage_is_reported_as_bad_gateway(client, fake_keitaro):
    fake_keitaro.fail("GET", "/offers", status=503, times=3)

    response = await client.get("/api/offers")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "keitaro_unavailable"
