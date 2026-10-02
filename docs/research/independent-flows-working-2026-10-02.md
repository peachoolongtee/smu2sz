# Independent lifecycle, capex, borrower-file and UI audit working evidence

Primary analysis read code before walkthrough/invariant/demo claims. Prior audit conclusions were not used. No product code changed. All experiments used local in-memory stores, recorded compiler outputs/rules, no network or live endpoints.

## Principal verdict from this workstream

The product does not currently have one consistent issued-receivable book. Agreed terms exist as modifiers replayed onto whichever invoices remain open, while the executor and reconciliation use unmodified invoice records. This is more fundamental than presentation or optimization. Genuine owner approval does not repair the mismatch, and a finite approved scope can silently roll into later invoices.

## F1: Accepted price/terms never become the actual issued invoice

- **Severity/type:** HIGH; FINANCIAL / EXECUTION / COMPLETENESS.
- **Evidence:** REPRODUCED through real demo compiler, verifier, actual counter, owner approval, clock and SYSTEM receipt. CODE-INSPECTED: `clock/__init__.py:75` constructs invoices from raw recurring face/terms; `financial/trajectory.py:227` applies changes only inside projection; `operations/executor.py:943` receives against raw outstanding; `alerts/reconcile.py:223` uses raw due day.
- **Reproduce:** from `services/api`, run `TERMSLEDGER_NO_DOTENV=1 PYTHONPATH=. .venv/bin/python /private/tmp/termsledger_real_counter_probe.py`. The script compiles `EX01_PACKAGE`, evaluates, selects the real Option B counter, calls `propose_commitment`, `AcceptOffer`, owner `decide`, and `Runtime.advance_to(3)`.
- **Result:** Option B says 60-day terms plus 0.45% price adjustment. Newly issued `RI:BUYER-1:2` has face ¥420,000 and due day 47. Current-books projection expects ¥421,890 on day 62. An actual SYSTEM receipt of ¥421,890 is refused because the ledger says only ¥420,000 is outstanding. A ¥100,000 partial receipt succeeds, but forecast residual becomes ¥321,440 instead of ¥321,890: ¥450 of agreed value disappears because the modifier is reapplied to the residual base.
- **Related result:** `/private/tmp/termsledger_reconciliation_probe.py` puts a live extension on current books and advances to day 50. Projection receives `RI:BUYER-1:2` on day 62; alerts correctly omit an overdue warning; reconciliation falsely marks it past due on raw day 47.
- **Business consequence:** a legitimate payment cannot book; cash/AR cannot reconcile; collections can pursue a payment before its agreed due date; accepted price compensation used to justify a concession never exists in the settlement book.
- **Hackathon consequence:** the product's own Option B fails a closed-loop demo; the headline explanation of financing a terms extension with a compensating price adjustment is unsupported.
- **Recommended fix:** resolve agreement applicability into immutable invoice economic records at issue (face, due date, applied commitment/obligation ids); compute forecasts of unissued invoices with the identical materialization function. Receipts reduce the agreed invoice face, never a base face whose percentage is reapplied. All reporting/eligibility/settlement read those economic records. Corrections to issued invoices require explicit credit/debit-note events.
- **Effort/regression/confidence/build:** L; high (touches issued and forecast invoice lifecycle); 100% on demonstrated failures; NOW.

## F2: Next-three-invoice authorization keeps rolling forever

- **Severity/type:** HIGH; AUTHORITY / FINANCIAL / EXECUTION.
- **Evidence:** REPRODUCED with real rules compiler, verifier and genuine owner approval. CODE-INSPECTED: `financial/trajectory.py:165` excludes settled invoices; `:220` selects the first N of the surviving pool. No immutable allocation or consumption is recorded.
- **Reproduce:** `TERMSLEDGER_NO_DOTENV=1 PYTHONPATH=. .venv/bin/python /private/tmp/termsledger_real_bounded_probe.py`.
- **Result:** text “We'd like 50 days on the next 3 invoices instead of 45.” compiles bounded N=3. The verifier asks for owner approval; the owner approves. Initial invoice due dates are RI2=52, RI32=82, RI62=112, RI92=137. Three SYSTEM payments after the first three issue, on days 3/33/63, all EXECUTE. Projection now extends RI92/122/152 to days 142/172/202, although these were outside the approved scope. Commitment remains ACTIVE. The same issue affects ONE_OFF selection and count-bounded prices.
- **Business consequence:** finite concessions acquire an unapproved perpetual tail. Faster customer settlement changes which future invoices get the concession; this violates economic scope and authorization without an attacker needing prompt injection.
- **Hackathon consequence:** the bounded-vs-perpetual compiler demonstration is only syntactic; actual execution does not preserve that distinction.
- **Recommended fix:** anchor count scope to original issue sequence/invoice identities, include settled historical invoices when determining membership, and record per-obligation applied/fulfilled quantities. Never select “next N open invoices” again during re-projection.
- **Effort/regression/confidence/build:** M/L; high due to commitment completion and historical migration; 100%; NOW.

## F3: Capex recommendation ignores decision-material cash and fees

