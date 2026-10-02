# TermsLedger v2 — independent principal audit

Completed 3 October 2026 (Singapore). Primary analysis: commit `8c419efd4ea390f4a15ae547ca540ad27858adbb`; subsequently reconciled with remote close-out commit `b0e0ab6`. This is an audit, not an approval to deploy or an implementation of its proposed fixes.

The required handover was read first and necessarily exposed earlier findings. Its conclusions were set aside. Three bounded reviewers read actual implementation before documentation and did not consult the earlier audit. The principal reconstructed books, execution, clock and persistence independently, then compared with the prior audit. Existing tests, golden fixtures, financial ADRs and derivation notes, the supplied SYSTEM_WALKTHROUGH, API/demo paths, security/evaluation reports and frontend source were inspected. Browser interaction is separately identified in the integration record; it is not evidence of financial correctness.

Evidence labels:

- **VERIFIED:** an assertion independently checked against source, arithmetic or an observed control.
- **REPRODUCED:** a local execution produced the stated counterexample; provenance identifies principal or bounded reviewer.
- **CODE-INSPECTED:** an execution path was traced but the complete failure was not run.
- **INFERENCE:** the business consequence follows from identified assumptions; not an observed external loss.
- **UNVERIFIED:** live model/provider, actual bank, PostgreSQL concurrency or legal enforceability was not tested.

Full technical evidence and formula details accompany this report: [financial evidence](independent-financial-working-2026-10-02.md), [security evidence](independent-security-working-2026-10-02.md), [flow evidence](independent-flows-working-2026-10-02.md). Those documents include commands, source lines, assumptions and detailed secondary findings. Reviewer scripts and request/response/state evidence are now preserved in [independent-audit-evidence-2026-10-03](independent-audit-evidence-2026-10-03/README.md). The principal's persistent [books probes](../../scripts/independent_audit_books.py) run only isolated memory/cache stores and assert the observed defects, not desirable regression behaviour. The principal also reran the security, real Counter B and real bounded-invoice probes after reconciliation; the central failures still reproduce.

## 1. Executive verdict

**NO-GO for autonomous financial use and live deployment.**

| Question | Verdict | Reason |
| --- | --- | --- |
| Financially trustworthy? | No, at product level | Accepted invoice economics do not become executable invoice balances; finite concessions can continue indefinitely; existing debt schedules and capex balances diverge. Correct arithmetic primitives do not repair these modelling errors. |
| Safe to act within stated bounds? | No | Negated owner instructions execute; explicit rejection can approve; unauthenticated buyer impersonation activates commitments; direct agent operations bypass material financial predicates. |
| Internally consistent? | No | Projection, executor, clock, reconciliation and capex describe different amounts, dates, debt and admissibility. |
| Ready for live models? | No | The wrong-execution defects exist in deterministic rules before the model runs. Live extraction adds unverified interpretation/fallback behaviour. |
| Ready for PostgreSQL? | No | Startup resets persisted ledger/state even outside demo mode. SQL transactions lack a demonstrated cross-process state-version/serialization boundary. The latter remains UNVERIFIED on PostgreSQL. |
| Defensible controlled demo? | Conditional | A scripted memory/cache demo can complete. It must be described as simulation and cannot substantiate the autonomy, one-books, cheapest-finance or bank-covenant claims. |

The fundamental assumption should change: **adding live obligations to a forecast does not create one coherent set of books.** An accepted commercial contract must define which invoices it affects; issuance must crystallise their contractual amounts/due dates; settlement must reduce those same balances. A loan must have an outstanding dated schedule shared by forecast and execution. Currently obligations are repeatedly reapplied to whatever invoices remain open, and loans are reconstructed from balances without their original contract dates.

Baseline on the primary revision: **4,033 passed, 19 skipped in 199.88 seconds**. The main demo completed its receipt, cure and repayment path. Independent counterexamples succeeded despite this baseline. Test counts are evidence of repeatability of encoded assumptions, not proof of the financial model.

## 2. Top critical findings and finding register

### A01 — Non-affirmative commands execute financing

**CRITICAL · AUTHORITY / EXECUTION / FINANCIAL · REPRODUCED by security reviewer · BUILD NOW · effort M · regression risk medium · confidence high.**

Evidence: `nl/rules.py`, `nl/service.py`, `nl/funding.py` recognise action words and execute rule-derived funding requests without proving the entire instruction is affirmative. Both owner and agent credentials are affected. On reset golden books, POST `/nl` with actor OWNER and `Do not draw ¥100,000 on the credit line.` executes a ¥100,000 draw. A safety question, an unmet cash condition, tomorrow, and Chinese negation do the same. `$100,000` and `¥1.001` can lose the explicit amount and execute the default ¥360,000 funding bundle.

Business consequence: unwanted debt/encumbrance contrary to expressed intent. Hackathon consequence: one ordinary sentence defeats the zero-wrong-executable claim. Fix: disable direct execution from general NL intent matching; generate a complete typed proposal. A small affirmative grammar or explicit UI action may authorise the exact proposal after every material term is accounted for. Invalid explicit amounts must cause clarification, never default funding.

### A02 — A rejection is interpreted as approval

**CRITICAL · AUTHORITY / SECURITY · REPRODUCED by security reviewer · BUILD NOW · effort S/M · regression risk medium · confidence high.**

Reproduce: queue an agent-originated RECEIVE_PAYMENT for ¥100, obtaining APR-000001. As authenticated owner, say `Do not approve APR-000001`, `Should I approve APR-000001?`, bare `APR-000001`, or `Reject APR-000001, do not approve`. Each approves and executes the receipt. Approval-ID recognition and confirmation cues outrank rejection; the short/direct-command check does not establish consent.

Business consequence: genuine human disapproval authorises a queued operation. The receipt is a minimal local proof; other Tier-2 operations use the same approval parser. Hackathon consequence: approval cards/tiers cannot defend authority. Fix: require an exact affirmative decision tied to the shown operation; negation, questions and conflicting verbs must never approve. Bare identifiers are references. Explicit rejection must be unambiguous and cannot lose to a substring `approve`.

### A03 — An unauthenticated buyer identity creates commitments

**CRITICAL · SECURITY / AUTHORITY · REPRODUCED by security reviewer · BUILD NOW · effort S/M · regression risk medium · confidence high.**

