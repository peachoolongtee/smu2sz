# 04. Technical spikes: the envelope, the portfolio and collections on the real engine

Ticket #43 of wayfinder map #39. Builds on `01-repo-primitives.md` (ticket #40, section 7: the call sequences) and checks
`03-deep-dives.md` (ticket #42, the expected figures). Three scripts under `services/api/scripts/research/` call the
engine read-only on the golden books and print what it says. They change no engine code, are imported by nothing in the
app, run only with `FLOW_RESEARCH_SPIKES=1`, and live on `research/strategy-spikes`, which is never merged into `dev`.
How to run them: `services/api/scripts/research/README.md`.

Base: `origin/dev` at `f636fd6`. The deep dive measured `d1eadb0`; the commits between them touch presentation and
web code, and every engine figure below reproduces, so nothing in the financial path moved. Machine: Apple Silicon,
Python 3.12 under `uv`. Money is formatted by `fmt_yuan` and rates by `fmt_pct` in every table; a figure is an engine
output, or a sum or difference of engine outputs (the script has no other money arithmetic).

"Passes" means the verifier's outcome is ACCEPT or NEEDS_OWNER_APPROVAL, as in the deep dive; a curable RESERVE_BREACH is
not a hard violation, AGG_CONCESSION_EXCEEDED is. The spikes add one reading of their own, stated where it is used.

## Findings in one page

1. **Envelope.** On the golden books Foshan (BUYER-1) can be offered: 45 days alone; 55 days with a price step; early pay
   at 0.85% on ¥257,200 (0.70% on the whole ¥420,000); a rebate up to 1.25%; not 60 days unless an early payment rides
   with it. All nine packages of the deep dive's interaction table reproduce to the fen. What the deep dive did not say:
   the smallest price that passes at 55 days is **0.25%**, not 0.30% (0.30% is the price that nets the cost to zero; the
   ¥5,000 budget can absorb the rest), and with Option A's early payment in the package the verifier passes terms up to
   **80 days** (cure up to ¥4,009.57, flagged "cannot run today"). Bisection agrees with a full scan of the grid.
2. **Portfolio.** Every figure of the deep dive's enumeration reproduces. Best: Option A on EX01 and reject both rebates
   (need ¥149,986.20, funding cost ¥841.57, posted cost ¥3,027.77). The engine's own sequential joint check ends at
   rank 7 of 9 on the three deals (accept EX08A, take no counter): ¥6,113.93 against ¥3,027.77. Pruning removed 7 of 16
   packages (46 of 64 with EX05 and EX06) and changed no result (the unpruned run finds the same 18 feasible portfolios).
3. **Collections.** RCV-A's residual saves ¥1,374.61 and leaves ¥37,200 to cover (as the deep dive), and the two
   invoices that can still arrive before day 42 are each worth ¥1,706.10 gross. Ranked by marginal value they come
   first; ranked net of the early-payment discount they would cost, RCV-A is first and the call is the only action that
   is free. The early-pay ceiling on RI:BUYER-1:2 is **0.80% on ¥200,000** (0.40% on the whole ¥420,000): the deep dive's
   headline "0.40% on ¥200,000" mixes the two faces; its own ¥888.28 and ¥24.20 reproduce exactly.

## 1. Spike 1: the Safe Deal Envelope (`envelope_spike.py`)

### 1.1 Code path

1. `load_scenario()`, `load_signed_mandate()`, `demo_owner_public_key_hex()`, `verifier.evaluate.clear_caches()` (cold start).
2. `whatif.offer.context(state)` on a copy whose recurring invoices are those of the asked buyer (BUYER-2 has none and is
   refused: no terms lever to value). The lever ranges come from `whatif.params` (terms 30 to 90 by 5, price 0 to 1.00%
   by 0.05%, rebate 0 to 2.00%, face in whole ¥100) and the discount is held to `mandate.max_immediate_discount_bp`
   (1.50%). A package outside them is refused before any evaluation (exit status 2).
3. One probe = `WhatIfParams(...)` then `whatif.offer.build(params, ctx)` then `verifier.evaluate(offer, state, mandate,
   trusted_owner_key_hex, plans="committed")`, memoised by lever setting. Inside `evaluate` the engine runs `bind`,
   `project`, `baseline`, the router's `plan`, `marginal_cost`, `value_concessions`, `check_predicates`,
   `induced_breach_days` and `cure_plan`, `_early_pay_vs_plan`, the covenant checks and, on a COUNTER, the counters with
   their `counter_recheck`. The probe keeps the outcome, tier, violation codes, the forward total, the reserve breach (day,
   curable, `cure_cost_fen`, the cure's flags) and the early-pay faces of the verifier's own counters.
4. Searches by bisection on the memo (`last_true` for a ceiling, `first_true` for a floor), each checking the two
   neighbours past the boundary: terms alone; terms with the forward budget ignored (every violation is a cap code or a
   curable reserve breach); the smallest price that passes at each terms value (the 13 x 21 grid, 5 days x 5 bp); the
   largest early-pay discount on each face; the largest rebate.
5. The face "Option A" is not typed in: it is the face of the early-pay counter the verifier returns when asked for the top
   of the discount range (`counter_faces_fen`), ¥257,200. The price that nets an extension's cost to zero is read from
   `bind` + `marginal_cost` + `value_concessions` + `counters.smallest_step_covering` (the Option B rule).
6. Approved packages: for each terms value from the terms in force and each early-pay variant (none, whole invoice at
   its maximum, Option A's face at its maximum), the smallest price that passes, then the largest rebate that still
   passes at that price; the whole package is one evaluation. `counters.infeasibility(verdict, state)` is applied as
   the re-check every counter must pass ("cure too late"); no passing package failed it.
7. `--exhaustive` scans all 273 grid points and compares with the bisection.

### 1.2 Runtime

| Run | Verifier runs | Time |
| --- | --- | --- |
| Lever maxima and the terms x price zone (steps 1 to 5 above) | 51 | 5.4 s |
| The 30 approved packages (smallest price, largest rebate) | 134 | 24.3 s |
| The whole spike, caches cleared | 185 (359 lookups) | 29.7 s (31 s with interpreter start) |
| `--exhaustive` check on top | 242 more | 51 s more (83 s in all) |

The deep dive's 22 evaluations in 1.6 s were the five lever maxima alone, warm. The same five searches plus the 13-row
zone cost 51 evaluations here, cold. A verifier run averages about 160 ms in the whole spike (185 runs in 29.7 s); the ones that carry a breach and a cure cost most.

### 1.3 Output on the golden books

```text
SAFE DEAL ENVELOPE for BUYER-1 on the golden books (day 0), invoice RCV-A, terms in force 45 days. READ-ONLY, hypothetical: nothing is booked or sent.
Levers and their ranges: terms 30-90 days by 5; price 0-1.00% by 0.05%; early pay 0-1.50% (the mandate's immediate-discount cap); rebate 0-2.00%. A lever outside them is refused.

1. Largest value of each lever alone (bisection over the verifier; "passes" = ACCEPT or NEEDS_OWNER_APPROVAL)
Lever                                             Largest that passes  Wall                          Budget used  Neighbours checked  Next step fails with                                                                 
------------------------------------------------  -------------------  ----------------------------  -----------  ------------------  -------------------------------------------------------------------------------------
Terms (days), alone                               45 days              forward budget                ¥0.00        yes                 50d: AGG_CONCESSION_EXCEEDED
Terms (days), budget ignored                      55 days              liquidity (reserve)           ¥16,217.95   yes                 60d: AGG_CONCESSION_EXCEEDED, RESERVE_BREACH (day 47, not curable)
Terms (days), with the price that compensates it  55 days at +0.25%    liquidity (reserve)           ¥2,567.95    yes                 60d +1.00%: RESERVE_BREACH (day 47, not curable)
Early pay on ¥420,000.00                          0.70%                plan comparison / break-even  ¥0.00        yes                 45d 0.75% early: EARLY_PAY_DEARER_THAN_PLAN
Early pay on ¥257,200.00                          0.85%                plan comparison / break-even  ¥0.00        yes                 45d 0.90% early on ¥257,200.00: DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN
Rebate on the expected order                      1.25%                forward budget                ¥5,000.00    yes                 45d 1.30% rebate: AGG_CONCESSION_EXCEEDED

2. Approved packages (terms, price, early payment, rebate; each is one whole verifier evaluation)
#   Terms  Price adj.  Early pay               Rebate  Result  Outcome               Budget used  Cure                                                                                Binding codes                                      
--  -----  ----------  ----------------------  ------  ------  --------------------  -----------  ----------------------------------------------------------------------------------  ---------------------------------------------------
1   45     0.00%       -                       1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥5,000.00    -                                                                                   -
2   45     0.00%       0.70% on whole invoice  1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥5,000.00    -                                                                                   -
3   45     0.00%       0.85% on ¥257,200.00    1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥5,000.00    -                                                                                   -
4   50     0.10%       -                       0.55%   PASS    NEEDS_OWNER_APPROVAL  ¥4,848.97    day 47: ¥1,570.36 (the cure cannot run today)                                       -
5   50     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥1,567.26 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
6   50     0.10%       0.85% on ¥257,200.00    0.55%   PASS    NEEDS_OWNER_APPROVAL  ¥4,848.97    day 47: ¥2,673.04 (the cure cannot run today)                                       -
7   55     0.25%       -                       0.60%   PASS    NEEDS_OWNER_APPROVAL  ¥4,967.95    day 47: ¥1,570.36 (the cure cannot run today)                                       -
8   55     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥1,567.26 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
9   55     0.25%       0.85% on ¥257,200.00    0.60%   PASS    NEEDS_OWNER_APPROVAL  ¥4,967.95    day 47: ¥2,673.04 (the cure cannot run today)                                       -
10  60     1.00%       -                       0.00%   FAIL    REJECT                ¥0.00        day 47: no cure                                                                     RESERVE_BREACH
11  60     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥2,369.24 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
12  60     0.40%       0.85% on ¥257,200.00    0.60%   PASS    NEEDS_OWNER_APPROVAL  ¥4,886.92    day 47: ¥2,673.04 (the cure cannot run today)                                       -
13  65     1.00%       -                       0.00%   FAIL    REJECT                ¥0.00        day 47: no cure                                                                     RESERVE_BREACH
14  65     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥3,553.86 (the cure needs the owner's approval; the cure cannot run today)  EARLY_PAY_DEARER_THAN_PLAN
15  65     0.55%       0.85% on ¥257,200.00    0.60%   PASS    NEEDS_OWNER_APPROVAL  ¥4,805.89    day 47: ¥4,009.57 (the cure needs the owner's approval; the cure cannot run today)  -
16  70     1.00%       -                       0.00%   FAIL    REJECT                ¥0.00        day 47: no cure                                                                     RESERVE_BREACH
17  70     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥3,553.86 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
18  70     0.70%       0.85% on ¥257,200.00    0.65%   PASS    NEEDS_OWNER_APPROVAL  ¥4,924.86    day 47: ¥4,009.57 (the cure cannot run today)                                       -
19  75     1.00%       -                       0.00%   FAIL    REJECT                ¥0.00        day 47: no cure                                                                     RESERVE_BREACH
20  75     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥0.00        day 47: ¥3,553.86 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
21  75     0.80%       0.85% on ¥257,200.00    0.00%   PASS    NEEDS_OWNER_APPROVAL  ¥4,973.84    day 47: ¥4,009.57 (the cure cannot run today)                                       -
22  80     1.00%       -                       0.00%   FAIL    REJECT                ¥2,162.81    day 47: no cure                                                                     RESERVE_BREACH
23  80     1.00%       0.70% on whole invoice  0.00%   FAIL    COUNTER               ¥2,162.81    day 47: ¥3,553.86 (the cure cannot run today)                                       EARLY_PAY_DEARER_THAN_PLAN
24  80     0.95%       0.85% on ¥257,200.00    0.00%   PASS    NEEDS_OWNER_APPROVAL  ¥4,892.81    day 47: ¥4,009.57 (the cure cannot run today)                                       -
25  85     1.00%       -                       0.00%   FAIL    REJECT                ¥10,271.78   day 47: no cure                                                                     AGG_CONCESSION_EXCEEDED, RESERVE_BREACH
26  85     1.00%       0.70% on whole invoice  0.00%   FAIL    REJECT                ¥10,271.78   day 47: ¥3,553.86 (the cure cannot run today)                                       AGG_CONCESSION_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN
27  85     1.00%       0.85% on ¥257,200.00    0.00%   FAIL    REJECT                ¥10,271.78   day 47: ¥4,009.57 (the cure cannot run today)                                       AGG_CONCESSION_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN
28  90     1.00%       -                       0.00%   FAIL    REJECT                ¥18,380.75   day 47: no cure                                                                     AGG_CONCESSION_EXCEEDED, RESERVE_BREACH
29  90     1.00%       0.70% on whole invoice  0.00%   FAIL    REJECT                ¥18,380.75   day 47: ¥4,756.85 (the cure cannot run today)                                       AGG_CONCESSION_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN
30  90     1.00%       0.85% on ¥257,200.00    0.00%   FAIL    REJECT                ¥18,380.75   day 47: ¥4,736.70 (the cure cannot run today)                                       AGG_CONCESSION_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN
   (price = the smallest that passes at that terms value; rebate = the largest that still passes at that price;
    a FAIL row is the verifier's answer at the largest price in range.)

3. Safe zone, terms days x price adjustment (no early payment, no rebate): the smallest price that passes
Terms  Smallest price that passes  Price that nets the cost to zero  Cost per invoice  Outcome there         Budget used  Reserve breach / cure  Binding at the largest price           
-----  --------------------------  --------------------------------  ----------------  --------------------  -----------  ---------------------  ---------------------------------------
30     0.00%                       -                                 -                 NEEDS_OWNER_APPROVAL  ¥0.00        -                      -
35     0.00%                       -                                 -                 NEEDS_OWNER_APPROVAL  ¥0.00        -                      -
40     0.00%                       -                                 -                 NEEDS_OWNER_APPROVAL  ¥0.00        -                      -
45     0.00%                       -                                 -                 ACCEPT                ¥0.00        -                      -
50     0.10%                       0.15%                             ¥623.77           NEEDS_OWNER_APPROVAL  ¥2,648.97    day 47: ¥1,570.36      -
55     0.25%                       0.30%                             ¥1,247.53         NEEDS_OWNER_APPROVAL  ¥2,567.95    day 47: ¥1,570.36      -
60     none in range               0.45%                             ¥1,871.30         REJECT                ¥0.00        day 47: no cure        RESERVE_BREACH
65     none in range               0.60%                             ¥2,495.07         REJECT                ¥0.00        day 47: no cure        RESERVE_BREACH
70     none in range               0.75%                             ¥3,118.84         REJECT                ¥0.00        day 47: no cure        RESERVE_BREACH
75     none in range               0.90%                             ¥3,742.60         REJECT                ¥0.00        day 47: no cure        RESERVE_BREACH
80     none in range               1.05%                             ¥4,366.37         REJECT                ¥2,162.81    day 47: no cure        RESERVE_BREACH
85     none in range               1.20%                             ¥4,990.14         REJECT                ¥10,271.78   day 47: no cure        AGG_CONCESSION_EXCEEDED, RESERVE_BREACH
90     none in range               1.35%                             ¥5,613.90         REJECT                ¥18,380.75   day 47: no cure        AGG_CONCESSION_EXCEEDED, RESERVE_BREACH

Exhaustive check: 242 further evaluations in 52.89 s; bisection agrees with the full scan.
Region, terms x price (# passes, . fails; price 0.00% on the left to 1.00% on the right, 0.05% a column):
   30d  #####################
   35d  #####################
   40d  #####################
   45d  #####################
   50d  ..###################
   55d  .....################
   60d  .....................
   65d  .....................
   70d  .....................
   75d  .....................
   80d  .....................
   85d  .....................
   90d  .....................
  lever searches and the terms x price zone (steps 1 to 4): 51 evaluations, 5.39 s
  approved packages (smallest price, then largest rebate, per terms value and early-pay variant): 134 evaluations, 24.31 s
Evaluations: 185 verifier runs (359 lookups, the rest from the memo); wall time 29.70 s (cold start, caches cleared).
```

The deep dive's interaction table, re-run with `--package` (rates in bp, face in fen):

```text
Packages asked for (--package):
#  Terms  Price adj.  Early pay               Rebate  Result  Outcome               Budget used  Cure                                           Binding codes                                                                 
-  -----  ----------  ----------------------  ------  ------  --------------------  -----------  ---------------------------------------------  ------------------------------------------------------------------------------
1  50     0.00%       -                       1.25%   FAIL    REJECT                ¥13,108.97   day 47: ¥1,570.36 (the cure cannot run today)  AGG_CONCESSION_EXCEEDED
2  55     0.30%       -                       0.00%   PASS    NEEDS_OWNER_APPROVAL  ¥0.00        day 47: ¥1,570.36 (the cure cannot run today)  -
3  55     0.30%       -                       1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥4,837.95    day 47: ¥1,570.36 (the cure cannot run today)  -
4  55     0.30%       -                       1.30%   FAIL    REJECT                ¥5,037.95    day 47: ¥1,570.36 (the cure cannot run today)  AGG_CONCESSION_EXCEEDED
5  55     0.35%       -                       1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥2,107.95    day 47: ¥1,570.36 (the cure cannot run today)  -
6  55     0.30%       0.85% on ¥257,200.00    0.00%   PASS    NEEDS_OWNER_APPROVAL  ¥0.00        day 47: ¥2,673.04 (the cure cannot run today)  -
7  45     0.00%       0.85% on ¥257,200.00    1.25%   PASS    NEEDS_OWNER_APPROVAL  ¥5,000.00    -                                              -
8  60     0.45%       0.85% on ¥257,200.00    0.00%   PASS    NEEDS_OWNER_APPROVAL  ¥0.00        day 47: ¥2,673.04 (the cure cannot run today)  -
9  60     0.00%       1.20% on whole invoice  1.00%   FAIL    REJECT                ¥28,326.92   day 47: ¥2,406.67 (the cure cannot run today)  AGG_CONCESSION_EXCEEDED, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN
```

### 1.4 Agreement with `03-deep-dives.md`

Reproduced exactly:

| Figure in 03 | Spike |
| --- | --- |
| Terms alone 45 days; +5 days is ¥8,108.97 over 13 invoices against ¥5,000 | 45 days; the 50-day step books ¥8,108.97 (AGG_CONCESSION_EXCEEDED) |
| Budget ignored: 55 days, cure ¥1,570.36 on day 47; 60 days has no cure | 55 days; ¥1,570.36; 60 days: RESERVE_BREACH not curable; ¥24,326.92 forward at 60 |
| Price that covers the cost: 50 to 0.15%, 55 to 0.30%, 60 to 0.45%; per invoice ¥623.77, ¥1,247.53, ¥1,871.30 | same, in the "Price that nets the cost to zero" column |
| 60 days: no price fixes it | no price up to 1.00% passes at 60 days or beyond |
| Early pay, whole ¥420,000: 0.70%; 0.75% is EARLY_PAY_DEARER_THAN_PLAN | same |
| Early pay on ¥257,200: 0.85%; 0.90% fails DISCOUNT_ABOVE_BREAK_EVEN | same |
| Rebate 1.25% (exactly ¥5,000); 1.30% is ¥5,200 and fails AGG | same |
| The nine packages of the interaction table, forward totals and cures (¥13,108.97, ¥0, ¥4,837.95, ¥5,037.95, ¥2,107.95, ¥0 with cure ¥2,673.04, ¥5,000, ¥0 with cure ¥2,673.04, ¥28,326.92 with cure ¥2,406.67) | all nine reproduce, with the same outcomes |

Differing or new figures (every one named):

| Item | 03 says | Spike says | Why |
| --- | --- | --- | --- |
| Smallest price that makes 55 days pass | 0.30% ("55 days at 0.30%") | **0.25%** (forward value ¥2,567.95 of the ¥5,000); 50 days passes at **0.10%** (not 0.15%) | 0.30% and 0.15% are the Option B rule: the price that nets the extension's cost to zero. The verifier passes a smaller price because the budget can absorb the remainder. 0.30% remains the counter FLOW would send; 0.25% is the floor of the zone |
| 60 days with Option A's early payment | passes at 0.45% | passes from **0.40%** (budget ¥4,886.92, rebate up to 0.60%) | same reason; 0.45% nets the cost to zero |
| Reserve breach day at 60 days without an early payment | "max shortfall ¥130,000 on day 60" | the verifier's violation is on **day 47**, not curable | the verifier reports the first induced breach day; 01 section 7.1 also says day 47. The ¥130,000 is the deepest shortfall, which the spike does not print |
| Longest terms with a package | 60 days (with 0.45% and Option A) | passes up to **80 days** (75 days at 0.80%, 80 days at 0.95%, each with 0.85% on ¥257,200 and no rebate); the cure grows to ¥4,009.57 and at 65 days needs the owner's approval; every cure "cannot run today" (it advances on an invoice not yet issued) | the deep dive tested 60 days only. 85 days fails AGG (forward ¥10,271.78) |
| Whole-invoice early pay together with an extension | not tested | at its standalone maximum (0.70%) it **never passes** with 50 days or more, at any price up to 1.00% (EARLY_PAY_DEARER_THAN_PLAN) | a smaller whole-face rate was not tried inside a package (see 1.5) |
| Evaluations / time | 22 evaluations, 1.6 s warm | 51 (levers and zone) or 185 (with packages), 5.4 s or 29.7 s cold | wider scope and cold caches, see 1.2 |

Bisection is sound here: the full scan of the 13 x 21 grid and of the terms column found, for every row, the passing
prices to be one run from the bisected minimum up, and the terms to be one run from the terms in force up to the
bisected maximum. The deep dive and 01 asked for that check; it holds on this fixture only.

### 1.5 What the spike could not do

- It answers for BUYER-1 on the day-0 books. BUYER-2 has no recurring invoice and no open invoice: the spike refuses it,
  as the what-if builder would. Day-34 books and live commitments are not read (the builder takes none).
- It cannot say whether the buyer accepts, or what volume or margin a concession buys; "approved" means the verifier and
  the counters' own re-check say yes, not that the deal is good.
- A passing package may rely on a cure the agent cannot run today (an advance on an invoice not yet issued, flagged in
  the Cure column) or that needs the owner's approval (from 65 days). The spike prints the flags and does not downgrade
  the package.
- The early-pay variants use each face's standalone maximum rate; the best rate inside a combined package is not searched.
  A smaller rate might pass where the standalone maximum fails, so the failing whole-invoice rows (5, 8, 11 and on) say
  "0.70% fails", not "no whole-invoice early payment can ride with an extension".
- Price and rebate trade off along a curve (a higher price buys a larger rebate); a package is reported at the smallest
  price, with the largest rebate at that price, not along the whole curve.
- The trade-credit exposure (¥140,000 at 55 days), the pro-forma DSCR and leverage at 60 days, and the shortfall
  amounts of the deep dive's table 1.1 are not printed; **not checked**.
- Bisection assumes monotone levers; it was verified by full scan here, and nothing in the engine guarantees it elsewhere.

## 2. Spike 2: the multi-deal portfolio (`portfolio_spike.py`)

### 2.1 Code path

1. `load_scenario()`, `load_signed_mandate()`, `current_books(state, ())`, `marginal_cost(state, mandate)`. Offer names resolve
   to the fixture ids (`EX01` is `EX01_PACKAGE`).
2. Per offer: `offer_documents(id)`, `compile_offer(docs, counterparty)` (cached compiler output), then
   `verifier.evaluate(offer, state, mandate, owner_declared=declared_costs, plans="committed")`. The candidates are: reject; each
   counter in `verdict.counters`, re-checked alone with `counter_recheck(...)(counter)`; "as asked" (`bound_obligations`).
3. Per candidate: `value_concessions(obligations, state, rate, label, H)` and `verifier.evaluate._forward_total`
   (the verifier's own netting, floored at zero per package, as a commitment books it; a private function, imported
   for exactness), and `project(...)` with and without it to learn whether it moves cash inside the horizon.
4. Pruning, in this order: a candidate the verifier will not accept alone (any violation code other than the cap codes
   and RESERVE_BREACH, which the joint checks re-test) is dropped before the enumeration; a depth-first walk over the
   deals cuts a partial choice as soon as its forward value exceeds the aggregate cap or a per-buyer cap (every package
   adds at least zero, so nothing below can fit: budget monotonicity); the router is called once per distinct set of
   cash-moving packages, because a package whose projection equals the status quo's (a rebate, an operational
   concession) interacts with the others through the caps alone (buyer separability).
5. Per surviving combination: `funding.plan(state, books.with_(chosen), mandate)` (admissible or the combination is out)
   and `project(state, obligations, plan.actions)` for the posted cost (interest + fees + discounts).
6. Ranking, lexicographic: feasible (no cap breach, an admissible plan, no conflict) as the filter; then the number of
   owner decisions the portfolio needs (packages whose own verdict is not Tier 1 plus plan legs flagged
   `needs_owner_approval`); then the posted cost plus the packages' forward value at the marginal rate. The "binding"
   column asks what blocks the next step up: each deal moved to a package that grants more of the ask, one deal at a time,
   and the reason that portfolio fails.
7. For comparison, `evaluate_many(offers as asked, in order)`, and where the portfolio it yields stands in the ranking.
   `--no-prune` enumerates every package, to check that nothing pruned was feasible.

### 2.2 Runtime

| Run | Packages | Evaluated | Router calls | Time |
| --- | --- | --- | --- | --- |
| EX01, EX08A, EX08B (default) | 16 | 9 | 3 | 0.52 s (candidates 0.42 s, enumeration 0.09 s); 1.9 s with interpreter start |
| EX01, EX02, EX04, EX06 (the ticket's list) | 72 | 12 | 12 | 0.70 s |
| EX01, EX08A, EX08B, EX05, EX06 | 64 | 18 | 6 | 0.79 s; 2.5 s with start |
| the same, `--no-prune` | 64 | 64 | 16 | 1.00 s |

The deep dive measured 16 packages in 0.43 s and 64 in 1.63 s with one `plan()` per package; here the router runs once per
distinct set of cash-moving packages, and the verifier evaluation of every candidate is included in the totals.

### 2.3 Output on the golden books

Default: EX01, EX08A, EX08B.

```text
PORTFOLIO of EX01, EX08A, EX08B on the golden books (day 0). READ-ONLY, hypothetical.
Forward budget ¥5,000.00; already booked ¥0.00; concessions valued at the committed marginal source FAC-IF rate.

Candidates per deal (alone = the verifier on that package by itself):
Deal   Package   Alone                    Codes alone                                                                                     Forward value  Moves cash  Enumerated
-----  --------  -----------------------  ----------------------------------------------------------------------------------------------  -------------  ----------  ----------
EX01   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX01   Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX01   Option B  NEEDS_OWNER_APPROVAL     RESERVE_BREACH                                                                                  ¥0.00          yes         yes
EX01   as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN  ¥28,326.92     yes         DROPPED
EX08A  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08A  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥3,000.00      no          yes
EX08B  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08B  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥2,500.00      no          yes

Ranked feasible portfolios (9 of 9): no hard breach, then owner decisions needed, then posted cost + concession value

#  Portfolio                                         Need         Funding cost  Posted cost  Concessions  Cost + concessions  Budget use              Owner decisions  Binding: what blocks the next step up                                                       
-  ------------------------------------------------  -----------  ------------  -----------  -----------  ------------------  ----------------------  ---------------  --------------------------------------------------------------------------------------------
1  EX01: Option A | EX08A: reject | EX08B: reject    ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00      0                EX01 as asked -> forward budget (and not acceptable alone)
2  EX01: reject | EX08A: reject | EX08B: reject      ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥0.00        ¥3,113.93           ¥0.00 of ¥5,000.00      0                EX01 as asked -> forward budget (and not acceptable alone)
3  EX01: Option B | EX08A: reject | EX08B: reject    ¥405,000.00  ¥3,706.46     ¥3,706.46    ¥0.00        ¥3,706.46           ¥0.00 of ¥5,000.00      1                EX01 as asked -> forward budget (and not acceptable alone)
4  EX01: Option A | EX08A: reject | EX08B: as asked  ¥149,986.20  ¥841.57       ¥3,027.77    ¥2,500.00    ¥5,527.77           ¥2,500.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08A as asked -> forward budget
5  EX01: reject | EX08A: reject | EX08B: as asked    ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥2,500.00    ¥5,613.93           ¥2,500.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08A as asked -> forward budget
6  EX01: Option A | EX08A: as asked | EX08B: reject  ¥149,986.20  ¥841.57       ¥3,027.77    ¥3,000.00    ¥6,027.77           ¥3,000.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08B as asked -> forward budget
7  EX01: reject | EX08A: as asked | EX08B: reject    ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥3,000.00    ¥6,113.93           ¥3,000.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08B as asked -> forward budget
8  EX01: Option B | EX08A: reject | EX08B: as asked  ¥405,000.00  ¥3,706.46     ¥3,706.46    ¥2,500.00    ¥6,206.46           ¥2,500.00 of ¥5,000.00  2                EX01 as asked -> forward budget (and not acceptable alone); EX08A as asked -> forward budget
9  EX01: Option B | EX08A: as asked | EX08B: reject  ¥405,000.00  ¥3,706.46     ¥3,706.46    ¥3,000.00    ¥6,706.46           ¥3,000.00 of ¥5,000.00  2                EX01 as asked -> forward budget (and not acceptable alone); EX08B as asked -> forward budget

Packages that are not in the ranked table, by reason:
Reason                                                                                                                                                              Packages
------------------------------------------------------------------------------------------------------------------------------------------------------------------  --------
dropped before enumeration: EX01 as asked is not acceptable alone (AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN)  4
cut before evaluation: forward budget                                                                                                                               3

Evaluated and infeasible:
Portfolio  Need  Funding cost  Budget use  Why not
---------  ----  ------------  ----------  -------

For comparison, the engine's own sequential joint check (evaluate_many, offers as asked, in this order): EX01 REJECT; EX08A NEEDS_OWNER_APPROVAL; EX08B COUNTER.
The portfolio it yields (accept what passes, take no counter) is EX01: reject, EX08A: as asked, EX08B: reject; it is #7 of 9 at ¥6,113.93 against ¥3,027.77 for #1.

Packages: 16 in all (4 x 2 x 2). Pruning removed 7: 4 by dropping 1 package(s) the verifier will not accept alone, 3 by the budget cut. Evaluated 9 (9 feasible, 0 not); the router ran 3 times (6 calls saved because the other packages do not move cash).
Wall time 0.52 s: candidates 0.42 s, enumeration and ranking 0.09 s.
```

With EX05 and EX06 added (top 8 of 18):

```text
PORTFOLIO of EX01, EX08A, EX08B, EX05, EX06 on the golden books (day 0). READ-ONLY, hypothetical.
Forward budget ¥5,000.00; already booked ¥0.00; concessions valued at the committed marginal source FAC-IF rate.

Candidates per deal (alone = the verifier on that package by itself):
Deal   Package   Alone                    Codes alone                                                                                     Forward value  Moves cash  Enumerated
-----  --------  -----------------------  ----------------------------------------------------------------------------------------------  -------------  ----------  ----------
EX01   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX01   Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX01   Option B  NEEDS_OWNER_APPROVAL     RESERVE_BREACH                                                                                  ¥0.00          yes         yes
EX01   as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN  ¥28,326.92     yes         DROPPED
EX08A  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08A  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥3,000.00      no          yes
EX08B  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08B  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥2,500.00      no          yes
EX05   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX05   as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥0.00          yes         yes
EX06   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX06   as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH                                                         ¥5,613.90      yes         yes

Ranked feasible portfolios (8 of 18): no hard breach, then owner decisions needed, then posted cost + concession value

#  Portfolio                                                                       Need         Funding cost  Posted cost  Concessions  Cost + concessions  Budget use              Owner decisions  Binding: what blocks the next step up                                                                      
-  ------------------------------------------------------------------------------  -----------  ------------  -----------  -----------  ------------------  ----------------------  ---------------  -----------------------------------------------------------------------------------------------------------
1  EX01: Option A | EX08A: reject | EX08B: reject | EX05: reject | EX06: reject    ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00      0                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget
2  EX01: reject | EX08A: reject | EX08B: reject | EX05: reject | EX06: reject      ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥0.00        ¥3,113.93           ¥0.00 of ¥5,000.00      0                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget
3  EX01: Option A | EX08A: reject | EX08B: reject | EX05: as asked | EX06: reject  ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00      1                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget
4  EX01: reject | EX08A: reject | EX08B: reject | EX05: as asked | EX06: reject    ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥0.00        ¥3,113.93           ¥0.00 of ¥5,000.00      1                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget
5  EX01: Option B | EX08A: reject | EX08B: reject | EX05: reject | EX06: reject    ¥405,000.00  ¥3,706.46     ¥3,706.46    ¥0.00        ¥3,706.46           ¥0.00 of ¥5,000.00      1                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget
6  EX01: Option A | EX08A: reject | EX08B: as asked | EX05: reject | EX06: reject  ¥149,986.20  ¥841.57       ¥3,027.77    ¥2,500.00    ¥5,527.77           ¥2,500.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08A as asked, EX06 as asked -> forward budget
7  EX01: reject | EX08A: reject | EX08B: as asked | EX05: reject | EX06: reject    ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥2,500.00    ¥5,613.93           ¥2,500.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08A as asked, EX06 as asked -> forward budget
8  EX01: Option A | EX08A: as asked | EX08B: reject | EX05: reject | EX06: reject  ¥149,986.20  ¥841.57       ¥3,027.77    ¥3,000.00    ¥6,027.77           ¥3,000.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX08B as asked, EX06 as asked -> forward budget

Packages that are not in the ranked table, by reason:
Reason                                                                                                                                                              Packages
------------------------------------------------------------------------------------------------------------------------------------------------------------------  --------
cut before evaluation: forward budget                                                                                                                               30
dropped before enumeration: EX01 as asked is not acceptable alone (AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN)  16

For comparison, the engine's own sequential joint check (evaluate_many, offers as asked, in this order): EX01 REJECT; EX08A NEEDS_OWNER_APPROVAL; EX08B COUNTER; EX05 NEEDS_OWNER_APPROVAL; EX06 REJECT.
The portfolio it yields (accept what passes, take no counter) is EX01: reject, EX08A: as asked, EX08B: reject, EX05: as asked, EX06: reject; it is #14 of 18 at ¥6,113.93 against ¥3,027.77 for #1.

Packages: 64 in all (4 x 2 x 2 x 2 x 2). Pruning removed 46: 16 by dropping 1 package(s) the verifier will not accept alone, 30 by the budget cut. Evaluated 18 (18 feasible, 0 not); the router ran 6 times (12 calls saved because the other packages do not move cash).
Wall time 0.79 s: candidates 0.61 s, enumeration and ranking 0.16 s.
```

The packages the pruned run never evaluates, re-run with `--no-prune --show-infeasible` (the same five deals): their needs and
costs, which the deep dive quotes for some of them. The 18 feasible portfolios are the same as in the pruned run.

```text
PORTFOLIO of EX01, EX08A, EX08B, EX05, EX06 on the golden books (day 0). READ-ONLY, hypothetical.
Forward budget ¥5,000.00; already booked ¥0.00; concessions valued at the committed marginal source FAC-IF rate.

Candidates per deal (alone = the verifier on that package by itself):
Deal   Package   Alone                    Codes alone                                                                                     Forward value  Moves cash  Enumerated
-----  --------  -----------------------  ----------------------------------------------------------------------------------------------  -------------  ----------  ----------
EX01   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX01   Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX01   Option B  NEEDS_OWNER_APPROVAL     RESERVE_BREACH                                                                                  ¥0.00          yes         yes
EX01   as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN  ¥28,326.92     yes         DROPPED
EX08A  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08A  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥3,000.00      no          yes
EX08B  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX08B  as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥2,500.00      no          yes
EX05   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX05   as asked  NEEDS_OWNER_APPROVAL     -                                                                                               ¥0.00          yes         yes
EX06   reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX06   as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH                                                         ¥5,613.90      yes         yes

Ranked feasible portfolios (1 of 18): no hard breach, then owner decisions needed, then posted cost + concession value

#  Portfolio                                                                     Need         Funding cost  Posted cost  Concessions  Cost + concessions  Budget use          Owner decisions  Binding: what blocks the next step up                                                      
-  ----------------------------------------------------------------------------  -----------  ------------  -----------  -----------  ------------------  ------------------  ---------------  -------------------------------------------------------------------------------------------
1  EX01: Option A | EX08A: reject | EX08B: reject | EX05: reject | EX06: reject  ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00  0                EX01 as asked -> forward budget (and not acceptable alone); EX06 as asked -> forward budget

Packages that are not in the ranked table, by reason:
Reason                                     Packages
-----------------------------------------  --------
forward budget                             30
forward budget (and not acceptable alone)  16

Evaluated and infeasible:
Portfolio                                                                             Need         Funding cost  Budget use  Why not                                  
------------------------------------------------------------------------------------  -----------  ------------  ----------  -----------------------------------------
EX01: Option A | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: reject    ¥149,986.20  ¥841.57       ¥5,500.00   forward budget
EX01: Option A | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: reject      ¥149,986.20  ¥841.57       ¥5,500.00   forward budget
EX01: Option B | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: reject    ¥405,000.00  ¥3,113.93     ¥5,500.00   forward budget
EX01: reject | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: reject      ¥405,000.00  ¥3,113.93     ¥5,500.00   forward budget
EX01: reject | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: reject        ¥405,000.00  ¥3,113.93     ¥5,500.00   forward budget
EX01: Option A | EX08A: reject | EX08B: reject | EX05: as asked | EX06: as asked      ¥149,986.20  ¥841.57       ¥5,613.90   forward budget
EX01: reject | EX08A: reject | EX08B: reject | EX05: as asked | EX06: as asked        ¥405,000.00  ¥3,113.93     ¥5,613.90   forward budget
EX01: Option B | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: reject      ¥405,000.00  ¥3,706.46     ¥5,500.00   forward budget
EX01: Option B | EX08A: reject | EX08B: reject | EX05: as asked | EX06: as asked      ¥405,000.00  ¥3,706.46     ¥5,613.90   forward budget
EX01: Option A | EX08A: reject | EX08B: reject | EX05: reject | EX06: as asked        ¥149,986.20  ¥1,630.53     ¥5,613.90   forward budget
EX01: reject | EX08A: reject | EX08B: reject | EX05: reject | EX06: as asked          ¥405,000.00  ¥3,873.58     ¥5,613.90   forward budget
EX01: Option B | EX08A: reject | EX08B: reject | EX05: reject | EX06: as asked        ¥405,000.00  ¥4,110.29     ¥5,613.90   forward budget
EX01: Option A | EX08A: reject | EX08B: as asked | EX05: as asked | EX06: as asked    ¥149,986.20  ¥841.57       ¥8,113.90   forward budget
EX01: reject | EX08A: reject | EX08B: as asked | EX05: as asked | EX06: as asked      ¥405,000.00  ¥3,113.93     ¥8,113.90   forward budget
EX01: Option A | EX08A: as asked | EX08B: reject | EX05: as asked | EX06: as asked    ¥149,986.20  ¥841.57       ¥8,613.90   forward budget
EX01: reject | EX08A: as asked | EX08B: reject | EX05: as asked | EX06: as asked      ¥405,000.00  ¥3,113.93     ¥8,613.90   forward budget
EX01: Option B | EX08A: reject | EX08B: as asked | EX05: as asked | EX06: as asked    ¥405,000.00  ¥3,706.46     ¥8,113.90   forward budget
EX01: Option A | EX08A: reject | EX08B: as asked | EX05: reject | EX06: as asked      ¥149,986.20  ¥1,630.53     ¥8,113.90   forward budget
EX01: reject | EX08A: reject | EX08B: as asked | EX05: reject | EX06: as asked        ¥405,000.00  ¥3,873.58     ¥8,113.90   forward budget
EX01: Option B | EX08A: reject | EX08B: as asked | EX05: reject | EX06: as asked      ¥405,000.00  ¥4,110.29     ¥8,113.90   forward budget
EX01: Option B | EX08A: as asked | EX08B: reject | EX05: as asked | EX06: as asked    ¥405,000.00  ¥3,706.46     ¥8,613.90   forward budget
EX01: Option A | EX08A: as asked | EX08B: reject | EX05: reject | EX06: as asked      ¥149,986.20  ¥1,630.53     ¥8,613.90   forward budget
EX01: reject | EX08A: as asked | EX08B: reject | EX05: reject | EX06: as asked        ¥405,000.00  ¥3,873.58     ¥8,613.90   forward budget
EX01: Option B | EX08A: as asked | EX08B: reject | EX05: reject | EX06: as asked      ¥405,000.00  ¥4,110.29     ¥8,613.90   forward budget
EX01: Option A | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: as asked  ¥149,986.20  ¥841.57       ¥11,113.90  forward budget
EX01: reject | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: as asked    ¥405,000.00  ¥3,113.93     ¥11,113.90  forward budget
EX01: Option B | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: as asked  ¥405,000.00  ¥3,706.46     ¥11,113.90  forward budget
EX01: Option A | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: as asked    ¥149,986.20  ¥1,630.53     ¥11,113.90  forward budget
EX01: reject | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: as asked      ¥405,000.00  ¥3,873.58     ¥11,113.90  forward budget
EX01: Option B | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: as asked    ¥405,000.00  ¥4,110.29     ¥11,113.90  forward budget
EX01: as asked | EX08A: reject | EX08B: reject | EX05: as asked | EX06: reject        -            -             -           forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: reject | EX05: reject | EX06: reject          ¥135,040.00  ¥1,468.05     ¥28,326.92  forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: as asked | EX05: as asked | EX06: reject      -            -             -           forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: reject | EX05: as asked | EX06: reject      -            -             -           forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: as asked | EX05: reject | EX06: reject        ¥135,040.00  ¥1,468.05     ¥30,826.92  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: reject | EX05: reject | EX06: reject        ¥135,040.00  ¥1,468.05     ¥31,326.92  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: reject    -            -             -           forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: reject      ¥135,040.00  ¥1,468.05     ¥33,826.92  forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: reject | EX05: as asked | EX06: as asked      ¥135,040.00  ¥1,468.05     ¥33,940.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: reject | EX05: reject | EX06: as asked        ¥135,040.00  ¥1,823.22     ¥33,940.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: as asked | EX05: as asked | EX06: as asked    ¥135,040.00  ¥1,468.05     ¥36,440.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: reject | EX08B: as asked | EX05: reject | EX06: as asked      ¥135,040.00  ¥1,823.22     ¥36,440.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: reject | EX05: as asked | EX06: as asked    ¥135,040.00  ¥1,468.05     ¥36,940.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: reject | EX05: reject | EX06: as asked      ¥135,040.00  ¥1,823.22     ¥36,940.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: as asked | EX05: as asked | EX06: as asked  ¥135,040.00  ¥1,468.05     ¥39,440.82  forward budget (and not acceptable alone)
EX01: as asked | EX08A: as asked | EX08B: as asked | EX05: reject | EX06: as asked    ¥135,040.00  ¥1,823.22     ¥39,440.82  forward budget (and not acceptable alone)

For comparison, the engine's own sequential joint check (evaluate_many, offers as asked, in this order): EX01 REJECT; EX08A NEEDS_OWNER_APPROVAL; EX08B COUNTER; EX05 NEEDS_OWNER_APPROVAL; EX06 REJECT.
The portfolio it yields (accept what passes, take no counter) is EX01: reject, EX08A: as asked, EX08B: reject, EX05: as asked, EX06: reject; it is #14 of 18 at ¥6,113.93 against ¥3,027.77 for #1.

Packages: 64 in all (4 x 2 x 2 x 2 x 2). No pruning (--no-prune): every package was evaluated. Evaluated 64 (18 feasible, 46 not); the router ran 16 times (2 calls saved because the other packages do not move cash).
Wall time 1.00 s: candidates 0.61 s, enumeration and ranking 0.36 s.
```

The ticket's own list of fixtures (EX01, EX02, EX04, EX06; EX01B is a reworded EX01). EX02's and EX04's counters are the same
early-payment promise on RCV-A that EX01's Option A is, so two of them at once are one invoice settled twice: the engine
refuses the pair (`ObligationError`) and the spike reports a conflict, the first, second and third rows being the
same promise from three different offers.

```text
PORTFOLIO of EX01, EX02, EX04, EX06 on the golden books (day 0). READ-ONLY, hypothetical.
Forward budget ¥5,000.00; already booked ¥0.00; concessions valued at the committed marginal source FAC-IF rate.

Candidates per deal (alone = the verifier on that package by itself):
Deal  Package   Alone                    Codes alone                                                                                     Forward value  Moves cash  Enumerated
----  --------  -----------------------  ----------------------------------------------------------------------------------------------  -------------  ----------  ----------
EX01  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX01  Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX01  Option B  NEEDS_OWNER_APPROVAL     RESERVE_BREACH                                                                                  ¥0.00          yes         yes
EX01  as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN  ¥28,326.92     yes         DROPPED
EX02  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX02  Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX02  as asked  COUNTER                  DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN                         ¥0.00          yes         DROPPED
EX04  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX04  Option A  ACCEPT                   -                                                                                               ¥0.00          yes         yes
EX04  as asked  REJECT                   UNEVIDENCED_PRIOR_CONCESSION                                                                    ¥0.00          no          DROPPED
EX06  reject    REJECT (nothing booked)  -                                                                                               ¥0.00          no          yes
EX06  as asked  REJECT                   AGG_CONCESSION_EXCEEDED, RESERVE_BREACH                                                         ¥5,613.90      yes         yes

Ranked feasible portfolios (6 of 7): no hard breach, then owner decisions needed, then posted cost + concession value

#  Portfolio                                                      Need         Funding cost  Posted cost  Concessions  Cost + concessions  Budget use          Owner decisions  Binding: what blocks the next step up                                                                                                                                                                                                                                                                                                                                                                           
-  -------------------------------------------------------------  -----------  ------------  -----------  -----------  ------------------  ------------------  ---------------  ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
1  EX01: Option A | EX02: reject | EX04: reject | EX06: reject    ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00  0                EX01 as asked -> forward budget (and not acceptable alone); EX02 Option A, EX04 Option A -> CONFLICT (ObligationError: two packages cannot both be booked); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget
2  EX01: reject | EX02: Option A | EX04: reject | EX06: reject    ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00  0                EX01 Option A, EX04 Option A -> CONFLICT (ObligationError: two packages cannot both be booked); EX01 as asked -> forward budget (and not acceptable alone); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget
3  EX01: reject | EX02: reject | EX04: Option A | EX06: reject    ¥149,986.20  ¥841.57       ¥3,027.77    ¥0.00        ¥3,027.77           ¥0.00 of ¥5,000.00  0                EX01 Option A, EX02 Option A -> CONFLICT (ObligationError: two packages cannot both be booked); EX01 as asked -> forward budget (and not acceptable alone); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget
4  EX01: reject | EX02: reject | EX04: reject | EX06: reject      ¥405,000.00  ¥3,113.93     ¥3,113.93    ¥0.00        ¥3,113.93           ¥0.00 of ¥5,000.00  0                EX01 as asked -> forward budget (and not acceptable alone); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget
5  EX01: Option B | EX02: Option A | EX04: reject | EX06: reject  ¥149,986.20  ¥1,499.04     ¥3,685.24    ¥0.00        ¥3,685.24           ¥0.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 Option A -> CONFLICT (ObligationError: two packages cannot both be booked); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget
6  EX01: Option B | EX02: reject | EX04: Option A | EX06: reject  ¥149,986.20  ¥1,499.04     ¥3,685.24    ¥0.00        ¥3,685.24           ¥0.00 of ¥5,000.00  1                EX01 as asked -> forward budget (and not acceptable alone); EX02 Option A -> CONFLICT (ObligationError: two packages cannot both be booked); EX02 as asked -> not acceptable alone: EX02 as asked (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN); EX04 as asked -> not acceptable alone: EX04 as asked (UNEVIDENCED_PRIOR_CONCESSION); EX06 as asked -> forward budget

Packages that are not in the ranked table, by reason:
Reason                                                                                                                                                              Packages
------------------------------------------------------------------------------------------------------------------------------------------------------------------  --------
dropped before enumeration: EX02 as asked is not acceptable alone (DISCOUNT_ABOVE_BREAK_EVEN, MAX_APR_EXCEEDED, EARLY_PAY_DEARER_THAN_PLAN)                         24
dropped before enumeration: EX04 as asked is not acceptable alone (UNEVIDENCED_PRIOR_CONCESSION)                                                                    24
dropped before enumeration: EX01 as asked is not acceptable alone (AGG_CONCESSION_EXCEEDED, RESERVE_BREACH, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN)  18
cut before evaluation: forward budget                                                                                                                               12
CONFLICT (ObligationError: two packages cannot both be booked)                                                                                                      5

For comparison, the engine's own sequential joint check (evaluate_many, offers as asked, in this order): EX01 REJECT; EX02 COUNTER; EX04 REJECT; EX06 REJECT.
The portfolio it yields (accept what passes, take no counter) is EX01: reject, EX02: reject, EX04: reject, EX06: reject; it is #4 of 7 at ¥3,113.93 against ¥3,027.77 for #1.

Packages: 72 in all (4 x 3 x 3 x 2). Pruning removed 60: 48 by dropping 3 package(s) the verifier will not accept alone, 12 by the budget cut. Evaluated 12 (7 feasible, 5 not); the router ran 12 times (0 calls saved because the other packages do not move cash).
Wall time 0.70 s: candidates 0.56 s, enumeration and ranking 0.12 s.
```

### 2.4 Agreement with `03-deep-dives.md`

Reproduced exactly: sixteen packages for EX01, EX08A, EX08B and sixty-four with EX05 and EX06; "Option A, reject, reject" is the
best at need ¥149,986.20 and funding cost ¥841.57 with ¥0 of budget; the status quo needs ¥405,000 at ¥3,113.93; Option B costs
¥3,706.46; Option A with both rebates uses ¥5,500 against ¥5,000 and is infeasible; accepting EX01 as asked needs
¥135,040 at ¥1,468.05; EX06 raises the cost of the standing need from ¥3,873.58 to ¥1,630.53 under Option A and stays over
the budget at ¥5,613.90; rebates and the operational concession change neither the need nor the cost (so the budget is the
only binding constraint for them).

Differing or new:

| Item | 03 says | Spike says |
| --- | --- | --- |
| Cost column | funding cost, ¥841.57 | both are printed: funding cost ¥841.57 and the posted cost ¥3,027.77 (interest + fees + the early-pay discount ¥2,186.20); ranked by posted cost plus concession value. Same order at the top, but the spike's ranking charges a rebate at its maximum, so rank 4 onward is "fewest concessions first", not value |
| "Accept EX01, any" | infeasible on the budget (≥ ¥28,326.92) | also not acceptable alone: the verifier returns REJECT with DISCOUNT_ABOVE_BREAK_EVEN and EARLY_PAY_DEARER_THAN_PLAN besides AGG and RESERVE_BREACH, so the spike drops it before enumerating; the two ways of counting agree on the result |
| The greedy order | "answers greedily in input order today" | measured: on EX01, EX08A, EX08B it yields "accept EX08A as asked, reject the rest" (EX01 REJECT, EX08A NEEDS_OWNER_APPROVAL, EX08B COUNTER), rank **7 of 9** at ¥6,113.93 against ¥3,027.77 for the best; with five deals rank 14 of 18 at the same cost. It takes no counter, by design, so the comparison is between the engine's sequential path and the enumeration, not between two searches |
| Time | 0.43 s and 1.63 s | 0.52 s and 0.79 s (1.00 s unpruned), with the verifier evaluations included |

The deep dive's kill criterion ("the greedy `evaluate_many` order picks the same packages as the enumeration in every
case that occurs") fails on the first fixture set: the enumeration finds Option A, which the sequential check never
proposes.

### 2.5 What the spike could not do

- No contribution, margin or customer value exists in the engine, so the ranking cannot say whether EX08A is worth more
  than EX08B; the budget decides between them by the posted cost alone and the rebate counts at its maximum. The spike
  confirms the deep dive's statement that the engine cannot rank a budget knapsack.
- The candidate set is the verifier's: as asked, its counters and reject. Alternatives from the lever grid, delays and
  conditional acceptance are not generated.
- The joint check is the caps plus the router's `plan()` (admissibility and posted cost), not a full re-evaluation of each
  deal on books that carry the others. The deep dive proposes `evaluate` on the shortlist; the spike prints the sequential
  `evaluate_many` outcomes instead.
- Per-buyer caps are implemented but untested: the golden mandate has none. Two packages that settle the same invoice are
  caught only as an engine error and reported as a conflict (five of the 72 packages of EX01, EX02, EX04, EX06); no
  exclusivity rule is modelled beyond that.
- "Owner decisions" and "binding" are definitions of the spike, not engine concepts (stated in 2.1).
- EX01B was not run: it is EX01 reworded (`expect: same_as EX01_PACKAGE`). EX03 and the other fixtures were not run; the
  script takes any fixture id.

## 3. Spike 3: collections prioritisation (`collections_spike.py`)

### 3.1 Code path

1. Day-0 books: `load_scenario()`, `load_signed_mandate()` in an `InMemoryLedgerStore` (for `alerts()`).
2. Day-34 books: the demo path replayed **in process** with a `TestClient` over the real app and an in-memory runtime, as
   `scripts/demo_run.py` does and with the steps of `tests/alerts/test_repay_alert.py::to_day34`: EX01 evaluated, Option A
   agreed (`POST /negotiate`), the clock to day 2, the agreed receipt of ¥255,013.80 by the bank feed, the clock to day 30
   and 34. The tests are not imported. The month-2 payroll of ¥200,000 on day 42 comes with the scenario events
   (`golden_sme.events.json`) when the clock advances; nothing is added by hand.
3. Per set of books: `current_books`, `funding.plan(state, obligations, mandate)`, `project(...)` (first breach day and days
   below the reserve), `alerts(state, mandate, store, day)` for the baseline.
4. Per open receivable (OPEN, outstanding face; FINANCED ones are listed and skipped), three labelled projections on a
   `model_copy`, each re-read with `plan()`, `project()` and `alerts()`: received today (status SETTLED, `settled_fen` = face,
   cash plus the outstanding); received N days before it is due (default 5) and received on the first breach day, both with
   the terms-days lever on the receivable copy (the engine posts the RECEIPT on issue day + terms). A receipt cannot be moved
   into the past, so an overdue invoice has only the "today" case.
5. The early-payment ceiling: a typed IMMEDIATE_DISCOUNT obligation on the receivable (effective day = `early_pay_lead`),
   and the ADR-0007 test as `_early_pay_vs_plan` runs it: C = interest + fees + discounts posted by `project` under the
   router's plan for those books; the largest whole-5bp rate whose C1 is below C0 (bisection, then the next step is priced
   too). Two faces: the whole outstanding invoice and the plan's need (`FundingPlan.need_fen`). An overdue invoice gets none.
6. Action rules, in order, each read from an engine output: overdue is "call now"; a receipt that saves nothing is
   "wait"; a ceiling above zero is "offer early pay up to X%"; otherwise "finance the invoice". The sentence is built from
   the same figures. Marginal value = the standing plan's cost less the cost with the receipt today. Net value = that
   saving for a call, the "beats by" at the ceiling for an early-pay offer (the least the offer can be worth), zero otherwise.
7. The cash price curve: for each arrival day d in the horizon, `plan()` on a copy with a confirmed ¥10,000 inflow on day d
   and on a copy with it on day d + 30; the difference is what arriving 30 days earlier is worth.

### 3.2 Runtime

| Run | Time |
| --- | --- |
| Day-0 receivable (1 receivable, 6 plan/alerts readings), without the curve | 0.33 s |
| Day-34 receivables (3 receivables, 11 readings), without the curve | 0.66 s |
| With the cash price curve (91 arrival days x 2 plans each), day 0 / day 34 | 6.8 s / 3.3 s |
| Whole spike | 11.9 s with interpreter start and the day-34 replay |

### 3.3 Output on the golden books

```text
COLLECTIONS: what is each open receivable worth? Receipts are hypothetical projections on a copy of the books (never a bank receipt); nothing is booked or sent.

== day 0: the golden scenario as loaded (fixtures/scenarios/golden_sme.json)
   cash ¥400,000.00; the standing plan needs ¥405,000.00 and costs ¥3,113.93; first breach day 12; 20 days below the reserve; alerts: RESERVE_BREACH_AHEAD, RESERVE_HEADROOM_LOW
#  Receivable  Outstanding  Due day  Saved if received today  Plan cost left  Need left  Breach days removed  Alerts cleared        Early-pay ceiling                           Net of the discount  Action                     
-  ----------  -----------  -------  -----------------------  --------------  ---------  -------------------  --------------------  ------------------------------------------  -------------------  ---------------------------
1  RCV-A       ¥420,000.00  32       ¥3,113.93                ¥0.00           ¥0.00      20 of 20             RESERVE_BREACH_AHEAD  0.70% on ¥420,000.00; 0.75% on ¥405,000.00  ¥173.93              offer early pay up to 0.75%

   Other receipt days (saving = standing-plan cost less cost with the receipt):
Receivable  Receipt                                    Saved      Need left    Breach days removed  Alerts cleared      
----------  -----------------------------------------  ---------  -----------  -------------------  --------------------
RCV-A       received 5 days before it is due (day 27)  ¥532.49    ¥360,000.00  5                    -
RCV-A       received by the first breach day (day 12)  ¥3,113.93  ¥0.00        20                   RESERVE_BREACH_AHEAD

   Early-payment discount that beats the standing plan (C1 < C0):
Receivable  Face                           Amount       Largest rate  C0 (without)  C1 (with, at that rate)  Beats by  Next step dearer by  Note
----------  -----------------------------  -----------  ------------  ------------  -----------------------  --------  -------------------  ----
RCV-A       the whole outstanding invoice  ¥420,000.00  0.70%         ¥3,113.93     ¥2,940.00                ¥173.93   0.75%: ¥36.07
RCV-A       the shortfall the plan covers  ¥405,000.00  0.75%         ¥3,113.93     ¥3,054.54                ¥59.39    0.80%: ¥144.25

   In the owner's words, ranked by marginal value:
   1. [offer early pay up to 0.75%] Offer Foshan Home Retail Co. early payment on RCV-A (¥420,000.00, due day 32) at up to 0.75% on ¥405,000.00 (0.70% if it covers ¥420,000.00): paying it today would avoid ¥3,113.93 of financing cost and clears the shortfall, and a discount up to that rate costs less than the financing it replaces. The standing plan already advances against it.

   Ranked by net value instead (the saving less the discount that earns it, at the ceiling rate): RCV-A ¥173.93 [offer early pay up to 0.75%]

   Cash price curve: what ¥10,000.00 arriving 30 days earlier is worth, by arrival day
Arrival day  Worth 
-----------  ------
0            ¥0.00
1-30         ¥89.11
31-90        ¥0.00
   6 plan/alerts readings, 6.82 s.

== day 34: the demo path replayed in process (scripts/demo_run.py; as tests/alerts/test_repay_alert.py::to_day34)
   cash ¥300,000.00; the standing plan needs ¥200,000.00 and costs ¥1,706.10; first breach day 42; 5 days below the reserve; alerts: RESERVE_BREACH_AHEAD, RECEIVABLE_PAST_DUE, RESERVE_HEADROOM_LOW
#  Receivable     Outstanding  Due day      Saved if received today  Plan cost left  Need left   Breach days removed  Alerts cleared                              Early-pay ceiling                           Net of the discount  Action                     
-  -------------  -----------  -----------  -----------------------  --------------  ----------  -------------------  ------------------------------------------  ------------------------------------------  -------------------  ---------------------------
1  RI:BUYER-1:2   ¥420,000.00  47           ¥1,706.10                ¥0.00           ¥0.00       5 of 5               RESERVE_BREACH_AHEAD, RESERVE_HEADROOM_LOW  0.40% on ¥420,000.00; 0.80% on ¥200,000.00  ¥77.58               offer early pay up to 0.80%
2  RI:BUYER-1:32  ¥420,000.00  77           ¥1,706.10                ¥0.00           ¥0.00       5 of 5               RESERVE_BREACH_AHEAD, RESERVE_HEADROOM_LOW  0.65% on ¥420,000.00; 1.20% on ¥200,000.00  ¥73.68               offer early pay up to 1.20%
3  RCV-A          ¥162,800.00  32 (2 late)  ¥1,374.61                ¥331.49         ¥37,200.00  0 of 5               RECEIVABLE_PAST_DUE, RESERVE_HEADROOM_LOW   -                                           ¥1,374.61            call now

   Other receipt days (saving = standing-plan cost less cost with the receipt):
Receivable     Receipt                                    Saved      Need left    Breach days removed  Alerts cleared      
-------------  -----------------------------------------  ---------  -----------  -------------------  --------------------
RI:BUYER-1:2   received 5 days before it is due (day 42)  ¥1,706.10  ¥0.00        5                    RESERVE_BREACH_AHEAD
RI:BUYER-1:32  received 5 days before it is due (day 72)  −¥76.09    ¥200,000.00  0                    -
RI:BUYER-1:32  received by the first breach day (day 42)  ¥1,706.10  ¥0.00        5                    RESERVE_BREACH_AHEAD

   Early-payment discount that beats the standing plan (C1 < C0):
Receivable     Face                           Amount       Largest rate  C0 (without)  C1 (with, at that rate)  Beats by  Next step dearer by  Note                                                                         
-------------  -----------------------------  -----------  ------------  ------------  -----------------------  --------  -------------------  -----------------------------------------------------------------------------
RI:BUYER-1:2   the whole outstanding invoice  ¥420,000.00  0.40%         ¥3,731.12     ¥3,705.02                ¥26.10    0.45%: ¥183.90
RI:BUYER-1:2   the shortfall the plan covers  ¥200,000.00  0.80%         ¥3,731.12     ¥3,653.54                ¥77.58    0.85%: ¥24.20
RI:BUYER-1:32  the whole outstanding invoice  ¥420,000.00  0.65%         ¥3,731.12     ¥3,676.76                ¥54.36    0.70%: ¥155.64
RI:BUYER-1:32  the shortfall the plan covers  ¥200,000.00  1.20%         ¥3,731.12     ¥3,657.44                ¥73.68    1.25%: ¥27.21
RCV-A          the whole outstanding invoice  ¥162,800.00  none          ¥3,731.12     -                        -         -                    overdue: an early-payment discount is never offered on an invoice already due

   In the owner's words, ranked by marginal value:
   1. [offer early pay up to 0.80%] Offer Foshan Home Retail Co. early payment on RI:BUYER-1:2 (¥420,000.00, due day 47) at up to 0.80% on ¥200,000.00 (0.40% if it covers ¥420,000.00): paying it today would avoid ¥1,706.10 of financing cost and clears the shortfall, and a discount up to that rate costs less than the financing it replaces. The standing plan already advances against it.
   2. [offer early pay up to 1.20%] Offer Foshan Home Retail Co. early payment on RI:BUYER-1:32 (¥420,000.00, due day 77) at up to 1.20% on ¥200,000.00 (0.65% if it covers ¥420,000.00): paying it today would avoid ¥1,706.10 of financing cost and clears the shortfall, and a discount up to that rate costs less than the financing it replaces. The standing plan already advances against it.
   3. [call now] Call Foshan Home Retail Co. first: recovering ¥162,800.00 now avoids ¥1,374.61 of financing cost and leaves ¥37,200.00 to cover.

   Ranked by net value instead (the saving less the discount that earns it, at the ceiling rate): RCV-A ¥1,374.61 [call now]; RI:BUYER-1:2 ¥77.58 [offer early pay up to 0.80%]; RI:BUYER-1:32 ¥73.68 [offer early pay up to 1.20%]

   Cash price curve: what ¥10,000.00 arriving 30 days earlier is worth, by arrival day
Arrival day  Worth  
-----------  -------
34-42        ¥178.22
43-60        ¥89.12
61-124       ¥0.00
   11 plan/alerts readings, 3.34 s.

(5 days earlier = the receipt moved with the terms-days lever; the curve moves a ¥ amount by 30 days)
```

### 3.4 Agreement with `03-deep-dives.md`

Reproduced exactly: day 34 needs ¥200,000, cure ¥1,706.10, first breach day 42, the alerts RESERVE_BREACH_AHEAD, RECEIVABLE_PAST_DUE and
RESERVE_HEADROOM_LOW; RCV-A's residual ¥162,800.00 (2 days late) saves ¥1,374.61 if recovered today and leaves ¥37,200
(cost ¥331.49 left, still not enough to clear the breach); RI:BUYER-1:2 and RI:BUYER-1:32 each save ¥1,706.10 and remove the breach;
on the whole ¥420,000 the early-pay ceiling is 0.40% (it beats the plan by ¥26.10; 0.45% is dearer by ¥183.90); on ¥200,000, 0.40%
beats the plan by ¥888.28 and 0.85% is ¥24.20 dearer; on day 0 the receipt by day 12 saves ¥3,113.93, and the whole-face early
pay on RCV-A is 0.70%.

Differing or new:

| Item | 03 says | Spike says |
| --- | --- | --- |
| Early-pay ceiling on RI:BUYER-1:2 | "offer early payment on ¥200,000 at ≤ 0.40%" | **0.80% on ¥200,000**; 0.40% is the ceiling on the whole ¥420,000. The deep dive's own ¥888.28 (at 0.40% on ¥200,000) and ¥24.20 (0.85% dearer) are exact, so 0.40% is a safe rate on ¥200,000, not the ceiling |
| Ranking | RCV-A first, then RI:BUYER-1:2, then RI:BUYER-1:32 | by marginal value (gross): RI:BUYER-1:2 and RI:BUYER-1:32 (¥1,706.10 each) before RCV-A (¥1,374.61). By net value the deep dive's order returns: RCV-A ¥1,374.61, RI:BUYER-1:2 ¥77.58, RI:BUYER-1:32 ¥73.68 |
| Action on RI:BUYER-1:32 | "wait; it is the cure's collateral" | the rules give "offer early pay up to 1.20% on ¥200,000 (0.65% on the whole invoice)": the engine does not model whether a buyer pays 41 days early, so "wait" is a judgment the spike does not reproduce. "Wait" never fired on these books |
| Receipt 5 days before due | not computed | RI:BUYER-1:2 on day 42: ¥1,706.10; RCV-A on day 27 (day 0): ¥532.49; RI:BUYER-1:32 on day 72: **−¥76.09**, a receipt that raises the cost (the router's cost is not monotone in the receipt date. An ad hoc call, not in the script's output: the receipt on day 75 costs ¥52.60 more than none with the same two advances, and the receipt on day 60 changes the plan to one advance of ¥200,000 on that invoice) |
| Cash price curve, day 0 | ¥89.10 per ¥10,000 per 30 days before day 32, ¥84.15 on the line, ¥0 after day 47 | **¥89.11** for arrival days 1 to 30, ¥0 from day 31 and on day 0 itself; the ¥84.15 band is not seen at a ¥10,000 step (a larger amount was not run). The definitions differ (the deep dive priced cash on a day, the spike prices the same cash 30 days earlier), so ¥0 from day 31 against "after day 47" is not a conflict |
| Cash price curve, day 34 | not computed | ¥178.22 for arrival days 34 to 42, ¥89.12 for 43 to 60, ¥0 from 61 |
| Day 0 partial receipts (¥100,000 → ¥891.09; ¥257,200 → ¥2,284.63) and RCV-A by day 20, 25, 31 (¥1,785.91, ¥585.10, ¥26.30) | in 03 | **not checked** (the spike moves the whole invoice: day 27 gives ¥532.49, day 12 ¥3,113.93, consistent with the curve) |

### 3.5 What the spike could not do

- It has no payment probability, dispute flag, buyer importance or days-late history: every receipt is a deterministic
  what-if, labelled hypothetical, never a bank receipt (receipts come from the bank feed only). The ranking is of cash
  consequence, not of the chance of being paid.
- It cannot know whether a buyer would accept an early-pay offer at any rate; the ceiling is what the owner can afford.
- FINANCED receivables (a receipt repays the lender first, ADR-0010) and invoices not yet issued are not simulated; on
  these books there are none.
- "Escalate by day 39, the last day an advance can be requested" (03) is not computed.
- The router searches on a ¥10,000 grid and a bounded space, so a small change in the books can move the plan's shape; the
  curve's day-0 value (¥0.00 on arrival day 0, because arrival on day 0 and on day 30 both serve the day-30 trough) and
  the −¥76.09 above are consequences. The curve amount equals the grid step.
- The cash price curve moves a confirmed ¥10,000 flow, not a particular receivable.

## 4. Every differing figure, in one list

1. Smallest price at 55 days: 0.25% (03: 0.30%); at 50 days: 0.10% (03: 0.15%). The 0.30% and 0.15% reproduce as the price that nets the cost to zero.
2. 60 days with Option A: passes from 0.40% (03: 0.45%).
3. Reserve breach day at 60 days alone: day 47 (03: day 60, ¥130,000).
4. Longest terms in a passing package: 80 days with Option A's early payment (03: 60 tested).
5. Whole-invoice early pay with any extension: never passes (03: not tested).
6. Early-pay ceiling on RI:BUYER-1:2: 0.80% on ¥200,000; 0.40% on ¥420,000 (03: 0.40% on ¥200,000).
7. Collections order: RI:BUYER-1:2, RI:BUYER-1:32, RCV-A by marginal value; the 03 order by net value (03: RCV-A first).
8. RI:BUYER-1:32: "offer early pay up to 1.20% on ¥200,000" (03: wait).
9. Cash price curve day 0: ¥89.11 (03: ¥89.10); ¥0 from arrival day 31 (03: after day 47, a different definition); no ¥84.15 band at ¥10,000.
10. Greedy `evaluate_many`: rank 7 of 9 (03: no figure).
11. Run times: 5.4 s (51 evaluations) for the maxima and zone, 29.7 s with the packages; portfolio 0.52 s and 0.79 s (03: 22 evaluations in 1.6 s; 0.43 s and 1.63 s).
12. Posted cost ¥3,027.77 beside funding cost ¥841.57 for the best portfolio (03 gives the second only).
13. RI:BUYER-1:32 received on day 72 costs ¥76.09 more than not (new, a router property).

## 5. Validation

- `uv run --project services/api ruff check services/api/scripts/research`: all checks passed. `mypy services/api/scripts/research`: no issues in 4 files.
- `SKIP_PERF_BENCH=1 uv run --project services/api pytest -q -p no:cacheprovider services/api/tests/api services/api/tests/verifier services/api/tests/funding`: 1513 passed, 22 skipped, exit 0.
  `git diff origin/dev -- services/api/app apps` is empty: no application file differs from `dev`, so the suite is the one `dev` runs.
- The flag: without `FLOW_RESEARCH_SPIKES=1` each script exits with status 2 and one line on stderr. A lever outside the ranges
  (`--package terms=60,discount=160`) exits with status 2 and names the range.
- Each script's `--json` output parses as JSON; every amount carries `fen` and `display`.