- **Severity/type:** HIGH; FINANCIAL / COMPLETENESS / UX.
- **Evidence:** REPRODUCED; `capex/evaluate.py:247` sums amortisation interest only, `:255` DSCR only adds existing `DebtPosition` service plus candidate payment, `:457` selects nominal interest; financed structures never run daily `project()`.
- **Reproduce:** `/private/tmp/termsledger_flow_probe.py` changes one input at a time. Add a known ¥10,000,000 outflow on day 1: 36-month loan still “Feasible”, selected, recommendation “Finance with...”. Set ETL upfront fee to 20%: selection and ¥53,206.14 total interest remain unchanged. That excludes ¥120,000 actual fee, exceeding the lease's entire ¥92,327.32 nominal interest. Set uplift zero: result says “Not worth doing ... Finance with the 36-month term loan”. API correctly refrains from queueing its application when worth_doing=False, but recommendation and selected UI remain contradictory.
- **Business consequence:** an insolvent daily cash position can be portrayed as financeable; an economically dearer loan can be selected as cheapest; a negative-value investment still receives financing instructions.
- **Hackathon consequence:** “best/cheapest financing” is indefensible outside the supplied zero-fee fixture.
- **Recommended fix:** until a complete cash-flow comparison exists, label as hypothetical covenant screen and nominal-interest comparison, remove “Finance with” for rejected investments, and avoid overall “feasible”. For real recommendations project purchase, settlement timing, fees, operating cash uplift separately from EBITDA uplift, existing facility service, repayments, residual/lease economics; rank comparable after-tax or explicitly pre-tax PV financing cash flows at one stated discount basis.
- **Effort/regression/confidence/build:** S to narrow, L to make comprehensive; medium/high; 100% reproduced omissions; NOW narrow, NEXT enrich only supported scope.

## F4: Capex models a financing term that the application cannot request

- **Severity/type:** HIGH; EXECUTION / FINANCIAL.
- **Evidence:** REPRODUCED candidate ETL 360 months accepted as feasible, despite menu ETL 36 months. `capex/evaluate.py:247` uses candidate arbitrary term; `api/capex.py:53` builds `ApplyForFacility` from facility id and amount only; actual operation carries no candidate term or schedule.
- **Business/hackathon consequence:** borrower believes a payment schedule was evaluated and approved that will never be the facility applied for or drawn. Default 18-month alternative is likewise a synthetic alternative absent from the menu.
- **Fix:** each candidate must be a complete evidenced financing quote with a unique version/fingerprint, or only evaluate the facility's actual tenor/repayment. Bind application and approval to that exact quote.
- **Effort/regression/confidence/build:** M; medium; 100%; NOW.

## F5: Equipment borrower pack silently retains the purchase proceeds

- **Severity/type:** HIGH; FINANCIAL / UX.
- **Evidence:** REPRODUCED plus CODE-INSPECTED. `apps/web/lib/demo.ts:80` names equipment purchase but supplies no `spend_day`; `borrower_file/build.py:528` includes a spending flow only when supplied. `:435` labels EBITDA “operating cash flow”.
- **Result:** same ¥600,000 loan, same intended machine: month-2 cash ¥1,261,855.38 when spend_day omitted (the actual web request); ¥661,855.38 with spend_day14. The default lender pack retains ¥600,000 cash while asserting the proceeds buy equipment. EBITDA is neither observed bank cash nor available debt-service cash.
- **Business consequence:** repayment capacity and liquidity evidence sent to a lender can be inflated by the whole equipment price, and profit is mislabeled as cash.
- **Hackathon consequence:** a CFO can invalidate the borrower pack immediately by asking where the purchase went.
- **Fix:** equipment pack must require or derive the purchase/spend schedule and propagate the evaluated structure/owner estimate. Unknown spend schedule must prominently prevent capacity conclusions; rename EBITDA exactly and separately show operating cash forecast.
- **Effort/regression/confidence/build:** S/M; medium; 100%; NOW.

## F6: Borrower-file approval does not authorize a meaningful effect

- **Severity/type:** MEDIUM; AUTHORITY / UX / ARCHITECTURE.
- **Evidence:** CODE-INSPECTED. `api/borrower_file.py:109` builds file before executor queue, `:122` caches regardless of result, `:126` download lookup never checks approval. Existing `tests/borrower_file/test_api.py::test_downloads` explicitly downloads while pending. `nl/capabilities.py:330` queues GenerateBorrowerFile but creates no retrievable artifact; executor `:729` just returns an authorization sentence.
- **Reproduce:** POST borrower file, download while pending, reject approval, download remains available. NL generate+approve returns “prepared” without a stored file id.
- **Business/hackathon consequence:** users cannot tell whether approval prepares a file, approves its financial contents, applies for financing or transmits information. One surface executes the purported effect before approval; another never performs it.
- **Fix:** make owner preparation a read-only artifact operation with provenance. Require approval for exact external disclosure/application only if that capability exists; unify NL/web artifact builder. Do not build an approval ceremony for generating a file that the authenticated owner already requested.
- **Effort/regression/confidence/build:** S/M; low/medium; high; NEXT.