Reproduce without headers: POST `/nl` with actor COUNTERPARTY, counterparty_id BUYER-1 and `We will pay the ¥420,000 invoice early at a 0.5% discount.` The response hides operations but the ledger records ACCEPT_OFFER EXECUTED and an ACTIVE commitment with a ¥2,100 discount. Also reproduced with DEMO_MODE=0 and no configured owner/agent credentials. `nl/offers.py` calls execution on this path; knowing a registry ID is treated as sender identity.

Business consequence: forged promises/concessions alter liquidity projections even if no bank transfer occurs. Hackathon consequence: the public chat is a financial write surface. Fix now: unauthenticated intake may only store/evaluate an untrusted proposal. Require authenticated counterparty-channel evidence and its authorised scope before autonomous acceptance. Response field scrubbing is not an execution gate.

### A04 — Runtime startup deletes persistent economic state

**CRITICAL · EXECUTION / SECURITY · REPRODUCED on SQLite by security reviewer; PostgreSQL path CODE-INSPECTED · BUILD NOW · effort S/M · regression risk medium · confidence high.**

Reproduce with temporary SQLite and DEMO_MODE=0: execute a ¥100,000 line draw, dispose the runtime, then initialise it again. Cash ¥500,000 becomes fixture ¥400,000; drawn balance ¥100,000 becomes zero; operation count one becomes zero; day resets to zero. `api/runtime.py:get_runtime` unconditionally calls reset, and `SqlLedgerStore.reset` clears ledger tables.

Business consequence: restart loses debt, approvals, replay memory and audit evidence. Hackathon consequence: persistence claims fail a restart demonstration. Fix: hydrate existing state/day/key configuration on startup; seed only a deliberately empty demo store; make demo reset unavailable against a non-demo database. Verify restart with completed/pending operations and receipts. Restoring a database backup is not the application startup contract.

### A05 — Executor admits operations the planner rejects

**CRITICAL · FINANCIAL / AUTHORITY / EXECUTION · REPRODUCED by principal · BUILD NOW · effort M/L · regression risk high · confidence high.**

Persistent probe `advance_exceeds_remaining_invoice`: receive ¥350,000 on RCV-A, leaving ¥70,000 outstanding. Planner rejects a ¥100,000 advance at an 80% advance rate; direct agent `/operations` executes it because `_finance` compares with original ¥420,000 face. `funds_before_lead_time`: day-31 financing is rejected by projection because day-34 arrival is after day-32 due; executor immediately credits ¥100,000. With a controlled committed tariff of 30% versus the signed 15% cap, Tier-1 financing executes. With EBITDA ¥1,000/month, Tier-1 draw executes despite subsequent DSCR/leverage breaches.

Business consequence: the agent can create inadmissible debt through an alternate route. Hackathon consequence: the verifier is advisory rather than an invariant at execution. Fix: one shared current-state action-admissibility function inside the transaction, including outstanding collateral, arrival, fees, debt, covenants, cash floor, borrowing permission and the explicitly defined rate cap. Owner approval cannot silently waive a contractual or hard prohibition. Protect mandatory bank receipts with separate ingestion semantics rather than refusing financial truth because a mandate expired.

### A06 — Accepted price and terms never become issued invoice economics

**HIGH · FINANCIAL / EXECUTION · REPRODUCED by flow reviewer through genuine compiler/verifier/owner path · BUILD NOW · effort L · regression risk high · confidence high.**

Reproduce real EX01 Option B: compile, evaluate, propose its 60-day/+0.45% counter, queue and genuinely approve it, then advance to day 3. RI:BUYER-1:2 is issued at ¥420,000 due day 47; current-books projection expects ¥421,890 due day 62. A bank receipt of the agreed ¥421,890 is refused as exceeding outstanding. After ¥100,000 partial receipt, projection expects ¥321,440 instead of ¥321,890: **¥450 disappears** because the price increment is applied again to the residual base. Reconciliation can call the same invoice overdue on day 47 while alerts/projection use day 62.

Business consequence: the agreed receivable cannot be settled or reconciled; partial payment destroys value. Hackathon consequence: the product's own counter cannot complete its lifecycle. Fix: resolve commercial terms at issuance into contractual face/due, preserving original values and commitment provenance. Apply price/terms exactly once; receipts reduce contractual face without repricing the balance. All modules read the same invoice position.

### A07 — Approval of the next three invoices expands to later invoices

**HIGH · AUTHORITY / FINANCIAL · REPRODUCED by flow reviewer through genuine compilation/approval · BUILD NOW · effort M/L · regression risk high · confidence high.**

Reproduce `We’d like 50 days on the next 3 invoices instead of 45.` Approve its bound three-invoice commitment. Initial issue days 2/32/62 receive +5 days; issue day 92 does not. Settle the first three after issuance on days 3/33/63. Now issue days 92/122/152 receive +5 days and the commitment remains ACTIVE. `_receivables` removes settled invoices and `_select_invoices` truncates the surviving open pool to three, continually replacing the approved set.

Business consequence: finite consent becomes rolling consent and concessions exceed their priced scope. Hackathon consequence: a bounded autonomous mandate does not bound actual commercial effects. Fix: bind to immutable invoice sequence/IDs, not current open status; retain consumption history and end the finite obligation when the approved sequence is fulfilled. Settling an invoice cannot make the fourth invoice inherit its authority.

### A08 — Forecast debt dates and actual passage of time disagree

**HIGH · FINANCIAL / EXECUTION · REPRODUCED by principal and financial reviewer · BUILD NOW · effort L · regression risk high · confidence high.**

Evidence: executor credits draws/advances immediately; projection applies lead time. Clock posts only state.flows and issuance/expiry, not the projected loan repayment schedule. A line repayment projected on day 47 remains a ¥150,000 actual balance after advancing to day 48. An as-of-day-61 amortising balance with actual cash ¥1m is projected to pay ¥10k on closed days 30 and 60, reducing projected current cash to ¥980k. New advances are carried as though drawn on day 0, unlike execution's logged date; fees/interest may cross different period boundaries.

Business consequence: invented cash, backdated payments, wrong interest, and misplaced maturity/clean-down. Hackathon consequence: advancing time does not preserve the originally displayed economics. Fix: persist settlement dates and outstanding contractual schedules; separate requested/pending/settled/failed funding; projection and actual events consume the same schedule. A projected discretionary repayment must remain a proposed action until executed. A due scheduled payment is a liability until an external payment event settles it; it must not vanish merely because the forecast assumes payment.

