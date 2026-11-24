"""Offers editor. Every action changes the draft and returns the whole stream."""

from typing import Annotated

from fastapi import APIRouter, Path

from app.api.deps import EditorDep
from app.api.schemas import AddOffer, PinOffer, StreamOut
from app.api.views import stream_out
from app.db import SessionDep

router = APIRouter(prefix="/streams", tags=["streams"])

StreamId = Annotated[int, Path(gt=0)]
OfferId = Annotated[int, Path(gt=0)]


@router.post("/{stream_id}/offers", response_model=StreamOut)
async def add_offer(stream_id: StreamId, data: AddOffer, session: SessionDep, editor: EditorDep):
    return stream_out(await editor.add_offer(session, stream_id, data.offer_id))


@router.delete("/{stream_id}/offers/{offer_id}", response_model=StreamOut)
async def remove_offer(
    stream_id: StreamId, offer_id: OfferId, session: SessionDep, editor: EditorDep
):
    return stream_out(await editor.remove_offer(session, stream_id, offer_id))


@router.post("/{stream_id}/offers/{offer_id}/restore", response_model=StreamOut)
async def restore_offer(
    stream_id: StreamId, offer_id: OfferId, session: SessionDep, editor: EditorDep
):
    return stream_out(await editor.restore_offer(session, stream_id, offer_id))


@router.patch("/{stream_id}/offers/{offer_id}", response_model=StreamOut)
async def pin_offer(
    stream_id: StreamId, offer_id: OfferId, data: PinOffer, session: SessionDep, editor: EditorDep
):
    return stream_out(await editor.set_pinned(session, stream_id, offer_id, data.pinned))


@router.post("/{stream_id}/cancel", response_model=StreamOut)
async def cancel_draft(stream_id: StreamId, session: SessionDep, editor: EditorDep):
    return stream_out(await editor.cancel(session, stream_id))
