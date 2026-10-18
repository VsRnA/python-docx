"""Keep document history when a style is deleted."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0016_allow_style_deletion"
down_revision: str | None = "0015_cleanup_render_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "fk_documents_style_version_id_document_style_versions",
        "documents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_documents_style_version_id_document_style_versions",
        "documents",
        "document_style_versions",
        ["style_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "fk_processing_profiles_style_version_id_document_style_versions",
        "processing_profiles",
        type_="foreignkey",
    )
    op.alter_column("processing_profiles", "style_version_id", nullable=True)
    op.create_foreign_key(
        "fk_processing_profiles_style_version_id_document_style_versions",
        "processing_profiles",
        "document_style_versions",
        ["style_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_processing_profiles_style_version_id_document_style_versions",
        "processing_profiles",
        type_="foreignkey",
    )
    op.alter_column("processing_profiles", "style_version_id", nullable=False)
    op.create_foreign_key(
        "fk_processing_profiles_style_version_id_document_style_versions",
        "processing_profiles",
        "document_style_versions",
        ["style_version_id"],
        ["id"],
    )
    op.drop_constraint(
        "fk_documents_style_version_id_document_style_versions",
        "documents",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_documents_style_version_id_document_style_versions",
        "documents",
        "document_style_versions",
        ["style_version_id"],
        ["id"],
    )