### A09 — A late receipt earns the expired early-payment discount

**HIGH · FINANCIAL / EXECUTION · REPRODUCED by principal · BUILD NOW · effort S/M · regression risk medium · confidence high.**

Real negotiated Counter A promises day 2, face ¥211,900, net ¥210,098.85. Advance to day 34 without receipt, then record exactly that net amount. `_early_pay_match` ignores the promised date, settles ¥211,900 and marks FULFILLED. The buyer receives **¥1,801.15** discount despite paying after the original day-32 due. Projection had already lapsed that early-payment obligation.

Business consequence: financially unsupported receivable write-off. Hackathon consequence: missed-promise monitoring does not govern settlement. Fix: record the cash receipt regardless, but permit discounted face settlement only when the contractual deadline/condition is satisfied or an explicitly authorised credit note exists. Reconcile a late discounted amount as a short payment; do not infer a waiver from equal amount alone.

### A10 — Confirmation approves a goal rather than the shown economic plan

**HIGH · AUTHORITY / EXECUTION · REPRODUCED by security reviewer · BUILD NOW · effort M · regression risk medium · confidence high.**

Show `Find me the cheapest way to fund the cash gap`: line ¥150,000 + advance ¥210,000, cost ¥2,712.94. Reduce actual cash by ¥100,000 and increment state version, then say `go ahead`. It replans to line ¥150,000 + advance ¥260,600, cost ¥3,763.84, and executes. PendingPlan stores goal/slots rather than immutable economics.

Business consequence: approval expands amount/cost/facility scope silently. Hackathon consequence: the shown plan is not what is approved. Fix: bind confirmation to canonical plan/action amounts, facility versions, contractual dates/cost basis, mandate version, state version and expiry. State changes may revalidate without reapproval only inside explicitly accepted tolerances; a cheaper plan can still change recourse, collateral, timing or lender and needs semantic comparison.

### A11 — Future gains and horizon scaling distort concession caps

**HIGH · FINANCIAL / AUTHORITY · REPRODUCED at typed valuation/predicate layer by financial reviewer · BUILD NOW for date/netting; NEXT for broader valuation · effort M · regression risk medium · confidence high; NL reachability of day-1000 example UNVERIFIED.**

A +1% perpetual price adjustment starting day 1000 is valued at −¥50,400 inside a 365-day horizon despite contributing no projected cash within it. It offsets a ¥6,000 rebate and passes a ¥5,000 cap. Separately identical three-invoice exposure costs ¥5,178.08 when bounded but ¥1,276.79 when perpetual at horizon 90; horizon 730 doubles the corresponding annualised cost again. The perpetual formula uses horizon-period sales and then multiplies by horizon once more. Extension service also assumes one invoice per month regardless of cadence.

Business consequence: caps/ratios pass for gains outside the period or incorrect exposure frequency. Hackathon consequence: changing wording/horizon changes economics for identical invoices. Fix: use the same dated affected-invoice schedule for valuation and projection; define the valuation interval starting today; offset only qualifying evidenced gains on that basis. Separate working-capital stock from funding expense. Match bounded/perpetual cases containing identical invoice sets.

### A12 — Capex recommendations omit material cash and debt

**HIGH · FINANCIAL / COMPLETENESS / UX · REPRODUCED by financial and flow reviewers · BUILD NOW to narrow; NEXT to enrich · effort S to narrow, M/L for full evaluation · regression risk medium/high · confidence high.**

Examples: a known ¥10m day-1 outflow leaves a loan feasible; existing ¥1.2m amortising debt yields displayed DSCR 2.40 instead of 0.80; a zero-interest loan with ¥60k upfront fee is chosen over a fee-free loan with ¥3,254.95 interest. A 360-month candidate is evaluated against a fixed 36-month facility but application carries only facility and amount. A project with zero uplift receives `Not worth doing` plus `Finance with…`. Cash+line feasibility bypasses borrowing/APR predicates. See financial F03–F05 and flow F03–F04.

Business consequence: an investment can be recommended with unpayable service, unaffordable dates, higher true cost or unavailable contractual tenor. Hackathon consequence: a CFO disproves “best” using the fee line. Fix now: suppress financing recommendations and label unsupported structures hypothetical nominal-interest/covenant illustrations. Next represent evidenced quotes, purchase cash, existing schedules, fees, ownership/residual outcomes and dated financing payments over current books. Compare a common PV basis where alternatives are economically comparable; otherwise show alternatives without a winner.

### A13 — Borrower pack can retain equipment purchase cash

**HIGH · FINANCIAL / UX · REPRODUCED by flow reviewer · BUILD NOW · effort S/M · regression risk medium · confidence high.**

Web-generated equipment pack omits spending date. It describes equipment borrowing but retains the ¥600,000 proceeds; month-2 cash is ¥1,261,855.38 versus ¥661,855.38 when the purchase is included. It labels monthly EBITDA operating cash flow. At day 34 its “12-month” forecast includes a closed day-30 row and stops at day 360; day 361 can crash with empty min().

Business consequence: a lender-facing file overstates available cash and mislabels repayment evidence. Hackathon consequence: the export contradicts the stated funding purpose. Fix: require dated use of proceeds; expose assumptions and reconcile cash/debt to current books. Forecast twelve months forward from today. Distinguish EBITDA, CFADS and bank cash rather than substituting their names.

Secondary findings have full cards in accompanying evidence: synthetic bullet DSCR (financial F10, HIGH/NOW); realised APR versus tariff (F08, HIGH/NOW); recurring upfront fee in break-even (F09, MEDIUM/NEXT); effective lease rate treated nominal (F11, MEDIUM/NEXT); undefined EBITDA/negative ratio display (F12, MEDIUM/NEXT); borrower preparation approval theatre (flow F06, MEDIUM/NEXT). Cross-process races, fresh-key bank duplicates and chain truncation are explicitly scoped in sections 7 and 17, not represented as reproduced PostgreSQL failures.

## 3. What is new versus already documented

Comparison was performed only after primary findings were recorded. “New” here means absent from the 1-Oct audit's specific conclusions and the supplied walkthrough, not proven never discussed anywhere.

