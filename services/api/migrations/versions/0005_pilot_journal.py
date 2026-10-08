"""The shadow pilot's journal: what the owner did against an answer FLOW gave (map #58, docs/pilot/JOURNAL_SPEC.md).

A new table only. It is not the financial state, not an operation and not part of the hash chain; the stores expose no update
or delete for it. On Postgres it gets row-level security like every other table (0002 covered the tables that existed then).

Revision ID: 0005
Revises: 0004
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pilot_journal",
        sa.Column("row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("week", sa.Integer(), nullable=False),
        sa.Column("sme", sa.String(length=64), nullable=False),
        sa.Column("answer", sa.String(length=16), nullable=False),
        sa.Column("flow_said", sa.Text(), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("owner_did", sa.Text(), nullable=False),
        sa.Column("choice", sa.String(length=16), nullable=False),
        sa.Column("recorded_on", sa.String(length=10), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_pilot_journal")),
    )
    op.create_index(op.f("ix_pilot_journal_week"), "pilot_journal", ["week"], unique=False)
    op.create_index(op.f("ix_pilot_journal_sme"), "pilot_journal", ["sme"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE public."pilot_journal" ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public."pilot_journal" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_index(op.f("ix_pilot_journal_sme"), table_name="pilot_journal")
    op.drop_index(op.f("ix_pilot_journal_week"), table_name="pilot_journal")
    op.drop_table("pilot_journal")
