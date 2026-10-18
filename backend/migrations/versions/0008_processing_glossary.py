"""Store the glossary version selected for a processing run."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_processing_glossary"
down_revision: str | None = "0007_snapshot_document_style"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "processing_profiles",
        sa.Column("glossary_version_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("processing_profiles", "glossary_version_id")
