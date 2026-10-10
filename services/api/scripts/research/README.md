# Research spikes: envelope, portfolio, collections

Wayfinder map #39, ticket #43. Read-only scripts that call the engine and print what it says. They now live on
`feat/strategy-mvp` as the differential oracle of map #47 (their output is recorded under `fixtures/strategy/`), are
still never imported by the app, never run in CI, and still refuse to run without `FLOW_RESEARCH_SPIKES=1`. Results and
findings: `docs/research/strategy/04-spikes.md`.

## The flag

Every script exits with status 2 and a one-line message unless `FLOW_RESEARCH_SPIKES=1` is set. They run on the in-memory
runtime with cached compiler output (`DATABASE_URL=memory`, `LLM_MODE=cache`, set for them if absent): nothing is
written, no model is called, no operation is executed. A simulated receipt, offer or package is a copy of the books
(`model_copy`) or a synthetic typed offer, labelled hypothetical.

## Run

From the repository root (any directory works with absolute paths):

```
export FLOW_RESEARCH_SPIKES=1
uv run --project services/api python services/api/scripts/research/envelope_spike.py [--buyer BUYER-1] [--face YUAN ...] [--package K=V,...] [--exhaustive] [--json]
uv run --project services/api python services/api/scripts/research/portfolio_spike.py [EX01 EX08A EX08B EX05 EX06 ...] [--top N] [--no-prune] [--show-infeasible] [--json]
uv run --project services/api python services/api/scripts/research/collections_spike.py [--day 0|34|both] [--days-earlier 5] [--no-curve] [--json]
```

`--json` prints one JSON document with every amount as `{"fen", "display"}` and every rate as `{"bp", "display"}`.
Every figure is an engine output formatted with `fmt_yuan` / `fmt_pct`, or a sum or difference of engine outputs.

## What each prints

`envelope_spike.py`: the Safe Deal Envelope for one buyer on the day-0 golden books, built on the what-if sandbox's own
call (`app.whatif.offer.build` then `app.verifier.evaluate`).
1. The largest value of each lever alone (terms; terms with the forward budget ignored; terms with the price that makes
   them pass; early pay on each face; rebate), each with the wall it hits, the budget used and what the next step fails with.
2. Approved packages: for each terms value and early-pay variant the smallest price that passes and the largest rebate
   that still passes at that price, each one whole verifier evaluation: PASS or FAIL, outcome, budget used, the
   reserve breach with its cure cost and cure flags, and the binding violation codes when it fails.
3. The safe zone: terms days x price adjustment (5-day x 5 bp steps), as the smallest price that passes each terms
   value, with the price that nets the extension's cost to zero (the Option B rule) beside it.
4. The number of verifier runs and the wall time (caches cleared first). `--exhaustive` scans the whole terms x price grid and
   compares it with the bisection (and prints the grid). A lever outside the ranges (terms 30-90 by 5, price 0-1.00% by
   0.05%, early pay 0-1.50% by 0.05% held to the mandate's immediate-discount cap, rebate 0-2.00%, a face in whole
   ¥100 within the open invoice) is refused with exit status 2. `--package terms=60,price=45,discount=85,face=25720000,rebate=0`
   evaluates one package of your own (rates in bp, face in fen).

`portfolio_spike.py`: the fixture offers named (default EX01_PACKAGE EX08A EX08B; EX05 and EX06 optional; `EX01` is
short for `EX01_PACKAGE`) are compiled and evaluated. Per deal the candidates are: as asked, each counter, reject.
The table of candidates, the ranked feasible portfolios (need, funding cost, posted cost, concession value,
budget use, owner decisions needed, and what blocks the next step up), the reasons the others are out, the count,
what the pruning removed and the wall time. `--no-prune` enumerates every package for the soundness check.

`collections_spike.py`: for each open receivable on the day-0 books and on the day-34 books (the demo path replayed in process):
the saving if it is received today, five days before it is due and on the first breach day, the need that is left, the
breach days and alerts removed, the largest early-payment discount that still beats the standing plan (C1 < C0), the
action (call now / offer early pay up to X% / finance the invoice / wait), one sentence in the owner's words, the
ranking by marginal value and by net value, and the cash price curve (what a sum arriving 30 days earlier is worth, by day).
