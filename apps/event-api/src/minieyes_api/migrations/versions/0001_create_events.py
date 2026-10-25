"""create events

Revision ID: 0001
Revises:
Create Date: 2026-10-25
"""

import sqlalchemy as sa
from alembic import op

from minieyes_api.db import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("site", sa.String(64), nullable=False),
        sa.Column("camera", sa.String(64), nullable=False),
        sa.Column("zone", sa.String(64), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("x2", sa.Float(), nullable=False),
        sa.Column("y2", sa.Float(), nullable=False),
        sa.Column("occurred_at", UTCDateTime(), nullable=False),
        sa.Column("received_at", UTCDateTime(), nullable=False),
    )
    op.create_index("ux_events_event_id", "events", ["event_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ux_events_event_id", table_name="events")
    op.drop_table("events")