| Findings | Comparison |
| --- | --- |
| A01/A02: negation, questions, conditions, invalid amounts and explicit refusal execute | New mechanisms; prior pasted-approval finding S2 did not cover direct non-consent. The later direct-command patch does not fix this. |
| A04: startup destroys persistence | New specific release-blocking mechanism. Earlier audit called persistence complete. |
| A05: original-face financing after partial settlement; direct financial-predicate bypass | New specific execution counterexamples. Earlier “advance-rate caps should not be rebuilt” is not justified across executor/projector. |
| A06/A07: real Counter B uncollectable; residual value destroyed; finite scope rolls | New lifecycle counterexamples after current-books changes. Earlier accepted-terms concern existed, but overlay projections did not solve crystallisation or scope consumption. |
| A09: late receipt still receives early discount | New concrete settlement/expiry defect. |
| A11: day-1000 gain offsets cap, quadratic horizon, invoice-frequency service | New derivation/predicate defects. |
| A08: immediate funding and manual projected repayment | Previously documented in walkthrough/tracker; closed-day carried amortisation and drawn-date charges are new concrete extensions. |
| A03/A10: buyer spoofing and confirmation replan | Previously documented as S6/S10; this audit elevates them because realistic operations reproduce financial state harm. |
| A12: nominal-interest capex ranking/effective lease convention | Earlier F9. Ignored fees, drawn service, liquidity, actual tenor and recommendation on rejected investment are additional counterexamples. |
| Realised APR, future-invoice financing, mandate key/lifecycle, unanchored chain | Previously documented; open status is not acceptable authority for live deployment. |

Completed tracker rows B1/B3/B4 are insufficient evidence of “one financial reality”; D4's level bullet service addresses an annual reserve approximation but not the stated monthly scheduled-service covenant. This audit specifically reopens those guarantees, not merely their UI.

## 4. Financial formula audit

The accompanying financial report contains the full formula table with economic interpretation, input units, day count, timing, rounding point, boundary behaviour, assumptions and match assessment for every requested category. The principal independently recalculated the material day-0 headline arithmetic:

| Quantity | Formula and independent result | Meaning/limits |
| --- | --- | --- |
| Line cost | post(¥150,000 × 0.064 × 32/365) = ¥841.64 | Actual/365 simple, posted at repayment; original draw date must be real. |
| Invoice financing | post(¥210,000 × .078 × 30/365) + post(¥210,000 × .0025) = ¥1,871.30 | One billed 30-day period, even though day-3 arrival to day-32 receipt is 29 days. |
| Baseline plan | ¥841.64 + ¥1,871.30 = ¥2,712.94 | Sum of posted parts; assumes those exact settlement/repayment dates. |
| Counter A | Discount ¥1,801.15; proceeds ¥210,098.85; residual line ¥149,901.15; line interest ¥841.09; total ¥2,642.24 | Arithmetic matches. It is not proof that the simulated buyer pays or the line actually repays day 32. |
| Early-pay implied annual rate | d/(1−d) × 365/n | Correct simple rate on net accelerated proceeds; d must be in [0,1), n>0. Not interchangeable with face-denominator tariffs. |
| Break-even | d*=c/(1+c), strict cheaper requires d<d* | Requires equivalent net proceeds, tenor and usable source. Upfront fee cannot repeat with every billing period. |
| Partial early face | minimal integer F satisfying F−post(dF)≥net need | Test fen boundary after posting; tidy rounding can only increase F subject to invoice outstanding/caps. |
| Amortisation | A=Pj/[1−(1+j)^−M], nominal j=r/12 | End-period interest rounded each month, final principal clears. Effective annual lease rate requires an effective monthly conversion. |
| Bullet service | contractual due principal+interest belongs to its contract-defined measurement window | Current level spread is a reserve-coverage proxy. Keep that name distinct from bank monthly DSCR. |
| Extension cost | Σ qualifying invoice face × delay × rate/365 | Simple approximation; not an exact whole-period lending cost. Structural tied-up cash F×delay/invoice interval is a stock, not an expense. |
| Project NPV | −purchase + Σ net project cash_m/(1+h)^(m/12) | Exact declared model using Decimal; no guarantee that EBITDA uplift equals net incremental cash. |
| Payback | first month cumulative undiscounted net project cash≥purchase | No payback if not reached inside life; no substitute for NPV. |
| Financing PV | PV(all dated net financing outflows)−net proceeds, common basis | Not the current capex ranking. Rentals, ownership/residual and fees may make alternatives incomparable without more inputs. |

Whole-period boundaries independently considered: 1/29/30 days bill one period, 31/59/60 two, 61/89/90 three, 91 four. Zero-day billing primitive has a minimum period; admissible funding normally must have a positive actual tenor. A ¥100k one-day advance costs ¥891.10 under the fixture tariff, about 325.25% simple annualised on principal, while the menu reports 10.84%. Choosing a contractual-tariff cap can be legitimate policy; calling it realised maximum APR is not.

DSCR/leverage thresholds use exact ratios; zero/negative EBITDA must yield explicit undefined/breach states, not uncaught capex errors. Clean-down requires a defined window/history, not a conveniently short projection. Ratios at month end cannot certify a daily debt limit. Forward values must not net future gains from outside their period. Cost ordering by nominal posted charges must be called a bounded search objective, not a globally cheapest treasury strategy.

