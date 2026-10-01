# Next fixes

Live tracker for the work after the 1 Oct audit (`SZ_Research/research/termsledger_v2_audit_2026-10-01/AUDIT.md`,
taken at commit `6d500a9`). Updated after every merge.

Status: OPEN, IN PROGRESS, DONE, DROPPED. Owner: **main** = main agent, **sub** = bounded subagent task.
Evidence: V = reproduced by me on 1 Oct, A = audit only, C = confirmed by reading the code.

## Wave A: security boundary (P0)

| ID | Fix | Audit | Evidence | Owner | Branch | Effort | Proof of completion | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | Counterparty `/nl` response carries reply and session only | S1 | V | sub | fix/nl-boundary | 3h | counterparty response has no verdict, plan, operations or protected value | DONE |
| A2 | Quoted or pasted text never becomes owner intent or an approval id | S2 | V | sub | fix/nl-boundary | 4h | pasted "approve APR-…" evaluates the offer, logs an event, approves nothing | DONE |
| A4 | Security scoreboard computed from run data | S11 | V | sub | fix/scoreboard | 2h | no literal `0` or `[]`; a seeded leak shows up in it | DONE |
| A5 | Coverage proof fails closed on unread words; reply restates typed terms | S3, C7 | A | sub | fix/coverage-fail-closed | 5h | rider cases go to owner review; no "Agreed as proposed" | DONE |
| A6 | Re-verify at accept and approve: receivable, exclusivity, caps, state version | S4, C2 | C | sub (spec: ADR-0006 §5) | fix/commit-state-binding | 6h | two 1.2% rebates: second refused over the ¥5,000 cap | DONE |
| A3 | Attack catalogue also runs through `/nl` as owner and as counterparty | C1 | C | sub | fix/nl-attacks | 5h | attacks via `/nl`: 0 harm, counted in the report | DONE |

Found by A3 and fixed the same day: text pasted without quote marks ("Attachment:", "> …", "Forwarded message")
could still approve a queued item, and a caller with only the agent key could say "go ahead" inside the owner's
session. Now a chat session is bound to the credential that opened it, and an approval, decline or go-ahead only
counts as a one-line instruction of at most 80 characters with no counterparty name and no forwarding marks.
Attack report: 122 through the API and 60 through chat, 0 with harm.

Still open from A3 (medium): buyer-role probing finds the accept/counter threshold to 1 bp in 12 messages with no
throttle, and each accepted probe queues its own owner approval (S5); the agent key can read cash, floor and
headroom through the chat status reply (S9).

## Wave B: one financial reality (P0/P1)

| ID | Fix | Audit | Owner | Effort | Proof | Status |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | ADR-0006 | C3 | main | done | `docs/adr/0006-current-books-and-clock.md` | DONE |
| B1 | `as_of_day`, `settled_fen`, engine drops closed days, `app.books.current_books` | C3 | main | 5h | golden values unchanged at day 0 | DONE |
| B2 | Partial settlement and FULFILLED in the executor (ADR §4) | wf 3 | sub, after A6 | 4h | ¥209,999.70 settles ¥211,800 of RCV-A; ¥208,200 stays open | DONE |
| B3 | Verifier, router, trajectory, what-if on current books | C3 | sub, after B1 | 5h | verdict after an accepted extension sees the shifted receipts | DONE |
| B4 | Alerts, capex, borrower file on current books | C3 | sub, after B1 | 4h | all screens give the same lowest-cash day | DONE |
| B5 | Counter A rounds up and is checked against the floor | F8 | sub | 2h | no critical alert straight after the demo deal | DONE |

Added during integration (all DONE): each financing advance is recorded on its invoice (`Receivable.advance_fen`)
so the projection repays it from that invoice; the clock applies a scenario's dated events
(`fixtures/scenarios/golden_sme.events.json`: month-2 payroll of ¥200,000 appears on day 25).

Integrated run on 1 Oct (EX01 → deal → receipt of ¥209,999.70 on day 2 → clock to day 34): the residual
¥208,200 is reported past due and the gap peaks at ¥200,000.30 on day 42. The only thing stopping a cure
is B5: Counter A leaves cash ¥0.30 under the floor, so the breach starts "today".

