# Forward-concession valuation: independent hand calculation (2026-10-03)

Status: independent derivation. Parts 1 to 10 were written before the implementation was read; part 11 compares them
with the code. Every table in parts 1 to 10 is printed by `scripts/handcalc_concessions.py` (standard library only,
no `app.*` import) and checked against this file with
`PYTHONUTF8=1 python scripts/handcalc_concessions.py --check docs/research/concession-valuation-handcalc-2026-10-03.md`.

Scope: the audit findings F-FIN-01, F-FIN-06, F-FIN-07, F-FIN-09 of `docs/research/independent-financial-working-2026-10-02.md`,
derived under the eight rules fixed by the owner. Where I think a rule is economically wrong I derive under it anyway and
list the objection in part 10.

## 0. Headline results (derived, golden recurring invoice)

1. Closed window [today, today+H] anchored on the golden `next_issue_day = 2` contains **13** invoices at H = 365, today = 0
   (issue days 2, 32, ..., 362), not 12. A 365-day window holds 12 or 13 monthly invoices depending on phase; `floor(H / every)`
   is the phase-blind floor. Golden numbers built from a count of 12 invoices therefore move to 13 under rules 1 and 2 (part 9 and part 11).
2. Perpetual and bounded scopes covering the same invoices give the same value at every horizon (part 3). At H = 90/180/365/730 and
   10% funding the extension costs 517,808 / 1,035,616 / 2,243,836 / 4,315,068 fen (CNY 5,178.08 / 10,356.16 / 22,438.36 / 43,150.68):
   linear in the number of invoices in the window, never in H squared.
3. Firm +1% from day 1000 is worth exactly 0 and the CNY 6,000 rebate stands alone against the CNY 5,000 cap: net 600,000 fen, breach by 100,000 fen (part 5).
4. Pro-forma monthly debt service (steady state) at 10%: 350,000 / 175,000 / 87,500 / 14,384 fen for invoices every 15 / 30 / 60 / 365 days
   (CNY 3,500.00 / 1,750.00 / 875.00 / 143.84); extra debt 42,000,000 / 21,000,000 / 10,500,000 / 1,726,027 fen (part 6, part 7).
5. Break-even with a once-only 1% upfront fee on CNY 100,000: d* = 1.856001% for n = 1..30, 2.706879% for 31..60, 3.543140% for 61..90, 4.365138% for 91 (part 8).
   Without upfront fee 0.883230% / 1.750984% / 2.603686% (display 0.8832% / 1.751% / 2.6037%): unchanged.

## 1. Conventions and inputs

Units: money in integer fen; rates are exact fractions (a basis point is 1/10,000); days are absolute integers;
year = 365 days; posting `post(x) = floor(x + 1/2)` applied to the signed value (so a negative value ending in exactly .5 rounds toward zero).
"Exact" means the unrounded rational number of fen; "posted" means `post` of it.

| input | value |
|---|---|
| face F | 42,000,000 fen (¥420,000.00) |
| every_days e | 30 |
| next_issue_day s0 | 2 |
| terms_days | 45 |
| mandate horizon H | 365 days |
| extension delta | 15 days |
| rate r1 | 1/10 = 10.0000% |
| golden marginal rate r2 = 780bp + 25bp x 365/30 | 1301/12000 = 10.841667% |
| per-invoice cost at r1, exact | 12600000/73 fen = 172602.7397 fen |
| per-invoice cost at r2, exact | 13660500/73 fen = 187130.1370 fen |
| per-invoice cost at r1, posted | 172,603 fen (¥1,726.03) |
| per-invoice cost at r2, posted | 187,130 fen (¥1,871.30) |

Golden inputs were read from `fixtures/scenarios/golden_sme.json` (recurring invoice: face 42,000,000, every 30, next issue day 2, terms 45;
mandate `forward_concession_horizon_days` 365, `max_aggregate_forward_concession_fen` 500,000) and from the invoice-financing facility FAC-IF
(`rate_bp` 780, `fee_bp_per_advance` 25 per 30-day `fee_period_days`, `upfront_fee_bp` 0, `advance_rate_bp` 8000).

Golden marginal funding rate: the cheapest committed source for a permanent need is invoice financing (ADR 0003, CONTEXT.md "Marginal cost of funds").
Its all-in annual rate is the interest rate plus the per-period fee annualised over a 365-day year:

    r2 = 780/10000 + (25/10000) x (365/30) = 39/500 + 73/2400 = 1301/12000 = 10.841667%

The golden values file prints it as 10.8417% (`if_all_in_rate_display`). A second rate, r1 = 10%, is used throughout so that the numbers
can be checked mentally. With face F = 42,000,000 and delta = 15 the per-invoice extension cost is
F x 15 x r / 365 = 12,600,000/73 fen at r1 and 13,660,500/73 fen at r2.

## 2. Rules 1 and 2: the valuation window and the scope of an obligation

Definition. W = [lo, hi] with hi = today + H and lo = max(today, effective day). `today` is `as_of_day`, H the mandate horizon.
Both ends are inclusive (the rule is written W = [today, today + H]); an invoice issued exactly on today or exactly on today + H counts.
An obligation's scope is a dated list of invoices; only invoices whose issue day lies in W, and inside the obligation's own scope, count. Nothing outside W
creates cost or gain, in either direction.

