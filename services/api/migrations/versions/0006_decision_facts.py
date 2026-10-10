"""The durable decision record's facts (ADR-0011): what a decision's read model cannot re-derive from the other tables.

A new table only. It is not the financial state, not an operation and not part of the hash chain; the stores expose no update
or delete for it, and a write is insert-if-absent on (decision_id, fact, fact_key). Unlike the pilot journal it is ledger
data, so `reset()` clears it. On Postgres it gets row-level security like every other table (0002 covered the tables that
existed then).

Revision ID: 0006
Revises: 0005
"""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_facts",
        sa.Column("row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("decision_id", sa.String(length=160), nullable=False),
        sa.Column("family", sa.String(length=8), nullable=False),
        sa.Column("fact", sa.String(length=16), nullable=False),
        sa.Column("fact_key", sa.String(length=256), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("body_json", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_decision_facts")),
        sa.UniqueConstraint("decision_id", "fact", "fact_key", name="uq_decision_facts_decision_id_fact_fact_key"),
    )
    op.create_index(op.f("ix_decision_facts_decision_id"), "decision_facts", ["decision_id"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE public."decision_facts" ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public."decision_facts" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_index(op.f("ix_decision_facts_decision_id"), table_name="decision_facts")
    op.drop_table("decision_facts")
