"""Add PostgreSQL worker leases to jobs."""

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0013_job_leases"
down_revision: str | None = "0012_style_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("lease_owner", sa.String(length=128), nullable=True))
    op.add_column("jobs", sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_jobs_lease_owner", "jobs", ["lease_owner"])
    op.create_index("ix_jobs_lease_until", "jobs", ["lease_until"])


def downgrade() -> None:
    op.drop_index("ix_jobs_lease_until", table_name="jobs")
    op.drop_index("ix_jobs_lease_owner", table_name="jobs")
    op.drop_column("jobs", "lease_until")
    op.drop_column("jobs", "lease_owner")
