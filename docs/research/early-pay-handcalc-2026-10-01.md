# Early-pay rule (ADR-0007): independent hand derivation, 1 Oct 2026

Derived from `fixtures/scenarios/golden_sme.json`, ARCHITECTURE "Engine semantics", ADR-0002 and the ADR text only,
before reading the verifier code. Money in fen unless shown as yuan. Rounding: half-up once per posting.

## Inputs

- Cash 400,000.00. Floor 300,000.00 (mandate `min_cash_fen`). Horizon 120.
- Flows: day 12 payroll -340,000; day 20 supplier -120,000; day 47 bill -100,000.
- RCV-A face 420,000, issued day -13, 45 terms, due day 32. Recurring invoice 420,000 issued day 2, due day 47
  (then day 32 issue / day 77 due, ...). Early-pay lead time 2: "day 2" settlement is 30 days early.
- Line: 6.40% simple, actual/365, limit 150,000, lead 0, interest posted at repayment.
- Invoice financing (IF): advance 80% (max 336,000 on RCV-A), 7.80% p.a. plus 25 bp fee, both per whole 30-day
  period, lead 3, repaid on receipt. Period count is taken from advance arrival (day 3) to repayment: the ADR's
  1,871.30 for 210,000 over day 3 to 32 (29 days) is k = 1; counting from request day 0 (32 days) would be k = 2.
- Per-period IF cost share: 0.078 x 30/365 + 0.0025 = 117/18250 + 1/400 = **1301/146000** = 0.891096%.

## 2a. Break-even d*(n), IF as marginal source

c(n) = k x 1301/146000, k = ceil(n/30). d* = c/(1+c) = 1301k / (146000 + 1301k).

| n (days early) | k | c | d* exact | d* % |
| --- | --- | --- | --- | --- |
| 3 | 1 | 1301/146000 | 1301/147301 | 0.883226 |
| 30 | 1 | 1301/146000 | 1301/147301 | 0.883226 |
| 31 | 2 | 1301/73000 | 1301/74301 | 1.750986 |
| 60 | 2 | 1301/73000 | 1301/74301 | 1.750986 |
| 90 | 3 | 3903/146000 | 3903/149903 | 2.603684 |

n = 3 and 30 share a limit because IF bills a whole period. The 5 bp floor of d* is 85 bp for k = 1.

## 2b. C0 on the golden books

Need profile without funding (cash minus floor): day 12 cash 60,000 (short 240,000); day 20 cash -60,000
(short 360,000); day 32 RCV-A +420,000 clears it. Line is cheaper per yuan than IF (0.561% vs 0.891% for ~30
days), so line first (150,000), IF takes the other 210,000 (the day-3 advance still lands before the day-12 short).

- Line 150,000 x 640/10000 x 32/365 = 15,000,000 x 0.064 x 32/365 = 30,720,000/365 = 84,164.38 -> **84,164**
- IF 210,000, k = 1: interest 21,000,000 x 0.078 x 30/365 = 49,140,000/365 = 134,630.14 -> 134,630; fee
  21,000,000 x 0.0025 = 52,500; total **187,130**
- **C0 = 84,164 + 187,130 = 271,294 fen = 2,712.94.** Agrees with the ADR.

Day 32 check: cash 300,000 + 420,000 - 150,000 - 84.16 - 210,000 - 1,871.30 = 357,044; day 47 the recurring receipt
(420,000) covers the 100,000 bill. Floor met every day.

## 2c. ADR table rows

| Row | Offer | Hand arithmetic | C1 | Expected |
| --- | --- | --- | --- | --- |
| 1 | whole 420,000 at 0.85%, day 2 | disc 42,000,000 x 0.0085 = 357,000; net 41,643,000. Cash day 20 = 400,000+416,430-340,000-120,000 = 356,430 >= 300,000, no funding | 357,000 = 3,570.00 | T1 pass (85 bp < 88.32 bp); T3 fail (3,570.00 >= 2,712.94): `EARLY_PAY_DEARER_THAN_PLAN`, COUNTER |
| 2 | whole at 0.64% | 42,000,000 x 0.0064 = 268,800 | 2,688.00 | pass all three; accept |
| 3 | whole at 0.65% | 42,000,000 x 0.0065 = 273,000 | 2,730.00 | T3 fail, COUNTER |
| 4 | 211,900 at 0.85%, day 2 | disc 21,190,000 x 0.0085 = 180,115 (1,801.15); net 21,009,885. Cash day 12 270,098.85, day 20 150,098.85, short 149,901.15 (<= line 150,000); RCV-A residual 208,100 pays day 32. Line 14,990,115 x 0.064 x 32/365 = 30,699,755.52/365 = 84,108.9 -> 84,109 | 180,115 + 84,109 = 264,224 = 2,642.24 | T1 pass, T3 pass (2,642.24 < 2,712.94); accept |
| 5 | any d > 0, cash never near floor | C0 = 0 (cash >= 760,000 means no short) | disc > 0 | `EARLY_PAY_NOT_NEEDED` |
| 6 | whole at 0.89%, 30 early | 0.89% >= 0.883226% | 3,738.00 | `DISCOUNT_ABOVE_BREAK_EVEN` (T3 would also fail) |

All six: AGREE with the ADR's own figures (my rows reproduce them to the fen).

## 2d. Additional cases

### Break-even neighbours, n = 30, whole invoice, d* = 88.3226 bp

