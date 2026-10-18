"""Store editable style prompts and S3 reference metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0012_style_materials"
down_revision: str | None = "0011_ai_response_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("document_style_versions", sa.Column("prompt", sa.Text(), nullable=True))
    op.add_column("document_style_versions", sa.Column("reference_object_key", sa.String(length=1500), nullable=True))
    op.add_column("document_style_versions", sa.Column("reference_filename", sa.String(length=1000), nullable=True))
    op.add_column("document_style_versions", sa.Column("reference_sha256", sa.String(length=64), nullable=True))
    op.add_column("document_style_versions", sa.Column("reference_size_bytes", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("document_style_versions", "reference_size_bytes")
    op.drop_column("document_style_versions", "reference_sha256")
    op.drop_column("document_style_versions", "reference_filename")
    op.drop_column("document_style_versions", "reference_object_key")
    op.drop_column("document_style_versions", "prompt")
