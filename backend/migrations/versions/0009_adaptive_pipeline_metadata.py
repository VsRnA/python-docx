"""Store adaptive PDF pipeline fingerprints and visual correction metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_adaptive_pipeline_metadata"
down_revision: str | None = "0008_processing_glossary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("pipeline_metadata", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("documents", sa.Column("design_system_version", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("source_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("source_render_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("style_reference_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "documents",
        sa.Column("renderer_fingerprint", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.alter_column("documents", "pipeline_metadata", server_default=None)
    op.alter_column("documents", "renderer_fingerprint", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "renderer_fingerprint")
    op.drop_column("documents", "style_reference_sha256")
    op.drop_column("documents", "source_render_sha256")
    op.drop_column("documents", "source_sha256")
    op.drop_column("documents", "design_system_version")
    op.drop_column("documents", "pipeline_metadata")
