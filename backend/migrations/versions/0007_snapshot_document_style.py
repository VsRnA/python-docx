"""Snapshot the selected style settings on each document."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_snapshot_document_style"
down_revision: str | None = "0006_revoke_publications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("style_version_id", sa.Uuid(), nullable=True))
    op.add_column("documents", sa.Column("style_settings", sa.JSON(), nullable=False, server_default="{}"))
    op.create_foreign_key(
        "fk_documents_style_version_id_document_style_versions",
        "documents",
        "document_style_versions",
        ["style_version_id"],
        ["id"],
    )
    op.alter_column("documents", "style_settings", server_default=None)


def downgrade() -> None:
    op.drop_constraint("fk_documents_style_version_id_document_style_versions", "documents", type_="foreignkey")
    op.drop_column("documents", "style_settings")
    op.drop_column("documents", "style_version_id")
