# ADR-0011: Buyer reliability is learned from payments and stays advisory

Status: proposed, 13 Oct 2026 (branch `feat/agent-optimiser`). Owner: technical owner.

## Problem

When several buyers send deals, the owner cannot see which of them actually pays on time. The verifier prices
every offer on its contractual terms only: a buyer who agrees 30 days and pays in 40 looks the same as one who pays
on day 30. The evidence already exists (the bank feed's receipts matched to invoices by `app/alerts/reconcile.py`,
promised early payments that were kept or lapsed), but nothing turns it into a judgement about the buyer.

## Decision

1. **A profile per buyer, learned from payments.** `app/reliability` folds every observation into a score with
   one written rule (module docstring): an on-time rate and an average delay, both recency-weighted (half-life
   365 days) and shrunk toward a neutral prior when there is little history, minus a penalty per incident (a part
   or short payment, an ignored discount, a lapsed promise). Grades: RELIABLE (≥ 75), WATCH (45–74), RISKY
   (< 45), UNRATED (no evidence; ranked as a neutral 50). The formula is returned with every profile.
2. **Evidence starts with an agreed deal.** An invoice exists only once the supplier has agreed and delivered, so
   observations are invoices (paid, or past due today) and the promises of accepted deals. Each new receipt from
   the bank feed is a new observation; nothing is stored, the profile is recomputed from the log on every read.
3. **Imported history is a prior, not cash.** The demo scenario carries simulated invoices settled before the books
   start (`fixtures/scenarios/<scenario>.payment_history.json`, every day negative). It never touches the books.
   Provisioned books have none and start UNRATED.
4. **Advisory only.** `GET /reliability` ranks the deals the owner names by the buyer's score, then by the
   verifier's business action. No engine module reads the score: the verdict, counters, plans, the mandate and
   the golden values are unchanged. The delay is priced in words at the engine's marginal cost of funds, for
   the owner to read.

## Consequences

- The Deals page shows a grade on each inbox thread and a "Who pays you reliably" card under the deal.
- Feeding expected delays into the EXPECTED projection, or a mandate rule on unreliable buyers, would be a
  financial change: it needs its own ADR, a hand-derived check and the owner's decision.
