# DSCR for bullet term loans: independent hand calculation (ADR-0008)

Date 2026-10-01. Checker: independent agent. Derived from ADR-0008, ADR-0002, ARCHITECTURE "Engine semantics" and
`golden_sme.json` only, BEFORE reading `trajectory.py` or `test_dscr_bullet_term.py`. All money in integer fen.

## Inputs (fixture)

| Item | Value |
| --- | --- |
| Monthly EBITDA | 9,000,000 (¥90,000) |
| Existing debt D-EQUIP service | 4,500,000 a month |
| FAC-GGL | 500 bp, 12 months, lead 21 days, BULLET, counts in DS and leverage, limit 50,000,000 |
| FAC-LINE | 640 bp, BULLET, no term_months, lead 0 (revolver: out of scope of the rule) |
| FAC-ETL | 560 bp, 36 months, AMORTISING (out of scope of the rule) |
| Covenant | EBITDA / DS >= 1.25, i.e. DS <= 7,200,000 |

Conventions: month m = days 30(m-1)+1 .. 30m. Arrival day = request day + lead time. Repayment day = arrival + 30 x term
(so 360 days for 12 months). Interest = round_half_up(principal x bp/10000 x days/365), once (ADR-0002). Level amount =
floor((principal + interest) / term); remainder (< term fen) goes to the last month of the term.

## 2a. 500,000 yuan on FAC-GGL, requested day 0

- Arrival day 0 + 21 = day 21 (month 1: days 1-30). Repayment day 21 + 360 = 381 (month 13: days 361-390).
- Interest = 50,000,000 x 0.05 x 360/365 = 900,000,000/365 = 2,465,753.42 -> **2,465,753 fen** (¥24,657.53).
- Total to spread = 52,465,753. 52,465,753 / 12 = 4,372,146.08. Level **4,372,146**; 12 x 4,372,146 = 52,465,752; remainder 1 fen.
- Months carrying it: months 1 to 12 (the 12 months starting with the arrival month). Month 12 carries 4,372,147.
- Debt service: months 1-11 = 4,500,000 + 4,372,146 = **8,872,146**; month 12 = **8,872,147**; month 13 on = 4,500,000.
- DSCR months 1-11 = 9,000,000 / 8,872,146 = 1.0144107 -> **1.014**. Month 12 = 9,000,000 / 8,872,147 = 1.0144106 -> **1.014**.
  Month 13 on = 9,000,000 / 4,500,000 = 2.000.
- 1.25x covenant: **fails in months 1 to 12** (needs DS <= 7,200,000; actual 8,872,146).
- Note: with lead 21 the repayment lands in month 13, not month 12 as the ADR's "before" line implies ("1.29x in month 12").
  Month-13 pre-ADR figure = 9,000,000 / (4,500,000 + 2,465,753) = 1.292. Immaterial to the rule, but the ADR text is loose.

## 2b. Same loan, 6 months at 5%

- Arrival day 21 (month 1). Repayment day 21 + 180 = 201 (month 7: days 181-210).
- Interest = 50,000,000 x 0.05 x 180/365 = 450,000,000/365 = 1,232,876.71 -> **1,232,877**.
- Total = 51,232,877. / 6 = 8,538,812.83. Level **8,538,812**; 6 x 8,538,812 = 51,232,872; remainder 5. Month 6 carries 8,538,817.
- Months 1-5 DS = 4,500,000 + 8,538,812 = **13,038,812**; month 6 = **13,038,817**; month 7 on 4,500,000.
- DSCR months 1-5 = 9,000,000 / 13,038,812 = 0.690247 -> **0.690**; month 6 = 9,000,000 / 13,038,817 = 0.690247 -> **0.690**.
- Fails 1.25x in months 1 to 6.

## 2c. 360,000 yuan on FAC-GGL (12 months)

- Interest = 36,000,000 x 0.05 x 360/365 = 648,000,000/365 = 1,775,342.47 -> **1,775,342**.
- Total = 37,775,342. / 12 = 3,147,945.17. Level **3,147,945**; 12 x 3,147,945 = 37,775,340; remainder 2 (month 12 carries 3,147,947).
- Month 1 DS = 4,500,000 + 3,147,945 = **7,647,945**. DSCR = 9,000,000 / 7,647,945 = 1.17679 -> **1.18** (1.177 to 3 dp).
- Headroom vs 1.25 = 1.17679 - 1.25 = -0.07321 -> **-0.07**.
- Answer to the question: **yes, 9,000,000 / 7,647,945 is what I get.** Still a breach (needs DS <= 7,200,000, level <= 2,700,000).

