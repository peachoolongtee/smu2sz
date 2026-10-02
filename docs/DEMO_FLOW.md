# Demo flow

The main scripted path is spec v2 §10, with the numbers from `fixtures/golden/golden_values.json`. The path from the deal to the repaid line (steps 1 to 17, Scene 1 and Scene 4 below) runs in process with `PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py`, and the web stepper is covered by Playwright. Both repeat after `POST /demo/reset`.

## 0. Reset and the mandate (Mandate screen)
- Fixture `golden_sme`: cash ¥400,000; payroll ¥340,000 on day 12; supplier ¥120,000 on day 20; Receivable A ¥420,000 due day 32; floor ¥300,000; concession cap ¥5,000; DSCR ≥ 1.25×; leverage ≤ 2.5×.
- The owner's signed mandate v1 is shown with its three tiers.

## Scene 1: the offer is a loan (Inbox → Trajectory → Funding → Verdict)
1. The buyer message arrives: "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter."
2. The compiler highlights three spans:
   - immediate discount ¥5,040 (receive ¥414,960 on day 2);
   - terms +15 days, recurring (¥210,000.00 of extra receivables);
   - contingent rebate ≤ ¥4,000.
3. The Debt Desk shows the marginal cost of funds: invoice financing at 10.84% all-in, because clean-down excludes the line. Break-even discount 0.88% for 30 days early (the break-even is taken for the actual days early, and an early payment must also be needed and cheaper than the router's plan; ADR-0007). The extension costs ¥1,871.30 per invoice and ¥24,326.92 over the 13 invoices dated inside the 365-day window (the notional line basis would be ¥14,360.55; the expected plan with the guaranteed loan, ¥11,973.32; all from `fixtures/golden/golden_values.json`). It adds ¥1,897.29 a month of debt service.
4. The forward-concession meter shows ¥28,326.92 against a ¥5,000 cap. The cash line dips to ¥254,960 on day 47, a ¥45,040 shortfall that invoice financing can cure for ¥802.70.
5. Verdict: **REJECT**: AGG_CONCESSION_EXCEEDED; RESERVE_BREACH@47 (curable); DISCOUNT_ABOVE_BREAK_EVEN (1.2% > the 0.88% break-even, which is why Option A is priced at 0.85%); EARLY_PAY_DEARER_THAN_PLAN (the package costs ¥5,529.64 against ¥2,870.95 for the plan without the early payment). Covenants hold: DSCR 1.92×, leverage 1.72×.
6. Counters go out:
   - **Option A:** 45-day terms, no rebate, early settlement on up to ¥211,900 at 0.85% (the exact ¥211,800.30 rounded up to a whole ¥100), nets ¥210,098.85 and costs ¥2,642.24 (discount ¥1,801.15 plus ¥841.09 on the line), less than the standing plan's ¥2,712.94.
   - **Option B:** 60-day terms with a 0.45% price adjustment of ¥1,890 per invoice, against a ¥1,871.30 funding cost.
7. The buyer kernel accepts Option A. The buyer's reply carries its own channel key (`X-Counterparty-Key`, `demo-buyer-1-key`); the same message with no key would be a proposal only, read and evaluated but never agreed. The commitment is recorded with a nonce and expiry, and the line draw is logged as a Tier-1 operation. In chat the owner's instructions follow propose, then confirm: the plan is shown with its cost, and "go ahead" runs exactly those operations (or shows a new proposal if the books moved).

## Scene 2: the buyer walks, and the gap is still covered
1. A different buyer reservation: the kernel refuses every counter within 3 rounds → **NO DEAL**.
2. The router funds ¥360,000 with the line (¥150,000) plus invoice financing (¥210,000) for ¥2,712.94, against ¥5,040 for taking the discount and ¥3,392.25 for the v1 optimum. The guaranteed loan is not admissible: it isn't committed and takes 21 days, after payroll on day 12. The line alone breaches on day 12. Even if it were committed, a bullet term loan is serviced on a level basis for DSCR (ADR-0008): the ¥500,000 12-month loan shows 1.014× against the 1.25× covenant and fails it, and the borrower file's ¥360,000 request shows 1.18×, below covenant, with the shortfall reported.
3. Tier-1 operations execute: `DrawFacility`, then `SubmitInvoiceForFinancing`. The line is cash at once; the advance lands on day 3 after the facility's 3-day lead time, so cash is ¥550,000 after the plan and ¥760,000 on day 3 (`tests/nl/test_intents.py`). Repayments are scheduled on day 32.
4. Wording invariance: EX01B, the same economics in other words, gets the same verdict.

## Scene 3: capex (flag `FEATURE_CAPEX`)
The owner asks: "Can we buy the ¥600k machine?"
1. Is it worth doing? NPV ¥380,885.77 and payback in month 31.
2. How should it be financed?
   - Cash + line: infeasible.
   - 18-month loan (an illustration: the facility's real term is 36 months): ¥34,830.60 a month, DSCR_BREACH in month 1 (1.10× in the demo, which has already drawn the day-0 plan; 1.13× on untouched books).
   - **36-month loan: ¥18,144.62 a month, charges ¥53,206.14, selected** (lowest total financing charges among the structures that pass).
   - Lease: ¥39,121.18 dearer in charges.
3. Leverage is 2.28× in the demo, or 2.47× if the extension were also funded (2.08× and 2.28× on untouched books). The screen is a screen, not an investment appraisal: the uplift is the owner's estimate, and the DSCR is the reserve-coverage reading of ADR-0008, not a bank covenant. The loan is Tier 2, so the borrower file is generated for the owner.

## Scene 4: the agent stays on duty (home `/`, chat, `scripts/demo_run.py`)
Continues from the books left by the Scene 1 deal. Figures are from `scripts/demo_run.py`, 3 Oct 2026 (14 ledger entries).
1. After the deal on Counter A: no critical alert, and one headroom warning on day 20.
2. The clock moves to day 2 and the bank feed reports the agreed early payment: ¥210,098.85 received on RCV-A, settling ¥211,900.00 at 0.85%; ¥208,100.00 is still due on day 32. The clock never records a receipt itself.
3. The clock moves to day 34. The residual has not arrived: RCV-A is 2 days past due. A reserve breach is ahead on day 42 (cash ¥100,000.00, ¥200,000.00 below the floor; the scenario added month-2 payroll of ¥200,000 on day 25). The alert carries a committed cure: finance ¥200,000.00 of RI:BUYER-1:2, cost ¥1,782.19, and says it is above the owner-approval ceiling, so it needs the owner.
4. The agent speaks first (`POST /nl/opener`, shown on the home page): it names the late ¥208,100.00 and the breach, and proposes the advance with its cost, 32.5% a year for 10 days (the days from the landing day, 37, to the due day, 47), and says that is above the 15.00% yearly ceiling because invoice financing bills whole 30-day periods, so it needs the owner's approval: "go ahead" queues it. It asks "Go ahead?"
5. Step one, the owner says "go ahead" (or clicks the button). The advance is **queued** as `APR-000001` (Tier 2, ledger entry 7, `PENDING_APPROVAL`); nothing has run, cash is unchanged and the alert is still open. Step two, the owner says "approve APR-000001" (or uses the approval card): the advance executes (entry 8), the reserve alert clears, and an info alert says the ¥200,000.00 lands on day 37.
6. Day 36: the buyer pays the residual ¥208,100.00. Day 38: the advance has landed (day 37). Day 47: RI:BUYER-1:2 is paid (¥420,000.00) and repays the advance ¥200,000.00 plus interest ¥1,282.19 and fee ¥500.00 (10 days billed as 1 whole period).
7. The agent proposes repaying the ¥149,901.15 line draw (interest to date ¥1,235.35; lowest projected cash ¥475,181.31 on day 47). The owner says "go ahead"; it is repaid. No alerts remain.
8. Reconciliation: 3 matched, 0 flagged, no balance still drawn. The ledger holds 14 hash-chained entries and the chain is valid.
9. An attack through chat is harmless: a FastCapital message sent as a counterparty gets a reply that discloses nothing and carries no verdict or operations; the same text pasted by the owner into a quoted message is not taken as an instruction (the intent stays ambiguous), is logged as a security event, and executes nothing.

If the early payment never arrives, reconciliation reports it LAPSED and no committed cure exists (the gap is ¥410,098.85).

## Security scene (flag `FEATURE_SECURITY_SCENES`)
The FastCapital message (`SEC_DEMO_FASTCAPITAL`) is refused with UNKNOWN_COUNTERPARTY, UNEVIDENCED_PRIOR_CONCESSION and DATA_EXTRACTION_REFUSED. Then show:
- no facility added, no commitment, ¥0 moved;
- a reply that discloses nothing;
- three security events in the audit log, each with its span.

## Under the hood
compiler → schema → engine → router → verifier → executor → hash-chained log. The model can only propose.
