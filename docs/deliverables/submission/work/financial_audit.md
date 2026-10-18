# Financial audit of the technical document

Reviewer's working file for the 2026 Fintechathon submission (International AI Track, Topic E). It audits every headline
money, rate, day and ratio figure in `docs/deliverables/technical_document.md` (and the figures it shares with
`execution_evidence.md`, `demo_video_script.md` and `deck_outline.md`) against two things:

- an **independent recomputation** (`work/fin/independent.py`), which is pure Python and reads only the demo books and
  mandate (`fixtures/scenarios/golden_sme.json`, `golden_sme.events.json`). It imports nothing from the application and
  reads no golden value;
- the **engine**, called in process (`work/fin/engine_probe.py`, `engine_probe2.py`, `engine_probe3.py`): the router, the
  verifier, the projection, capex, and the demo story replayed day by day through the API with FastAPI's TestClient
  (`DEMO_MODE=1`, `TERMSLEDGER_NO_DOTENV=1`, `DATABASE_URL=memory`, `LLM_MODE=cache`; no server, no port, no live model).

`work/fin/compare.py` compares the two, figure by figure: **39 of 39 match to the fen** (`work/fin/compare.csv`). The engine
does its arithmetic correctly. The findings below are about **what the figures mean**: which convention produced them,
whether the words around them say so, and where a figure is stale or the wrong one for its claim.