## 2d. Two lots: 200,000 yuan arriving in month 1, 100,000 yuan arriving in month 3

Interest depends only on the term (360 days), not on the arrival day.

| Lot | Principal | Interest (half-up) | Total | Level | Remainder | Months carried |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 20,000,000 | 20,000,000 x 0.05 x 360/365 = 986,301.37 -> 986,301 | 20,986,301 | 1,748,858 (12 x = 20,986,296) | 5 | 1-12; month 12 = 1,748,863 |
| 2 | 10,000,000 | 10,000,000 x 0.05 x 360/365 = 493,150.68 -> 493,151 | 10,493,151 | 874,429 (12 x = 10,493,148) | 3 | 3-14; month 14 = 874,432 |

| Month | Existing | Lot 1 | Lot 2 | Debt service |
| --- | --- | --- | --- | --- |
| 1, 2 | 4,500,000 | 1,748,858 | 0 | **6,248,858** |
| 3 to 11 | 4,500,000 | 1,748,858 | 874,429 | **7,123,287** |
| 12 | 4,500,000 | 1,748,863 | 874,429 | **7,123,292** |
| 13 | 4,500,000 | 0 | 874,429 | **5,374,429** |
| 14 | 4,500,000 | 0 | 874,432 | **5,374,432** |
| 15 | 4,500,000 | 0 | 0 | **4,500,000** |

DSCR: months 1-2 = 1.440 (9,000,000 / 6,248,858 = 1.44026); months 3-11 = 1.264 (9,000,000 / 7,123,287 = 1.26349), so a
1.25x covenant is met; month 12 = 1.26348; month 13-14 = 1.675.

## 2e. Loan maturing after a 90-day horizon

500,000 yuan on FAC-GGL, requested day 0, horizon 90 days (months 1-3 only). The loan arrives day 21 and repays day 381, far
outside. Months 1, 2, 3 each carry the level **4,372,146**: DS **8,872,146** each, DSCR **1.014** each. Not 2.00x.

## 2f. Annual cross-check for case 2a

- 12 months EBITDA = 12 x 9,000,000 = 108,000,000.
- 12 months DS = 12 x 4,500,000 + 52,465,753 = 54,000,000 + 52,465,753 = 106,465,753.
- Annual ratio = 108,000,000 / 106,465,753 = 1.0144106. Monthly (months 1-11) = 1.0144107. They differ by 1e-7 only
  because of the 1 fen remainder in month 12. This is the audit's "about 1.01x on an annual basis".

## 2g. Spread interest as well as principal? Alternatives

I **agree** with the ADR. Reasons: the covenant text is "principal + interest"; a level accrual-style charge makes the annual and the
monthly reading agree (2f); an amortising facility already carries its interest month by month, so interest in one lump
would treat a bullet differently from every other term loan; and a single month spike distorts one month's DSCR (it
would sit in month 13, outside the first twelve, so an annual look at months 1-12 would not even contain it).

Alternative (principal only spread, interest stays in the repayment month 13):

| Month | Principal share | DS | DSCR |
| --- | --- | --- | --- |
| 1-11 | floor(50,000,000 / 12) = 4,166,666 | 8,666,666 | 9,000,000 / 8,666,666 = 1.03846 -> **1.038** |
| 12 | 4,166,666 + remainder 8 = 4,166,674 | 8,666,674 | 1.03846 -> **1.038** |
| 13 | 0 principal + interest 2,465,753 | 6,965,753 | 9,000,000 / 6,965,753 = 1.29200 -> **1.292** |

Both choices breach in months 1 to 12 for this loan, so the decision does not change the case-a outcome. Under the
alternative a smaller loan could pass months 1-12 (principal share only) and the interest month would look better than
the true cost; the ADR's choice is the more conservative one for the lender-facing test, by about 0.024x in months 1-11.

## Result of testing the implementation against the figures above

Test file: `services/api/tests/financial/test_dscr_bullet_handcalc.py` (8 tests, all hard-coded from this note).