Recurring invoices are issued on days s0 + k e for k = 0, 1, 2, ... (s0 = `next_issue_day`, e = `every_days`; golden s0 = 2, e = 30). Invoices before
`today` are history. Scope selection on the in-window list (in issue order):

| kind | invoices in scope |
|---|---|
| perpetual | all of them |
| count-bounded N | the first N of them (N larger than the window holds is truncated by W) |
| date-bounded end_day | those with issue day <= end_day |
| ONE_OFF | the first one |
| named invoice | that invoice if its issue day is in W, else none |

Effective day: if it is earlier than today it is clamped to today; if it is later than today + H the scope is empty and the value is 0 (not an error).
For a perpetual scope the number of invoices is

    N = max(0, floor((hi - s0) / e) - max(0, ceil((lo - s0) / e)) + 1)

For the golden anchor, today = 0, H = 365: floor(363/30) - 0 + 1 = 12 + 1 = 13. For today = 34: lo = 34, hi = 399, ceil(32/30) = 2, floor(397/30) = 13, N = 13 - 2 + 1 = 12 (days 62 ... 392).
The sequence stays anchored at s0 = 2 whatever `today` is; the day-32 invoice is history when today = 34.

Identical invoice sets give identical value whatever the wording:

| check | result |
|---|---|
| P90 and B90 give the same invoice list | True |
| P180 and B180 give the same invoice list | True |
| P365 and B365 give the same invoice list | True |
| P730 and B730 give the same invoice list | True |
| P90 and T90 give the same invoice list | True |
| P365 and D400 give the same invoice list | True |
| P365 (13 invoices) vs Q365 (12 invoices) | same list False; extra invoice in P365: day 362 |
| P730 (25 invoices) vs Q730 (24 invoices) | same list False; extra invoice in P730: day 722 |

Case catalogue (every id is used in the value tables below):

| id | today | H | W = [today, today+H] | scope | N | issue days in scope |
|---|---|---|---|---|---|---|
| P90 | 0 | 90 | [0, 90] | perpetual, H=90 | 3 | 2,32,62 |
| P180 | 0 | 180 | [0, 180] | perpetual, H=180 | 6 | 2,32,...,152 |
| P365 | 0 | 365 | [0, 365] | perpetual, H=365 (golden) | 13 | 2,32,...,362 |
| P730 | 0 | 730 | [0, 730] | perpetual, H=730 | 25 | 2,32,...,722 |
| P360 | 0 | 360 | [0, 360] | perpetual, H=360 (last issue 332) | 12 | 2,32,...,332 |
| P361 | 0 | 361 | [0, 361] | perpetual, H=361 | 12 | 2,32,...,332 |
| P362 | 0 | 362 | [0, 362] | perpetual, H=362 (issue day 362 on the edge of W) | 13 | 2,32,...,362 |
| B90 | 0 | 90 | [0, 90] | bounded N=3 (= invoices of P90), H=90 | 3 | 2,32,62 |
| B180 | 0 | 180 | [0, 180] | bounded N=6 (= invoices of P180), H=180 | 6 | 2,32,...,152 |
| B365 | 0 | 365 | [0, 365] | bounded N=13 (= invoices of P365), H=365 | 13 | 2,32,...,362 |
| B730 | 0 | 730 | [0, 730] | bounded N=25 (= invoices of P730), H=730 | 25 | 2,32,...,722 |
| Q365 | 0 | 365 | [0, 365] | bounded N=12 = floor(H/every), H=365 | 12 | 2,32,...,332 |
| Q730 | 0 | 730 | [0, 730] | bounded N=24 = floor(H/every), H=730 | 24 | 2,32,...,692 |
| T90 | 0 | 90 | [0, 90] | bounded N=100, truncated by W, H=90 | 3 | 2,32,62 |
| D100 | 0 | 365 | [0, 365] | date-bounded end_day=100, H=365 | 4 | 2,32,62,92 |
| D400 | 0 | 365 | [0, 365] | date-bounded end_day=400, truncated by W, H=365 | 13 | 2,32,...,362 |
| O365 | 0 | 365 | [0, 365] | ONE_OFF, H=365 | 1 | 2 |
| O100 | 0 | 365 | [0, 365] | ONE_OFF effective day 100 (first issue >= 100 is 122) | 1 | 122 |
| N3 | 0 | 365 | [0, 365] | next 3, H=365 | 3 | 2,32,62 |
| N3e300 | 0 | 365 | [0, 365] | next 3 from effective day 300 (302, 332, 362) | 3 | 302,332,362 |
| N3e330 | 0 | 365 | [0, 365] | next 3 from effective day 330, cut by W (332, 362) | 2 | 332,362 |
| E100 | 0 | 365 | [0, 365] | perpetual, effective day 100 (inside W) | 9 | 122,152,...,362 |
| E362 | 0 | 365 | [0, 365] | perpetual, effective day 362 (issue exactly on it) | 1 | 362 |
| E363 | 0 | 365 | [0, 365] | perpetual, effective day 363 (next issue 392 is outside W) | 0 | none |
| E365 | 0 | 365 | [0, 365] | perpetual, effective day 365 = today+H (edge of W) | 0 | none |
| E1000 | 0 | 365 | [0, 365] | perpetual, effective day 1000 (beyond W) | 0 | none |
| T34 | 34 | 365 | [34, 399] | today=34, perpetual, H=365 | 12 | 62,92,...,392 |
| T34h90 | 34 | 90 | [34, 124] | today=34, perpetual, H=90 | 3 | 62,92,122 |
| T34e100 | 34 | 365 | [34, 399] | today=34, perpetual, effective day 100 | 10 | 122,152,...,392 |
| T34o | 34 | 365 | [34, 399] | today=34, ONE_OFF | 1 | 62 |
| T34n3 | 34 | 365 | [34, 399] | today=34, next 3 | 3 | 62,92,122 |

