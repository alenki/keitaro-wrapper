"""How offer shares inside one stream are recalculated."""

from collections.abc import Sequence
from typing import Protocol

from app.models import OfferState

TOTAL = 100


class ShareSlot(Protocol):
    state: OfferState
    share: int
    pinned: bool


def split_evenly(total: int, count: int) -> list[int]:
    """Split `total` into `count` whole numbers that differ by at most 1.

    The leftover points go to the first items: 100 into 3 parts is [34, 33, 33].
    """
    if count <= 0:
        return []
    base, leftover = divmod(total, count)
    return [base + 1 if i < leftover else base for i in range(count)]


def rebalance(offers: Sequence[ShareSlot]) -> list[int]:
    """New shares for the offers of a stream, in the same order.

    Pinned active offers keep their share, and whatever is left of 100 is split evenly
    between the other active offers. Disabled offers keep their share, removed ones get 0.
    """
    active = [offer for offer in offers if offer.state == OfferState.ACTIVE]
    pinned_total = sum(offer.share for offer in active if offer.pinned)
    floating = [offer for offer in active if not offer.pinned]
    parts = iter(split_evenly(max(TOTAL - pinned_total, 0), len(floating)))

    shares = []
    for offer in offers:
        if offer.state == OfferState.REMOVED:
            shares.append(0)
        elif offer.state == OfferState.ACTIVE and not offer.pinned:
            shares.append(next(parts))
        else:
            shares.append(offer.share)
    return shares


def active_total(offers: Sequence[ShareSlot]) -> int:
    return sum(offer.share for offer in offers if offer.state == OfferState.ACTIVE)
