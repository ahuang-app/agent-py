"""add llm usage events

Revision ID: 202610240001
Revises: 202607110007
Create Date: 2026-10-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "202610240001"
down_revision: str | None = "202607110007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_usage_events",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_llm_usage_events_owner_created",
        "llm_usage_events",
        ["owner_user_id", "created_at"],
    )
    op.create_index(
        "ix_llm_usage_events_created",
        "llm_usage_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_usage_events_created", table_name="llm_usage_events")
    op.drop_index("ix_llm_usage_events_owner_created", table_name="llm_usage_events")
    op.drop_table("llm_usage_events")