## 3. Rule 3: terms extension

Definition. Extending payment terms by delta days on an invoice of face F makes the supplier fund F for delta more days.
Unit: fen. Formula, per invoice and in total over the in-scope list I (face F_i, extension delta_i):

    cost = sum over i in I of F_i x delta_i x r / 365      (r = marginal annual funding rate, a given input)

posted once at the end. delta < 0 gives a negative cost (a gain); r = 0, delta = 0 or I empty give 0.
With equal faces: cost = N x F x delta x r / 365. It is linear in N and independent of H except through N.

Rounding: posting once versus per invoice. "Posted once" is `post(N x exact)`; "sum of per-invoice postings" is `N x post(exact)`.
The column "once minus per-invoice" is the difference in fen. At r1 the per-invoice exact value is 172,602.74 fen, so each invoice rounds up by 0.26 fen
and per-invoice posting overstates by 0.26 fen x N (3 fen at N = 13, 7 fen at N = 25). At r2 the per-invoice exact value is 187,130.14 fen, so
per-invoice posting understates by 0.14 fen x N (2 fen at N = 13, 3 fen at N = 25). So the choice changes the golden numbers by 2 to 3 fen at the golden
invoice count and by up to 7 fen in the tables; it never changes them by a yuan.
The rule (post once) is used for every value below.

### 3.1 Funding rate 10%

| id | N | exact total (fen) | posted once | sum of per-invoice postings | once minus per-invoice (fen) | posted once (CNY) |
|---|---|---|---|---|---|---|
| P90 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| P180 | 6 | 75600000/73 | 1,035,616 | 1,035,618 | -2 | ¥10,356.16 |
| P365 | 13 | 163800000/73 | 2,243,836 | 2,243,839 | -3 | ¥22,438.36 |
| P730 | 25 | 315000000/73 | 4,315,068 | 4,315,075 | -7 | ¥43,150.68 |
| P360 | 12 | 151200000/73 | 2,071,233 | 2,071,236 | -3 | ¥20,712.33 |
| P361 | 12 | 151200000/73 | 2,071,233 | 2,071,236 | -3 | ¥20,712.33 |
| P362 | 13 | 163800000/73 | 2,243,836 | 2,243,839 | -3 | ¥22,438.36 |
| B90 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| B180 | 6 | 75600000/73 | 1,035,616 | 1,035,618 | -2 | ¥10,356.16 |
| B365 | 13 | 163800000/73 | 2,243,836 | 2,243,839 | -3 | ¥22,438.36 |
| B730 | 25 | 315000000/73 | 4,315,068 | 4,315,075 | -7 | ¥43,150.68 |
| Q365 | 12 | 151200000/73 | 2,071,233 | 2,071,236 | -3 | ¥20,712.33 |
| Q730 | 24 | 302400000/73 | 4,142,466 | 4,142,472 | -6 | ¥41,424.66 |
| T90 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| D100 | 4 | 50400000/73 | 690,411 | 690,412 | -1 | ¥6,904.11 |
| D400 | 13 | 163800000/73 | 2,243,836 | 2,243,839 | -3 | ¥22,438.36 |
| O365 | 1 | 12600000/73 | 172,603 | 172,603 | 0 | ¥1,726.03 |
| O100 | 1 | 12600000/73 | 172,603 | 172,603 | 0 | ¥1,726.03 |
| N3 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| N3e300 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| N3e330 | 2 | 25200000/73 | 345,205 | 345,206 | -1 | ¥3,452.05 |
| E100 | 9 | 113400000/73 | 1,553,425 | 1,553,427 | -2 | ¥15,534.25 |
| E362 | 1 | 12600000/73 | 172,603 | 172,603 | 0 | ¥1,726.03 |
| E363 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| E365 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| E1000 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| T34 | 12 | 151200000/73 | 2,071,233 | 2,071,236 | -3 | ¥20,712.33 |
| T34h90 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |
| T34e100 | 10 | 126000000/73 | 1,726,027 | 1,726,030 | -3 | ¥17,260.27 |
| T34o | 1 | 12600000/73 | 172,603 | 172,603 | 0 | ¥1,726.03 |
| T34n3 | 3 | 37800000/73 | 517,808 | 517,809 | -1 | ¥5,178.08 |

### 3.2 Golden marginal rate 10.8417% (r2 = 1301/12000)

