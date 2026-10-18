from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0015_cleanup_render_metadata"
down_revision: str | None = "0014_ai_edit_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("documents", "renderer_fingerprint")
    op.drop_column("documents", "source_render_sha256")
    op.drop_column("documents", "design_system_version")


def downgrade() -> None:
    op.add_column("documents", sa.Column("design_system_version", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("source_render_sha256", sa.String(length=64), nullable=True))
    op.add_column("documents", sa.Column("renderer_fingerprint", sa.JSON(), nullable=False, server_default="{}"))
    op.alter_column("documents", "renderer_fingerprint", server_default=None)
