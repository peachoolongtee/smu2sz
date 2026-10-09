# Demo flow

The guided Demo in the web app is the late-payment loop in six scenes and eleven steps (`apps/web/lib/demo.ts`, `DEMO_STEPS`). The earlier module tour is kept as "More to show" (below) and as the engine reference in the sections after it. The numbers come from `fixtures/golden/golden_values.json`; the path from the deal to the repaid line (Scene 4 below) also runs in process with `PYTHONUTF8=1 uv run --project services/api python scripts/demo_run.py`. Both repeat after `POST /demo/reset`.

## The guided Demo: the late-payment loop

Run it with Start demo and Next on the stepper (Demo mode keeps it on every page), or step by step on the story page (`/demo`). Every step does its work through the same API calls the Business pages use, then opens the Business page that shows the result. A step waits for the one before it, because the story moves time. Back only moves the pointer; Next after a Back is a Show up to the highest step finished, and only the step after that is run. Every step is convergent: Run brings the books to at least that step's state, and when they are already there it only reads them again, so Replay and a second Run are safe. Show only opens a finished step's screen. Reset (or Replay of step 1) erases the books and starts over.

| Scene | Step (what Next does) | Screen |
| --- | --- | --- |
| 1 Buyer asks | 1. Reset the books and read the buyer's message (EX01) | Deals: the request beside the interpreted terms |
| 2 FLOW decides | 2. Check the offer (evaluate); the Debt Desk's view at decision time is kept for Cash | Deals: forward cost, cash impact, the recommended counter and its scope |
| 3 The agreement acts | 3. Send the recommended counter, bound to the verdict id, counter id and books version shown (`POST /negotiate` with `verdict_id`, `counter_id`, `state_version`; cooperative buyer) | Deals, the live agreement |
|  | 4. Read cash now against what is still arriving, and the execution summary | Cash |
| 4 Reality diverges | 5. "Bank: the agreed early payment arrives (synthetic)": the clock moves to the day the buyer promised to pay by (it records nothing), then `POST /demo/bank-receipt` posts the one receipt | Receivables |
|  | 6. Time passes: the clock moves to day 34; nothing is recorded as received, the later payment does not arrive | Home: the reserve breach and the cure priced above the autonomous ceiling |
| 5 The owner stays in control | 7. Queue the cure: exactly the Home button's bound act (the home's `state_version` and suggestions); it needs the owner, so it waits | Approvals, the card |
|  | 8. The owner approves: the card's own Approve is the only approval (`POST /approvals/{id}`). The step itself never decides: while the cure waits, running it only opens the approval card and leaves the story where it was; once the owner has decided, it reads the decision and shows it. The stepper never presses Approve | Approvals |
|  | 9. Time passes: the clock moves to the day after the funding lands (day 38); the cash is in hand, not in transit | Cash |
| 6 Outcome and proof | 10. Where the books stand: updated cash and the risk that remains, the deal's record (Fulfilled) and the cure's (Settled) | Home |
|  | 11. The record and the proof: Activity with what changed, why it matters and what remains, and the evidence export link | Activity |

**The clock never invents receipts.** The one receipt in the story is the synthetic bank event of step 5. It goes through `POST /demo/bank-receipt` (owner token, `DEMO_MODE` only; 403 `DEMO_ONLY` otherwise): the server posts exactly the operation the bank feed would post (`RECEIVE_PAYMENT`, requested by `SYSTEM`) for the one early payment the books are still waiting for, in the amount they promised, with the bank reference `DEMO-RCPT-1`. A second call books nothing (409 `NO_PROMISED_RECEIPT`). The bank-feed key stays on the server, so the browser never holds it. Activity words any `DEMO-` reference as "Synthetic bank event, reference DEMO-RCPT-1; no real funds moved." The stepper labels the step "(synthetic)".

**Narration comes from the responses.** After a step runs, its sentence (`demo.done.<step>` in the dictionary) is filled from what the server just told it: the deal record's state and remaining task, the verdict workspace's recommendation, the home's `headline` and `note`, the approval's `presentation.headline` and `execution.summary_text`. Each sentence of a template is shown only when everything it names was supplied; otherwise the plain sentence (`demo.desc.<step>`, no figure) is shown. No figure is typed into the dictionary (`scripts/w6-demo.test.mjs` checks it).