B5 merged 1 Oct: Counter A is ¥211,900 at 0.85% (nets ¥210,098.85; discount ¥1,801.15 + line ¥841.09 =
¥2,642.24), offered only when the router's plan on books with the counter is admissible. Integrated run
(`scripts/demo_run.py`): no critical alert after the deal; on day 34, with the ¥208,100 residual unpaid, the
breach on day 42 (¥200,000) comes with a committed cure: finance ¥200,000 of `RI:BUYER-1:2`. If the early
payment never arrives at all, reconciliation reports it LAPSED and no committed cure exists (gap ¥410,098.85).

## Wave C: clock, event, re-plan (P1)

| ID | Fix | Owner | Effort | Proof | Status |
| --- | --- | --- | --- | --- | --- |
| C1 | `Runtime.advance_to` and `POST /clock/advance` (ADR §2) | main | 4h | day 40 cash includes payroll; expired commitments marked | DONE |
| C2 | Alert carries a typed cure; `POST /alerts/{id}/act` executes Tier 1 or queues Tier 2 | sub, after B4 | 5h | missed receipt → "draw ¥150,000" → one call executes it | DONE |
| C3 | Reconcile compares receipts with what commitments promised | sub, after B2 | 3h | missing early payment reported as lapsed | DONE |
| C4 | Proactive opener in `/nl` and the UI after a clock or bank-feed event | sub, after C2 | 4h | demo steps 8 to 13 run from the chat | OPEN |

## Wave D: financial correctness (P0 where a verdict changes)

| ID | Fix | Audit | Owner | Effort | Proof | Status |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | Break-even from actual days early | F1 | main formula, sub tests | 3h | 30 days still 0.88%; 90 days at 1.2% accepted | IN PROGRESS (fix/early-pay-economics) |
| D2 | Early pay only when cash is needed and cheaper than the router's plan | F2 | main rule, sub code | 4h | no-need offer is not accepted | IN PROGRESS (fix/early-pay-economics) |
| D3 | Financed receivable settled early repays the advance that day | F7 | covered by B2 | — | day-20 cash not double counted | DONE |
| D4 | DSCR counts scheduled bullet principal | F6 | sub + second sub to check | 3h | hand-calculated case | OPEN |
| D5 | APR gate on posted cost over actual days | F5 | sub | 3h | 3-day advance fails the 15% cap | IF TIME |

## Wave E: interaction (P2)

| ID | Fix | Audit | Owner | Effort | Status |
| --- | --- | --- | --- | --- | --- |
| E1 | `/nl` intents: financing comparison, alerts, reconcile, ratios, capex, borrower file | C6 | sub | 6h | OPEN |
| E2 | Nearest-capability fallback | C6 | sub | 2h | OPEN |
| E3 | Owner home at `/` | C8 | sub (frontend) | 5h | OPEN |
| E4 | Approval card with operation, clause, after-state | C8 | sub (frontend) | 4h | OPEN |
| E5 | Autonomy proof shown on Tier-1 accepts; REJECT badge fix | C8 | sub (frontend) | 2h | OPEN |
| E6 | Annualised column next to every discount | §9 | sub | 3h | OPEN |
| E7 | Compliance half-page, LICENSE, reframed accuracy numbers | §8 | sub (docs) | 2h | OPEN |
| E8 | Demo fixes: Start 401, mock/live mismatch | §9 | sub (frontend) | 2h | OPEN |

## Wave F: optional (P3, only when A to D are green)

Named stresses (C9), receipt instrument (C10), guarded supplier payment (C11), recurring outflows (C12),
Chinese server text, deployment. Post-hackathon: S6, S7, S8, C13, F9.

## Dependencies

```
A1+A2 ──► A3 ──► security report refresh
A4 ─────► A3
A6 ──► B2 ──► C3
B1 ──► B3, B4 ──► C2 ──► C4
B1 ──► C1 ──► C2
B3 ──► D1, D2
B5 independent      A5 independent      E7 independent
E1, E2 after A1+A2 (same files)         E3–E6 after B4 and C2
```

## Stop conditions

- Any task past 1.5× its effort stops and reports.
- B1 changes more than 15% of golden values at day 0: revert, rethink.
- C waves not green by 9 Oct: ship alert-with-button only (C2), drop C4.
- E3–E6 never delay the video recording: home view first, the rest if time.
- No Wave F work while any A to D row is open.

## Scoreboard

Generated by `scripts/evaluate.py`. Baseline at `6d500a9`: backend 3,557 passed; scenarios 37/37; 122
attacks, 0 harm (none through `/nl`); golden 55/55. To add: attacks through `/nl`, protected fields
disclosed (computed), stale-state executions, current-books consistency, `/nl` capability coverage.
