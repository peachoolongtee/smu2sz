# ADR-0011: One durable decision record, derived from the canonical stores plus three small facts

Status: accepted. Implemented 10 Oct 2026 (map #65, ticket #71). Proposed 9 Oct 2026. Owner: main architect. Addresses audit (independent-flow-ux-audit-2026-10-09) F02, F04,
F06, F07, F13, F14, F17; sets the time-wording contract Wave 1 needs for F01 and F03. Changes no financial rule: the
engine stability gate (CONTINUOUS_OPTIMIZATION section 0) holds.

## Problem

A commercial decision runs from a buyer message (or a cash alert) through evaluation, response, approval, operations,
settlement and receipts. Each step is stored, in its own place, by its own module, and nothing links them:

- The verdict page says "Nothing is executed" after a negotiation funded a gap (F04), because the page reads the verdict
  alone.
- Deals call an acceptable offer agreed, and keep an expired agreement on screen (F06), because the web derives agreement
  from its session cache instead of the commitment lifecycle.
- "Send this counter" does not send the counter shown (F07): the route takes only a buyer profile.
- An approval card's cost disappears after the decision (F13): the queue prices it from today's open alert.
- A refused execution after approval leaves pending controls (F14), and "You declined" is written for a refusal the owner
  did not make.
- After a partial rescue nothing says what is left to decide (F17).
- Commercial terms sit in "Audit details" and Approve stays enabled when they cannot be read (F02).

Three facts cannot be re-derived later from the stores: the day a verdict was made (Verdict has no day), which counter
was sent and which the buyer accepted (Commitment keeps verdict_id, not counter_id; the transcript is only in the HTTP
response), and the economics the owner was shown when an action was queued or run (computed from the alert and plan of
that moment; the alert later moves or disappears).

## Decision

### 1. A read model, not a second engine

A decision record is assembled on request from the stores that already own each fact:

| Part | Source of truth (never recomputed) |
| --- | --- |
| source | CompiledOffer (offer_id, version, received_day, doc_ids, counterparty_id); or the alert named in a QUOTED fact |
| parsed terms, assumptions | CompiledOffer.obligations / abstentions; Verdict.bound_obligations, Verdict.plan actions (repay_day is an assumption) |
| evaluation | Verdict (outcome, violations, counters, required_tier, state_version) |
| recommended response | Verdict.counters, business_action(outcome, len(counters)) |
| quoted economics | the SENT or QUOTED fact (below) |
| selected option | SENT.chosen_counter_id / accepted_counter_id |
| authorization | ApprovalRecord (status, decided_day, decided_by); OperationResult.tier |
| agreement | Commitment.status, lapsed_obligations, settled_obligations, expires_day |
| bound operations, execution | the operations log, read with app.operations.log.read_entries |
| settlement | FinancialState.lots (lot.id == op_id or starts with op_id + "#"; settled) |
| receipts, reconciliation | reconcile(): ReceiptMatch rows and PromisedReceipt rows for the commitment |
| residual risk | today's alerts (RESERVE_BREACH_AHEAD), read now and labelled as current |

Display strings are written by the server (INVARIANT 13). The only arithmetic is summing operation amounts that
the log already holds, for a display total. No projection, price or rate is computed for a past moment.

### 2. One small append-only table: decision_facts

Only what cannot be re-derived is stored. Pattern of the pilot journal (migration 0005): its own table in both
stores, a migration, append-only, never the financial state, never an operation, never on the hash chain. Unlike the
pilot journal it is ledger data: `reset()` clears it with the ledger.

    decision_facts
      row_id         BIGINT (INTEGER on SQLite)  primary key, autoincrement
      decision_id    VARCHAR(160)  NOT NULL, indexed
      family         VARCHAR(8)    NOT NULL   -- DEAL | FUNDING
      fact           VARCHAR(16)   NOT NULL   -- EVALUATED | SENT | QUOTED
      fact_key       VARCHAR(256)  NOT NULL   -- the canonical id the fact is about
      state_version  INTEGER       NOT NULL   -- the books the fact was written against
      day            INTEGER       NOT NULL   -- the clock day of the write
      body_json      TEXT          NOT NULL   -- canonical JSON of the fact model below
      recorded_at    VARCHAR(40)   NOT NULL
      UNIQUE (decision_id, fact, fact_key)

A write is insert-if-absent: a second write with the same (decision_id, fact, fact_key) returns the row already
stored and changes nothing. The stores expose no update or delete (SQL: the Core append-only guard, `_PROTECTED`).
On PostgreSQL the table gets row-level security as in 0005.

Fact bodies are strict Pydantic models (`extra="forbid"`): integer fen, integer days, ids, exact Ratio for rates.
They hold no buyer text and no model output.

- EVALUATED (DEAL; fact_key = verdict_id). offer_id, offer_version, verdict_id, outcome, counter_ids, recommended_counter_id,
  mandate_version. Gives the evaluation its day.
- SENT (DEAL; fact_key = "accept-{commitment_id}" when the buyer accepted, else "nodeal:{verdict_id}:{buyer_profile}", with
  ":{counter_id}" added for a bound send, so a send of one counter after another's refusal is its own fact).
  offer_id, verdict_id, state_version_shown, chosen_counter_id (null for an unbound send), counter_ids_sent in round
  order, buyer_profile, simulated = true, outcome (DEAL | NO_DEAL), accepted_counter_id, transcript_hash,
  commitment_id, accept_op_id, funding_op_ids, funding_blocked (null or the router's reason code), counter_economics of
  the chosen or accepted counter {supplier_cost_fen, forward_value_fen, funding_cost_fen, offset_fen, net_fen,
  basis_facility_id, basis_rate} as `counter_economics()` gave it at send time, gap_plan {need_fen, total_cost_fen, legs [{kind,
  facility_id, receivable_id, amount_fen, lands_day}]}. The counter economics hold numbers and ids only: the basis is
  `basis_facility_id` and an exact `basis_rate` Ratio (not a `basis_label`), and the server words the label per language.
- QUOTED (FUNDING; fact_key = decision_id). alert_id, alert_kind, alert_day, state_version_shown, source (cure | router),
  legs [{op_id, kind, facility_id, receivable_id, amount_fen, cost_fen, annual_rate, cost_days, cost_end_day, lands_day,
  above_ceiling}], total_cost_fen (null when the engine gave no total), cost_note (draw_interest_excluded | null),
  needs_owner, max_apr_bp, projected, restores_reserve (null when not projected), after_first_short_day (null with projected = safe through the horizon), horizon_days,
  if_decline {kind: below_reserve | below_zero | closed, day, zero_day, shortfall_fen, max_shortfall_fen,
  worst_day}, residual_shortfall_fen (numbers, never display strings). Every number is copied from the Alert's SuggestedAction pricing, the alert's
  inputs, the router plan's cost lines (`cost_lines_by_leg`) and the after-state projection the home already shows
  (`cure_after_words`). Nothing is priced for the fact.

### 3. Decision identity

`decision_id` is deterministic, so the read model and every write agree without a lookup table:

| Family | decision_id | Members |
| --- | --- | --- |
| DEAL | `deal:{offer_id}` | the offer (all versions), its verdicts, its commitments, the ACCEPT_OFFER / RECORD_COMMITMENT operations on them (`accept-{commitment_id}`), the funding legs in SENT.funding_op_ids (fallback for older logs: `fund-{offer_id}-{cooperative|hard_line}-{i}`), receipts reconcile() matches to its commitments |
| FUNDING (alert cure) | `alert:{alert_id}:v{state_version}` | log rows and approvals whose op_id starts with `alert:{alert_id}:v{state_version}:` and has no `:plan:` |
| FUNDING (router plan) | `alert:{alert_id}:v{state_version}:plan` | op_id starts with `alert:{alert_id}:v{state_version}:plan:` |
| FUNDING (chat) | `nl:{session}:{scope}` | operations whose idempotency key starts with it (an NL ACCEPT_OFFER belongs to its deal) |
| any other approval | `approval:{approval_id}` | the queued operation and its decision run (capex apply, a direct POST /operations) |

The alert id is frozen into the op ids at act time, so the decision keeps its id when the alert's start day moves. A
bank receipt is evidence on a deal, never a decision of its own. A Tier-1 operation posted directly to /operations
with no approval is Activity, not a decision.

### 4. Write points (API layer only, after the canonical event)

| Route | Canonical event first | Then writes | If the second write fails |
| --- | --- | --- | --- |
| POST /offers/{id}/evaluate | `put_verdict` | EVALUATED | the record still shows the verdict; its date reads "date not recorded" |
| POST /negotiate/{offer_id} | `propose_commitment`, the AcceptOffer unit, each funding unit | SENT | agreement state and operations still derive from the commitment and the log; the counter shown at send time reads "not recorded" |
| POST /alerts/{id}/act | each operation's executor unit | QUOTED (also when every leg was refused: it is what was attempted) | state still derives from the log, approvals and lots; the quote reads "not recorded" |
| POST /approvals/{id} | `executor.decide` | nothing: ApprovalRecord and the decision run in the log already hold it | n/a |
| POST /clock/advance | the ADVANCE_CLOCK unit | nothing: expiry, lapse, fulfilment and lot settlement are in commitments, lots and the clock's log payload | n/a |
| POST /operations, /nl | the executor's units | nothing in this ADR (see consequences) | n/a |

Rules for every write:

- It happens inside the route's `rt.lock`, after the executor returned, so in one process no read sees the operation
  without its fact.
- The quote is computed before the executor runs, from the alert and plan the route already recomputed and bound to
  the shown `state_version` and suggestions (409 ALERT_CHANGED otherwise). So the quote is exactly what the owner was
  shown.
- It goes through one helper, `record_fact()`. The helper catches any store error, logs it, and sets
  `decision_recorded: false` in the response. It never turns a committed canonical event into a 500, because a
  client retry of a 500 could repeat a negotiation.
- Retrying is safe: the same canonical ids give the same fact_key, and the insert is a no-op.
- A missing fact is shown as missing. The read model never fills it by recomputing history from today's alert,
  today's plan or today's books.

Rejected: writing the fact inside the executor's unit of work (the executor and the stores' transaction stay
untouched in stability mode), and wrapping execute plus fact in one outer `store.transaction()` (a nested unit cannot
run the executor's compare-and-swap retry, and an alert act runs several units: a late failure would roll back legs
that had executed).

### 5. States, derived from stored reality only

One function `derive(inputs) -> DecisionState`, pure, in `app/decisions/state.py`. First matching rule wins.

DEAL. O = the offer (latest version); V = the last stored verdict with V.offer_id = O.offer_id; C = the commitment
named by the latest SENT fact, else the last stored commitment for the offer; A = the approval whose operation is
RECORD_COMMITMENT(C.id) or ACCEPT_OFFER(offer_id, offer_version, nonce = C.nonce); X = the last non-DUPLICATE log
result of that accept operation (an owner-decided re-run included, a non-owner `#decide:` attempt excluded);
P = reconcile().promised rows for C.

| # | State | Rule | Terminal |
| --- | --- | --- | --- |
| 1 | REVOKED | C.status = REVOKED | yes |
| 2 | FULFILLED | C.status = FULFILLED | yes |
| 3 | MISSED | C.status = EXPIRED and C.lapsed_obligations non-empty | yes (the invoice stays owed) |
| 4 | MISSED | C.status = ACTIVE and some P row is LAPSED | no (other terms live) |
| 5 | AGREED | C.status = ACTIVE | no |
| 6 | EXPIRED | C.status = EXPIRED, no lapsed obligations (it lapsed before agreement) | yes |
| 7 | AUTHORIZATION_REQUIRED | A.status = PENDING | no |
| 8 | DECLINED | A.status = REJECTED | yes |
| 9 | FAILED | X.status = REFUSED and A is not REJECTED (refused at once, or approved then refused on re-run) | yes |
| 10 | NO_DEAL | the latest SENT for V has outcome NO_DEAL | yes |
| 11 | NEEDS_CLARIFICATION | O.status is ABSTAINED or CONFLICTING_SOURCES, or V.outcome = NO_VERDICT | no |
| 12 | RESPONSE_READY | V exists | no |
| 13 | RECEIVED | otherwise | no |

RESPONSE_READY carries `business_action` from the verdict: with outcome ACCEPT it reads "Acceptable, awaiting
agreement", never "Agreed". The agreement words follow C only: Agreed (ACTIVE), Fulfilled, Expired, Revoked, and
"Early payment did not arrive" (MISSED).

FUNDING. L = the decision's operations, each with its last non-DUPLICATE result as above; Q = the QUOTED fact;
lots(op) = lots whose id is op_id or starts with op_id + "#".

| # | State | Rule | Terminal |
| --- | --- | --- | --- |
| 1 | AUTHORIZATION_REQUIRED | an approval of an operation in L is PENDING (legs already executed are listed beside it) | no |
| 2 | DECLINED | no leg EXECUTED and an approval in L is REJECTED | yes |
| 3 | FAILED | no leg EXECUTED and a leg is REFUSED | yes |
| 4 | PARTIALLY_EXECUTED | some legs EXECUTED, and a leg REFUSED or fewer legs logged than Q.legs | no |
| 5 | SETTLEMENT_PENDING | all legs EXECUTED and some lot unsettled | no |
| 6 | SETTLED | all legs EXECUTED, they created lots, every lot settled | yes, unless residual |
| 7 | EXECUTED | all legs EXECUTED and none created a lot (a repayment, an application) | yes |

Residual risk is a field, not a state. It is set on the newest FUNDING record whose Q.alert_kind is
RESERVE_BREACH_AHEAD and which is in state 4 to 7, when Q.restores_reserve is false or a RESERVE_BREACH_AHEAD alert
is open today. It holds the current shortfall, the first day it starts and whether a committed cure exists. It is
read now and labelled as today's position.

Candidate states not kept, and why:

- INTERPRETED is merged into RECEIVED: compilation is synchronous in POST /offers.
- EVALUATED is merged into RESPONSE_READY.
- RESPONSE_SENT and BUYER_ACCEPTED cannot persist: the simulated buyer answers in the same request.
- AUTHORIZED is transient: approval re-runs at once and becomes EXECUTED or FAILED.
- OPERATIONS_BOUND and EXECUTION_REQUESTED are covered by SETTLEMENT_PENDING.
- MONITORING is AGREED.
- BREACHED is MISSED.
- CURE_READY is the home's next_action, a proposal, not a record.
- RESOLVED is FULFILLED / SETTLED / EXECUTED.

### 6. What FLOW is waiting for

`waiting_for(state, inputs) -> {code, party, day}`, pure, beside `derive`:

| State | code | party | day |
| --- | --- | --- | --- |
| RECEIVED, RESPONSE_READY | OWNER_RESPONSE | owner | none |
| NEEDS_CLARIFICATION | BUYER_CLARIFICATION | buyer | none |
| AUTHORIZATION_REQUIRED | OWNER_APPROVAL | owner | DEAL: C.expires_day; FUNDING: Q.alert_day (when the cash is needed) |
| AGREED, an AWAITED promise | BANK_RECEIPT | buyer | the earliest promised_day |
| AGREED, an adjustment of C still in state.invoice_adjustments | INVOICE_ISSUE | the books | the buyer's recurring next_issue_day |
| AGREED, invoices carrying "{C.id}:" in `applied` still outstanding | BANK_RECEIPT | buyer | the earliest due day |
| MISSED | BANK_RECEIPT | buyer | the invoice's own due day (overdue when before today) |
| SETTLEMENT_PENDING (any family, linked funding included) | FUNDING_SETTLEMENT | the lender (facility name) | the latest unsettled arrival_day |
| PARTIALLY_EXECUTED, or residual set | OWNER_DECISION | owner | the current reserve alert's day |
| anything else | NOTHING | none | none |

The record's `remaining_task` is the owner-words sentence for this result. For example: "Nothing is waiting: the
action is complete." or "Your minimum cash reserve is still ¥X short from {when}; no committed funding restores it.
This needs your decision."

### 7. API

- `GET /decisions?lang=en|zh&family=DEAL|FUNDING&open=true&limit=N`: newest first (by the day of the latest
  event, then log seq). Each item: id, family, state, state_text, terminal, headline, counterparty_name,
  amount_display, opened_when, updated_when, waiting_for {code, party, party_name, day, when, text}, residual.
- `GET /decisions/{decision_id}?lang=`: the summary, plus:
  - source, interpretation.terms (server sentences), evaluation (verdict_id, outcome, business_action,
    evaluated_when);
  - response (counters with labels and economics display, recommended_counter_id, sent);
  - quote (lines, total, rate basis, lands, after-state, if-declined, `recorded`);
  - authorization (required tier, approval_id, status, decided_when, decided_by);
  - agreement (commitment_id, status, status_text, expires_when);
  - operations (op_id, kind, status, event_text, when);
  - execution (summary_text, requested_display, landed_display, in_transit_display);
  - settlement (lots), receipts (detail_when), promises, residual, waiting_for, remaining_task.
  404 for an unknown id.
- Owner only, under `rt.lock`.
- Embedding:
  - /home adds `open_decisions` (up to three non-terminal summaries) and `remaining_task` (F17).
  - /approvals/queue rows add `decision_id`, `decision_state`, `quote`, `terms_available`, `terms`, `execution`.
  - The evaluate, negotiate and act responses add `decision_id`.
  - /ledger operations add `decision_id`, so Activity links each entry to its record.

Where the findings attach:

- **F02.** The queue resolves the commitment on the server: RECORD_COMMITMENT by id; ACCEPT_OFFER by offer_id,
  offer_version and an exact nonce. It writes the terms as sentences before Approve. `terms_available` is false
  when the commitment is missing, unreadable, has no obligations, or is no longer PROPOSED/ACCEPTED, and the card
  then disables Approve with the reason and a recovery link. Ids and hashes stay under audit details.
- **F04.** The verdict page shows `execution.summary_text` above the verdict. The evaluation label becomes
  "Evaluation alone makes no changes."
- **F06.** Deal steps and the Deals list read `state` / `agreement.status_text`, never the session cache.
- **F07.** NegotiateIn gains `verdict_id`, `counter_id` and `state_version`. If any differs from the latest stored
  verdict, a counter in it, or the books' current version, the answer is 409 COUNTER_CHANGED and nothing is
  proposed, accepted or funded. The 409 carries the latest verdict's guarded counters when that verdict is on the
  current books, else `reevaluate: true`. A bound send offers only the chosen counter. SENT records it. The evaluate
  view gives each counter a `send_scope` sentence (simulated reply; records the agreement, with your approval when
  it changes terms; runs the funding for any remaining gap within your limits).
- **F13.** Decided rows show the QUOTED economics, the actual result (lot request and arrival days) and the
  difference (for example, approved later, so the cash lands later). Without a fact, decided rows say "quoted cost
  was not recorded" and pending rows say "price today".
- **F14.** FAILED is a terminal record state. The queue's `execution` says "You approved it, but it could not run:
  {reason}. No money moved." The web rereads the queue after every completed decision.
- **F17.** Residual plus OWNER_DECISION gives /home.remaining_task.

## Consequences

- The record's state follows the stores within the same request. Clock expiry, lapse and settlement need no write
  of their own.
- Three writes in three routes. One new table, one migration (0006), one pure module, one router.
- A decision written before this ADR has no facts. Its state derives, and its quote and sent counter read "not
  recorded".
- Chat decisions (`nl:`) and direct /operations approvals get identity and state, but no quote until a later step
  records one.
- Demo reset clears the facts with the ledger.
- The facts are not on the hash chain. They point at chain entries by op_id and seq.
- PostgreSQL behaviour of the new table is covered by the same pending G4 run.
- Every read takes `lang` (F28): the facts hold numbers, the server writes the sentences per request.

## What it deliberately does not do

- It does not compute money, price a past moment, project history or decide anything. It reads canonical records
  and three facts.
- It does not touch `app/financial`, `app/verifier`, `app/funding`, `app/alerts`, `app/operations`, `app/clock`, the
  mandate or the stores' transaction. No engine module imports `app.decisions`; a test pins that.
- It grants no authority. Consent stays on the approval, the bound act and the bound send; a record cannot be
  approved.
- It does not make the simulated buyer asynchronous, add a buyer channel or model a sent-but-unanswered counter.
- It does not let the owner waive a hard rule. Residual risk asks for a decision; it offers no override.
- It stores no sentence, no buyer text and no model output. It has no edit or delete.

## The lead's answers to the architect's open questions (9 Oct)

1. An unbound `POST /negotiate` (no `counter_id`) keeps the current behaviour (the Demo stepper and the existing tests use it) and is recorded as SENT with `chosen_counter_id` null; the Business "Send" always binds. The 409 path never writes a verdict: it returns the latest verdict's guarded counters when that verdict is on the current books, else `reevaluate: true`.
2. Chat ("go ahead") decisions stay derived-only in Wave 2 with "quote not recorded"; a follow-up ticket records the plan shown in the earlier turn.
3. The card shows the queued quote and today's price when they differ. Enforcing the quoted cost as a ceiling on approvals is an engine change, recorded on grilling #66 for the owner, not done here.
4. `remaining_task` is a statement plus the supported routes as links (compare options on Cash; the named invoice on Receivables; the limits page); no facility application is invented.
5. Standalone approvals appear as `approval:` records; the facts stay off the hash chain and out of the evidence export.

## Implementation notes (10 Oct 2026)

Decisions taken while building it, all inside the rules above:

- The facts hold no sentence. `basis_label`, `max_shortfall_display` and `residual_shortfall_display` became `basis_facility_id` plus
  `basis_rate`, `max_shortfall_fen` and `residual_shortfall_fen`.
- The residual (section 5) is set only while a RESERVE_BREACH_AHEAD alert is open today. ADR text also let `restores_reserve` false
  alone set it; with no open alert there is no current shortfall to show. `quoted_to_restore` keeps the quote's flag. The newest
  reserve record carries it (`derive_all`), and it keeps SETTLED and EXECUTED records open.
- ACCEPTED, the transient twin of ACTIVE, reads AGREED. A FUNDING record with a quote and no logged operation reads FAILED (nothing
  ran). The deal table is applied as written: an approve that the run refused because the commitment had expired is EXPIRED (row 6
  before row 9); the FAILED record is the funding one (for example the cure approved after the mandate expired).
- The module takes protocols for the log entry, the promise and the alert, so it imports only `app.domain` and
  `app.persistence.records`. `decision_id_for` takes a keyword `approval_id` and returns None for activity.
- Waiting: a deal's linked funding in transit is checked after the buyer rows, for AGREED and NO_DEAL.
- A router-plan quote stores no per-leg rate (the plan's cost lines carry none); a cure quote stores the alert's exact rate.

## Review fixes (10 Oct 2026)

- The residual belongs to the record whose breach it is: the open alert is the record's own (`alert_id`), or the engine says nothing
  fixes it (`committed_cure` false). A later, unrelated breach with a committed cure is the next step on the home, not an old record's
  residual, and the old record closes. When the alert still has a committed cure the sentence says a funding plan is ready, not that
  nothing restores the reserve.
- A quote says whether it projected anything (`projected`). A repayment, an application and a failed projection did not, and say
  nothing about the reserve; a repayment's after-state is "The balance is repaid and the interest stops."
- A bound send is idempotent: while a commitment for the same verdict and the same terms is PROPOSED, ACCEPTED or ACTIVE, a second
  identical send is 409 `ALREADY_SENT` (with the commitment and approval ids) and creates nothing. The binding check and the side
  effects run in one lock. Any binding field present also requires the latest verdict to be on the current books.
- `record_fact` builds the fact inside its guard and answers `true`, `false` or `"already_recorded_differently"` (a fact with that
  key was stored earlier with other content; the earlier one stands).
- A router-plan leg keeps the rate its cost line stated (to two places). A decision that cannot be derived is logged and left out.
- Known: `fen_of` reads money back from the alert's display strings. And `/negotiate` funds the gap in the same call as a queued
  accept, which moves the books, so approving that accept later is refused ("The books changed since verdict ...") and the record reads
  FAILED. That is executor behaviour; it is recorded, not changed here.
