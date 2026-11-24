from sqlalchemy import text


def offers_of(body: dict, stream_id: int) -> list[tuple]:
    [stream] = [s for s in body["streams"] if s["id"] == stream_id]
    return [
        (o["offer_id"], o["state"], o["share"], o["published_state"], o["published_share"])
        for o in stream["offers"]
    ]


async def test_campaign_is_fetched_from_keitaro_on_first_open(client, fake_keitaro):
    campaign, geo, offers = fake_keitaro.add_campaign_with_streams(
        [(18001, 33), (18002, 33), (18003, 34)]
    )

    response = await client.get(f"/api/campaigns/{campaign['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "test_karaf_campaign1"
    assert body["keitaro_url"] == (f"http://keitaro.test/admin/#!/campaign/{campaign['id']}/main")
    assert body["domain"] == {"id": 1813, "name": "kt-emulator.test"}
    assert body["group"] == {"id": 10332, "name": "FORTESTS"}
    assert body["traffic_source"] == {"id": 836, "name": "FORTESTS"}
    assert [s["id"] for s in body["streams"]] == [geo["id"], offers["id"]]

    geo_view, offers_view = body["streams"]
    assert geo_view["name"] == "Geo AU"
    assert geo_view["has_offers"] is False
    assert geo_view["offers"] == []
    assert offers_view["has_offers"] is True
    assert offers_view["dirty"] is False
    assert offers_view["active_total"] == 100
    assert offers_view["offers"][0] == {
        "offer_id": 18001,
        "name": "18001 Detoxin [HAIR-CL] [vsl es -] CPAHUB v2",
        "countries": ["CL"],
        "state": "active",
        "share": 33,
        "pinned": False,
        "published_state": "active",
        "published_share": 33,
    }


async def test_opened_campaign_is_served_from_the_database(client, fake_keitaro):
    campaign, _, _ = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    await client.get(f"/api/campaigns/{campaign['id']}")

    await client.get(f"/api/campaigns/{campaign['id']}")

    assert len(fake_keitaro.requests("GET", f"/campaigns/{campaign['id']}")) == 1


async def test_offers_deleted_in_keitaro_become_removed_after_fetch(client, fake_keitaro):
    campaign, _, offers = fake_keitaro.add_campaign_with_streams(
        [(18001, 34), (18002, 33), (18003, 33)]
    )
    await client.get(f"/api/campaigns/{campaign['id']}")
    fake_keitaro.set_stream_offers(offers["id"], [(18002, 25, "active"), (18003, 25, "active")])

    response = await client.post(f"/api/campaigns/{campaign['id']}/fetch")

    assert response.status_code == 200
    assert offers_of(response.json(), offers["id"]) == [
        (18001, "removed", 0, "removed", 0),
        (18002, "active", 25, "active", 25),
        (18003, "active", 25, "active", 25),
    ]
    [stream] = [s for s in response.json()["streams"] if s["id"] == offers["id"]]
    assert stream["active_total"] == 50
    assert stream["dirty"] is False


async def test_offers_added_in_keitaro_are_appended_after_fetch(client, fake_keitaro):
    campaign, _, offers = fake_keitaro.add_campaign_with_streams([(18002, 100)])
    await client.get(f"/api/campaigns/{campaign['id']}")
    fake_keitaro.set_stream_offers(offers["id"], [(18001, 50, "active"), (18002, 50, "active")])

    response = await client.post(f"/api/campaigns/{campaign['id']}/fetch")

    assert offers_of(response.json(), offers["id"]) == [
        (18002, "active", 50, "active", 50),
        (18001, "active", 50, "active", 50),
    ]


async def test_offers_disabled_in_keitaro_stay_disabled(client, fake_keitaro):
    campaign, _, offers = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    fake_keitaro.set_stream_offers(offers["id"], [(18001, 100, "active"), (18002, 40, "disabled")])

    response = await client.get(f"/api/campaigns/{campaign['id']}")

    assert offers_of(response.json(), offers["id"])[1] == (18002, "disabled", 40, "disabled", 40)


async def test_fetch_keeps_pins_and_unpins_removed_offers(client, fake_keitaro, db_engine):
    campaign, _, offers = fake_keitaro.add_campaign_with_streams([(18001, 50), (18002, 50)])
    await client.get(f"/api/campaigns/{campaign['id']}")
    async with db_engine.begin() as conn:
        await conn.execute(text("UPDATE stream_offers SET pinned = true"))
    fake_keitaro.set_stream_offers(offers["id"], [(18002, 100, "active")])

    response = await client.post(f"/api/campaigns/{campaign['id']}/fetch")

    [stream] = [s for s in response.json()["streams"] if s["id"] == offers["id"]]
    assert [(o["offer_id"], o["pinned"]) for o in stream["offers"]] == [
        (18001, False),
        (18002, True),
    ]


async def test_streams_deleted_in_keitaro_disappear_after_fetch(client, fake_keitaro):
    campaign, geo, offers = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    await client.get(f"/api/campaigns/{campaign['id']}")
    del fake_keitaro.streams[geo["id"]]

    response = await client.post(f"/api/campaigns/{campaign['id']}/fetch")

    assert [s["id"] for s in response.json()["streams"]] == [offers["id"]]


async def test_campaign_deleted_in_keitaro_is_removed_locally(client, fake_keitaro, db_engine):
    campaign, _, _ = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    await client.get(f"/api/campaigns/{campaign['id']}")
    del fake_keitaro.campaigns[campaign["id"]]

    response = await client.post(f"/api/campaigns/{campaign['id']}/fetch")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "campaign_not_found"
    async with db_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM campaigns")) == 0


async def test_unknown_campaign_is_not_found(client):
    response = await client.get("/api/campaigns/424242")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "campaign_not_found"


async def test_offer_missing_from_the_catalog_gets_a_placeholder_name(client, fake_keitaro):
    campaign, _, offers = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    fake_keitaro.set_stream_offers(offers["id"], [(18001, 50, "active"), (99999, 50, "active")])

    response = await client.get(f"/api/campaigns/{campaign['id']}")

    [stream] = [s for s in response.json()["streams"] if s["id"] == offers["id"]]
    assert stream["offers"][1]["name"] == "Оффер #99999"


async def test_campaign_list_comes_from_keitaro_newest_first(client, fake_keitaro):
    first = fake_keitaro.add_campaign("test_karaf_first")
    second = fake_keitaro.add_campaign("test_karaf_second")

    response = await client.get("/api/campaigns")

    assert response.status_code == 200
    assert [(c["id"], c["name"]) for c in response.json()] == [
        (second["id"], "test_karaf_second"),
        (first["id"], "test_karaf_first"),
    ]
    assert set(response.json()[0]) == {"id", "name", "alias", "state", "updated_at"}
