"""Add versioned document styles and processing profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_styles_profiles"
down_revision: str | None = "0003_add_document_source_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_styles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_styles_owner_id", "document_styles", ["owner_id"])
    op.create_table(
        "document_style_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("style_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["style_id"], ["document_styles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("style_id", "version", name="uq_document_style_versions_version"),
    )
    op.create_index("ix_document_style_versions_style_id", "document_style_versions", ["style_id"])
    op.create_table(
        "processing_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("style_version_id", sa.Uuid(), nullable=False),
        sa.Column("source_language", sa.String(length=32), nullable=True),
        sa.Column("target_language", sa.String(length=32), nullable=True),
        sa.Column("translation_enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["style_version_id"], ["document_style_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_profiles_document_id", "processing_profiles", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_processing_profiles_document_id", table_name="processing_profiles")
    op.drop_table("processing_profiles")
    op.drop_index("ix_document_style_versions_style_id", table_name="document_style_versions")
    op.drop_table("document_style_versions")
    op.drop_index("ix_document_styles_owner_id", table_name="document_styles")
    op.drop_table("document_styles")
