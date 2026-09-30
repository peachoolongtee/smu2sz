# Demo flow

The main scripted path is spec v2 §10, with the numbers from `fixtures/golden/golden_values.json`. Every step must be runnable by `scripts/demo.py` and by Playwright, repeatedly, after `POST /demo/reset`.

## 0. Reset and the mandate (Mandate screen)
- Fixture `golden_sme`: cash ¥400,000; payroll ¥340,000 on day 12; supplier ¥120,000 on day 20; Receivable A ¥420,000 due day 32; floor ¥300,000; concession cap ¥5,000; DSCR ≥ 1.25×; leverage ≤ 2.5×.
- The owner's signed mandate v1 is shown with its three tiers.

## Scene 1: the offer is a loan (Inbox → Trajectory → Funding → Verdict)
1. The buyer message arrives: "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter."
2. The compiler highlights three spans:
   - immediate discount ¥5,040 (receive ¥414,960 on day 2);
   - terms +15 days, recurring (≈¥207,123.29 of extra receivables);
   - contingent rebate ≤ ¥4,000.
3. The Debt Desk shows the marginal cost of funds: invoice financing at 10.84% all-in, because clean-down excludes the line. Break-even discount 0.88%. The extension costs ¥1,871.30 per invoice and ¥22,455.62 a year (the notional line basis would be ¥13,255.89; the expected plan with the guaranteed loan, ¥11,052.30).
4. The forward-concession meter shows ¥26,455.62 against a ¥5,000 cap. The cash line dips to ¥254,960 on day 47, a ¥45,040 shortfall that invoice financing can cure for ¥802.70.
5. Verdict: **REJECT**: AGG_CONCESSION_EXCEEDED; RESERVE_BREACH@47 (curable). Covenants hold: DSCR 1.92×, leverage 1.72×.
6. Counters go out:
   - **Option A:** 45-day terms, no rebate, early settlement on up to ¥211,800 at 0.85%, costing ¥2,641.94.
   - **Option B:** 60-day terms with a 0.45% price adjustment of ¥1,890 per invoice, against a ¥1,871.30 funding cost.
7. The buyer kernel accepts Option A. The commitment is recorded with a nonce and expiry, and the line draw is logged as a Tier-1 operation.

## Scene 2: the buyer walks, and the gap is still covered
1. A different buyer reservation: the kernel refuses every counter within 3 rounds → **NO DEAL**.
2. The router funds ¥360,000 with the line (¥150,000) plus invoice financing (¥210,000) for ¥2,712.94, against ¥5,040 for taking the discount and ¥3,392.25 for the v1 optimum. The guaranteed loan is not admissible: it isn't committed and takes 21 days, after payroll on day 12. The line alone breaches on day 12.
3. Tier-1 operations execute: `DrawFacility`, then `SubmitInvoiceForFinancing`. Repayments are scheduled on day 32.
4. Wording invariance: EX01B, the same economics in other words, gets the same verdict.

## Scene 3: capex (flag `FEATURE_CAPEX`)
The owner asks: "Can we buy the ¥600k machine?"
1. Is it worth doing? NPV ¥380,885.77 and payback in month 31.
2. How should it be financed?
   - Cash + line: infeasible.
   - 18-month loan: ¥34,830.60 a month, DSCR_BREACH in month 1 (1.13×).
   - **36-month loan: ¥18,144.62 a month, selected.**
   - Lease: ¥39,121.18 dearer.
3. Leverage is 2.08×, or 2.28× if the extension were also funded. The loan is Tier 2, so the borrower file is generated for the owner.

## Security scene (flag `FEATURE_SECURITY_SCENES`)
The FastCapital message (`SEC_DEMO_FASTCAPITAL`) is refused with UNKNOWN_COUNTERPARTY, UNEVIDENCED_PRIOR_CONCESSION and DATA_EXTRACTION_REFUSED. Then show:
- no facility added, no commitment, ¥0 moved;
- a reply that discloses nothing;
- three security events in the audit log, each with its span.

## Under the hood
compiler → schema → engine → router → verifier → executor → hash-chained log. The model can only propose.
