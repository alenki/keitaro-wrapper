async def open_stream(client, fake_keitaro, offers: list[tuple[int, int]]) -> tuple[int, int]:
    """Create a campaign in the fake Keitaro, open it in the wrapper, return its ids."""
    campaign, _, stream = fake_keitaro.add_campaign_with_streams(offers)
    await client.get(f"/api/campaigns/{campaign['id']}")
    return campaign["id"], stream["id"]


def summary(stream: dict) -> list[tuple]:
    return [(o["offer_id"], o["state"], o["share"]) for o in stream["offers"]]


async def add(client, stream_id: int, offer_id: int):
    return await client.post(f"/api/streams/{stream_id}/offers", json={"offer_id": offer_id})


async def pin(client, stream_id: int, offer_id: int, pinned: bool = True):
    return await client.patch(
        f"/api/streams/{stream_id}/offers/{offer_id}", json={"pinned": pinned}
    )


async def test_added_offer_gets_an_equal_share_and_the_stream_becomes_dirty(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await add(client, stream_id, 18002)

    assert response.status_code == 200
    body = response.json()
    assert summary(body) == [(18001, "active", 50), (18002, "active", 50)]
    assert body["dirty"] is True
    assert body["active_total"] == 100
    assert body["offers"][1]["published_state"] is None
    assert fake_keitaro.requests("PUT") == []


async def test_three_offers_get_34_33_33(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])

    response = await add(client, stream_id, 18003)

    assert [o["share"] for o in response.json()["offers"]] == [34, 33, 33]


async def test_offer_already_in_the_stream_cannot_be_added_again(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await add(client, stream_id, 18001)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "offer_already_added"


async def test_unknown_offer_cannot_be_added(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await add(client, stream_id, 55555)

    assert response.status_code == 422


async def test_removed_offer_turns_grey_and_the_rest_is_split_again(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 34), (18002, 33), (18003, 33)])

    response = await client.delete(f"/api/streams/{stream_id}/offers/18001")

    assert response.status_code == 200
    assert summary(response.json()) == [
        (18001, "removed", 0),
        (18002, "active", 50),
        (18003, "active", 50),
    ]
    assert response.json()["offers"][0]["published_state"] == "active"
    assert response.json()["dirty"] is True


async def test_last_active_offer_cannot_be_removed(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await client.delete(f"/api/streams/{stream_id}/offers/18001")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_active_offer"


async def test_removing_an_offer_added_in_the_draft_just_unlinks_it(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)

    response = await client.delete(f"/api/streams/{stream_id}/offers/18002")

    assert summary(response.json()) == [(18001, "active", 100)]
    assert response.json()["dirty"] is False


async def test_removed_offer_can_be_brought_back(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await client.delete(f"/api/streams/{stream_id}/offers/18002")

    response = await client.post(f"/api/streams/{stream_id}/offers/18002/restore")

    assert response.status_code == 200
    assert summary(response.json()) == [(18001, "active", 50), (18002, "active", 50)]
    assert response.json()["dirty"] is False


async def test_adding_a_removed_offer_brings_it_back(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await client.delete(f"/api/streams/{stream_id}/offers/18002")

    response = await add(client, stream_id, 18002)

    assert summary(response.json()) == [(18001, "active", 50), (18002, "active", 50)]


async def test_only_removed_offers_can_be_brought_back(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await client.post(f"/api/streams/{stream_id}/offers/18001/restore")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "offer_not_removed"


async def test_pinning_keeps_the_numbers_and_the_stream_clean(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 25), (18003, 25)])

    response = await pin(client, stream_id, 18001)

    assert response.status_code == 200
    assert response.json()["offers"][0]["pinned"] is True
    assert [o["share"] for o in response.json()["offers"]] == [50, 25, 25]
    assert response.json()["dirty"] is False


async def test_pinned_share_is_kept_when_offers_are_added(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 25), (18003, 25)])
    await pin(client, stream_id, 18001)

    response = await add(client, stream_id, 18004)

    assert summary(response.json()) == [
        (18001, "active", 50),
        (18002, "active", 17),
        (18003, "active", 17),
        (18004, "active", 16),
    ]


async def test_unpinning_splits_the_shares_again(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 25), (18003, 25)])
    await pin(client, stream_id, 18001)

    response = await pin(client, stream_id, 18001, pinned=False)

    assert [o["share"] for o in response.json()["offers"]] == [34, 33, 33]
    assert response.json()["dirty"] is True


async def test_only_active_offers_can_be_pinned(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await client.delete(f"/api/streams/{stream_id}/offers/18002")

    response = await pin(client, stream_id, 18002)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "offer_not_active"


async def test_cancel_restores_keitaro_values_and_drops_new_offers(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 50), (18002, 50)])
    await add(client, stream_id, 18003)
    await client.delete(f"/api/streams/{stream_id}/offers/18001")

    response = await client.post(f"/api/streams/{stream_id}/cancel")

    assert response.status_code == 200
    assert summary(response.json()) == [(18001, "active", 50), (18002, "active", 50)]
    assert response.json()["dirty"] is False


async def test_draft_is_kept_across_page_reloads(client, fake_keitaro):
    campaign_id, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)

    response = await client.get(f"/api/campaigns/{campaign_id}")

    [stream] = [s for s in response.json()["streams"] if s["id"] == stream_id]
    assert stream["dirty"] is True
    assert summary(stream) == [(18001, "active", 50), (18002, "active", 50)]


async def test_fetch_from_keitaro_drops_the_draft(client, fake_keitaro):
    campaign_id, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])
    await add(client, stream_id, 18002)

    response = await client.post(f"/api/campaigns/{campaign_id}/fetch")

    [stream] = [s for s in response.json()["streams"] if s["id"] == stream_id]
    assert summary(stream) == [(18001, "active", 100)]
    assert stream["dirty"] is False


async def test_stream_without_offers_cannot_be_edited(client, fake_keitaro):
    campaign, geo, _ = fake_keitaro.add_campaign_with_streams([(18001, 100)])
    await client.get(f"/api/campaigns/{campaign['id']}")

    response = await add(client, geo["id"], 18002)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stream_without_offers"


async def test_unknown_stream_is_not_found(client):
    response = await add(client, 424242, 18001)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "stream_not_found"


async def test_offer_that_is_not_in_the_stream_is_not_found(client, fake_keitaro):
    _, stream_id = await open_stream(client, fake_keitaro, [(18001, 100)])

    response = await client.delete(f"/api/streams/{stream_id}/offers/18005")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "offer_not_in_stream"
