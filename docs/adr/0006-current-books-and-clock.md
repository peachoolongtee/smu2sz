# ADR-0006: One set of current books, a moving clock, and re-verification at commitment

Status: accepted, 1 Oct 2026. Owner: main architect. Implements audit items C2, C3, C4.

## Problem

Modules project from different books. The verifier, router, trajectory, capex and what-if read the raw
state; alerts and the borrower file add live commitments. The clock never moves in the served app, a
partial receipt settles a whole receivable, and a verdict computed on old books still authorises a
commitment.

## Decision

### 1. Source of truth

- `FinancialState` in the store is the **actual position today**: cash, facility balances, receivables,
  unposted scheduled flows. Only the executor and the clock write it.
- Commitments in the store are the **agreed changes not yet realised**.
- **Current books** = `(state, live obligations)` from `app.books.current_books(store, day)`. Every
  projection in every module runs on current books plus whatever it is testing. No module projects from
  the raw state alone.

### 2. Time

- New field `FinancialState.as_of_day` (default 0): the books are closed for every day before it.
  `cash_fen` is the cash at the start of `as_of_day`.
- Days stay absolute. Nothing is re-based, so ids, effective days and golden values keep their meaning.
- The engine drops scheduled flows and receivable receipts dated before `as_of_day`: they are either
  already in `cash_fen` (posted) or did not happen (an unpaid receivable). Conservative projection never
  assumes an overdue receipt arrives. With `as_of_day = 0` nothing is dropped, so every existing golden
  value is unchanged.
- `Runtime.advance_to(day)` is the only way time moves. For each day passed it, in order:
  1. posts scheduled flows dated that day into cash and removes them from `flows`;
  2. turns recurring invoices issued that day into real receivables (same id the engine generated);
  3. moves PROPOSED/ACCEPTED commitments past `expires_day` to EXPIRED;
  4. sets `as_of_day`, bumps `state_version`, logs one `ADVANCE_CLOCK` entry on the hash chain.
  It never records a receipt. Receipts come only from the bank feed (`ReceivePayment`), which is what
  makes a missing receipt detectable.

### 3. Live obligations

`current_books` returns the cash-relevant obligations of ACCEPTED/ACTIVE commitments, in acceptance
order, that still bind to the state. Excluded, and reported separately as `lapsed`:

- an early-pay obligation whose effective day is before `as_of_day` and whose receivable is still unpaid
  (the buyer did not pay early; the receivable reverts to its original due day);
- an obligation whose receivable is settled (history, not projection).

Rebates and concessions without an effective day stay where they are today: booked at their maximum in
`state.forward_concessions` at acceptance and removed on revoke.

Obligations are deltas. Two accepted terms extensions for one buyer stack, which is correct because the
second was verified on books that already held the first.

### 4. Settlement

- New field `Receivable.settled_fen` (default 0). Outstanding = `face_fen − settled_fen`. The engine
  projects the outstanding amount.
- `ReceivePayment` of amount `a` on a receivable:
  - if a live early-pay obligation covers face `P` of it at discount `d` and `a` equals the posted
    `P × (1 − d)`: `settled_fen += P`, and the commitment becomes FULFILLED;
  - otherwise `settled_fen += a`.
  - `settled_fen == face_fen` → SETTLED. Less → stays OPEN with the residual due on the original day.
  - `a` above the outstanding amount is refused. The same idempotency key is a DUPLICATE as before.
- A FINANCED receivable repays its whole advance, interest and fee on the first receipt (as today), then
  is OPEN with any residual, or SETTLED.

### 5. Re-verification at commitment (state binding)

A verdict is not standing authority. `AcceptOffer`, `RecordCommitment` and the owner's approval of either
all pass through the executor's `_commit`, which now checks, against the state and mandate at that moment:

1. every receivable an obligation names is still OPEN or FINANCED with enough outstanding face;
2. no other ACCEPTED/ACTIVE commitment has an obligation on the same named receivable;
3. booked forward concessions + this commitment's value ≤ the aggregate cap, and ≤ the buyer's cap when
   one is set;
4. if `state_version` differs from the verdict's: the commitment's obligations are re-verified on current
   books through an injected `reverify` hook (the executor does not import the verifier). The hook must
   return ACCEPT or NEEDS_OWNER_APPROVAL, otherwise the operation is refused.

A failure is `REFUSED` with code `STALE_VERDICT` or `CONFLICTING_COMMITMENT` and the message says to
re-evaluate. Nothing is ever executed from a verdict that no longer holds.

### 6. Ordering, idempotency, concurrency

- One executor lock and one store transaction per operation, as before. Checks 1–4 run inside it, so two
  concurrent accepts are serialised and the second sees the first.
- Idempotency keys are unchanged. `ADVANCE_CLOCK` uses the key `clock-<from>-<to>`; advancing to a day
  already reached is a no-op.
- Projections always consume current books. Stored verdicts are historical records and are never
  re-read as if current.

## Consequences

- Interest on a balance drawn after day 0 is still projected as if drawn on day 0 (existing convention,
  overstates only). The executor charges actual days.
- A financed receivable that goes overdue keeps its advance outstanding in the projection until the
  horizon end. Known limit; say so in the technical document.

## Kill condition

If more than about 15% of golden tests change value after the engine change with `as_of_day = 0`, stop:
the change is wrong, not the tests.
