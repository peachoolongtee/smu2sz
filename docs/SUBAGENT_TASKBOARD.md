# Subagent taskboard

The main architect owns `app/domain/`, `app/api/`, `app/main.py`, `app/config.py`, `fixtures/`, `docs/` and `CONTEXT.md`, as well as integration, cross-module tests and the demo. Each agent owns only the paths listed for it. Agents send shared-interface changes as `INTERFACE_CHANGE_REQUEST: <what> / <why> / <affected modules>` in their return report.

| Wave | Agent | Branch | Owns | Status |
| --- | --- | --- | --- | --- |
| 0 | main | dev | contracts, docs, fixtures, oracle, skeleton | done |
| 1 | A: financial engine | agent/financial-engine | `app/financial/**`, `tests/financial/**` | running |
| 1 | B: covenants + mandate | agent/covenants-mandate | `app/covenants/**`, `app/mandate/**`, `tests/covenants/**`, `tests/mandate/**` | merged |
| 1 | C: compiler | agent/compiler | `app/compiler/**`, `tests/compiler/**`, `fixtures/compiler_cache/**` | running |
| 1 | D: persistence + commitments | agent/persistence | `app/persistence/**`, `app/commitments/**`, `services/api/migrations/**`, `tests/persistence/**`, `tests/commitments/**` | running |
| 1 | J: frontend (mock data) | agent/frontend | `apps/web/**` | running |
| 2 | E: funding router | agent/funding-router | `app/funding/**`, `tests/funding/**` | blocked on A, B |
| 2 | F: verifier + operations | agent/verifier-ops | `app/verifier/**`, `app/operations/**`, `tests/verifier/**`, `tests/operations/**` | blocked on A, B, D, E |
| 2 | G: security suite | agent/security | `app/security/**`, `evals/security/**`, `tests/security/**` | blocked on C, F |
| 3 | H: buyer + lender simulators | agent/counterparties | `app/counterparties/**`, `tests/counterparties/**` | after wave 2 |
| 3 | I: /nl harness | agent/nl | `app/nl/**`, `evals/e2e/**`, `tests/nl/**` | after wave 2 |
| 4 | K: capex | agent/capex | `app/capex/**`, `tests/capex/**` | after core E2E |
| 4 | L: borrower file + alerts | agent/borrower-file | `app/borrower_file/**`, `app/alerts/**`, `tests/borrower_file/**` | after core E2E |
| 5 | Eval agent | agent/evals | `evals/**` (except security), `scripts/evaluate.py` | after first integrated build |

## Return format (every coding agent)
STATUS / FILES CHANGED / INTERFACES IMPLEMENTED / TESTS ADDED / TEST COMMAND / TEST RESULT / ASSUMPTIONS / KNOWN LIMITATIONS / INTERFACE CHANGE REQUESTS / NEXT INTEGRATION STEP

## Integration log
- **B merged.** 98 tests. Architect change: draws on COMMITTED facilities are Tier 1 at any size (spec §5.3). Accepted interface changes: `tier_for` keywords (`accepts_terms_change`, `commitment_value_fen`), owner-key pinning in `verify_signature` / `check_validity`, and the line event `ref` convention.
