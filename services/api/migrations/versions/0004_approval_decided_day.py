"""Record the clock day an approval was decided.

A nullable column: rows decided before it existed load with `decided_day = None`.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("approvals") as batch:
        batch.add_column(sa.Column("decided_day", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("approvals") as batch:
        batch.drop_column("decided_day")