## F7: Borrower-file forward window is anchored to day 0 and crashes after day 360

- **Severity/type:** MEDIUM; EXECUTION / UX.
- **Evidence:** REPRODUCED; `borrower_file/build.py:276` takes first twelve absolute months, `:448` lowest cash window is today..360, `:449` unguarded min.
- **Result:** generate on day34: “12-month” table starts day30 (a closed day), ends day360, not day394. Generate day361: ValueError “min() iterable argument is empty” (API catches only BorrowerFileError, so 500).
- **Fix:** rolling window today..today+360; report closed-month history separately; choose consistent partial-month debt service; prohibit indexing past absolute dates as forecast.
- **Effort/regression/confidence/build:** M; medium; 100%; NEXT.

## Additional UI evidence (CODE-INSPECTED)

- `apps/web/app/capex/page.tsx:78` always green NPV; omits result `estimate_note`, `worth_doing`, `recommendation` and workings; still offers file generation without valid selected financing. `lib/demo.ts:81` falls back to ETL when no selected facility exists. Do not imply observation from a scenario default owner estimate.
- Borrower-file display `capex/page.tsx:196` strips evidence labels, row notes, section notes and formulas although server returns them. Owner sees unqualified figures; downloadable artifact carries richer qualifications.
- Capex and borrower response persist in session storage and are not invalidated on `bump()`, clock advance or receipts. This should be a dated snapshot with state version and explicit re-evaluate action, not current recommendation. Funding snapshot does at least display a snapshot callout.
- `lib/live/approvals.ts:33` assigns current simulated day to every historical approval decision; “decided day” changes as clock advances. Preserve decision timestamp in the authoritative record or omit the claim.
- Reconciliation page has no rendering of new `promised` / `lapsed_promises` fields; missed agreed payment is not directly visible in its own promise-to-receipt screen.
- PlanCard reports request day and repayment day, but no cash landing day for each action; an operation result saying executed can be read as cash availability. Show requested, pending settlement and settled as distinct states.

## Decision-material omissions and simplifications

CODE-INSPECTED `domain/models.py:238`: facilities have no dated maturity, expiry, availability end, cancellation/freeze, quote version or concentration/eligibility rule. `Receivable:343` has confirmation/status but no dispute, assignment/pledge, currency or allocation to multiple receipts/claims. Conservative decision scope must explicitly exclude unsupported facts rather than treating owner-approved + confirmed as universal eligibility. Do not recommend every lending product: impose a narrow supported contract.

Application handling `executor.py:1004` only sets PENDING; no operation changes an existing approved facility to COMMITTED. The unused mock lender is acknowledged in walkthrough. This is a preparation/demo workflow, not a live financing lifecycle. Do not add realistic-looking lender orchestration before exact quotes, pending settlement, failure and contract update semantics exist.

Consolidate three duplicated mechanisms: agreement→invoice economic materialization; facility quote/eligibility→admissibility (router, alerts greedy cure, capex, borrower); dated funding/debt event schedules (projection and execution). Keep accounting context/event schedules explicit, rather than hiding inconsistencies behind a generic “current_books” wrapper. Remove borrower-file Tier2 ceremony, unused aftersign stub and broad lease/equity/payment-instrument claims where unsupported.

## Tests run and tests needed

`TERMSLEDGER_NO_DOTENV=1 .venv/bin/pytest tests/alerts tests/borrower_file tests/capex tests/whatif tests/books/test_capex_borrower_alerts_on_books.py -q` completed exit 0, 100%. This does not validate the newly demonstrated properties.

Add end-to-end properties:

1. Accepted future terms/price become identical issue face/due in projection, clock, invoice-finance eligibility, receipt execution and reconciliation.
2. Agreed invoice amount = total booked receipts + credits/writeoffs + economic outstanding after every partial receipt (fen-exact).
3. Settling invoices never expands a count-bounded concession; first N scope remains identical after settlement, retries and clock advance.
4. Real Option B accepted by owner can book its full agreed receipt and subsequently reports settled, not unmatched.
5. A known extra outflow cannot preserve a financed capex feasibility result when it creates a reserve breach; adding fees cannot reduce compared financing cost.
6. Selected financing fingerprint, tenor, repayment and fees match the application and approval exactly.
7. Equipment pack deducts its stated purchase, tags estimates, and projects exactly twelve future months from any valid current day.

Questions changing the design: Are price changes contractual invoice amounts or merely forecasts? Does “next N invoices” mean the original issue sequence or N open balances (the latter must be named and priced differently)? Is capex a conditional covenant screen or an investment/funding recommendation? Does borrower approval authorize preparation, disclosure or a financing application? Are bills/debt service actual bank events or calendar assumptions? These answers must enter typed semantics, not only documentation.

## Go/no-go conditions

No real autonomous concessions or borrower submissions until F1/F2 are closed with actual issue→receipt traces. A bounded, explicitly simulated read-only hackathon can proceed with unsupported recommendation claims removed; avoid showing “all guaranteed” security/financial readiness. Next deep dive: crystallized invoice economics and scope; exact financing quotes/cash settlement schedules; evidence-qualified owner decisions and lender artifact provenance.
