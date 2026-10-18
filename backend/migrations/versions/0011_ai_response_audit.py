"""Store every Astra response before contract validation."""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0011_ai_response_audit"
down_revision: str | None = "0010_transactional_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_responses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("response_id", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("reasoning_effort", sa.String(length=32), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_ai_responses_document_id", "ai_responses", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_responses_document_id", table_name="ai_responses")
    op.drop_table("ai_responses")