| d | disc | T1 | T3 (C1 vs 2,712.94) | Caught by |
| --- | --- | --- | --- | --- |
| 87 bp | 3,654.00 | pass | fail | test 3 only |
| 88 bp | 3,696.00 | pass (88 < 88.3226) | fail | test 3 only |
| 89 bp | 3,738.00 | fail | fail | test 1 (first screen) |

88 bp is the last whole bp passing the first screen. Every whole-bp d on the whole invoice that passes T1 is
caught by T3: the whole invoice at d needs d x 420,000 < 2,712.94, i.e. d < 0.6459% (64 bp).

### 3 days early (settle day 29, due day 32)

T1: n = 3, k = 1, limit 1301/147301 = 0.8832%, same as 30 days. 85 bp passes T1.
Cash for 3 days: early cash lands day 29 instead of 32, so funding is still needed from day 12 to day 29
(day-20 short 360,000), 3 days shorter. Plan: line 150,000 to day 29, IF 210,000 on RCV-A (day 3 to 29, 26 days, k = 1).
- Line: 15,000,000 x 0.064 x 29/365 = 27,840,000/365 = 76,273.97 -> 76,274
- IF: 187,130 (unchanged: whole period)
- C1(0.85%) = 357,000 + 76,274 + 187,130 = **620,404 = 6,204.04** > 2,712.94: T3 fail, `EARLY_PAY_DEARER_THAN_PLAN`.
- C1(1 bp, 0.01%) = 4,200 + 76,274 + 187,130 = **267,604 = 2,676.04** < 2,712.94: passes T3. (Saving is only the line's
  3 days, 84,164 - 76,274 = 7,890 fen; the IF period does not shrink. So the discount must be below 78.90.)
Router uncertainty: assumes the router may finance RCV-A that is itself being early-paid. If it cannot, the
need (360,000 vs line 150,000) is uncurable with the offer, the C1 plan is inadmissible, T2/T3 are not evaluated
and the reserve predicate reports the breach. State both candidates; the implementation decides.

### 90 days early at 1.2% (due day 92, terms_days 105, settle day 2)

T1: n = 90, k = 3, limit 3903/149903 = 2.6037%. 1.2% passes (the old fixed limit 0.8832% wrongly countered it).

C0, books with RCV-A due day 92: cash minus floor: day 12 short 240,000; day 20 short 360,000; day 47 cash =
400-340-120+420-100 = 260,000 (recurring invoice due day 47), short 40,000; day 77 the recurring invoice (issued
day 32) pays 420,000, cured. Funding must be drawn day 0. IF is repaid only at RCV-A's due day 92, so arrival day 3 to 92
= 89 days, **k = 3** (the cost of carrying the gap is three periods, not one).
- IF 210,000, k = 3: interest 21,000,000 x 0.078 x 90/365 = 147,420,000/365 -> 403,890.41 -> 403,890; fee 52,500 x 3 = 157,500; total **561,390**
  (check: 3 x 187,130 = 561,390).
- Line 150,000 only needs to stay to day 47: after day 47 the IF's 210,000 alone covers the 40,000 short.
  15,000,000 x 0.064 x 47/365 = 45,120,000/365 = 123,616.44 -> **123,616**.
- **C0 = 561,390 + 123,616 = 685,006 = 6,850.06.**
Candidate if the router holds the line to day 77 instead: line 15,000,000 x 0.064 x 77/365 = 202,521 (2,025.21);
C0 = 763,911 = 7,639.11. 6,850.06 is the lower bound (IF >= 210,000 is forced by the line cap; IF cost is fixed by
k = 3; the line needs at least day 47).
C1: whole invoice at 1.2% day 2: disc 42,000,000 x 0.012 = 504,000; net 41,496,000; cash day 20 = 354,960
>= 300,000, day 47 fine. No funding: **C1 = 504,000 = 5,040.00**.
T3: 5,040.00 < 6,850.06 (and < 7,639.11): passes whichever C0. Verdict: accept (no early-pay fault).

### 0 days early

Settle day 32 = due day 32, n = 0: not an early payment; no test applies, no early-pay code.

### No cash need

Cash 1,000,000.00 (100,000,000 fen): nothing is ever short, C0 = 0. Whole invoice at 0.5%: disc 210,000 = 2,100.00 > 0.
T1: 50 bp < 88.32 bp pass. T2 fail: `EARLY_PAY_NOT_NEEDED`. At any positive d: C1 = d x 420,000 > 0 = C0.
(T3 also holds by letter: C1 >= C0; the ADR does not say whether both codes are reported.)

### Partial gap: 100,000 of RCV-A at 0.5%, day 2

Discount 10,000,000 x 0.005 = 50,000 (500.00); net 9,950,000. Residual RCV-A 320,000, still due day 32.
Cash: day 2 499,500; day 12 159,500 (short 140,500); day 20 39,500 (short 260,500); day 32 +320,000.
Funding 260,500: line 150,000 (84,164 as before) + IF 110,500 on the residual (<= 80% x 320,000 = 256,000):
- IF interest 11,050,000 x 0.078 x 30/365 = 25,857,000/365 -> 70,841.10 -> 70,841; fee 11,050,000 x 0.0025 = 27,625; total 98,466
- **C1 = 50,000 + 84,164 + 98,466 = 232,630 = 2,326.30** < C0 2,712.94. T1 pass (50 bp), T3 pass: accept.
Router uncertainty: sizing the IF to exactly the gap (110,500) is assumed, as in the golden plan; a router that
over-advanced would cost more.