| id | N | exact total (fen) | posted once | sum of per-invoice postings | once minus per-invoice (fen) | posted once (CNY) |
|---|---|---|---|---|---|---|
| P90 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| P180 | 6 | 81963000/73 | 1,122,781 | 1,122,780 | 1 | ¥11,227.81 |
| P365 | 13 | 177586500/73 | 2,432,692 | 2,432,690 | 2 | ¥24,326.92 |
| P730 | 25 | 341512500/73 | 4,678,253 | 4,678,250 | 3 | ¥46,782.53 |
| P360 | 12 | 163926000/73 | 2,245,562 | 2,245,560 | 2 | ¥22,455.62 |
| P361 | 12 | 163926000/73 | 2,245,562 | 2,245,560 | 2 | ¥22,455.62 |
| P362 | 13 | 177586500/73 | 2,432,692 | 2,432,690 | 2 | ¥24,326.92 |
| B90 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| B180 | 6 | 81963000/73 | 1,122,781 | 1,122,780 | 1 | ¥11,227.81 |
| B365 | 13 | 177586500/73 | 2,432,692 | 2,432,690 | 2 | ¥24,326.92 |
| B730 | 25 | 341512500/73 | 4,678,253 | 4,678,250 | 3 | ¥46,782.53 |
| Q365 | 12 | 163926000/73 | 2,245,562 | 2,245,560 | 2 | ¥22,455.62 |
| Q730 | 24 | 327852000/73 | 4,491,123 | 4,491,120 | 3 | ¥44,911.23 |
| T90 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| D100 | 4 | 54642000/73 | 748,521 | 748,520 | 1 | ¥7,485.21 |
| D400 | 13 | 177586500/73 | 2,432,692 | 2,432,690 | 2 | ¥24,326.92 |
| O365 | 1 | 13660500/73 | 187,130 | 187,130 | 0 | ¥1,871.30 |
| O100 | 1 | 13660500/73 | 187,130 | 187,130 | 0 | ¥1,871.30 |
| N3 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| N3e300 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| N3e330 | 2 | 27321000/73 | 374,260 | 374,260 | 0 | ¥3,742.60 |
| E100 | 9 | 122944500/73 | 1,684,171 | 1,684,170 | 1 | ¥16,841.71 |
| E362 | 1 | 13660500/73 | 187,130 | 187,130 | 0 | ¥1,871.30 |
| E363 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| E365 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| E1000 | 0 | 0 | 0 | 0 | 0 | ¥0.00 |
| T34 | 12 | 163926000/73 | 2,245,562 | 2,245,560 | 2 | ¥22,455.62 |
| T34h90 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |
| T34e100 | 10 | 136605000/73 | 1,871,301 | 1,871,300 | 1 | ¥18,713.01 |
| T34o | 1 | 13660500/73 | 187,130 | 187,130 | 0 | ¥1,871.30 |
| T34n3 | 3 | 40981500/73 | 561,390 | 561,390 | 0 | ¥5,613.90 |

### 3.3 Reading the tables

- Perpetual against bounded with the same invoice count (P90/B90, P180/B180, P365/B365, P730/B730): identical, to the fen, at every H and both rates.
  The value does not depend on the word perpetual or bounded, only on the dated invoice list.
- Perpetual against `floor(H/every)` bounded counts (Q365, Q730): they are not the same invoice set. At H = 365 the window holds a 13th invoice (day 362);
  at H = 730 a 25th (day 722). The difference is exactly one invoice: at r2, 187,130 fen at both H; at r1, 172,603 fen at H = 365 and 172,602 fen at H = 730 (posting once of N x 172,602.74).
  At H = 90 and 180 the two counts coincide (3 and 6).
- Edge of W: H = 361 gives 12 invoices, H = 362 gives 13, because the day-362 issue lies exactly on today + H. With an effective day, 362 is in (1 invoice), 363 is out
  (0), and effective day 365 = today + H is also empty because the next issue day is 392. Effective day 1000 is beyond W: cost 0.
- ONE_OFF is one invoice: 172,603 fen at r1 (CNY 1,726.03), 187,130 fen at r2 (CNY 1,871.30), whichever invoice it is.
- today = 34: the day-32 invoice is history, W = [34, 399] holds days 62 ... 392: 12 invoices (not 13); with H = 90 it holds 62, 92, 122.
  The same perpetual obligation is therefore worth one invoice less when today moves from 0 to 34.
- Gain (delta = -15): the value is the mirror image, as in the next table.

| case | exact (fen) | posted once | note |
|---|---|---|---|
| delta=-15, perpetual H=365, N=13, r=10% | -163800000/73 | -2,243,836 | gain; mirror of the +15 cost, differs only when the exact value ends in .5 |
| delta=-15, perpetual H=365, N=13, r=golden 10.8417% | -177586500/73 | -2,432,692 | gain; mirror of the +15 cost, differs only when the exact value ends in .5 |

## 4. Rule 4: price adjustment

Definition. A price adjustment of p (positive = the supplier gains) on every in-scope invoice. Unit: fen.

    value = - sum over i in I of post(p x F_i)

Each invoice is posted separately (rule 4 as given); with golden face the products are exact integers (0.45% x 42,000,000 = 189,000; 1% x 42,000,000 = 420,000)
so posting once or per invoice makes no difference here. Negative value = gain. A positive p on N invoices has value -N x p x F; a negative p (price cut) is a cost.

### 4.1 +0.45% (45 bp)

