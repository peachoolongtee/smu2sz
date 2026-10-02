# Independent audit reproduction evidence

These are isolated audit probes, not implementation fixes or desired regression tests. They demonstrate
defects against the audited/reconciled code. All runs must use synthetic data, memory/cache mode and no dotenv.
No live bank, PostgreSQL database or model provider was accessed. Published demo credentials are fixture data.

Run from the repository root:

```sh
services/api/.venv/bin/python scripts/independent_audit_books.py
services/api/.venv/bin/python docs/research/independent-audit-evidence-2026-10-03/security-repro.py
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api services/api/.venv/bin/python docs/research/independent-audit-evidence-2026-10-03/counter-repro.py
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api services/api/.venv/bin/python docs/research/independent-audit-evidence-2026-10-03/bounded-repro.py
TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONPATH=services/api services/api/.venv/bin/python docs/research/independent-audit-evidence-2026-10-03/financial-repro.py
```

`security-repro.py` overrides environment configuration before importing the application, uses only memory
and a temporary SQLite file, then removes that SQLite file. It writes a new result file under `/tmp`.
Other scripts require the explicit environment prefixes above and produce stdout only.

- `security-results.json`: complete requests, responses, operation payloads and before/after state from the
  principal's post-reconciliation repeat of the reviewer's probes.
- `books-results.log`: principal API probes for outstanding-face financing, lead time, direct predicate bypass,
  late discounted settlement and forecast-only repayment.
- `counter-results.log`: real EX01 Option B through genuine owner approval, issuance and full/partial receipt.
- `bounded-results.log`: real compiled/approved next-three-invoices scope followed by genuine receipt events.
- `financial-repro.py`: financial reviewer's pure formula/capex counterexamples. Altered unsigned mandates are
  used only as numerical predicate inputs, not accepted executor authority.

Runtime-generated commitment IDs and compiler log timestamps vary; asserted amounts, dates and economic
state are the evidence. A passing probe process means it successfully reproduced a defect; it does not mean
the product passed an acceptance test. Detailed context is in the accompanying principal and working audits.
