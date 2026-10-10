"""SQLAlchemy 2 Core tables. Portable across SQLite (dev/tests) and Postgres (deploy).

Typed contract payloads are stored as canonical JSON text (`payload_json`) beside the indexed
columns that queries need. Money columns are BIGINT fen; nothing is float. Migration 0001 in
`services/api/migrations/` creates exactly these tables; a test keeps the two in sync.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

# Autoincrement surrogate key: BIGINT on Postgres, INTEGER (rowid alias) on SQLite.
RowId = BigInteger().with_variant(Integer(), "sqlite")

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING)

HASH = String(64)
ID = String(128)


def _row_id() -> Column:
    return Column("row_id", RowId, primary_key=True, autoincrement=True)


organizations = Table(
    "organizations",
    metadata,
    Column("id", ID, primary_key=True),
    Column("name", String(256), nullable=True),
)

counterparties = Table(
    "counterparties",
    metadata,
    Column("id", ID, primary_key=True),
    Column("org_id", ID, nullable=False, index=True),
    Column("name", String(256), nullable=False),
    Column("role", String(16), nullable=False),
    Column("known", Boolean, nullable=False),
    Column("payload_json", Text, nullable=False),
)

offers = Table(
    "offers",
    metadata,
    _row_id(),
    Column("offer_id", ID, nullable=False),
    Column("version", Integer, nullable=False),
    Column("counterparty_id", ID, nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("received_day", Integer, nullable=False),
    Column("payload_json", Text, nullable=False),
    UniqueConstraint("offer_id", "version", name="uq_offers_offer_id_version"),
)

obligations = Table(
    "obligations",
    metadata,
    _row_id(),
    Column("offer_id", ID, nullable=False, index=True),
    Column("offer_version", Integer, nullable=False),
    Column("obligation_id", ID, nullable=False),
    Column("type", String(32), nullable=False),
    Column("counterparty_id", ID, nullable=False, index=True),
    Column("contingency", String(32), nullable=False),
    Column("rate_bp", Integer, nullable=True),
    Column("amount_fen", BigInteger, nullable=True),
    Column("days_delta", Integer, nullable=True),
    Column("effective_day", Integer, nullable=True),
    Column("payload_json", Text, nullable=False),
)

facilities = Table(
    "facilities",
    metadata,
    _row_id(),
    Column("state_row_id", BigInteger, nullable=False, index=True),
    Column("facility_id", ID, nullable=False, index=True),
    Column("org_id", ID, nullable=False),
    Column("kind", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("lender_id", ID, nullable=False),
    Column("owner_approved", Boolean, nullable=False),
    Column("limit_fen", BigInteger, nullable=False),
    Column("drawn_fen", BigInteger, nullable=False),
    Column("rate_bp", Integer, nullable=False),
    Column("payload_json", Text, nullable=False),
)

mandates = Table(
    "mandates",
    metadata,
    _row_id(),
    Column("org_id", ID, nullable=False, index=True),
    Column("version", Integer, nullable=False, index=True),
    Column("issued_day", Integer, nullable=False),
    Column("expires_day", Integer, nullable=False),
    Column("revoked", Boolean, nullable=False),
    Column("min_cash_fen", BigInteger, nullable=False),
    Column("payload_json", Text, nullable=False),
)

states = Table(
    "states",
    metadata,
    _row_id(),
    Column("org_id", ID, nullable=False, index=True),
    Column("state_version", Integer, nullable=False, index=True),
    Column("as_of", String(32), nullable=False),
    Column("cash_fen", BigInteger, nullable=False),
    Column("monthly_ebitda_fen", BigInteger, nullable=False),
    Column("payload_json", Text, nullable=False),
)

verdicts = Table(
    "verdicts",
    metadata,
    _row_id(),
    Column("id", ID, nullable=False, unique=True),
    Column("offer_id", ID, nullable=False, index=True),
    Column("offer_version", Integer, nullable=False),
    Column("outcome", String(32), nullable=False),
    Column("required_tier", String(16), nullable=False),
    Column("mandate_version", Integer, nullable=False),
    Column("state_version", Integer, nullable=False),
    Column("forward_concession_total_fen", BigInteger, nullable=False),
    Column("payload_json", Text, nullable=False),
)

commitments = Table(
    "commitments",
    metadata,
    _row_id(),
    Column("id", ID, nullable=False, unique=True),
    Column("offer_id", ID, nullable=False, index=True),
    Column("offer_version", Integer, nullable=False),
    Column("counterparty_id", ID, nullable=False, index=True),
    Column("verdict_id", ID, nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("terms_hash", HASH, nullable=False),
    Column("nonce", String(128), nullable=False),
    Column("expires_day", Integer, nullable=False),
    Column("mandate_version", Integer, nullable=False),
    Column("forward_value_fen", BigInteger, nullable=False),
    Column("payload_json", Text, nullable=False),
)

# Append-only and hash-chained. The stores expose no update or delete for it.
operations = Table(
    "operations",
    metadata,
    Column("seq", BigInteger, primary_key=True, autoincrement=False),
    Column("op_id", ID, nullable=False, index=True),
    Column("kind", String(64), nullable=False, index=True),
    Column("idempotency_key", String(256), nullable=False, index=True),
    Column("payload_json", Text, nullable=False),
    Column("result_json", Text, nullable=False),
    Column("prev_hash", HASH, nullable=False),
    Column("entry_hash", HASH, nullable=False, unique=True),
)

used_nonces = Table(
    "used_nonces",
    metadata,
    Column("nonce", String(128), primary_key=True),
)

approvals = Table(
    "approvals",
    metadata,
    _row_id(),
    Column("id", String(32), nullable=False, unique=True),
    Column("op_id", ID, nullable=True, index=True),
    Column("kind", String(64), nullable=True),
    Column("op_json", Text, nullable=False),
    Column("reason", Text, nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("decided_by", String(64), nullable=True),
    Column("decided_day", Integer, nullable=True),
)

# Documents the agent read (brief 03): the text, the reading and the owner's decision, as one canonical JSON
# payload. Never read by the engine: a confirmed contract writes no books.
contract_records = Table(
    "contract_records",
    metadata,
    _row_id(),
    Column("id", String(32), nullable=False, unique=True),
    Column("kind", String(32), nullable=False),
    Column("counterparty_id", ID, nullable=False, index=True),
    Column("status", String(16), nullable=False, index=True),
    Column("doc_hash", HASH, nullable=False),
    Column("uploaded_day", Integer, nullable=False),
    Column("decided_day", Integer, nullable=True),
    Column("payload_json", Text, nullable=False),
)

security_events = Table(
    "security_events",
    metadata,
    _row_id(),
    Column("id", ID, nullable=False, index=True),
    Column("day", Integer, nullable=False),
    Column("kind", String(32), nullable=False, index=True),
    Column("counterparty_id", ID, nullable=True),
    Column("trace_id", ID, nullable=True),
    Column("payload_json", Text, nullable=False),
)

llm_calls = Table(
    "llm_calls",
    metadata,
    _row_id(),
    Column("backend", String(32), nullable=False),
    Column("model", String(128), nullable=False),
    Column("prompt_version", String(64), nullable=False),
    Column("input_sha256", HASH, nullable=False, index=True),
    Column("status", String(32), nullable=False),
    Column("output_json", Text, nullable=True),
    Column("latency_ms", Integer, nullable=False),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cache_hit", Boolean, nullable=False),
    Column("trace_id", ID, nullable=True),
    Column("error", Text, nullable=True),
)

evaluation_runs = Table(
    "evaluation_runs",
    metadata,
    _row_id(),
    Column("suite", String(128), nullable=False, index=True),
    Column("passed", Integer, nullable=False),
    Column("failed", Integer, nullable=False),
    Column("metrics_json", Text, nullable=False),
    Column("git_sha", String(64), nullable=True),
    Column("notes", Text, nullable=False),
)

evidence_exports = Table(
    "evidence_exports",
    metadata,
    _row_id(),
    Column("operations", BigInteger, nullable=False),
    Column("head_hash", HASH, nullable=False),
    Column("chain_valid", Boolean, nullable=False),
    Column("content_sha256", HASH, nullable=False),
    Column("exported_at", String(40), nullable=False),
)

# Tables that `reset()` keeps: telemetry, not ledger state.
TELEMETRY_TABLES = (llm_calls, evaluation_runs)

__all__ = [
    "TELEMETRY_TABLES",
    "approvals",
    "commitments",
    "contract_records",
    "counterparties",
    "evaluation_runs",
    "evidence_exports",
    "facilities",
    "llm_calls",
    "mandates",
    "metadata",
    "obligations",
    "offers",
    "operations",
    "organizations",
    "security_events",
    "states",
    "used_nonces",
    "verdicts",
]
