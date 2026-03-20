"""Add webhook_outbox table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-01 00:01:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "webhook_outbox",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_webhook_outbox_org_id", "webhook_outbox", ["org_id"])
    op.create_index("ix_webhook_outbox_status", "webhook_outbox", ["status"])
    op.create_index(
        "ix_webhook_outbox_pending",
        "webhook_outbox",
        ["status", "attempts", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("webhook_outbox")
