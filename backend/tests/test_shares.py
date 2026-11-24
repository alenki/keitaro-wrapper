from dataclasses import dataclass

import pytest

from app.models import OfferState
from app.services.shares import active_total, rebalance, split_evenly

ACTIVE, DISABLED, REMOVED = OfferState.ACTIVE, OfferState.DISABLED, OfferState.REMOVED


@dataclass
class Slot:
    state: OfferState
    share: int = 0
    pinned: bool = False


@pytest.mark.parametrize(
    ("total", "count", "expected"),
    [
        (100, 1, [100]),
        (100, 2, [50, 50]),
        (100, 3, [34, 33, 33]),
        (100, 4, [25, 25, 25, 25]),
        (100, 6, [17, 17, 17, 17, 16, 16]),
        (75, 2, [38, 37]),
        (2, 3, [1, 1, 0]),
        (0, 2, [0, 0]),
    ],
)
def test_split_evenly_differs_by_at_most_one_and_keeps_the_total(total, count, expected):
    parts = split_evenly(total, count)

    assert parts == expected
    assert sum(parts) == total


def test_split_evenly_into_nothing_is_empty():
    assert split_evenly(100, 0) == []


def test_new_offer_gets_an_equal_share():
    offers = [Slot(ACTIVE, 100), Slot(ACTIVE, 0)]

    assert rebalance(offers) == [50, 50]


def test_pinned_share_stays_and_the_rest_is_split_like_in_the_video():
    offers = [
        Slot(ACTIVE, 0),
        Slot(ACTIVE, 25, pinned=True),
        Slot(REMOVED, 0),
        Slot(ACTIVE, 25),
    ]

    assert rebalance(offers) == [38, 25, 0, 37]


def test_disabled_offers_keep_their_share_and_are_not_counted():
    offers = [Slot(ACTIVE, 50), Slot(DISABLED, 30), Slot(ACTIVE, 0)]

    assert rebalance(offers) == [50, 30, 50]


def test_removed_offers_get_zero():
    offers = [Slot(ACTIVE, 50), Slot(REMOVED, 50)]

    assert rebalance(offers) == [100, 0]


def test_pinned_shares_over_100_leave_nothing_for_the_others():
    offers = [Slot(ACTIVE, 70, pinned=True), Slot(ACTIVE, 40, pinned=True), Slot(ACTIVE, 10)]

    assert rebalance(offers) == [70, 40, 0]


def test_offers_are_left_alone_when_all_are_pinned():
    offers = [Slot(ACTIVE, 25, pinned=True), Slot(ACTIVE, 25, pinned=True)]

    assert rebalance(offers) == [25, 25]


def test_active_total_ignores_disabled_and_removed_offers():
    offers = [Slot(ACTIVE, 60), Slot(DISABLED, 30), Slot(REMOVED, 0), Slot(ACTIVE, 40)]

    assert active_total(offers) == 100
