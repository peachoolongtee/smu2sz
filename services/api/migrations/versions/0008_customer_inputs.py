"""What the owner told FLOW about a buyer or the firm (map #88, brief H.4): the customer-inputs table.

A new table only. It is not the financial state, not an operation and not part of the hash chain; the stores expose no update
or delete for it. Append-only: the latest row per (counterparty, field) is the one in force and the history stays. A null
`counterparty_id` is a firm row (the VAT rate, the company gross margin). `field` and `provenance` are enums over this one
table, held as checked strings so a later phase's fields need no second migration. It is ledger data, so `reset()` clears it. On
Postgres it gets row-level security like every other table (no policies: the anon and authenticated roles are denied; the API
connects as the owner).

Revision ID: 0008
Revises: 0007
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

FIELDS = (
    "annual_sales_fen", "margin_bp", "margin_basis", "classification", "typical_delay_days", "aggregate", "vat_rate_bp",
    "company_gross_margin_bp",
)
PROVENANCES = ("ACCOUNTING_HISTORY", "INVOICE_HISTORY", "OWNER_ENTERED", "ERP", "DERIVED", "ESTIMATED", "PROJECTED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "customer_inputs",
        sa.Column("row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("org_id", sa.String(length=128), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=True),
        sa.Column("field", sa.String(length=32), nullable=False),
        sa.Column("value_json", sa.Text(), nullable=False),
        sa.Column("provenance", sa.String(length=24), nullable=False),
        sa.Column("source_ref", sa.String(length=256), nullable=False),
        sa.Column("entered_by", sa.String(length=64), nullable=False),
        sa.Column("entered_day", sa.Integer(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_customer_inputs")),
        sa.CheckConstraint(_in("field", FIELDS), name="ck_customer_inputs_field"),
        sa.CheckConstraint(_in("provenance", PROVENANCES), name="ck_customer_inputs_provenance"),
    )
    op.create_index(op.f("ix_customer_inputs_org_id"), "customer_inputs", ["org_id"], unique=False)
    op.create_index(op.f("ix_customer_inputs_counterparty_id"), "customer_inputs", ["counterparty_id"], unique=False)
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE public."customer_inputs" ENABLE ROW LEVEL SECURITY')
        op.execute('REVOKE ALL ON TABLE public."customer_inputs" FROM anon, authenticated')


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_inputs_counterparty_id"), table_name="customer_inputs")
    op.drop_index(op.f("ix_customer_inputs_org_id"), table_name="customer_inputs")
    op.drop_table("customer_inputs")
