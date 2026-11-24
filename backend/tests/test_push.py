async def open_stream(client, fake_keitaro, offers):
    campaign, _, stream = fake_keitaro.add_campaign_with_streams(offers)
    await client.get(f"/api/campaigns/{campaign['id']}")
    return campaign["id"], stream["id"]


async def add(client, stream_id: int, offer_id: int):
    return await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": offer_id})


def published(stream: dict) -> list[tuple]:
    return [(o["offer_id"], o["published_state"], o["published_share"]) for o in stream["offers"]]


async def test_push_sends_the_draft_to_keitaro(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 200
    [put] = fake_keitaro.requests("PUT")
    assert put.path == f"/streams/{stream_id}"
    assert put.body == {
        "offers": [
            {"offer_id": 18001, "share": 50, "state": "active"},
            {"offer_id": 18002, "share": 50, "state": "active"},
        ]
    }
    assert fake_keitaro.stream_offers(stream_id) == [(18001, 50, "active"), (18002, 50, "active")]
    assert response.json()["dirty"] is False
    assert published(response.json()) == [(18001, "active", 50), (18002, "active", 50)]


async def test_pushed_removal_keeps_the_offer_in_the_archive(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await client.delete(f"/api/streams/{stream_id}/offers/18002")

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert fake_keitaro.stream_offers(stream_id) == [(18001, 100, "active")]
    assert published(response.json()) == [(18001, "active", 100), (18002, "removed", 0)]
    assert response.json()["offers"][1]["state"] == "removed"
    assert response.json()["dirty"] is False


async def test_brought_back_offer_returns_to_keitaro(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await client.delete(f"/api/streams/{stream_id}/offers/18002")
    await client.post(f"/api/streams/{stream_id}/push")
    assert fake_keitaro.stream_offers(stream_id) == [(18001, 100, "active")]
    await client.post(f"/api/streams/{stream_id}/offers/18002/restore")

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 200
    assert fake_keitaro.stream_offers(stream_id) == [(18001, 50, "active"), (18002, 50, "active")]


async def test_pinned_share_reaches_keitaro_like_in_the_video(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 25), (18002, 25)])
    await client.patch(f"/api/streams/{stream_id}/offers/18002", json={"pinned": True})
    await add(client, stream_id, 18003)

    await client.post(f"/api/streams/{stream_id}/push")

    assert fake_keitaro.stream_offers(stream_id) == [
        (18001, 38, "active"),
        (18002, 25, "active"),
        (18003, 37, "active"),
    ]


async def test_push_without_changes_does_not_call_keitaro(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    calls_before = len(fake_keitaro.calls)

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 200
    assert len(fake_keitaro.calls) == calls_before


async def test_push_is_refused_when_shares_do_not_add_up_to_100(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 60), (18002, 60)])
    for offer_id in (18001, 18002):
        await client.patch(f"/api/streams/{stream_id}/offers/{offer_id}", json={"pinned": True})
    await add(client, stream_id, 18003)

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "shares_not_100"
    assert "120" in response.json()["error"]["message"]
    assert fake_keitaro.requests("PUT") == []


async def test_push_is_refused_when_keitaro_changed_after_the_fetch(client, fake_keitaro):
    campaign_id, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)
    fake_keitaro.set_stream_offers(stream_id, [(18001, 70, "active"), (18004, 30, "active")])

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stream_changed_in_keitaro"
    assert fake_keitaro.requests("PUT") == []
    campaign = await client.get(f"/api/campaigns/{campaign_id}")
    [stream] = [s for s in campaign.json()["streams"] if s["id"] == stream_id]
    assert stream["dirty"] is True


async def test_push_after_a_lost_answer_just_marks_the_stream_published(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)
    # The earlier PUT reached Keitaro, but its answer never came back
    fake_keitaro.set_stream_offers(stream_id, [(18001, 50, "active"), (18002, 50, "active")])

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 200
    assert fake_keitaro.requests("PUT") == []
    assert response.json()["dirty"] is False


async def test_keitaro_failure_keeps_the_draft(client, fake_keitaro):
    campaign_id, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)
    fake_keitaro.fail("PUT", f"/streams/{stream_id}", status=503, times=3)

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "keitaro_unavailable"
    campaign = await client.get(f"/api/campaigns/{campaign_id}")
    [stream] = [s for s in campaign.json()["streams"] if s["id"] == stream_id]
    assert stream["dirty"] is True
    assert [o["share"] for o in stream["offers"]] == [50, 50]


async def test_disabled_offers_are_pushed_unchanged(client, fake_keitaro):
    campaign, _, stream = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    fake_keitaro.set_stream_offers(stream["id"], [(18001, 100, "active"), (18002, 40, "disabled")])
    await client.get(f"/api/campaigns/{campaign['id']}")
    await add(client, stream["id"], 18003)

    await client.post(f"/api/streams/{stream['id']}/push")

    assert fake_keitaro.stream_offers(stream["id"]) == [
        (18001, 50, "active"),
        (18002, 40, "disabled"),
        (18003, 50, "active"),
    ]


async def test_stream_deleted_in_keitaro_cannot_be_pushed(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)
    del fake_keitaro.streams[stream_id]

    response = await client.post(f"/api/streams/{stream_id}/push")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "stream_not_found"
