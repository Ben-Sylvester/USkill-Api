"""Initial schema — all tables

Revision ID: 0001
Revises:
Create Date: 2026-03-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── api_keys ────────────────────────────────────────────────────
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(20), nullable=False),
        sa.Column("plan", sa.String(20), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scopes", sa.String(200), nullable=False, server_default="read write"),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])

    # ── connections ─────────────────────────────────────────────────
    op.create_table(
        "connections",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_domain", sa.String(64), nullable=False),
        sa.Column("destination_domain", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("gap_threshold", sa.Float(), nullable=False, server_default="0.70"),
        sa.Column("allow_partial", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("auto_rollback", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("webhook_url", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("transfer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_compat_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_connections_org_id", "connections", ["org_id"])

    # ── skills ──────────────────────────────────────────────────────
    op.create_table(
        "skills",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(20),
            sa.ForeignKey("connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("version", sa.String(20), nullable=False, server_default="2.0.0"),
        sa.Column("source_domain", sa.String(64), nullable=False),
        sa.Column("extraction_episodes", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("extraction_depth", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("extraction_edge_cases", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("primitives", sa.JSON(), nullable=False),
        sa.Column("intent_graph", sa.JSON(), nullable=False),
        sa.Column("edge_cases", sa.JSON(), nullable=False),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("transferability", sa.Float(), nullable=False, server_default="0.75"),
        sa.Column("confidence_score", sa.Float(), nullable=False, server_default="0.85"),
        sa.Column("rollback_token", sa.String(32), nullable=True),
        sa.Column("rollback_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "previous_skill_id",
            sa.String(20),
            sa.ForeignKey("skills.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("refine_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_skills_org_id", "skills", ["org_id"])
    op.create_index("ix_skills_connection_id", "skills", ["connection_id"])
    op.create_index("ix_skills_source_domain", "skills", ["source_domain"])
    op.create_index("ix_skills_rollback_token", "skills", ["rollback_token"])

    # ── transfers ───────────────────────────────────────────────────
    op.create_table(
        "transfers",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column(
            "connection_id",
            sa.String(20),
            sa.ForeignKey("connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "skill_id",
            sa.String(20),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_domain", sa.String(64), nullable=False),
        sa.Column("destination_domain", sa.String(64), nullable=False),
        sa.Column("compat_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("sub_scores", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("adapter_log", sa.JSON(), nullable=False),
        sa.Column("rollback_token", sa.String(32), nullable=True),
        sa.Column("rollback_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_transfers_org_id", "transfers", ["org_id"])
    op.create_index("ix_transfers_connection_id", "transfers", ["connection_id"])
    op.create_index("ix_transfers_skill_id", "transfers", ["skill_id"])

    # ── custom_domains ───────────────────────────────────────────────
    op.create_table(
        "custom_domains",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("icon", sa.String(10), nullable=False, server_default="⬡"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("feature_vector", sa.JSON(), nullable=False),
        sa.Column("primitive_impls", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_custom_domains_org_id", "custom_domains", ["org_id"])

    # ── jobs ─────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(24), primary_key=True),
        sa.Column("org_id", sa.String(64), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("progress_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("progress_name", sa.String(100), nullable=True),
        sa.Column("input_data", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_org_id", "jobs", ["org_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_expires_at", "jobs", ["expires_at"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_table("custom_domains")
    op.drop_table("transfers")
    op.drop_table("skills")
    op.drop_table("connections")
    op.drop_table("api_keys")