| id | N | per-invoice posting (fen) | value (fen) | value (CNY) |
|---|---|---|---|---|
| P90 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| P180 | 6 | 189,000 | -1,134,000 | -¥11,340.00 |
| P365 | 13 | 189,000 | -2,457,000 | -¥24,570.00 |
| P730 | 25 | 189,000 | -4,725,000 | -¥47,250.00 |
| P360 | 12 | 189,000 | -2,268,000 | -¥22,680.00 |
| P361 | 12 | 189,000 | -2,268,000 | -¥22,680.00 |
| P362 | 13 | 189,000 | -2,457,000 | -¥24,570.00 |
| B90 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| B180 | 6 | 189,000 | -1,134,000 | -¥11,340.00 |
| B365 | 13 | 189,000 | -2,457,000 | -¥24,570.00 |
| B730 | 25 | 189,000 | -4,725,000 | -¥47,250.00 |
| Q365 | 12 | 189,000 | -2,268,000 | -¥22,680.00 |
| Q730 | 24 | 189,000 | -4,536,000 | -¥45,360.00 |
| T90 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| D100 | 4 | 189,000 | -756,000 | -¥7,560.00 |
| D400 | 13 | 189,000 | -2,457,000 | -¥24,570.00 |
| O365 | 1 | 189,000 | -189,000 | -¥1,890.00 |
| O100 | 1 | 189,000 | -189,000 | -¥1,890.00 |
| N3 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| N3e300 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| N3e330 | 2 | 189,000 | -378,000 | -¥3,780.00 |
| E100 | 9 | 189,000 | -1,701,000 | -¥17,010.00 |
| E362 | 1 | 189,000 | -189,000 | -¥1,890.00 |
| E363 | 0 | 189,000 | 0 | ¥0.00 |
| E365 | 0 | 189,000 | 0 | ¥0.00 |
| E1000 | 0 | 189,000 | 0 | ¥0.00 |
| T34 | 12 | 189,000 | -2,268,000 | -¥22,680.00 |
| T34h90 | 3 | 189,000 | -567,000 | -¥5,670.00 |
| T34e100 | 10 | 189,000 | -1,890,000 | -¥18,900.00 |
| T34o | 1 | 189,000 | -189,000 | -¥1,890.00 |
| T34n3 | 3 | 189,000 | -567,000 | -¥5,670.00 |

### 4.2 +1% (100 bp)

| id | N | per-invoice posting (fen) | value (fen) | value (CNY) |
|---|---|---|---|---|
| P90 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| P180 | 6 | 420,000 | -2,520,000 | -¥25,200.00 |
| P365 | 13 | 420,000 | -5,460,000 | -¥54,600.00 |
| P730 | 25 | 420,000 | -10,500,000 | -¥105,000.00 |
| P360 | 12 | 420,000 | -5,040,000 | -¥50,400.00 |
| P361 | 12 | 420,000 | -5,040,000 | -¥50,400.00 |
| P362 | 13 | 420,000 | -5,460,000 | -¥54,600.00 |
| B90 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| B180 | 6 | 420,000 | -2,520,000 | -¥25,200.00 |
| B365 | 13 | 420,000 | -5,460,000 | -¥54,600.00 |
| B730 | 25 | 420,000 | -10,500,000 | -¥105,000.00 |
| Q365 | 12 | 420,000 | -5,040,000 | -¥50,400.00 |
| Q730 | 24 | 420,000 | -10,080,000 | -¥100,800.00 |
| T90 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| D100 | 4 | 420,000 | -1,680,000 | -¥16,800.00 |
| D400 | 13 | 420,000 | -5,460,000 | -¥54,600.00 |
| O365 | 1 | 420,000 | -420,000 | -¥4,200.00 |
| O100 | 1 | 420,000 | -420,000 | -¥4,200.00 |
| N3 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| N3e300 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| N3e330 | 2 | 420,000 | -840,000 | -¥8,400.00 |
| E100 | 9 | 420,000 | -3,780,000 | -¥37,800.00 |
| E362 | 1 | 420,000 | -420,000 | -¥4,200.00 |
| E363 | 0 | 420,000 | 0 | ¥0.00 |
| E365 | 0 | 420,000 | 0 | ¥0.00 |
| E1000 | 0 | 420,000 | 0 | ¥0.00 |
| T34 | 12 | 420,000 | -5,040,000 | -¥50,400.00 |
| T34h90 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |
| T34e100 | 10 | 420,000 | -4,200,000 | -¥42,000.00 |
| T34o | 1 | 420,000 | -420,000 | -¥4,200.00 |
| T34n3 | 3 | 420,000 | -1,260,000 | -¥12,600.00 |

Note: the price adjustment does not use r, so the two rates are irrelevant here, but the invoice COUNT is the whole story: the perpetual +0.45% over
H = 90 / 180 / 365 / 730 is -567,000 / -1,134,000 / -2,457,000 / -4,725,000 fen, linear in the window, never in H squared.

## 5. Rule 5: netting gains against the cap, and the F-FIN-01 case

Definition. The aggregate forward concession compared with the cap is

    counted = sum of concession costs (positive values)  +  sum of gains (negative values) that are FIRM and inside W

and the cap test is counted <= cap. With the dating fixed by rule 1, a gain whose invoices are all outside W has value 0, so it cannot offset anything. Whether `counted`
is floored at 0 is an existing rule that this derivation does not touch ("not derivable from the given inputs": the floor is missing as an input; the rows below are
unfloored and none of the verdicts depends on a floor).

Rebate: CNY 6,000 = 600,000 fen of cost (inside W, taken as given). Cap: CNY 5,000 = 500,000 fen.