**More to show** (on the story page; never part of Next, and they never move the story's step):
- *The buyer walks away* and *the same offer, other words*: the old Scene 2 (a hard-line buyer refuses every counter, the gap is still funded; EX01B gets the same verdict as EX01). It replaces the books, so the story starts over afterwards, and the page says so before it is opened.
- *Can we buy a machine?*: the capex evaluation and the read-only borrower file (Scene 3 below). Applying stays the owner's click on the Capex page.
- *The attack message*: the FastCapital message (Security scene below).
- The engine's own pages: signed mandate, cash line, Debt Desk, verdict, ledger, evidence export.

Tests: `apps/web/e2e/demo.spec.ts` (mock and live) runs the six scenes end to end, checks that the approve step needs the click, that Cash shows the landed funding, the receipt carries its synthetic reference in Activity, the deal record is FULFILLED and the cure's SETTLED, the rapid-click and Show/Replay/Reset rules, and the optional scenes. The mocks (`apps/web/mocks`) are recorded from the API by `scripts/record-mocks.mjs`, which walks the engine's own sequences.

## Engine reference

The sections below are the engine's own scenes, in the order of spec v2 section 10. The guided Demo above reaches Scene 1's deal and Scene 4's loop through the Business pages; the rest is reached from "More to show".

## 0. Reset and the mandate (Mandate screen)
- Fixture `golden_sme`: cash ¥400,000; payroll ¥340,000 on day 12; supplier ¥120,000 on day 20; the existing equipment loan's ¥45,000 payment on day 30 (and every 30 days after: it leaves cash); Receivable A ¥420,000 due day 32; floor ¥300,000; concession cap ¥5,000; DSCR ≥ 1.25×; leverage ≤ 2.5×. Before day 32 the cash falls ¥405,000 short of the floor (the day-0 gap).
- The owner's signed mandate v1 is shown with its three tiers.

## Scene 1: the offer is a loan (Inbox → Trajectory → Funding → Verdict)
1. The buyer message arrives: "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter."
2. The compiler highlights three spans:
   - immediate discount ¥5,040 (receive ¥414,960 on day 2);
   - terms +15 days, recurring (¥210,000.00 of extra receivables);
   - contingent rebate ≤ ¥4,000.
3. The Debt Desk shows the marginal cost of funds: invoice financing at 10.84% all-in, because clean-down excludes the line. Break-even discount 0.88% for 30 days early (the break-even is taken for the actual days early, and an early payment must also be needed and cheaper than the router's plan; ADR-0007). The extension costs ¥1,871.30 per invoice and ¥24,326.92 over the 13 invoices dated inside the 365-day window (the notional line basis would be ¥14,360.55; the expected plan with the guaranteed loan, ¥11,973.32; all from `fixtures/golden/golden_values.json`). It adds ¥1,897.29 a month of debt service.
4. The forward-concession meter shows ¥28,326.92 against a ¥5,000 cap. The cash line dips to ¥209,960 on day 47, a ¥90,040 shortfall that invoice financing can cure for ¥2,406.67.
5. Verdict: **REJECT**: AGG_CONCESSION_EXCEEDED; RESERVE_BREACH@47 (curable); DISCOUNT_ABOVE_BREAK_EVEN (1.2% > the 0.88% break-even, which is why Option A is priced at 0.85%); EARLY_PAY_DEARER_THAN_PLAN (the package costs ¥6,508.05 against ¥3,550.64 for the plan without the early payment). Covenants hold: DSCR 1.92×, leverage 1.47× (drawn debt over annual EBITDA; the committed line's undrawn room is not counted).
6. Counters go out:
   - **Option A:** 45-day terms, no rebate, early settlement on up to ¥257,200 at 0.85% (the exact ¥257,186.08 rounded up to a whole ¥100), and says so: "paid on or before day 2" (any portion of the face paid by that day earns the rate), nets ¥255,013.80 and costs ¥3,027.77 (discount ¥2,186.20 plus ¥841.57 on the line), less than the standing plan's ¥3,113.93.
   - **Option B:** "55-day terms accepted with a 0.30% price adjustment on future invoices, no rebate": ¥1,260.00 per invoice against a ¥1,247.53 funding cost for the 10 extra days; over the 13 invoices of the window the net is −¥162.05, so it costs the supplier nothing; it needs the owner because it lengthens terms. It is 55 days and not the 60 the buyer asked for because every counter must pass its own re-check, and at 60 days the invoice would be paid after the day-60 loan payment with no committed cure for the shortfall.
7. The buyer kernel accepts Option A. The buyer's reply carries its own channel key (`X-Counterparty-Key`, `demo-buyer-1-key`); the same message with no key would be a proposal only, read and evaluated but never agreed. The commitment is recorded with a nonce and expiry, and the line draw is logged as a Tier-1 operation. In chat the owner's instructions follow propose, then confirm: the plan is shown with its cost, and "go ahead" runs exactly those operations (or shows a new proposal if the books moved).

## Scene 2: the buyer walks, and the gap is still covered
1. A different buyer reservation: the kernel refuses every counter within 3 rounds → **NO DEAL**.
2. The router funds ¥405,000 with the line (¥150,000) plus invoice financing (¥255,000 on RCV-A) for ¥3,113.93, against ¥5,040 for taking the discount and ¥3,938.81 for the v1 optimum. The guaranteed loan is not admissible: it isn't committed and takes 21 days, after payroll on day 12. The line alone breaches on day 12. Even if it were committed, a bullet term loan is serviced on a level basis for DSCR (ADR-0008): the ¥500,000 12-month loan shows 1.014× against the 1.25× covenant and fails it, and the borrower file's ¥360,000 request shows 1.18×, below covenant, with the shortfall reported.
3. Tier-1 operations execute: `DrawFacility`, then `SubmitInvoiceForFinancing`. The line is cash at once; the advance lands on day 3 after the facility's 3-day lead time, so cash is ¥550,000 after the plan and ¥805,000 on day 3 (`tests/nl/test_intents.py`). Repayments are scheduled on day 32.
4. Wording invariance: EX01B, the same economics in other words, gets the same verdict.

## Scene 3: capex (flag `FEATURE_CAPEX`)
The owner asks: "Can we buy the ¥600k machine?" Evaluating writes nothing: no operation, no approval.
1. Is it worth doing? NPV ¥380,885.77 and payback in month 31.
2. How should it be financed? On untouched books (`fixtures/golden/golden_values.json`):
   - Cash + line: infeasible.
   - 18-month loan (an illustration: the facility's real term is 36 months): ¥34,830.60 a month, DSCR_BREACH in month 1 (1.13×).
   - 36-month loan: ¥18,144.62 a month, charges ¥53,206.14, DSCR holds (1.43×) but it is rejected: its first instalment on day 44 takes cash to ¥296,855.38, below the ¥300,000 reserve, now that the existing loan's payments leave cash.
   - **48-month lease: ¥14,423.49 a month, charges ¥92,327.32, selected** (lowest total financing charges among the structures that pass; its first payment on day 40 leaves ¥300,576.51). It is ¥39,121.18 dearer in interest than the loan the reserve rules out.
   In the stepper the day-0 plan has already been drawn, so the cash is higher: there the 18-month illustration shows 1.09×, the 36-month loan 1.37× and the lease 1.45×, and the 36-month loan is selected (a probe of the demo path on 3 Oct; the web test checks the 1.09× and the ¥18,144.62).
3. Leverage is 2.28× in the demo, or 2.47× if the extension were also funded (1.90× and 2.10× on untouched books; one definition, drawn debt over annual EBITDA). The screen is a screen, not an investment appraisal: the uplift is the owner's estimate, and the DSCR is the reserve-coverage reading of ADR-0008, not a bank covenant.
4. The apply step. Applying is a separate act: the owner clicks Apply on the Capex page, which calls `POST /capex/apply` with the state version of the evaluation they saw (409 `STATE_VERSION_MOVED` if the books moved). That queues one Tier-2 application for the selected structure in the approvals queue; nothing is applied for until the owner approves it. The borrower file is a separate read-only owner action: it is built at once with its provenance (generation day, versions, evidence hash), nothing is queued for it, and it is prepared, not sent.

## Scene 4: the agent stays on duty (home `/`, chat, `scripts/demo_run.py`)
Continues from the books left by the Scene 1 deal. Figures are from `scripts/demo_run.py`, 3 Oct 2026 (14 ledger entries).
1. After the deal on Counter A: no critical alert, and one headroom warning on day 30 (cash sits exactly on the floor).
2. The clock moves to day 2 and the bank feed reports the agreed early payment: ¥255,013.80 received on RCV-A, settling ¥257,200.00 at 0.85%; ¥162,800.00 is still due on day 32. The clock never records a receipt itself. Receipts can carry the bank's own reference: the same reference on the same receivable books once whatever the idempotency key, and the reconciliation page shows the reference on each receipt.
3. The clock moves to day 34 (the existing loan's ¥45,000 payment left cash on day 30). The residual has not arrived: RCV-A is 2 days past due. A reserve breach is ahead on day 42 (cash ¥100,000.00, ¥200,000.00 below the floor; the scenario added month-2 payroll of ¥200,000 on day 25). The alert carries a committed cure: finance ¥200,000.00 of RI:BUYER-1:2, cost ¥1,782.19, and says it is above the owner-approval ceiling, so it needs the owner. The alert's button is bound to what is on screen: it sends the state version and the suggestions shown, and if either has moved the server answers 409 `ALERT_CHANGED` and runs nothing.
4. The agent speaks first (`POST /nl/opener`, shown on the home page): it names the late ¥162,800.00 and the breach, and proposes the advance with its cost, 32.5% a year for 10 days (the days from the landing day, 37, to the due day, 47), and says that is above the 15.00% yearly ceiling because invoice financing bills whole 30-day periods, so it needs the owner's approval: "go ahead" queues it. It asks "Go ahead?"
5. Step one, the owner says "go ahead" (or clicks the button). The advance is **queued** as `APR-000001` (Tier 2, ledger entry 7, `PENDING_APPROVAL`); nothing has run, cash is unchanged and the alert is still open. Step two, the owner says "approve APR-000001" (or uses the approval card): the advance executes (entry 8), the reserve alert clears, and an info alert says the ¥200,000.00 lands on day 37.
6. Day 36: the buyer pays the residual ¥162,800.00. Day 38: the advance has landed (day 37) and cash is ¥662,800.00. Day 47: RI:BUYER-1:2 is paid (¥420,000.00) and repays the advance ¥200,000.00 plus interest ¥1,282.19 and fee ¥500.00 (10 days billed as 1 whole period).
7. The agent proposes repaying the ¥149,986.20 line draw (interest to date ¥1,236.05; lowest projected cash ¥384,795.56 on day 60). The owner says "go ahead"; it is repaid. No alerts remain.
8. Reconciliation: 3 matched, 0 flagged, no balance still drawn. The ledger holds 14 hash-chained entries and the chain is valid.
9. An attack through chat is harmless: a FastCapital message sent as a counterparty gets a reply that discloses nothing and carries no verdict or operations; the same text pasted by the owner into a quoted message is not taken as an instruction (the intent stays ambiguous), is logged as a security event, and executes nothing.

Other things the agent now says plainly. If the owner tells chat "we have a supplier bill of ¥80,000 due on day 30", it answers that it cannot record the fact and that the forecast is unchanged (it arms no confirmation and runs nothing). A buyer message about an invoice that is already past due needs the owner, with the invoice and the days named. A mandate within 14 days of expiry raises a warning on the home page with no button, because renewal is an offline owner step.

If the early payment never arrives, reconciliation reports it LAPSED and no committed plan restores the reserve: on day 34 the gap peaks at ¥455,013.80 and the alert falls back to the cure that only keeps cash at or above zero (¥155,013.80 on invoice financing, cost ¥1,381.32), titled "cash goes below zero on day 42 without action", and says that it does not restore the reserve (a probe of the demo path on 3 Oct: deal, then the clock to day 34 with no receipt).

An alternative start for the zero-floor cure: `POST /demo/reset?scenario=short_facilities` loads the golden books with the credit line and the invoice-financing limits cut to ¥60,000 each. No committed plan restores the reserve, so the alert reads "cash goes below zero on day N without action" and offers the cure that only keeps cash at or above zero. `POST /demo/reset` returns to the golden scenario. Scenario events (the golden scenario's month-2 payroll) apply only in demo mode, to books seeded from the scenario that carries them; this scenario does not add the payroll.

## Security scene (flag `FEATURE_SECURITY_SCENES`)
The FastCapital message (`SEC_DEMO_FASTCAPITAL`) is refused with UNKNOWN_COUNTERPARTY, UNEVIDENCED_PRIOR_CONCESSION and DATA_EXTRACTION_REFUSED. Then show:
- no facility added, no commitment, ¥0 moved;
- a reply that discloses nothing;
- three security events in the audit log, each with its span.

## Under the hood
compiler → schema → engine → router → verifier → executor → hash-chained log. The model can only propose.
