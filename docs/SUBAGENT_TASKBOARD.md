# Subagent taskboard

The main architect owns `app/domain/`, `app/api/`, `app/main.py`, `app/config.py`, `fixtures/`, `docs/` and `CONTEXT.md`, as well as integration, cross-module tests and the demo. Each agent owns only the paths listed for it. Agents send shared-interface changes as `INTERFACE_CHANGE_REQUEST: <what> / <why> / <affected modules>` in their return report.

| Wave | Agent | Branch | Owns | Status |
| --- | --- | --- | --- | --- |
| 0 | main | dev | contracts, docs, fixtures, oracle, skeleton | done |
| 1 | A: financial engine | agent/financial-engine | `app/financial/**`, `tests/financial/**` | merged |
| 1 | B: covenants + mandate | agent/covenants-mandate | `app/covenants/**`, `app/mandate/**`, `tests/covenants/**`, `tests/mandate/**` | merged |
| 1 | C: compiler | agent/compiler | `app/compiler/**`, `tests/compiler/**`, `fixtures/compiler_cache/**` | merged |
| 1 | D: persistence + commitments | agent/persistence | `app/persistence/**`, `app/commitments/**`, `services/api/migrations/**`, `tests/persistence/**`, `tests/commitments/**` | merged |
| 1 | J: frontend (mock data) | agent/frontend | `apps/web/**` | merged |
| 2 | E: funding router | agent/funding-router | `app/funding/**`, `tests/funding/**` | merged |
| 2 | F1: executor | agent/executor | `app/operations/**`, `tests/operations/**` | merged |
| 2 | F2: verifier + counters | agent/verifier | `app/verifier/**`, `tests/verifier/**` | merged |
| 2 | Contracts follow-up | agent/contracts-followup | compiler, verifier, operations, `mandate/tiers.py` | running |
| 2 | G: security suite | agent/security | `app/security/**`, `evals/security/**`, `tests/security/**`, `docs/SECURITY_SELF_ASSESSMENT.md` | running |
| 3 | H: buyer + lender simulators | agent/counterparties | `app/counterparties/**`, `tests/counterparties/**`, `fixtures/counterparties/**` | merged |
| 3 | I: /nl harness | agent/nl | `app/nl/**`, `app/api/nl.py`, `evals/e2e/**`, `tests/nl/**`, `scripts/run_scenarios.py` | running |
| 4 | K: capex | agent/capex | `app/capex/**`, `app/api/capex.py`, `tests/capex/**` | running |
| 4 | L: borrower file + alerts | agent/borrower-file | `app/borrower_file/**`, `app/alerts/**`, `app/api/{borrower_file,alerts}.py` | running |
| 3 | Egress guard (owner-requested) | agent/egress-guard | `app/egress/**`, `tests/egress/**`, `fixtures/security/canaries.yaml` (+ a canary in compiler prompts) | merged |
| 3 | What-if sandbox (owner-requested) | agent/whatif | `app/whatif/**`, `tests/whatif/**`, `apps/web/app/whatif/**` (+ nav and dictionary entries) | running |
| 5 | Eval agent | agent/evals | `evals/**` (except security), `scripts/evaluate.py` | after first integrated build |

## Return format (every coding agent)
STATUS / FILES CHANGED / INTERFACES IMPLEMENTED / TESTS ADDED / TEST COMMAND / TEST RESULT / ASSUMPTIONS / KNOWN LIMITATIONS / INTERFACE CHANGE REQUESTS / NEXT INTEGRATION STEP

## Integration log
- **B merged.** 98 tests. Architect change: draws on COMMITTED facilities are Tier 1 at any size (spec §5.3). Accepted interface changes: `tier_for` keywords (`accepts_terms_change`, `commitment_value_fen`), owner-key pinning in `verify_signature` / `check_validity`, and the line event `ref` convention.
- **A merged.** 48 tests; every golden value matches exactly. Accepted: `MonthPoint.leverage` may be None. Deferred: `DayPoint.facility_balances_fen`.
- **D merged.** 152 tests; SQL and in-memory stores; hash chain; Alembic. Accepted: read-only `OperationRecord`, approvals and evidence on the port. Accepted deviation: ACTIVE commitments can still be fulfilled after expiry.
- `main` fast-forwarded to `dev` at 76ee428 (checkpoint: engine, covenants, mandate, persistence).
- **C merged.** 180 tests, 25 injection cases (zh + en), offline cache and rules grammar, Claude and DeepSeek adapters. Accepted: equity clauses and injection flags on term sheets.
- **J merged.** 7 screens + Approvals/Security/Evidence, demo stepper, en/中文, mock mode. Its view-shape requests are being applied in `app/api/` (state, mandate, ledger and audit done).
- **E merged.** Golden plan ¥2,712.94 found in 0.14 s; beats the line-first baseline in 6 designed cases. Accepted: NEW_BORROWING_NOT_ALLOWED, `compare` on the port.
- **F1 merged**, plus a follow-up: effective_day, approval_id, PRECONDITION_FAILED / STALE_OPERATION, shared charge helpers in `app.financial`.
- **H merged.** Scene 1 accept, Scene 2 NO_DEAL in 3 rounds, hidden reservations never leak.
- Main: evidence export per ADR-0004 plus `scripts/verify_evidence.py`; `/operations`, `/approvals`, `/circuit` endpoints with an owner token; Supabase (Singapore pooler) migrated with RLS on every table; the DeepSeek live path verified.
- Decision: the reserve-breach cure is priced only on permanent-capable sources (no clean-down line), because a terms extension recurs. The verifier computes the figure, and golden values and docs follow it.
- Backlog: compiler live-mode contingency calibration (DeepSeek marks the whole package CONTINGENT).
- **F2 merged.** Every offers.yaml verdict reproduces. The cure cost is set to **¥802.70** (2 IF periods, ADR-0003); oracle and docs updated.
- **Egress guard merged.** 925 tests; canaries in the system prompt and in hidden fields.
- Main: `/offers/{id}/evaluate`, `/negotiate/{offer_id}`, `/router/plan` wired, with the egress guard on counters and buyer replies. Scenes 1 and 2 run end to end through the API: DEAL → accept + line draw at Tier 1; NO_DEAL → line + IF ¥2,712.94 executed. The core E2E path works, so wave 4 is launched.
