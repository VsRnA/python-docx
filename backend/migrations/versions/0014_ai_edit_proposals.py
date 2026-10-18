"""Persist AI edit proposals before acceptance."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_ai_edit_proposals"
down_revision: str | None = "0013_job_leases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_edit_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("before_html", sa.Text(), nullable=False),
        sa.Column("after_html", sa.Text(), nullable=False),
        sa.Column("operations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("accepted_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_edit_proposals_document_id", "ai_edit_proposals", ["document_id"])
    op.create_index("ix_ai_edit_proposals_owner_id", "ai_edit_proposals", ["owner_id"])
    op.create_index("ix_ai_edit_proposals_status", "ai_edit_proposals", ["status"])
    op.create_index("ix_ai_edit_proposals_document_status", "ai_edit_proposals", ["document_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_ai_edit_proposals_document_status", table_name="ai_edit_proposals")
    op.drop_index("ix_ai_edit_proposals_status", table_name="ai_edit_proposals")
    op.drop_index("ix_ai_edit_proposals_owner_id", table_name="ai_edit_proposals")
    op.drop_index("ix_ai_edit_proposals_document_id", table_name="ai_edit_proposals")
    op.drop_table("ai_edit_proposals")

