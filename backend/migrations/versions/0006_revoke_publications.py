"""Track publication revocation."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_revoke_publications"
down_revision: str | None = "0005_add_document_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("publications", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("publications", "revoked_at")