| case | rebate cost | price-adjustment value | net counted against cap | cap | result |
|---|---|---|---|---|---|
| F-FIN-01: firm +1% from day 1000, H=365 (N=0) | 600,000 | 0 | 600,000 | 500,000 | BREACH by 100,000 fen (¥1,000.00) |
| +1% from day 100, FIRM, H=365 (N=9) | 600,000 | -3,780,000 | -3,180,000 | 500,000 | pass |
| +1% from day 100, NOT firm, H=365 (N=9) | 600,000 | -3,780,000 | 600,000 | 500,000 | BREACH by 100,000 fen (¥1,000.00) |
| +1% from day 362, FIRM, H=365 (N=1) | 600,000 | -420,000 | 180,000 | 500,000 | pass |
| +1% from day 363, FIRM, H=365 (N=0) | 600,000 | 0 | 600,000 | 500,000 | BREACH by 100,000 fen (¥1,000.00) |

First row is the F-FIN-01 case: the +1% starts on day 1000, which is beyond W = [0, 365]; N = 0; value 0; counted = 600,000 > 500,000, so the cap is breached by 100,000 fen (CNY 1,000.00).
The unfirm row shows that a gain only counts if firm even when it is inside W.

## 6. Rule 6: pro-forma monthly debt service of an extension

Definition. The steady-state monthly funding cost of the extension, if invoices keep arriving every e days. Unit: fen per month.

    annual cost  = per-invoice cost x 365 / e  = F x delta x r / e
    monthly      = annual / 12 = F x delta x r / (12 e)

posted once at the end. (Use the exact per-invoice cost, not the posted one: rounding it first moves the monthly number by up to 0.5 x 365/(12 e) fen, about 1 fen at e = 15.)

Rate 10%.

| every_days | per-invoice cost (exact fen) | annual cost = per-invoice x 365/e (exact fen) | monthly service = annual/12 (exact fen) | monthly service posted | monthly service (CNY) | extra debt F x delta / e (exact fen) | extra debt posted | extra debt (CNY) |
|---|---|---|---|---|---|---|---|---|
| 15 | 12600000/73 | 4200000 | 350000 | 350,000 | ¥3,500.00 | 42000000 | 42,000,000 | ¥420,000.00 |
| 30 | 12600000/73 | 2100000 | 175000 | 175,000 | ¥1,750.00 | 21000000 | 21,000,000 | ¥210,000.00 |
| 60 | 12600000/73 | 1050000 | 87500 | 87,500 | ¥875.00 | 10500000 | 10,500,000 | ¥105,000.00 |
| 365 | 12600000/73 | 12600000/73 | 1050000/73 | 14,384 | ¥143.84 | 126000000/73 | 1,726,027 | ¥17,260.27 |

Rate golden 10.8417%.

| every_days | per-invoice cost (exact fen) | annual cost = per-invoice x 365/e (exact fen) | monthly service = annual/12 (exact fen) | monthly service posted | monthly service (CNY) | extra debt F x delta / e (exact fen) | extra debt posted | extra debt (CNY) |
|---|---|---|---|---|---|---|---|---|
| 15 | 13660500/73 | 4553500 | 1138375/3 | 379,458 | ¥3,794.58 | 42000000 | 42,000,000 | ¥420,000.00 |
| 30 | 13660500/73 | 2276750 | 1138375/6 | 189,729 | ¥1,897.29 | 21000000 | 21,000,000 | ¥210,000.00 |
| 60 | 13660500/73 | 1138375 | 1138375/12 | 94,865 | ¥948.65 | 10500000 | 10,500,000 | ¥105,000.00 |
| 365 | 13660500/73 | 13660500/73 | 1138375/73 | 15,594 | ¥155.94 | 126000000/73 | 1,726,027 | ¥17,260.27 |

Identity check (service = extra debt x r / 12):

| every_days | rate | monthly service posted | extra debt posted x r / 12 posted | equal |
|---|---|---|---|---|
| 15 | 10% | 350,000 | 350,000 | True |
| 30 | 10% | 175,000 | 175,000 | True |
| 60 | 10% | 87,500 | 87,500 | True |
| 365 | 10% | 14,384 | 14,384 | True |
| 15 | golden 10.8417% | 379,458 | 379,458 | True |
| 30 | golden 10.8417% | 189,729 | 189,729 | True |
| 60 | golden 10.8417% | 94,865 | 94,865 | True |
| 365 | golden 10.8417% | 15,594 | 15,594 | True |

Reading: at the golden e = 30 and r2 the monthly service is 189,729 fen (CNY 1,897.29), not the per-invoice cost 187,130 fen (CNY 1,871.30), because 365/30 = 12.1667 invoices
a year are spread over 12 months. At r1 it is 175,000 fen (CNY 1,750.00) against a per-invoice 172,603 fen (CNY 1,726.03), a difference of 2,397 fen.
It is exactly proportional to 1/e: halving the invoice interval doubles the service.

### 6.1 Alternative: sum of dated charges per 30-day month

Each invoice's extension cost c_i is a charge dated on the extended due day (issue + terms 45 + delta 15, so the first charge falls on day 62). A covenant month is a 30-day block.
The long-run mean number of charges per block is 30/e; the blocks differ from the mean when e does not divide 30.

Rate 10%; one charge of 172,603 fen per invoice dated on the extended due day (issue + 45 + 15).

| every_days | charges per 30-day month: min | max | mean | peak month (fen) | mean month (exact fen) | steady-state (fen) | steady-state / mean |
|---|---|---|---|---|---|---|---|
| 15 | 2 | 2 | 2.0000 | 345,206 | 345205.48 | 350,000 | 1.0139 |
| 30 | 1 | 1 | 1.0000 | 172,603 | 172602.74 | 175,000 | 1.0139 |
| 60 | 0 | 1 | 0.5000 | 172,603 | 86301.37 | 87,500 | 1.0139 |
| 365 | 0 | 1 | 0.0822 | 172,603 | 14186.53 | 14,384 | 1.0139 |

