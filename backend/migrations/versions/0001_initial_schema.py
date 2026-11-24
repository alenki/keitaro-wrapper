"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-24 12:49:45
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _offer_state(name: str) -> sa.Enum:
    return sa.Enum(
        "active",
        "disabled",
        "removed",
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
    )


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("alias", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("domain_id", sa.Integer(), nullable=True),
        sa.Column("group_id", sa.Integer(), nullable=True),
        sa.Column("traffic_source_id", sa.Integer(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_campaigns")),
    )
    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("countries", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offers")),
    )
    op.create_table(
        "streams",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("schema_name", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campaign_id"],
            ["campaigns.id"],
            name=op.f("fk_streams_campaign_id_campaigns"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_streams")),
    )
    op.create_index(op.f("ix_streams_campaign_id"), "streams", ["campaign_id"])
    op.create_table(
        "stream_offers",
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("offer_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("state", _offer_state("state"), nullable=False),
        sa.Column("share", sa.Integer(), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("published_state", _offer_state("published_state"), nullable=True),
        sa.Column("published_share", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "published_share IS NULL OR published_share BETWEEN 0 AND 100",
            name=op.f("ck_stream_offers_published_share_range"),
        ),
        sa.CheckConstraint("share BETWEEN 0 AND 100", name=op.f("ck_stream_offers_share_range")),
        sa.ForeignKeyConstraint(
            ["offer_id"], ["offers.id"], name=op.f("fk_stream_offers_offer_id_offers")
        ),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["streams.id"],
            name=op.f("fk_stream_offers_stream_id_streams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stream_id", "offer_id", name=op.f("pk_stream_offers")),
    )
    op.create_index(op.f("ix_stream_offers_offer_id"), "stream_offers", ["offer_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_stream_offers_offer_id"), table_name="stream_offers")
    op.drop_table("stream_offers")
    op.drop_index(op.f("ix_streams_campaign_id"), table_name="streams")
    op.drop_table("streams")
    op.drop_table("offers")
    op.drop_table("campaigns")