| Case | Hand figure | Implementation | Verdict |
| --- | --- | --- | --- |
| 2a interest | 2,465,753 | 2,465,753 | AGREE |
| 2a DS months 1-11 / 12 / 13 | 8,872,146 / 8,872,147 / 4,500,000 | same | AGREE |
| 2a DSCR, covenant | 1.014, fails months 1-12, passes 13 | same (observed "1.01x" in the report) | AGREE |
| 2b interest, level, DS | 1,232,877; 8,538,812 (r5); 13,038,812 months 1-5, 13,038,817 month 6; 0.690 | same | AGREE |
| 2c level, month-1 DS, DSCR, headroom | 3,147,945; 7,647,945; 1.177 -> 1.18; -0.07 | same | AGREE (9,000,000 / 7,647,945 confirmed) |
| 2d months 1-15 | 6,248,858 x2; 7,123,287 x9; 7,123,292; 5,374,429; 5,374,432; 4,500,000 | same | AGREE |
| 2e 90-day horizon, months 1-3 | 8,872,146 each | same | AGREE |
| 2f annual | 108,000,000 / 106,465,753 = 1.0144106 | DS sum 106,465,753 | AGREE |
| Boundary 1.25x | rate 0, 32,400,000: DS 7,200,000 passes; +12 fen fails | same | AGREE |
| 2g design choice | agree with spreading interest | n/a | AGREE (judgement) |

One wording point in the ADR (not a calculation error): the "before" line says "1.29x in the twelfth [month]". With the 21-day
lead the repayment is on day 381, which is month 13, so the old 1.29x was in month 13. The engine also puts it in month 13.

## Cases the rule handles that the ADR does not define (what the code does)

Observed by running `project()` on the golden books (probe test, not committed).

| Case | Code behaviour | Concern |
| --- | --- | --- |
| Early repayment of a term loan by an explicit `repay_day` on the DRAW (500,000 on FAC-GGL, repay day 60) | Interest for the actual 39 days (267,123); principal + interest 50,267,123 still spread over all 12 term months (4,188,926 a month). Cash leaves in month 2, DSCR keeps carrying it through month 12 | Debt service is charged after the debt is gone. Conservative but not what the ADR says ("over the months of its term" is the contract term, not the holding period). Needs a decision. |
| Repayment later than maturity (repay day 500) | Interest for 479 days (3,280,822) spread over 12 months; repayment lands in month 17 | Level amount is spread over the term but the debt outlives it; months 13-17 carry nothing. |
| REPAY action on a term bullet draw | `FundingActionError` "exceeds its open draws" (the draw already has a fixed repay day) | Acceptable, but it means early repayment can only be expressed through `repay_day` on the DRAW. |
| Credit line that has `term_months` (FAC-LINE with 12) | A DRAW is treated as a bullet term lot: repaid at arrival + 360 and spread (level 1,328,904 months 1-11; r1 in 12). With an explicit `repay_day=32` it is spread over 12 months (1,257,013 a month), where the same line without `term_months` posts interest in month 2 only | `_is_bullet_term` does not exclude `CREDIT_LINE`, but the carried-balance branch does (line ~603). ADR says a line is BULLET with *no* term_months, so it is technically undefined, but the two code paths disagree. |
| Carried balance on a term bullet (GGL `drawn_fen` 10,000,000, no actions) | Treated as a lot arriving day 0, repaid at day 360; interest 493,151; spread months 1-12 (874,429, month 12 874,432) | Overstates the service when part of the term has already elapsed (the same "can only overstate" as interest). Conservative. |
| Carried balance on a credit line that has `term_months` | Not spread (excluded by kind); interest posts in month 2 (28,055) as a plain line | Inconsistent with a draw on the same line (above). |
| Facility with `counts_in_debt_service` false | Not spread; nothing added (0 each month), interest still posted to cash | Consistent with the ADR. |
| Upfront fee | Included in the level amount (covered by the existing test) | Fine. |
| Horizon shorter than the term | The engine already extends the horizon to the last repayment + 1, so a 90-day look still shows 13 months and the term lot is never cut off | The ADR's "months beyond the horizon are not shown" clause is only live for a lot with no repay day (none exists for a term bullet). |
