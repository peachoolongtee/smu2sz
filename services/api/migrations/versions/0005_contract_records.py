"""Documents the agent read and the owner's decision on them (contract ingestion, brief 03).

One row per upload: the canonical JSON of the `ContractRecord` beside the columns queries need. On Postgres the
new table gets row-level security like every table in 0002 (no policies: the anon and authenticated roles are
denied; the API connects as the owner).

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
        "contract_records",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("doc_hash", sa.String(length=64), nullable=False),
        sa.Column("uploaded_day", sa.Integer(), nullable=False),
        sa.Column("decided_day", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_contract_records")),
        sa.UniqueConstraint("id", name=op.f("uq_contract_records_id")),
    )
    op.create_index(op.f("ix_contract_records_counterparty_id"), "contract_records", ["counterparty_id"], unique=False)
    op.create_index(op.f("ix_contract_records_status"), "contract_records", ["status"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE public."contract_records" ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public."contract_records" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_index(op.f("ix_contract_records_status"), table_name="contract_records")
    op.drop_index(op.f("ix_contract_records_counterparty_id"), table_name="contract_records")
    op.drop_table("contract_records")