No contractual debt-service definition is universal. The intended ledger must reconcile opening/closing financing liabilities and actual movements; this is consistent with [IAS 7's financing-liability reconciliation requirements](https://www.ifrs.org/issued-standards/list-of-standards/ias-7-statement-of-cash-flows.html/). This is contextual support, not a claim TermsLedger is an IFRS accounting system.

## 5. Lifecycle and planner versus executor

| Transition | Source of truth / authority / state effects | Audit conclusion |
| --- | --- | --- |
| NL → compilation | Untrusted documents; rules/cache/model propose typed rows and spans | Spans prove occurrence of text, not complete financial intent. Owner command rules have weaker safety than offer coverage. |
| Compilation → binding | Registered buyer/current invoices/recurring templates | Identity is body-supplied; relative dates can be replaced by fixed lead time; finite invoice scope is not frozen. |
| Binding → current books | Persisted FinancialState plus live obligations | Overlays are forecasts; raw issued amounts/due dates remain different. Closed-day debt can be reposted. |
| Books → projection → funding search | Pure scenario events and selected facilities | Future recurring invoices become confirmed hypothetical receivables. Forecast does not establish current collateral or settled cash. |
| Search → covenant/mandate → verdict | Exact predicates on represented cash/ratios | Economic correctness depends on omitted dates/debt/eligible collateral and the contractual measurement basis. |
| Verdict → human/agent authority | Tier, signed version, approved operation | Direct parser non-consent failures; stale goal confirmations change economics; re-verification must propagate authority requirements, not just outcome. |
| Operation → persistence | Executor and store transaction | Some financial preconditions bypass verifier; API-process locks do not establish multi-worker serialization. Startup reset is destructive. |
| Time → external event | Clock simulation and SYSTEM/owner receipts | Funding/repayment time differs between forecast and actual books; receipt authority is separate from receipt truth. |
| Receipt → reconciliation | Invoice face/status and accepted promises | Late discounts, accepted adjusted invoices and partial balance repricing fail economic conservation. |
| Reprojection → alert/cure | New forecasts plus greedy cure suggestions | Alert cure admissibility differs from router; supported plan actions are only partly materialised. A warning is not enforcement. |
| Completion | Commitment status, receivable settled amount, debt balance | Finite future commitments do not consume scope correctly; concessions can remain booked until revoke; repayment may exist only in projection. |

Important per-operation comparison:

| Operation | Planner/verifier | Executor/ledger | UI implication |
| --- | --- | --- | --- |
| Draw | Cash after lead; repayment dates/interest in forecast | Cash immediately; only balance/operation persisted, repayment discretionary/manual | “Funded” can mean requested, projected or actual cash depending on path. |
| Invoice finance | Outstanding face, effective projected due, arrival before due | Original face, raw due, cash now | A displayed rejected source can still execute; quoted cost period can differ. |
| Early-pay accept | Promised date and face, discount changes forecast | Commitment overlay; receipt amount alone may waive face later | “Agreed” neither authenticates buyer nor guarantees cash; missed promise can still earn discount. |
| Terms/price accept | Future invoices shift face/due | Raw recurring invoice issued; modifiers remain live | Projection receipt can be refused; reconciliation disagrees with alert. |
| Repay | Assumed affordable date, FIFO amount/interest | Explicit operation charges logged lot days | Forecast payment is not an executed standing instruction. |
| Apply / borrower file | Hypothetical funding or pack | Application becomes PENDING; no complete quote settlement lifecycle | Application/pack generation is not committed liquidity or transmission. |
| Clock | Forecast posts scheduled finance | Clock only closes its actual flow list | Forecast suffix is not invariant under advancing time. |

## 6. Authority and mandate audit

| Mandate field | Intended classification | Actual enforcement issue |
| --- | --- | --- |
| min_cash_fen | Financial hard limit under declared forecast basis | Router/verifier check; direct draws/repayments are not evaluated against complete future cash at executor. |
| max_aggregate_forward_concession_fen, per_buyer_caps_fen | Hard cap | Accept gate rechecks booked values, but scope/valuation can be wrong. Future gains net outside horizon. |
| max_immediate_discount_bp | Pricing ceiling; clarify owner override policy | Verifier pricing fault, not a shared operation-wide hard prohibition. |
| min_dscr_bp, max_leverage_bp | Financial hard limits | Checked in some projections; direct funding and capex can bypass or calculate different books. |
| max_apr_bp | Named maximum, metric/policy ambiguous | Tariff/realised yield differ; alerts may flag rather than block; executor does not universally gate. Rename or define enforceable meaning. |
| require_clean_down | Contract/owner requirement | Forecast window test; history/observation period missing; capex has separate approximation. |
| allow_new_borrowing | Hard prohibition | Draw/finance gate checks it; capex cash+line can claim feasible anyway. |
| tier2_single_commitment_fen | Autonomy limit | Applies concession value on accepted commitments, not gross affected invoice exposure; committed facility draws are Tier 1 within facility room regardless amount. Label exactly what “single commitment” measures. |
| horizon_days, forward_concession_horizon_days | Analytical scope | Not authority to ignore maturity or losses; inconsistent today/horizon/frequency valuations. |
| org_id / version / signing key / revoked / expiry | Identity and authority validity | Demo key pinned in runtime; replacement/revocation not operable through a supported owner flow; issuance-day lower bound is not checked by validity. |

There are no first-class warnings/preferences fields. Some “maximum” behaviour acts as pricing or warning depending on route, so the distinction must be made explicit. An owner approval should override only declared autonomy limits; it cannot silently change hard prohibitions or lender contract eligibility.

Approvals are tied to stored canonical operation data, and commitment nonce/hash/version checks provide specific controls against changed payloads. They do not make the NL decision correct, bind a goal confirmation, or freeze invoice scope. Old versions/revocation/expiry are checked at operation time in code, but automatic pending-approval invalidation and a real signed mandate replacement flow are absent. Existing contracts survive a revoked agent mandate; reducing new authority must not erase genuine receivables/debt or block ingestion of their bank events. Current executor's global mandate validity gate conflates these concerns.

## 7. Security and failure modes

Primary reproduced attack classes are A01–A04 and A10. This audit sought economic state harm, not just transfers: a forged receivable promise changes financial decisions; a perpetual scope expansion leaks authority; wiped replay history breaks later recovery. Existing catalogues' “zero harm” describes their particular attempts, not the public surface.

| Failure/attack | Evidence and result | Exact next control |
| --- | --- | --- |
| Prompt/quoted-text injection, fake lender/prior agreement | Existing focused tests and catalogue pass locally; finite catalogue coverage only VERIFIED | Retain controls; add genuine non-consent/semantic transformations and evaluate full persisted state, not response text alone. |
| Buyer impersonation | REPRODUCED even outside demo auth | Authenticate sender/channel or make public intake proposal-only. |
| Receipt replay with same idempotency key | Existing controls VERIFIED in local tests | Retain transaction+duplicate behaviour. |
| Same external bank event with new keys | CODE-INSPECTED design gap: receipt has no independent bank transaction identity; INFERENCE of double partial settlement | Require unique external event ID and semantic digest; altered duplicate payload must conflict. Two legitimate equal-amount receipts must remain distinct. |
| Failed log append/transaction rollback | Existing memory/SQLite rollback tests pass; no external side effect model | Keep one transactional local operation; record external command result/outbox if real execution is later introduced. |
| Multi-operation plan partly commits | CODE-INSPECTED: plan loops execute individual units; rt.lock is not a bundle transaction | Define partial outcome/recovery. Reserve and authorise whole plan; do not label all funded when one leg fails. Real bank events cannot be rolled back by SQL. |
| Response lost after commit | Same-key retry is locally safe; new NL session/request key is not stable economic identity | Persist request/plan command identity independently of in-memory chat sessions. |
| Process restart | REPRODUCED destructive reset | Hydrate state; preserve nonce/approval/command history. |
| Multiple API workers | CODE-INSPECTED risk: RLock is process-local; SQL state snapshots have no unique org/version CAS boundary | Database serialization/advisory lock or compare-and-swap per organisation; test real PostgreSQL with forced interleavings. Exact harm UNVERIFIED. |
| LLM timeout/malformed output/fallback | Backend fallback code/tested offline; live chain UNVERIFIED | Differentiate no interpretation from changed interpretation; abstain on material residue; never escalate fallback into permission. |
| Funding fails or terms change | No complete pending settlement/failure/quote lifecycle | Freeze quote; zero cash until settlement; failure releases reservations and reprojects without inventing proceeds. |
| Chain truncation/rewrite | CODE-INSPECTED, previously documented: head/count not anchored externally | Limit claim to internally checkable chain; before live use authenticate/checkpoint head plus event scope. |
| Reserve/threshold probing | Previously documented; behavioural outcome is an oracle even with clean reply | Authenticate/rate-limit counterparties; minimise exact counter quantities exposing need/caps; disclose commercial prices deliberately. |

Unicode/mixed-language examples in the existing catalogue pass, while new Chinese negative owner commands fail. Live provider fallback, malicious document extraction beyond supplied text, timing side-channel exploitation, actual lender feeds and infrastructure compromise remain UNVERIFIED. These limits are specific, not a blanket security certification.

## 8. Decision-material business gaps

Build the minimum evidence that changes admissibility: issued vs forecast invoice; disputed/assigned/pledged eligibility; outstanding versus original face; explicit facility maturity/availability and funding settlement/failure; contract fees and repayment dates; duplicate external-event identity; credible payroll/supplier/tax/outflow horizon; debtor lateness and overdue recourse. The golden buyer is 100% of receivables. Treating every recurring invoice as confirmed collateral and scheduling all collections exactly on due date is a strong optimistic assumption, even in “CONSERVATIVE” mode.

Do not implement a full collateral marketplace. Add explicit eligible/ineligible/unknown status plus evidenced cap restrictions to block unsupported borrowing. Receivables eligibility, concentration and reserves materially affect asset-based lending according to the [OCC Asset-Based Lending handbook](https://www.occ.gov/publications-and-resources/publications/comptrollers-handbook/files/asset-based-lending/pub-ch-asset-based-lending.pdf); this is a reference for missing decision inputs, not a claim about the fixture's legal jurisdiction.

Scenario events already expose one missed payment, but demo cash otherwise rises from recurring sales with sparse future expenses. EBITDA is not a substitute for a cash outflow schedule. A recommendation horizon needs declared completeness, or the product should say it screens the entered obligations only. Default/renewal calendars, guarantees/collateral enforcement, acceptance bills and lease residuals should be POST-HACKATHON unless they are actually offered in the demonstrated transaction.

## 9. Capex audit

The project NPV/payback computation can be valid for its declared stream while the financing recommendation is wrong. Current “best/cheapest” combines nominal interest, separate estimated DSCR, arbitrary tenors and incomplete cash schedules. Fees, existing drawn service and actual purchase timing change the decision. Lease-as-loan annuity arithmetic assumes equivalence of cash/ownership outcomes that is not established.

NOW: remove a financing winner when the project is not worth doing, fees/quote terms are missing, complete liquidity cannot be checked, or a structure violates shared authority. Keep a conditional project NPV calculator with explicit net-cash/hurdle/start/life assumptions. NEXT: dated evidenced quote alternatives on the shared books, present nominal charges and a common PV separately, and show no winner for economically incomparable alternatives. Do not claim lender covenant compliance from synthetic level service or loan-rate labels alone.

## 10. Language/compiler audit

| Interpretation class | Observed examples | Required disposition |
| --- | --- | --- |
| Correct executable | Specific baseline scripted operations | Only affirmative complete intent plus current authority may execute. |
| Correct read-only | Status/comparison/explanation scenarios | Never inherit execution solely from a funding verb. |
| Safe clarification/abstention | Unparsed offer riders/amounts in focused suites | Accept lower coverage as intended safety behaviour. |
| Wrong but harmless | Unsupported phrasing → clarification | Record separately from correct interpretation and abstention. |
| Wrong and material | Negations/questions execute; invalid amount defaults; today/tomorrow bind day 2; bounded scope rolls | A01/A02/A07 are release blockers; zero-wrong-executable target is falsified. |

Coverage proof for a buyer offer does not protect owner financial commands. Grounding verifies a quoted span, not its economic meaning or consent. Transformations must preserve/refine typed semantics: assertion→negation must remove execution; question must become read-only; RMB→USD must clarify; today→tomorrow must change settlement date or abstain; 3 invoices→all future invoices must change frozen scope; cash→acceptance bill must change eligibility or abstain. A confidence threshold is not proof of complete authority.

Historical held-out/live-DeepSeek reports were inspected after primary analysis; their recorded successes/failures are not fresh verification on this revision. Never present safe abstention, correct-but-owner-only interpretation and correct executable interpretation as one accuracy metric. Human review of incomplete extracted terms also requires showing what was not interpreted, not just a reassuring Tier-2 label.

## 11. UX/human factors

The UI must distinguish requested, awaiting approval, awaiting settlement, settled, refused and partially completed. Each approval should identify the exact amount, facility/buyer, contract dates, cost basis, binding rule, after-state, authority and rejection alternative. Show when cash actually becomes spendable. A button saying Go ahead must refer to that immutable action set.

Specific problematic displays: capex positive styling on negative NPV, unsupported “Finance with” recommendation, lender file EBITDA called cash flow, raw reconciliation due dates versus adjusted trajectory, DEAL/remaining-gap-funded replies when acceptance/funding results are queued/refused/skipped, and an annual rate beside an incomparable tariff. These are not cosmetic: they invite wrong financial interpretation. Narrow claims immediately instead of adding explanation tabs around inconsistent data.

Borrower preparation approval should have a coherent purpose: the web creates/downloads the file before approval, while the NL handler can approve a sentence without storing a downloadable artifact. Preparation for the authenticated owner can be read-only; transmission/application, if implemented, should authorise an exact destination and payload. Do not invent an external transmission feature just to make this approval meaningful.

## 12. Architecture simplification

The useful seam is a **contractual position with dated outstanding schedules**, plus a shared pure admissibility function consumed by planner and executor. Preserve original invoice terms for audit, crystallise accepted terms once, retain consumed finite scope, and distinguish actual cash from requested/forecast settlement. Persist loan lot dates/principal/accrual/payment obligations instead of reconstructing them separately in projection, executor log, capex and alerts.

Remove duplicated capex debt baselines, extension-service approximations, separate cure admissibility and bespoke role/command permission checks once the shared contracts cover them. A funded-plan executor should refuse unsupported action kinds instead of skipping them and reporting success. Keep the modular monolith; these failures do not justify microservices, a generic event-sourcing framework or a solver. Exact money/charges primitives should remain small. Delete/disable unsupported recommendation paths before extending interfaces.

The egress guard cannot substitute for sender authentication or command consent. More canaries and more adversarial prompt variants have lower immediate value than fixing the economic write boundary. The empty aftersign package and unused mock lender can remain disabled or be removed; extending them does not fix any proven defect.

## 13. Top ten fixes, in order

1. Close unintended authority: stop NL action execution without complete affirmative consent and fix explicit approval rejection (A01/A02).
2. Make unauthenticated buyer intake proposal-only (A03).
3. Remove destructive startup reset and configure real owner-key/mandate hydration (A04).
4. Enforce shared current financial admissibility inside every agent financial execution transaction, including outstanding-face financing (A05).
5. Crystallise accepted price/terms into issued receivable positions; preserve partial-settlement value and one due date across modules (A06).
6. Freeze finite invoice scope and consume it durably (A07).
7. Share outstanding loan/funding schedules; honour arrival, maturity, fees and closed days; gate early discount by actual contract conditions (A08/A09).
8. Bind confirmations/approvals to the shown economic envelope and stale-state policy (A10).
9. Date concession gains/exposure/frequency consistently; remove false cap headroom and name tariff/realised rate distinctly (A11).
10. Narrow capex/borrower financial claims; require complete proceeds/purchase/debt schedules before reinstating recommendations (A12/A13).

The first two are small compared with a ledger redesign and directly cause wrong autonomous action. They outrank richer UI, more lender options, multilingual reply polish and demo breadth. A constrained advisory demo is preferable to pretending all ten are closed by the event deadline.

## 14. Things not to build

**DO NOT BUILD before these blockers:** autonomous supplier/payee payments; more lender negotiation/disbursement connectors; automatic covenant cure on partial books; learning/optimisation that increases autonomous coverage; new capex winners for unsupported leases/quotes; broader payment instruments labelled equivalent to cash; more dashboards to explain divergent state; a new general solver/framework/microservice split; blanket bank-compliance certificates; claims of “safe by construction” based on test count.

**POST-HACKATHON only when actual decision inputs require it:** tax engine, FX, holidays/business-day calendars, collateral registration/default enforcement, sophisticated lease residual/ownership models, treasury rate curves. **IF TIME:** explainable stress scenarios for late buyer receipt/facility unavailable only after consistent books and authority. Do not rebuild correct posting arithmetic just to preserve an old demo number; change golden outputs where the contractual economics change.

## 15. Tests to add

Each test must assert economic state before/after as well as response:

1. All negative/interrogative/conditional/quoted/mixed-language variants of financial verbs produce zero executed operations; invalid explicit currency/precision cannot become default funding.
2. Reject/Do not approve/Should I approve/bare approval ID never approve; affirmative exact approval executes once; copied IDs do not bypass caller/session authority.
3. Public known-buyer-ID requests create zero ACTIVE commitments, cash/debt writes or authorisation reservations.
4. Real approved Option B → invoice issuance → full and partial bank receipts conserves agreed face, due and residual; alerts/reconcile/router/capex agree.
5. Three-invoice bound promise affects exactly the frozen three regardless of order/partial/full settlement; invoice four never inherits scope.
6. Projection current cash equals actual cash when no same-day events exist; no posting before as_of_day. Advancing actual scheduled events then projecting reproduces the remaining schedule.
7. Direct operation and planner admission agree under identical state for amount threshold−1/at/+1 fen; outstanding face, advance ratio, maturity, lead time, covenant and borrowing permission all included.
8. Missed early-payment date cannot grant discount; day-before/on/after deadline receipts and one-fen amount differences are explicit.
9. Stable bank event replay cannot double partial settlement, including changed request IDs and process restart; different legitimate events of identical amount remain distinct.
10. State/mandate/facility changes after displayed plan require fresh confirmation unless inside declared tolerances; changed payload under an idempotency key conflicts.
11. No dated gain outside valuation interval expands headroom; equivalent bounded/perpetual dated invoice sets value equally; invoice frequency changes monthly service correctly.
12. IF days 1/29/30/31/59/60/61/89/90/91, one-time vs period fee, 1-fen/¥1/full/partial face, zero/tiny/unfundable gap; compare realised net-proceeds rates with the explicitly selected cap basis.
13. Capex existing DebtPosition vs identical facility schedule yields identical debt/service; increasing fee/rate cannot lower comparable all-in cost; actual quote tenor cannot be replaced silently; purchase use of proceeds is always present.
14. Zero/negative EBITDA returns structured undefined/breach; no negative-ratio formatting magnitude error.
15. True PostgreSQL forced interleavings: concurrent draws against final room, receipt versus finance, accept versus revoke, two copies of external event, rollback/log failure, response loss and process restart. Do not use a single in-process RLock test as evidence of database concurrency.

Removing a usable source should not improve an exact optimum for the same complete feasible set; bounded/grid search may violate a claim of global optimality, so test search-quality separately from admission safety. Every counter offered as executable must itself pass current shared admission and complete issuance/settlement. A stricter mandate may reduce authority, never expand it. Increase discount→supplier proceeds cannot rise; receipt→outstanding cannot rise; settlement→finite scope cannot expand.

## 16. Questions that change the design

- Is this a simulation/advisory product or a system intended to create legally effective commercial commitments? What authenticates each buyer and the acceptance channel?
- Is minimum cash a closing-bank-balance policy, forecast reserve or intraday available-cash requirement? Which forecast receipts may satisfy it?
- Does a discount expire at the promised day, or is it an unconditional credit note once accepted? The current projector and executor answer differently.
- Which invoice issue sequence does “next N” bind to, including cancellations, reissues and partial settlements?
- Which quoted bank covenant defines numerator, observation period, scheduled principal, lease treatment and clean-down history? Is level bullet reserve coverage only an owner analytical metric?
- Is max APR a tariff cap, realised simple-rate cap or cash-flow IRR cap? Which fields are owner-overridable versus hard prohibitions?
- Do DebtPosition and Facility.drawn represent disjoint debt? How is existing debt's dated cash schedule included in all-in flows without double counting?
- Are recurring invoices firm contracted sales or forecasts? What evidence establishes eligibility, assignment restrictions and concentration room?
- Does project uplift mean EBITDA, operating cash flow or net incremental cash after working capital/taxes/maintenance?
- What exactly may change after Go ahead without renewed consent—cost, amount, tenor, lender, collateral or cash date? “Cheaper” alone is insufficient.
- Which real event confirms funding, repayments and bank receipts? What happens on failure, response loss and fresh request ID retries?

Answers should define executable contracts and unknown states, not merely documentation labels. No clarification is needed to close reproduced non-consent, spoofing, reset and amount-conservation failures.

## 17. Go / no-go conditions

**Autonomy NO-GO** until A01–A11 are either fixed on every executable path or the affected actions are disabled, with focused properties proving zero unintended execution and planner/executor agreement. Showing a warning, Tier-2 badge or hidden operations array does not satisfy the condition.

**Live-model NO-GO** until the deterministic boundary is repaired and a fresh independent set tests correct executable interpretation separately from abstention/read-only behaviour across live backend, fallback, malformed output and timeout. Historical tuned held-outs do not qualify.

**PostgreSQL NO-GO** until restart preserves the entire state and command history, real owner configuration is pinned, destructive demo reset cannot touch the deployment database, and actual multi-process race/recovery tests prove serialization and external-event deduplication. PostgreSQL was not accessed in this audit; inference must not be presented as a reproduced production incident.

**CFO/borrower recommendation NO-GO** while A06/A08/A11/A12/A13 or unidentified contractual covenant bases remain. A read-only illustration can be offered if it explicitly confines the evaluated assumptions and avoids “best”, “compliant” and guaranteed cash language.

**Controlled hackathon demonstration conditional GO:** memory/cache-only, visibly simulated credentials/counterparties/clock/bank feed; the exact scripted transaction settles and reconciles; known unsupported paths disabled; audit limitations and any manual repayment disclosed. Passing the demo does not reverse the deployment verdict.

## 18. Next three deep-dive workstreams

1. **Economic contract and settlement model.** Owner: principal financial architect. Freeze invoice applicability, crystallise face/due, conserve partial balances, persist funding/debt lot dates and payment obligations, prove rolling-time equality. Acceptance: real Counter B and bounded-three-invoice cases settle correctly; as-of-day61 invents no past cash; dates/costs agree across every module. Output: one explicit transition contract and focused differential lifecycle tests, not a wholesale rewrite.
2. **Authority at every write boundary.** Owner: execution/security lead. Affirmative complete consent, public proposal-only intake, shared admissibility, immutable confirmation envelope, signed owner lifecycle and stable external-event identity. Acceptance: all new command/rejection/spoofing probes perform zero unauthorised writes; stale plan gets re-presented; strict mandates never expand authority; restart and concurrent writes cannot erase/replay economics.
3. **Defensible financial claims and constrained demo.** Owner: financial/product lead. Contractual covenant windows, dated forward valuation, tariff versus realised rates, capex narrowing and borrower use of proceeds; prune unsupported actions/claims. Acceptance: CFO can reproduce each displayed number from disclosed inputs and actual schedule; incomplete evidence produces no strong recommendation; the smallest supported end-to-end demo includes a missed receipt and reconciled recovery without silently changing terms.

Implementation of these workstreams was not performed during the audit. Repository branch reconciliation preserves the findings; it does not close them.

## Integration record: branch reconciliation on 3 October

Local `dev` had one audit-only commit (`a5f7b70`) and was 30 commits behind `origin/dev` (`b0e0ab6`). Merge `274a74d` preserves both histories without conflicts or force updates. Relative to that remote head, the merge introduced no application code differences; its local additions were audit documents/probes. The completed report/evidence and this record were added afterwards.

Checks on the merged application:

- Backend full suite: **4,050 passed, 19 skipped, one failed** in 199.78 seconds. Failure was EX01 latency **261 ms versus 250 ms**. The isolated rerun passed in 1.24 seconds overall. Do not report the original full run as entirely passing.
- Scenarios: **46/46**, 79 turns; outputs written under `/tmp` without replacing tracked evidence.
- Existing attack catalogue: **182 attempts, zero catalogue harm**; independent successful attacks above still stand.
- TypeScript check and all **five web unit checks** passed.
- Next.js production build passed using Webpack. The default Turbopack browser launch could not bind its internal port in this execution environment; no product configuration was changed to hide that failure.
- Browser checks with temporary Webpack/memory-API configuration: **54 passed, one skipped, two failed**. Isolated phone rerun: one passed, two failed. `/security` page horizontal overflow was 6 px; chat panel right edge was approximately 431 px on a 412 px viewport. Upstream application code is identical, so these are reproducible upstream checks, not changes introduced by combining the audit commit. The temporary test configuration/build directory was removed and Next.js's automatic tsconfig rewrite was restored to its original bytes.

Phone layout finding: **LOW · UX · REPRODUCED · BUILD IF TIME · effort S · regression risk low · confidence high**. Reproduce `e2e/responsive.spec.ts` phone project. Business consequence: clipped mobile content/composer; hackathon consequence: mobile responsiveness checks fail. Fix security-page width/wrapping and chat-panel viewport containment, including animation completion in the test if applicable; verify actual settled layout before attributing the chat measurement solely to CSS. It ranks below all wrong financial executions.