Rate golden 10.8417%; one charge of 187,130 fen per invoice dated on the extended due day (issue + 45 + 15).

| every_days | charges per 30-day month: min | max | mean | peak month (fen) | mean month (exact fen) | steady-state (fen) | steady-state / mean |
|---|---|---|---|---|---|---|---|
| 15 | 2 | 2 | 2.0000 | 374,260 | 374260.27 | 379,458 | 1.0139 |
| 30 | 1 | 1 | 1.0000 | 187,130 | 187130.14 | 189,729 | 1.0139 |
| 60 | 0 | 1 | 0.5000 | 187,130 | 93565.07 | 94,865 | 1.0139 |
| 365 | 0 | 1 | 0.0822 | 187,130 | 15380.56 | 15,594 | 1.0139 |

They differ when:
1. always, on average, by the factor 365/360 = 1.0139 (steady-state is the larger), because a year has 12.1667 30-day blocks, not 12;
2. for e > 30, in the single block that contains a charge: the steady-state number understates that month by a factor e/30 x 360/365 (about 2 at e = 60, about 12 at e = 365). A covenant that is tested per month sees the full per-invoice charge in that month;
3. for e < 30 they differ by the same 365/360 factor only (2 charges every block at e = 15).
At e = 30 and e = 15 the dated profile is the same every month and differs from the steady state only by the 365/360 factor. The steady-state figure is the right one for an annualised funding-cost estimate; the dated profile is the right one for a month-by-month covenant test.
(With r2 and e = 30 the dated charge is 187,130 fen every block against a steady-state 189,729: 2,599 fen.)

## 7. Rule 7: pro-forma extra debt

Definition. Working capital tied up by the extension in steady state: a stock, in fen, equal to delta days of sales:

    extra debt = F x delta / e

Independent of H and of r. Derivation: with invoices every e days the supplier carries delta extra days of receivables, and sales run at F / e per day. At e = 30:
42,000,000 x 15 / 30 = 21,000,000 fen (CNY 210,000.00). Values for e = 15 / 30 / 60 / 365 are in the table in part 6: 42,000,000 / 21,000,000 / 10,500,000 / 1,726,027 fen
(the last exact value is 126,000,000/73 = 1,726,027.40 fen, posted 1,726,027). Check: extra debt x r = annual funding cost, which is what part 6 computes
(the identity table above).

## 8. Rule 8: early-pay break-even cost share for invoice financing

Definition. For principal P financed n days with the golden invoice-financing tariff (7.8% a year, 0.25% fee per 30-day period, period p = 30):

    k      = max(1, ceil(n / p))                       whole billed periods
    interest = post(P x 780/10000 x 30 x k / 365)
    period fees = post(P x 25/10000 x k)
    upfront = post(P x u)                              once, u = upfront fee rate
    T(n)   = interest + period fees + upfront           = finance_invoice_charges(P, n) + upfront_fee(P)
    c(n)   = T(n) / P                                  cost share of principal
    d*     = c / (1 + c) = T / (P + T)                 break-even discount

Interest and the per-period fee are billed per whole period; the upfront fee is charged ONCE however many periods run. P = 10,000,000 fen (CNY 100,000.00).
Each component is posted to the fen separately (as the ledger posts charges), and c is the posted total over P.
Compare the discount d with d*: an early-pay discount at or above d* costs the supplier more than borrowing.

Upfront fee 0 bp (charged once).

| n | k = max(1, ceil(n/30)) | interest (fen) | period fees (fen) | upfront (fen) | total charges (fen) | c(n) | d* = c/(1+c) |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 64,110 | 25,000 | 0 | 89,110 | 0.891100% | 0.883230% |
| 29 | 1 | 64,110 | 25,000 | 0 | 89,110 | 0.891100% | 0.883230% |
| 30 | 1 | 64,110 | 25,000 | 0 | 89,110 | 0.891100% | 0.883230% |
| 31 | 2 | 128,219 | 50,000 | 0 | 178,219 | 1.782190% | 1.750984% |
| 59 | 2 | 128,219 | 50,000 | 0 | 178,219 | 1.782190% | 1.750984% |
| 60 | 2 | 128,219 | 50,000 | 0 | 178,219 | 1.782190% | 1.750984% |
| 61 | 3 | 192,329 | 75,000 | 0 | 267,329 | 2.673290% | 2.603686% |
| 89 | 3 | 192,329 | 75,000 | 0 | 267,329 | 2.673290% | 2.603686% |
| 90 | 3 | 192,329 | 75,000 | 0 | 267,329 | 2.673290% | 2.603686% |
| 91 | 4 | 256,438 | 100,000 | 0 | 356,438 | 3.564380% | 3.441705% |

Upfront fee 100 bp (charged once).

