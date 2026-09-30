"""Store the model HTML before backend normalization."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_add_astra_html"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_versions", sa.Column("astra_html", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_versions", "astra_html")