All amounts are **CNY** (the document's ¥). Day 0 is 1 Oct 2026, the books' `as_of`. "Day d" means the closing cash of day d.

Reproduce (from the repo root):

```
DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe.py
DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe2.py
DEMO_MODE=1 TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache PYTHONUTF8=1 uv run --project services/api python docs/deliverables/submission/work/fin/engine_probe3.py
python -I docs/deliverables/submission/work/fin/independent.py
python -I docs/deliverables/submission/work/fin/compare.py
```

## 1. What needs changing, in order of importance

| # | Where | Problem | Verdict |
| --- | --- | --- | --- |
| 1 | Table 7, Option B row (l. 560) | "Funding —" with "lowest cash ¥300,000, no breach". Without funding, Option B's books fall to −¥105,000 on day 30 and ¥215,000 on day 47. They need the router's plan: credit line ¥90,000 (day 0 to 57) plus invoice financing ¥315,000 on RCV-A (day 3 to 32), **CNY 3,706.46**, which is ¥592.53 more than the standing plan. "≈ ¥0 net" is the forward-concession figure only. | **WRONG** |
| 2 | §01 demo story step 3 (l. 99), §06 walkthrough (l. 1204) | "¥160,000 is still unpaid and cash is heading under the reserve" leaves out the cause. The day-34 breach comes from the month-2 payroll of **CNY 200,000 on day 42**, which the bookkeeper adds on day 25 (`golden_sme.events.json`). Even if the ¥160,000 had arrived on day 32 and the line had been repaid, cash would still close at ¥111,964.01 on day 42. The document never mentions this payroll. | **AMBIGUOUS (material)** |
| 3 | §01 l. 58–62 | "every month" (the invoices are issued every 30 days); "¥210,000 … permanently" (an average); "¥24,326.92 a year" (13 invoices dated by issue day, not a year's cash cost); "funding that on … invoice financing costs ¥1,871.30" (a pricing rate: the platform advances at most 80% and bills whole periods). Each figure is right; the words claim more than the figures. | **AMBIGUOUS** |
| 4 | §03 item 8 (l. 592–598), limitations (l. 1036) | The lease is selected only because the screen is run on the untouched books, which already breach the reserve on days 12–31. Once FLOW's ¥3,113.93 plan is paid on day 32, the engine itself rejects the lease as well: cash is **¥297,462.58 on day 40**, ¥2,537.42 below the reserve. "About ¥39,000 less" is undiscounted interest across a 36- and a 48-month tenor. At the 10% hurdle the gap in present value is **CNY 7,493.45**. | **AMBIGUOUS (material)** |
| 5 | `execution_evidence.md` l. 29, 92–104; `demo_video_script.md` l. 38, 40, 59–60; `deck_outline.md` l. 44 | Stale demo figures from before the 16 Oct ¥10,000 rounding: ¥257,200 face, ¥255,013.80 receipt, ¥162,800 late, ¥149,986.20 line, ¥1,236.05 interest, Option A **¥3,027.77**. Today's engine and the technical document give ¥260,000, ¥257,790.00, ¥160,000.00, ¥147,210.00, ¥1,213.17 and **¥3,035.99**. | **WRONG (stale)** |
| 6 | Table 7 row 1 (l. 553) | "¥405,000 short, days 12–31". ¥405,000 is the peak shortfall, on days 30–31. Day 12 is ¥240,000 short. | AMBIGUOUS |
| 7 | Data (l. 293–296), Table 6 (l. 312) | The books as described cannot reproduce days 42, 47 or 60. Missing: the recurring ¥420,000 invoice (issued day 2, then every 30 days, 45-day terms), the ¥100,000 operating bill on day 47, the loan's ¥1,500,000 principal at 0%, EBITDA of ¥90,000 a month, the payroll added on day 25, and the 80% advance rate on invoice financing. | AMBIGUOUS |
| 8 | Table 7 columns | "Funding cost" and "Future concessions" overlap. The EX01 cure pays for the cash effect of the first invoice's 15 extra days, which ¥24,326.92 already prices (¥1,871.30 of it). They must not be added. | AMBIGUOUS |
| 9 | `JUDGING_QUESTIONS.md` l. 132–133, 160–161 | "DSCR low 2.00×, leverage high 1.35×" are on the untouched books (cash −¥105,000). With FLOW's standing plan they are DSCR 1.87× (month 2) and leverage 1.72× (month 1). | AMBIGUOUS |
| 10 | Appendix D (l. 1124–1125), §03 item 3 (l. 511) | "Marginal cost of funds: … able to carry a *permanent* need" is also used for a 30-day early-payment test. "Break-even discount: the largest … discount cheaper": 0.8832% is the threshold, not a discount on offer. The counter's rate is 0.85%. | AMBIGUOUS (minor) |

Outside the deliverables, `docs/adr/0002-rounding.md` and `docs/adr/0003-fixture-timeline-and-funding-timing.md` still show
the spec-v2 figures: plan ¥2,712.94, counter A ¥2,641.94, a ¥45,040 shortfall, a ¥802.70 cure, and "¥210,000 advance costs
¥1,871.30". `JUDGING_QUESTIONS.md` l. 58 gives an ¥85,000 day-47 shortfall for the pasted chat request. That figure matches a
terms-only reading (¥315,000 − ¥100,000 = ¥215,000 on day 47), not the full package's ¥90,040. Each of these is worth a one-line note, not a
rewrite.

## 2. Conventions in the implementation

| Topic | Convention (where it lives) | Consequence for the headline figures |
| --- | --- | --- |
| Money | Integer fen. Rates in integer bp. Exact `Fraction` until posted. Half-up (四舍五入) to the fen, **once**: when a cash movement posts, or when a valuation is reported (ADR-0002, `app/domain/money.py`). | A plan's cost is the sum of its posted parts: ¥3,113.93 = 841.64 + 1,634.79 + 637.50. A valuation is the exact sum rounded once: ¥24,326.92 = round(13 × 1,871.3014…), which is 2 fen more than 13 × ¥1,871.30 = ¥24,326.90. |
| Days and months | One closing balance per day. Month m = days 30(m−1)+1 … 30m, with day 0 in month 1 (`financial/trajectory.py`). On the clock, "advance to d+1" posts day d's flows. | "Months" in DSCR and leverage are 30-day blocks, not calendar months. |
| Credit line | Actual/365 simple interest per drawn lot, from landing to repayment, posted at repayment (`financial/charges.py`). Every leg is requested on the decision day, so the line is drawn on day 0 even when the cash is needed later (ADR-0003). It is repaid on the first receipt day after which cash stays at or above the reserve. | EX01's line cure is ¥1,468.05 for 62 days. Drawn just in time on day 47 it would cost ¥355.17. |
| Invoice financing | Up to 80% of the invoice's open face, ¥350,000 limit, 3-day lead time. **Interest and the 0.25% fee are both billed in whole 30-day periods**, at least one, posted when the receipt repays the advance. | 29 days held pays 30 days of interest (plan, ¥1,634.79). 10 days held pays a full period (cure, ¥1,782.19). The document says only that "invoice financing bills whole 30-day periods" beside "interest is Actual/365". |
| "All-in rate" | rate + fee × 365/30 = 7.8% + 3.0417% = **10.8417%** simple, no compounding (`if_all_in_rate`). It is a tariff equivalent: the fee is spread as if it accrued daily. | It is the effective cost only for an advance held exactly whole periods. Effective cost of a real advance = all its charges / amount × 365 / days held: 11.22% for the plan's 29 days, 16.7% for 39 days (the "10 days late" stress), 32.5% for the cure's 10 days. |
| Buyer early payment | Discount d posted on the receipt day, 2-day lead time. Annualised d/(1−d) × 365/days early (1.2% for 30 days = 14.78%). | The 1.2% ask passes the 15% APR ceiling but fails break-even. |
| Recurring invoices | ¥420,000 issued on day 2, then **every 30 days** (not monthly), 45-day terms. Assumed paid on the due day: the forecast is not conservative about collections. | 13 issue days fall in a 365-day window (2, 32, …, 362), not 12. |
| Forward concessions | Window W = [today, today + 365). Each invoice is counted on its **issue** day. Terms extension = Σ face × Δdays / 365 × marginal all-in rate, rounded once. A contingent rebate counts at its maximum. Only firm gains offset a cost. An immediate discount is capped separately (1.5%) and is not a forward concession (`financial/concessions.py`). | ¥24,326.92 counts all 13 invoices in full, although the 15 extra days of the last two (issued on days 332 and 362) fall after day 365. |
| Extra receivables | face × Δdays / invoice interval = 420,000 × 15/30 = ¥210,000: a **steady-state average** (`extension_extra_debt`). The real increment is ¥420,000 for 15 days of every 30. | It feeds the DSCR 1.92× and leverage estimates. It is not a balance any facility carries. |
| Annualised cost vs first-year cash | Three readings of the same extension: 13 invoices by issue day **¥24,326.92** (the engine's figure, used against the cap); steady state 210,000 × 10.8417% = **¥22,767.50** a year; cash actually spent in days 0–364 (11 invoices) **¥20,584.32**. If "a year" meant 12 invoices: ¥22,455.62. | The document should name the first reading, not "a year". |
| Is the permanent need fundable on the named facility? | Not as priced. Per invoice the platform can advance at most ¥336,000 of the ¥420,000 peak. Advancing that for the 15 extra days costs one whole period, **¥2,994.08**, which leaves ¥84,000 unfunded. The line cannot carry a recurring need of 15 days in every 30: its 30-day clean-down never happens. | ¥1,871.30 is exactly the cost of one whole-period advance of ¥210,000 (half the face) for 30 days. It is a sound pricing proxy, but not an executable quote. |
| Reserve test | Conservative mode: unconfirmed inflows ignored, overdue receivables dropped. A breach is charged to an offer only where cash is below the floor **and** below the no-offer baseline. | EX01's breach starts on day 47, although the untouched books already breach on days 12–31. |
| Covenants | DSCR = EBITDA_m / DS_m, every projected month. EBITDA is a **fixed ¥90,000** fixture input, not read from the books. DS_m = the existing loan's ¥45,000 (all principal: the fixture's 0% rate) + facility interest and fees posted that month. Bullet principal on the line and on invoice financing is excluded. A bullet term loan is serviced on a level basis (ADR-0008). Leverage = month-end drawn debt / (12 × EBITDA_m). The definitions are the synthetic credit line's covenants (`FAC-LINE-DSCR`, `FAC-LINE-LEV`), repeated in the mandate. | DSCR is a monthly, forward-looking **screening proxy** of a synthetic contractual covenant. It is not the trailing-12-month test on reported accounts that a bank would normally apply. 2.00×/1.35× are the untouched books; with the plan, 1.87×/1.72×. |
| Capex | Annuity payment r/12, rounded half-up. Each month's interest posted. The final payment clears the balance. NPV at the effective monthly rate (1.10)^(1/12) − 1 of +¥22,000 a month, months 4–60, against ¥600,000 in month 0: no residual value, no tax, no maintenance, unlevered. Simple payback. Structures are ranked by **undiscounted** total interest. One structure at a time, no bridge. Loan lands day 14, first instalment day 44; lease lands day 10, first instalment day 40. The lease is modelled as a 7.2% amortising loan with no residual or purchase option. | Comparing undiscounted charges across 36 and 48 months favours the shorter tenor by ¥39,121.18. In present value at the hurdle the gap is ¥7,493.45. |

## 3. Every figure

Verdicts: **OK**, the figure and its words are right. **AMBIGUOUS**, the figure is right but the words claim more, or less,
than the convention gives. **WRONG**, the figure, or the claim it supports, does not hold. "Indep." is
`independent.py`; "engine" is the probes. Where they agree, one value is shown.

### 3.1 The extension and the request (§01, §03 item 5, §06)

| Figure | Where | Indep. = engine | Convention | Verdict | Corrected wording |
| --- | --- | --- | --- | --- | --- |
| ¥420,000 invoice "every month" | l. 58 | every 30 days, from day 2 | recurring invoice | AMBIGUOUS | "a ¥420,000 invoice every 30 days" |
| ¥210,000 extra receivables, "permanently" | l. 60, deck | 210,000.00 | face × 15/30, an average | AMBIGUOUS | "ties up ¥210,000 more in receivables on average for as long as the terms last (¥420,000 for 15 days of every 30)" |
| invoice financing 10.84% all-in | l. 61, 312, 512, 1124 | 10.8417% | 7.8% + 0.25% × 365/30 | OK | add "a tariff equivalent; an advance held for less than a whole period costs more" |
| "cheapest committed source able to carry a permanent need" | l. 61, 511 | the line is excluded by clean-down; IF advances at most 80% (¥336,000) | — | AMBIGUOUS | "priced at the rate of invoice financing, the cheapest committed source the clean-down rule allows" |
| ¥1,871.30 per invoice | l. 62, DEMO_FLOW | 1,871.30 | 420,000 × 15/365 × 10.8417%, rounded | OK as pricing | "…costs ¥1,871.30 per invoice at that rate" (actually advancing 80% for the 15 days costs ¥2,994.08) |
| ¥24,326.92 "a year" | l. 62, 555, 1221 | 24,326.92 (13 × 1,871.30 = 24,326.90) | 13 invoices by issue day, exact sum rounded once | AMBIGUOUS | "¥24,326.92 over the 13 invoices issued in the next 365 days" (steady state ¥22,767.50 a year; cash in the first 365 days ¥20,584.32) |
| 1.2% early-payment discount ¥5,040 | l. 63, 507, 555 | 5,040.00 | 1.2% × 420,000, posted day 2 | OK | — |
| rebate up to ¥4,000 | l. 63, 555 | 4,000.00 | 1% × ¥400,000 expected, not firm, order; counted at maximum | OK | "1% off next quarter's expected ¥400,000, counted at its maximum ¥4,000" |
| ¥28,326.92 future concessions | l. 555, 574, 1186; video "over 12 months" | 28,326.92 | 24,326.92 + 4,000; excludes the ¥5,040 | OK (tech doc); AMBIGUOUS (video, deck: "would cost … over 12 months") | video: "¥28,326.92 of future concessions over the next 365 days, on top of a ¥5,040 discount now". On FLOW's pricing, "accept as asked" gives away ¥33,366.92. |
| "more than five times" the limit | l. 65 | 5.67× | 28,326.92 / 5,000 | OK | — |
| below the reserve "on day 47" | l. 66, 555, 1187 | day 47 | 60-day terms move the day-2 invoice to day 62 | OK | — |
| ¥90,040 short on day 47; ¥135,040 on day 60; 15 days | l. 545–547, 555 | 209,960.00 → 90,040.00; 164,960.00 → 135,040.00; days 47–61 | conservative mode | OK | — |
| lowest ¥164,960 (day 60) | l. 555 | 164,960.00 | — | OK | — |
| cure ¥2,406.67 on invoice issued day 32 | l. 556 | 2,406.67 (135,040 × 7.8% × 60/365 + 0.25% × 2) | requested day 32, lands 35, repaid 92: 57 days, 2 periods | OK | — |
| runnable cure ¥1,468.05, line repaid day 62 | l. 557 | 1,468.05 (135,040 × 6.4% × 62/365) | drawn on decision day 0 | OK | add "drawn today; the need starts on day 47" |
| early-pay test ¥6,508.05 vs ¥3,873.58 | l. 558 | 6,508.05 = 5,040 + 1,468.05; 3,873.58 = line 135,000 × 6.4% × 62/365 (1,467.62) + IF 270,000 one period (2,405.96) | ADR-0007 test 3 | OK | — |
| Table 7 columns side by side | l. 549–560 | — | the cure funds part of what ¥24,326.92 prices | AMBIGUOUS | add under the table: "Funding cost and future concessions overlap; do not add them" |

### 3.2 The untouched books and the standing plan (§02, §03 items 1–3, §06)

| Figure | Where | Indep. = engine | Convention | Verdict | Corrected wording |
| --- | --- | --- | --- | --- | --- |
| cash ¥400,000; payroll ¥340,000 day 12; supplier ¥120,000 day 20; loan ¥45,000 every 30 days; RCV-A ¥420,000 day 32 | l. 293–294 | as stated | — | AMBIGUOUS (incomplete) | add: "the next ¥420,000 invoice is issued on day 2 and every 30 days after, on 45-day terms; a ¥100,000 operating bill on day 47; the loan is ¥1,500,000 at 0%; EBITDA ¥90,000 a month" |
| reserve ¥300,000; cap ¥5,000; DSCR ≥ 1.25×; leverage ≤ 2.5×; APR ≤ 15% | l. 295–296 | mandate 30,000,000 fen; 500,000; 12,500 bp; 25,000 bp; 1,500 bp | — | OK | — |
| lowest −¥105,000 on day 30 | l. 498, 553, 1159, 1212 | −105,000.00 (days 30–31) | — | OK | — |
| first breach day 12 | l. 498, 1162, 1212, 1220 | 12 | — | OK | — |
| "¥405,000 short, days 12–31" | l. 553 | peak 405,000 (days 30–31); 240,000 on day 12; 20 days | — | AMBIGUOUS | "below the reserve on days 12–31 (20 days), at worst ¥405,000 short (days 30–31)" |
| ¥405,000 funding need | l. 506, 1212 | 405,000.00 = 340,000 + 120,000 + 45,000 + 300,000 − 400,000 | — | OK | — |
| ¥505,000 due in 30 days; below zero from day 20 | l. 1219–1220 | 505,000.00; day 20 −60,000 | — | OK | — |
| line ¥150,000, interest ¥841.64 | l. 506, 1163 | 841.64 = 150,000 × 6.4% × 32/365 | drawn day 0, repaid day 32 | OK | — |
| invoice financing ¥255,000, ¥2,272.29 | l. 506, 1163 | 1,634.79 + 637.50 = 2,272.29 | lands day 3, repaid day 32: 29 days, 1 period | OK | "…¥2,272.29 (one 30-day period of interest and fee)" |
| plan ¥3,113.93; reserve held | l. 498, 507, 554, 583, 1003, 1159, 1220 | 3,113.93; lowest exactly 300,000.00 on day 30 (zero headroom) | charges paid on day 32 | OK | — |
| Tier 1 (no approval) | l. 554, 1159 | IF effective 11.22%, line 6.4%, both < 15% | per-leg effective rate | OK | — |
| full 1.2% discount instead ¥5,040.00 | l. 507 | 5,040.00 | — | OK | — |
| break-even 0.8832% (0.88%) | l. 399, 514, 1125, 1187 | 0.883225% = c/(1+c), c = 7.8% × 30/365 + 0.25% = 0.8911% | one whole IF period; borrow the net (1−d)F; 30 days early (day 2 vs day 32); IF at 100% of face; engine truncates to 88 bp | OK | Appendix D: "the discount above which an early payment costs more than that source" (against the line it would be 0.5233%; the line is already fully used by the plan) |
| 0.75% whole invoice ¥3,150.00 countered; 0.74% ¥3,108.00 accepted | l. 520–521, 1004 | 3,150.00 / 3,108.00 against 3,113.93 | — | OK | — |
| ¥500,000 guaranteed loan → DSCR 1.01× | l. 528 | 90,000 / (45,000 + 41,666.67 + 2,083.33) = 1.014 | bullet serviced on a level basis (ADR-0008) | OK | add "a 12-month bullet, levelised" |
| DSCR, leverage, clean-down definitions | l. 524–526 | — | §2 Covenants | AMBIGUOUS | add "tested on each 30-day month of the projection with a fixed ¥90,000 monthly EBITDA: a screening proxy for the synthetic covenant, not a trailing-12-month test" |
| stress: 10 days late, ¥5,649.25, 16.7% | l. 724 | 5,649.25 = line 150,000 × 6.4% × 42/365 (1,104.66) + IF 255,000 two periods (4,544.59); 16.68% | — | OK | — |
| stress: half paid, 35 days below | l. 725 | days 12–46 | — | OK | — |
| stress: EBITDA −20%, DSCR 1.50×, leverage 2.15× | l. 726 | 72,000 / 48,113.93 = 1.496; 1,860,000 / 864,000 = 2.153 | with the standing plan | OK | — |
| DSCR 2.00× / leverage 1.35× (JUDGING_QUESTIONS) | JQ l. 132–133 | 2.00 / 1.347 on untouched books; 1.87 (month 2) / 1.72 (month 1) with the plan | — | AMBIGUOUS | "on today's books before funding; with FLOW's plan, 1.87× and 1.72×" |

### 3.3 The counters (§01, §03 item 6, §06)

| Figure | Where | Indep. = engine | Convention | Verdict | Corrected wording |
| --- | --- | --- | --- | --- | --- |
| Option A rate 0.85% | l. 98, 564, 1188 | 85 bp: the largest whole 5 bp below 0.8832% | — | OK | — |
| Option A face ¥260,000 | l. 98, 565 | 255,000 / (1 − 0.85%) = 257,186.08 → 260,000 | rounded up to ¥10,000 (R-10) | OK | — |
| ¥257,790.00 on day 2 | l. 98, 1204 | 260,000 − 2,210 | — | OK | — |
| Option A ¥3,035.99 | l. 107, 559, 567, 1188 | 2,210.00 + 825.99 (line 147,210 × 6.4% × 32/365) | the quote assumes the ¥160,000 residual arrives on day 32 | OK | — |
| saving ¥77.94 | l. 573 | 3,113.93 − 3,035.99 | — | OK | — |
| Option A ¥3,027.77 | video l. 38, 59; deck l. 44 | 3,027.77 is the old ¥100-rounded face (257,200) | pre-16 Oct | **WRONG (stale)** | "¥3,035.99" |
| Option B 55 days + 0.30% | l. 107, 560, 570, 1188 | per invoice 1,247.53 (10 days at 10.8417%); 0.30% × 420,000 = 1,260 ≥ 1,247.53 | smallest whole-5 bp | OK | — |
| Option B "≈ ¥0 net over 12 months" | l. 560 | 13 × 1,247.53 → 16,217.95; −13 × 1,260 = −16,380.00; net −162.05 (a gain) | 13 invoices by issue day | OK as forward value | "a net gain of ¥162 in forward concessions over the 13 invoices" |
| Option B funding "—"; lowest ¥300,000; no breach | l. 560 | unfunded: −105,000 day 30, 215,000 day 47. Funded: line 90,000 day 0–57 (899.51) + IF 315,000 day 3–32 (2,806.95) = **3,706.46**, lowest 300,000 on day 30 | router on Option B's books | **WRONG** | "Funding: line ¥90,000 + invoice financing ¥315,000, ¥3,706.46 (¥592.53 more than the standing plan)". The counter's own re-check also reports an ¥85,000 shortfall on day 47 whose separate cure "cannot run today". |

### 3.4 The demo story after the deal (§01, §06, Figure 9, Execution Evidence)

| Figure | Where | Indep. = engine | Convention | Verdict | Corrected wording |
| --- | --- | --- | --- | --- | --- |
| day 34: ¥160,000 unpaid, "heading under the reserve" | l. 99, 1204 | day 34 cash 300,000.00; day 42 100,000.00 after the ¥200,000 payroll added on day 25 | conservative mode drops the overdue ¥160,000 | AMBIGUOUS (material) | "Day 34: ¥160,000 of the invoice is two days late, and the month-2 payroll of ¥200,000 the bookkeeper scheduled on day 25 would take cash to ¥100,000 on day 42, ¥200,000 below the reserve" |
| ¥200,000 advance, ¥1,782.19 | l. 100, 1205, 1020 | 1,282.19 (30 days of interest) + 500.00 (fee) | on the invoice issued day 2 (due 47); requested 34, lands 37 | OK | "an advance on the invoice due on day 47" |
| 32.5% a year vs the 15% ceiling | l. 101, 1206, 1005 | 32.525% = 1,782.19 / 200,000 × 365/10 | whole-period billing on a 10-day hold; tariff 10.84% | OK | add "(a full 30-day period billed for 10 days)" |
| cash lands day 37; late money day 36; financed invoice paid day 47 | l. 102–103, 1206–1207 | as stated | 3-day lead | OK | — |
| line repaid at the end | l. 104, 1209 | 147,210 + 1,213.17 on day 47 (47 days, not the 32 quoted) | — | OK, but the cost is not given | add "the line, out 15 days longer than quoted, costs ¥1,213.17" |
| 14 hash-chained entries | l. 104 | 14 operations in `demo_run.py` | — | OK | — |
| ¥255,013.80 / ¥162,800.00 / ¥149,986.20 / ¥1,236.05 / ¥257,200 | exec. evidence l. 29, 92–104; video l. 40, 60 | today: 257,790.00 / 160,000.00 / 147,210.00 / 1,213.17 / 260,000 | evidence run 16 Oct at `0f92d433`, before the ¥10,000 rounding | **WRONG (stale)** | regenerate the evidence, or replace the five figures |
| "unsafe in 8 days"; "¥200k below the ¥300k minimum" | video l. 40, 61 | day 34 + 8 = day 42; 200,000 | — | OK | — |

### 3.5 Capex (§03 item 8, limitations, §06)

| Figure | Where | Indep. = engine | Convention | Verdict | Corrected wording |
| --- | --- | --- | --- | --- | --- |
| ¥600,000 machine, NPV ¥380,885.77 at 10% | DEMO_FLOW l. 70; feature inventory | 380,885.77 | +¥22,000 a month, months 4–60; effective monthly hurdle; no residual value, tax or maintenance; unlevered | OK | add the assumptions |
| payback month 31 | DEMO_FLOW l. 70 | 31 (28 × 22,000 ≥ 600,000) | simple, undiscounted; discounted payback month 35 | OK | "simple payback in month 31 (discounted, month 35)" |
| lease ¥92,327.32; 36-month loan ¥53,206.14; 18-month DSCR 1.13× | l. 592–593 | 92,327.32 (14,423.49 a month); 53,206.14 (18,144.62); 26,950.84 (34,830.60; DSCR 1.127) | undiscounted total interest | OK | — |
| 36-month loan ¥3,144.62 below for three days | l. 593 | 315,000 − 18,144.62 = 296,855.38, days 44–46 | untouched books after day 32 | OK | — |
| "selects the lease" | l. 592, 1236 | selected on the untouched books (cash ¥300,576.51 on day 40). With the standing plan paid: ¥297,462.58, **rejected**; no structure passes alone | the screen ignores the existing day-12–31 breach | AMBIGUOUS (material) | "On today's unfunded books the lease passes and is selected. Once FLOW's ¥3,113.93 plan is paid, every structure needs a few days' bridge on the line (lease ¥3.11, 36-month loan ¥3.29)." |
| bridge ¥1.65; "about ¥39,000 less" | l. 597–598, 1036–1037 | 3,144.62 × 6.4% × 3/365 = 1.65; 39,121.18 − 1.65 = 39,119.53 | undiscounted, 36 vs 48 months | AMBIGUOUS (material) | "about ¥39,000 less interest (about ¥7,500 less in present value at the 10% hurdle)" |
| leverage financed 1.90× | golden, capex | (1,455,000 + 600,000) / 1,080,000 | month-1 end | OK | — |

## 4. The authoritative worked example

One chain, every number derived, on the golden books with Mandate v1. These are the figures the demo shows today, replayed
day by day through the API (`engine_probe2.py`) and recomputed independently (`independent.py`). The two agree to the fen.

### 4.1 Request (day 0)

Foshan Home Retail writes: *"We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and
give us 1% off next quarter."* The compiler reads three terms: an immediate 1.2% discount on RCV-A (¥420,000, due day 32),
a +15-day extension on every future invoice, and a contingent 1% rebate on the ¥400,000 expected next quarter.

The books on day 0: cash ¥400,000; payroll −¥340,000 (day 12), supplier −¥120,000 (day 20), loan −¥45,000 (days 30, 60, …),
RCV-A +¥420,000 (day 32), a ¥420,000 invoice issued on day 2 and every 30 days after on 45-day terms (paid days 47, 77, …),
an operating bill −¥100,000 (day 47). Reserve ¥300,000.

Untouched, cash closes at ¥60,000 on day 12, −¥60,000 on day 20 and −¥105,000 on days 30–31. It is below the reserve on
days 12–31, and the need is 340,000 + 120,000 + 45,000 + 300,000 − 400,000 = **¥405,000**. FLOW's standing plan: the line
¥150,000 on day 0 (¥841.64 for 32 days) plus invoice financing ¥255,000 landing on day 3 (one period, ¥1,634.79 interest +
¥637.50 fee). **Total ¥3,113.93**, paid on day 32. Cash closes exactly at ¥300,000 on day 30.

### 4.2 Verdict: REJECT, four reasons

| Rule | Derivation |
| --- | --- |
| Concession cap | 13 invoices × 420,000 × 15/365 × 10.8417% = ¥24,326.92 (rounded once), + rebate 1% × 400,000 = ¥4,000 → **¥28,326.92** > ¥5,000 (5.67×) |
| Reserve | Early receipt on day 2: 400,000 + 420,000 − 5,040 = 814,960; less 340,000, 120,000 and 45,000 → 309,960 on day 30; the day-2 invoice now pays on day 62, so day 47 = 309,960 − 100,000 = **¥209,960** (¥90,040 short); day 60 = ¥164,960 (¥135,040 short); 15 days below |
| Break-even | c = 7.8% × 30/365 + 0.25% = 0.8911%; d < c/(1+c) = **0.8832%**; 1.2% is above it (annualised 14.78%, under the 15% APR ceiling) |
| Dearer than the plan | With the early payment: ¥5,040 + line ¥135,040 × 6.4% × 62/365 (¥1,468.05) = **¥6,508.05**. Without it, same terms: line ¥135,000 × 6.4% × 62/365 (¥1,467.62) + IF ¥270,000, one period (¥2,405.96) = **¥3,873.58** |

On FLOW's pricing, "accept as asked" gives away ¥5,040 now plus ¥28,326.92 of future concessions (¥33,366.92), and still
needs funding for days 47–61.

### 4.3 Counter: Option A

- Rate: the largest whole 5 bp below 0.8832%, so **0.85%**.
- Face: (405,000 − line 150,000) / (1 − 0.85%) = 257,186.08, rounded up to ¥10,000: **¥260,000**.
- Discount: 0.85% × 260,000 = **¥2,210.00**. Receipt on day 2: **¥257,790.00**.
- Terms stay at 45 days, no rebate. Forward concession ¥0.

Option B (55 days + 0.30%) is a ¥162.05 forward gain, but its books need ¥3,706.46 of funding. FLOW recommends A.

### 4.4 Funding plan as quoted

The line carries the rest: 405,000 − 257,790 = **¥147,210**, drawn on day 0 and repaid on day 32 from RCV-A's ¥160,000
residual. Interest 147,210 × 6.4% × 32/365 = **¥825.99**. **Quoted cost ¥3,035.99** (2,210.00 + 825.99), ¥77.94 below the
standing plan. Lowest cash ¥300,000 on day 30. Tier 1: early payment within break-even, line at 6.4%.

### 4.5 Commitment and receipt

Day 0: `ACCEPT_OFFER` (forward concession ¥0.00 booked) and `DRAW_FACILITY` ¥147,210 on the line; cash ¥547,210.
Day 2: the bank posts ¥257,790.00 on RCV-A (¥260,000 settled at 0.85%, ¥160,000 still due on day 32); cash ¥805,000.
Days 12, 20, 30: ¥465,000, ¥345,000, then **¥300,000** (the reserve, zero headroom).

### 4.6 Reality diverges

- Day 25: the bookkeeper schedules month-2 payroll of **¥200,000 for day 42**.
- Day 32: the ¥160,000 residual does not arrive. The line cannot be repaid, and cash stays at ¥300,000.
- Day 34: the conservative forecast (the overdue ¥160,000 dropped) closes day 42 at **¥100,000**, ¥200,000 short, on days
  42–46. Had the residual arrived on time and the line been repaid, day 42 would still be ¥111,964.01: the payroll causes
  the breach, and the late payment deepens it.

### 4.7 Cure

Invoice financing of **¥200,000** on the invoice issued on day 2 (open face ¥420,000; 80% allows ¥336,000). Requested on
day 34, it lands on day 37 and is repaid from that invoice on day 47: 10 days, billed as one whole period. Interest
200,000 × 7.8% × 30/365 = ¥1,282.19, fee 0.25% = ¥500.00, **cost ¥1,782.19**. Effective rate 1,782.19 / 200,000 × 365/10 =
**32.5% a year**, above the 15% ceiling (the tariff is 10.84%). So "go ahead" queues it as APR-000001, and only the owner's
"approve APR-000001" runs it. Cash does not move on day 34.

### 4.8 Receipts and close

| Day | Event | Cash (closing) |
| --- | --- | --- |
| 36 | residual ¥160,000 arrives | 460,000.00 |
| 37 | the ¥200,000 advance lands | 660,000.00 |
| 42 | payroll month 2 −¥200,000 | 460,000.00 (reserve held) |
| 47 | invoice +¥420,000; advance repaid ¥200,000 + ¥1,782.19; line repaid ¥147,210 + **¥1,213.17** (47 days); bill −¥100,000 | 429,794.64 |
| 60 | loan −¥45,000 | 384,794.64 |

### 4.9 Final costs

| Item | Quoted on day 0 | Actually posted |
| --- | --- | --- |
| Early-payment discount | 2,210.00 | 2,210.00 |
| Credit line interest | 825.99 (32 days) | 1,213.17 (47 days, residual late) |
| Cure: invoice financing | — | 1,782.19 |
| **Total** | **3,035.99** | **5,205.36** |

Cross-check: day-62 cash = 400,000 + 420,000 + 420,000 − 340,000 − 120,000 − 2 × 45,000 − 200,000 − 100,000 − 5,205.36 =
**¥384,794.64**, the engine's figure.

The overrun is ¥2,169.37: ¥387.18 because the line stayed out 15 days longer, and ¥1,782.19 for the cure, which a new
¥200,000 payroll made necessary. Against the request as asked, the supplier kept its 45-day terms and gave no rebate. It
avoided ¥28,326.92 of future concessions, the ¥5,040 discount and a day-47 breach, and the reserve held on every day.

Assumptions of this example: the buyer pays the residual on day 36 and the day-2 invoice on its due day 47; the owner
approves on day 34; no other flow is added. The chart series below extend it.

## 5. Data for the financial chart

`work/fin/daily_cash.csv`, days 0–62, closing cash in CNY with the reserve line:

| Column | Scenario |
| --- | --- |
| `reserve_cny` | ¥300,000 every day |
| `baseline_no_funding_cny` | untouched books (lowest −¥105,000, days 30–31) |
| `standing_plan_line150k_if255k_cny` | FLOW's ¥3,113.93 plan (exactly ¥300,000 on day 30) |
| `ex01_as_asked_no_funding_cny` | the request as asked, no funding (¥209,960 on day 47, ¥164,960 on day 60) |
| `option_a_as_quoted_cny` | Option A with its ¥147,210 line, residual on time |
| `option_a_as_quoted_plus_month2_payroll_cny` | the same with the day-42 payroll (¥111,964.01): the breach would come anyway |
| `option_b_with_its_funding_cny` | Option B with its ¥3,706.46 plan |
| `demo_actual_option_a_late_residual_cure_cny` | the demo as it runs (§4) |

`work/fin/events.csv` dates every event to annotate (day, scenario, event, amount). Only the demo series includes the
month-2 payroll, which the clock adds on day 25; the other series are day-0 books. Suggested chart: lines for the baseline,
the standing plan, EX01 as asked and the demo; a dashed reserve; markers on days 2, 12, 30, 34, 37, 42 and 47. The
Option A/B series can sit behind a toggle.

## 6. Files

- `work/fin/independent.py`: independent recomputation; writes `independent_values.json`, `daily_cash.csv`, `events.csv`.
- `work/fin/engine_probe.py`, `engine_probe2.py`, `engine_probe3.py`: engine values in process; write `engine_values*.json`.
- `work/fin/compare.py`: the 39-figure comparison; writes `compare.csv`.

No application code, fixture or mock was changed.