| n | k = max(1, ceil(n/30)) | interest (fen) | period fees (fen) | upfront (fen) | total charges (fen) | c(n) | d* = c/(1+c) |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 64,110 | 25,000 | 100,000 | 189,110 | 1.891100% | 1.856001% |
| 29 | 1 | 64,110 | 25,000 | 100,000 | 189,110 | 1.891100% | 1.856001% |
| 30 | 1 | 64,110 | 25,000 | 100,000 | 189,110 | 1.891100% | 1.856001% |
| 31 | 2 | 128,219 | 50,000 | 100,000 | 278,219 | 2.782190% | 2.706879% |
| 59 | 2 | 128,219 | 50,000 | 100,000 | 278,219 | 2.782190% | 2.706879% |
| 60 | 2 | 128,219 | 50,000 | 100,000 | 278,219 | 2.782190% | 2.706879% |
| 61 | 3 | 192,329 | 75,000 | 100,000 | 367,329 | 3.673290% | 3.543140% |
| 89 | 3 | 192,329 | 75,000 | 100,000 | 367,329 | 3.673290% | 3.543140% |
| 90 | 3 | 192,329 | 75,000 | 100,000 | 367,329 | 3.673290% | 3.543140% |
| 91 | 4 | 256,438 | 100,000 | 100,000 | 456,438 | 4.564380% | 4.365138% |

In both fee cases the upfront fee enters T exactly once: the 1% fee adds 100,000 fen to T(n) at every n (c(n) rises by exactly 1.000000 percentage point),
and the d* column rises by 0.972771 / 0.955895 / 0.939454 / 0.923433 percentage points at k = 1 / 2 / 3 / 4 because d* = T/(P+T) is concave in T.
The fee periods step at n = 31, 61, 91 (k changes), and are flat inside 1..30, 31..60, 61..90.

Golden check (no upfront fee, the current golden displays 0.8832% / 1.751% / 2.6037%):

| n (period count k) | d* with no upfront fee, 4 dp | d* exact (no posting), 6 dp |
|---|---|---|
| 30 (k=1) | 0.8832% | 0.883226% |
| 60 (k=2) | 1.7510% | 1.750986% |
| 90 (k=3) | 2.6037% | 2.603684% |

## 9. Golden numbers under rules 1 to 8 (derived, before looking at the code)

Using today = 0, H = 365, golden anchor 2, face 42,000,000, delta = 15, marginal rate r2:

| basis | N | exact (fen) | posted once | posted once (CNY) |
|---|---|---|---|---|
| window count, today=0, H=365, anchor s0=2 | 13 | 177586500/73 | 2,432,692 | ¥24,326.92 |
| floor(H/every) count (phase-blind) | 12 | 163926000/73 | 2,245,562 | ¥22,455.62 |
| difference (13 minus 12 invoices) | 1 | 13660500/73 | 187,130 | |

Rules 1 and 2 give 13 invoices. The floor(H/every) = 12 count reproduces the golden file's 12-month committed cost exactly (2,245,562 fen = `extension_committed_12m`,
and 187,130 fen = `extension_committed_per_invoice` per invoice), which shows that the golden file counts 12 and that rounding once is the golden posting basis.
Under the window rules, the golden 12-month committed cost, and everything computed from it, becomes 13 invoices: 2,432,692 fen, +187,130 fen. Part 11 lists what depends on it.
If the owner wants the golden numbers to stay at 12 at H = 365, today = 0, the rule has to say so explicitly (for example by anchoring the window to the first issue day
instead of today); as written, rules 1 and 2 give 13.
The break-even values 0.8832% / 1.751% / 2.6037% do not depend on the invoice count and have no upfront fee: they are unchanged.

## 10. Objections (derived under the rules anyway)

1. Rule 1 values by ISSUE day, but the money moves at collection and across the delta days. A gain whose invoice is issued inside W but collected outside it is counted in full inside W.
   Counterexample: firm +1% effective day 362, H = 365. The invoice issued on day 362 is collected on day 362 + 45 = 407, outside W. Rule 1 counts a gain of -420,000 fen, so the counted
   total is 600,000 - 420,000 = 180,000 and the cap of 500,000 passes (row "from day 362" in part 5). Cash received inside W from the price adjustment is 0, and a cash-basis count would be
   600,000, a breach by 100,000 fen. This is F-FIN-01 shifted by 45 days to the window edge. Likewise an extension on the day-362 invoice is charged 172,603 fen (r1) inside W although its funding days
   (from day 407 to day 422) are all after day 365. The same argument runs the other way for invoices issued before today whose collection is inside W (they count 0 under rule 1). A consistent alternative: value dated cash movements
   (collection day = issue day + terms) in W, or at least forbid gains from offsetting when collection is outside W.
2. Rule 6's steady-state "annual / 12" (365-day year over 12 months) overstates a 30-day month by 365/360 = 1.39% and hides the lumpiness of rare invoices (part 6.1): at e = 365 and r1 the steady-state
   figure is 14,384 fen while the one month that carries the charge pays 172,603 fen, 12.0 times as much. A covenant tested monthly can fail in that month while the pro-forma passes.
3. Rule 3 posts once but rule 4 posts per invoice. The two are consistent only when the per-invoice price adjustment is an integer number of fen; for faces with fractional fen products the rules diverge by at most N/2 fen. The golden values are integers so no number here depends on it.
4. Rule 7 is a time-average over one invoice interval, not a peak. For one invoice extended by 15 days (F = 42,000,000, e = 30) the extra receivable is the full 42,000,000 fen for 15 days; averaged over the 30-day interval that is 21,000,000 fen, which is what the rule reports. A leverage covenant tested on the peak day sees 42,000,000, twice the pro-forma stock. The derivation uses the rule as given (steady state, an average).

