from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, MetaData, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Stable constraint names, so migrations don't depend on what Postgres would generate
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class OfferState(StrEnum):
    """State of an offer inside a stream. Keitaro knows active and disabled, removed is ours."""

    ACTIVE = "active"
    DISABLED = "disabled"
    REMOVED = "removed"


def _offer_state_column(name: str) -> Enum:
    return Enum(
        OfferState,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda states: [state.value for state in states],
    )


class Offer(Base):
    """Copy of an offer from the Keitaro catalog, used for search and for names."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    state: Mapped[str]
    countries: Mapped[list[str]] = mapped_column(ARRAY(String))
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]
    alias: Mapped[str]
    state: Mapped[str]
    domain_id: Mapped[int | None]
    group_id: Mapped[int | None]
    traffic_source_id: Mapped[int | None]
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    streams: Mapped[list["Stream"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Stream.position",
        lazy="selectin",
    )


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    position: Mapped[int]
    type: Mapped[str]
    # Keitaro "schema": landings (landings and offers), redirect or action
    schema_name: Mapped[str]
    state: Mapped[str]
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    campaign: Mapped[Campaign] = relationship(back_populates="streams")
    offers: Mapped[list["StreamOffer"]] = relationship(
        back_populates="stream",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StreamOffer.position",
        lazy="selectin",
    )

    @property
    def has_offers(self) -> bool:
        return self.schema_name == "landings"


class StreamOffer(Base):
    """An offer in a stream: the draft (state, share) and what Keitaro has (published_*).

    published_state is None while the offer was never pushed to Keitaro.
    """

    __tablename__ = "stream_offers"
    __table_args__ = (
        CheckConstraint("share BETWEEN 0 AND 100", name="share_range"),
        CheckConstraint(
            "published_share IS NULL OR published_share BETWEEN 0 AND 100",
            name="published_share_range",
        ),
    )

    stream_id: Mapped[int] = mapped_column(
        ForeignKey("streams.id", ondelete="CASCADE"), primary_key=True
    )
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True, index=True)
    position: Mapped[int]
    state: Mapped[OfferState] = mapped_column(_offer_state_column("state"))
    share: Mapped[int]
    pinned: Mapped[bool] = mapped_column(default=False)
    published_state: Mapped[OfferState | None] = mapped_column(
        _offer_state_column("published_state")
    )
    published_share: Mapped[int | None]

    stream: Mapped[Stream] = relationship(back_populates="offers")
    offer: Mapped[Offer] = relationship(lazy="joined")
