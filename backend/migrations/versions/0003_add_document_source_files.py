"""Add source files for merged documents."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_document_source_files"
down_revision: str | None = "0002_add_astra_html"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_source_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("source_document_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=1000), nullable=False),
        sa.Column("object_key", sa.String(length=1500), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_source_files_document_id",
        "document_source_files",
        ["document_id"],
    )
    op.create_index(
        "ix_document_source_files_document_position",
        "document_source_files",
        ["document_id", "position"],
    )
    op.create_index(
        "ix_document_source_files_sha256",
        "document_source_files",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_source_files_sha256", table_name="document_source_files")
    op.drop_index("ix_document_source_files_document_position", table_name="document_source_files")
    op.drop_index("ix_document_source_files_document_id", table_name="document_source_files")
    op.drop_table("document_source_files")
