# Execution evidence pack

A fresh sandbox run for deliverable 6, produced on 16 Oct 2026 at commit `0f92d433` (`dev`) on branch `docs/submission-code`, in `LLM_MODE=cache` (recorded model outputs, no network, no paid model), `DATABASE_URL=memory`, `DEMO_MODE=1`. Everything is synthetic. The narrative is in [../execution_evidence.md](../execution_evidence.md).

The figures quoted in the final technical document come from a later run, on `dev` at `975e082f` (17 Oct 2026): see
[EVIDENCE_PACK.md](EVIDENCE_PACK.md), which gives the command and source for each one.

| File | What it is | Command that makes it |
| --- | --- | --- |
| [demo_run_output.txt](demo_run_output.txt) | The 17-step demo walk, printed: deal on Counter A, the agreed early payment on day 2, the late residual on day 34, "go ahead" then "approve", the cure's cash on day 37, the receipts, the repayment, an attack through chat. Ends `RESULT: … cure executed and alert cleared: True`, exit 0. The recorder's `compiler.call` log lines (timings, hashes of the cached text) are removed. | `DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py` |
| [scenarios/summary.md](scenarios/summary.md) | The table of all 49 scripted `/nl` tasks: **49/49 passed**, 87 turns, median 16.8 ms per turn | `DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/run_scenarios.py --inproc --out OUT` |
| [scenarios/turn_logs.md](scenarios/turn_logs.md) | Seven tasks turn by turn (the demo deal, NO DEAL, the FastCapital message, a Tier 2 approval, injection, replay, a buyer trying to approve) | same run |
| [scenarios/evidence/](scenarios/evidence/) | The seven tasks' own hash chains (JSONL); [verify_output.txt](scenarios/verify_output.txt) is their verification | `python3 scripts/verify_evidence.py FILE` |
| [demo_walk/operations_log.jsonl](demo_walk/operations_log.jsonl) | The operations log of the full demo walk exported with `GET /evidence` per ADR-0004: 14 operations, 9 security events, one chain | `DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/export_demo_evidence.py OUT.jsonl` |
| [demo_walk/operations_log.md](demo_walk/operations_log.md) | The same log as readable tables, with the tamper check | generated from the JSONL |
| [demo_walk/verify_output.txt](demo_walk/verify_output.txt), [verify_tampered_output.txt](demo_walk/verify_tampered_output.txt) | `VALID: 14 operations, 9 security events, head 99febe38404ee7e6…`; and `INVALID … seq 2: entry_hash mismatch` after one fen is added to a payload | `python3 scripts/verify_evidence.py FILE` |
| [security_refusals.md](security_refusals.md), [.json](security_refusals.json) | Four refusals with their security events: an over-limit draw, a prompt-injection buyer message, the agent key at owner routes, a buyer past its daily budget | `DEMO_MODE=1 PYTHONUTF8=1 uv run --project services/api python scripts/security_refusals_evidence.py OUT.json` |
| [contracts_cn.md](contracts_cn.md) | Chinese contract reading: what changed and how to re-score; the 30-contract table is not in the repository | `services/api/scripts/eval_contracts.py` |

The bulk of the 49-task run (all 49 chains, 87 turn cards, `results.json`) was kept out of the repository; the committed run from 3 Oct is still at `services/api/evals/e2e/latest/`. Head hashes differ from run to run (ADR-0004, note of 3 Oct): compare VALID, not the head.
