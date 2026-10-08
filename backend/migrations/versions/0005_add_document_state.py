"""Add snapshots, operations and comments for the document editor."""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_document_state"
down_revision: str | None = "0004_styles_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("document_tree", sa.JSON(), nullable=False),
        sa.Column("pagination_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "revision", name="uq_document_snapshots_revision"),
    )
    op.create_index("ix_document_snapshots_document_id", "document_snapshots", ["document_id"])
    op.create_table(
        "document_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("resulting_revision", sa.Integer(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("block_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_operations_document_id", "document_operations", ["document_id"])
    op.create_table(
        "document_comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("block_id", sa.String(length=255), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_comments_document_id", "document_comments", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_comments_document_id", table_name="document_comments")
    op.drop_table("document_comments")
    op.drop_index("ix_document_operations_document_id", table_name="document_operations")
    op.drop_table("document_operations")
    op.drop_index("ix_document_snapshots_document_id", table_name="document_snapshots")
    op.drop_table("document_snapshots")
