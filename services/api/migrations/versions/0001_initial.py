"""Create all TermsLedger tables.

Revision ID: 0001
Revises:
Create Date: 2026-10-01

Mirrors app/persistence/tables.py; tests/persistence/test_migrations.py checks they agree.
Portable DDL only (SQLite for dev/tests, Postgres to deploy; ADR-0001).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("op_id", sa.String(length=128), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=True),
        sa.Column("op_json", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_approvals")),
        sa.UniqueConstraint("id", name=op.f("uq_approvals_id")),
    )
    op.create_index(op.f("ix_approvals_op_id"), "approvals", ["op_id"], unique=False)
    op.create_index(op.f("ix_approvals_status"), "approvals", ["status"], unique=False)

    op.create_table(
        "commitments",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("offer_id", sa.String(length=128), nullable=False),
        sa.Column("offer_version", sa.Integer(), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("verdict_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("terms_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.Column("expires_day", sa.Integer(), nullable=False),
        sa.Column("mandate_version", sa.Integer(), nullable=False),
        sa.Column("forward_value_fen", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_commitments")),
        sa.UniqueConstraint("id", name=op.f("uq_commitments_id")),
    )
    op.create_index(op.f("ix_commitments_counterparty_id"), "commitments", ["counterparty_id"], unique=False)
    op.create_index(op.f("ix_commitments_offer_id"), "commitments", ["offer_id"], unique=False)
    op.create_index(op.f("ix_commitments_status"), "commitments", ["status"], unique=False)

    op.create_table(
        "counterparties",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("org_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("known", sa.Boolean(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_counterparties")),
    )
    op.create_index(op.f("ix_counterparties_org_id"), "counterparties", ["org_id"], unique=False)

    op.create_table(
        "evaluation_runs",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("suite", sa.String(length=128), nullable=False),
        sa.Column("passed", sa.Integer(), nullable=False),
        sa.Column("failed", sa.Integer(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_evaluation_runs")),
    )
    op.create_index(op.f("ix_evaluation_runs_suite"), "evaluation_runs", ["suite"], unique=False)

    op.create_table(
        "evidence_exports",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("operations", sa.BigInteger(), nullable=False),
        sa.Column("head_hash", sa.String(length=64), nullable=False),
        sa.Column("chain_valid", sa.Boolean(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("exported_at", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_evidence_exports")),
    )
    op.create_table(
        "facilities",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("state_row_id", sa.BigInteger(), nullable=False),
        sa.Column("facility_id", sa.String(length=128), nullable=False),
        sa.Column("org_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lender_id", sa.String(length=128), nullable=False),
        sa.Column("owner_approved", sa.Boolean(), nullable=False),
        sa.Column("limit_fen", sa.BigInteger(), nullable=False),
        sa.Column("drawn_fen", sa.BigInteger(), nullable=False),
        sa.Column("rate_bp", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_facilities")),
    )
    op.create_index(op.f("ix_facilities_facility_id"), "facilities", ["facility_id"], unique=False)
    op.create_index(op.f("ix_facilities_state_row_id"), "facilities", ["state_row_id"], unique=False)

    op.create_table(
        "llm_calls",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("backend", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("input_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_llm_calls")),
    )
    op.create_index(op.f("ix_llm_calls_input_sha256"), "llm_calls", ["input_sha256"], unique=False)

    op.create_table(
        "mandates",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("org_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("issued_day", sa.Integer(), nullable=False),
        sa.Column("expires_day", sa.Integer(), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("min_cash_fen", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_mandates")),
    )
    op.create_index(op.f("ix_mandates_org_id"), "mandates", ["org_id"], unique=False)
    op.create_index(op.f("ix_mandates_version"), "mandates", ["version"], unique=False)

    op.create_table(
        "obligations",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("offer_id", sa.String(length=128), nullable=False),
        sa.Column("offer_version", sa.Integer(), nullable=False),
        sa.Column("obligation_id", sa.String(length=128), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("contingency", sa.String(length=32), nullable=False),
        sa.Column("rate_bp", sa.Integer(), nullable=True),
        sa.Column("amount_fen", sa.BigInteger(), nullable=True),
        sa.Column("days_delta", sa.Integer(), nullable=True),
        sa.Column("effective_day", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_obligations")),
    )
    op.create_index(op.f("ix_obligations_counterparty_id"), "obligations", ["counterparty_id"], unique=False)
    op.create_index(op.f("ix_obligations_offer_id"), "obligations", ["offer_id"], unique=False)

    op.create_table(
        "offers",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("offer_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("received_day", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_offers")),
        sa.UniqueConstraint("offer_id", "version", name="uq_offers_offer_id_version"),
    )
    op.create_index(op.f("ix_offers_counterparty_id"), "offers", ["counterparty_id"], unique=False)

    op.create_table(
        "operations",
        sa.Column("seq", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("op_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column("prev_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("seq", name=op.f("pk_operations")),
        sa.UniqueConstraint("entry_hash", name=op.f("uq_operations_entry_hash")),
    )
    op.create_index(op.f("ix_operations_idempotency_key"), "operations", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_operations_kind"), "operations", ["kind"], unique=False)
    op.create_index(op.f("ix_operations_op_id"), "operations", ["op_id"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
    )
    op.create_table(
        "security_events",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("day", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("counterparty_id", sa.String(length=128), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_security_events")),
    )
    op.create_index(op.f("ix_security_events_id"), "security_events", ["id"], unique=False)
    op.create_index(op.f("ix_security_events_kind"), "security_events", ["kind"], unique=False)

    op.create_table(
        "states",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("org_id", sa.String(length=128), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.String(length=32), nullable=False),
        sa.Column("cash_fen", sa.BigInteger(), nullable=False),
        sa.Column("monthly_ebitda_fen", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_states")),
    )
    op.create_index(op.f("ix_states_org_id"), "states", ["org_id"], unique=False)
    op.create_index(op.f("ix_states_state_version"), "states", ["state_version"], unique=False)

    op.create_table(
        "used_nonces",
        sa.Column("nonce", sa.String(length=128), nullable=False),
        sa.PrimaryKeyConstraint("nonce", name=op.f("pk_used_nonces")),
    )
    op.create_table(
        "verdicts",
        sa.Column(
            "row_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False
        ),
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("offer_id", sa.String(length=128), nullable=False),
        sa.Column("offer_version", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("required_tier", sa.String(length=16), nullable=False),
        sa.Column("mandate_version", sa.Integer(), nullable=False),
        sa.Column("state_version", sa.Integer(), nullable=False),
        sa.Column("forward_concession_total_fen", sa.BigInteger(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("row_id", name=op.f("pk_verdicts")),
        sa.UniqueConstraint("id", name=op.f("uq_verdicts_id")),
    )
    op.create_index(op.f("ix_verdicts_offer_id"), "verdicts", ["offer_id"], unique=False)


def downgrade() -> None:
    op.drop_table("verdicts")
    op.drop_table("used_nonces")
    op.drop_table("states")
    op.drop_table("security_events")
    op.drop_table("organizations")
    op.drop_table("operations")
    op.drop_table("offers")
    op.drop_table("obligations")
    op.drop_table("mandates")
    op.drop_table("llm_calls")
    op.drop_table("facilities")
    op.drop_table("evidence_exports")
    op.drop_table("evaluation_runs")
    op.drop_table("counterparties")
    op.drop_table("commitments")
    op.drop_table("approvals")
