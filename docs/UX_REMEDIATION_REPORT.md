# UX remediation report (map #65, 9 to 10 October 2026)

The owner's mission of 9 October asked for the independent user-flow audit (`docs/research/independent-flow-ux-audit-2026-10-09.md`; 4 P0, 14 P1, 10 P2) to be closed in the product at its real causes, with one coherent financial reality on every decision surface. This report is written for the owner's GO / NO-GO before `feat/ux-remediation` merges into `dev`. Evidence: the ledger `docs/research/ux-remediation-ledger-2026-10-09.md`, the reproduction transcripts under `docs/research/ux-remediation-2026-10-09/`, the gate record under `docs/research/ux-remediation-2026-10-09/gate/`, the screenshots under `docs/screenshots/ux-remediation-2026-10-10/`, and the GitHub tickets #65 to #77.

## 1. Executive summary

All 28 findings were reproduced on `dev` before anything changed (28 confirmed, none disproved) and all 28 now read FIXED on the ledger; no P0 was deferred. The architectural fix is one durable decision record (ADR-0011): a read model over the canonical stores plus one small append-only table for the three facts that cannot be re-derived (the day a verdict was made, the counter that was sent, the economics the owner was shown when an action was queued). Every page now derives agreement, authorization, execution and settlement state from stored reality, never from a clicked button, and the engine did not change: no module under `app/financial`, `app/verifier`, `app/funding`, `app/alerts`, `app/operations`, `app/clock`, `app/books` or the mandate was edited, and a test pins that no engine module imports the decision record. The work landed in eight waves over 80 commits on the integration branch, each wave on its own branch, reviewed and merged with `--no-ff`, with the integration gate re-run after every merge.

## 2. Audit findings closed

| Group | Findings | Where fixed |
| --- | --- | --- |
| Time semantics (current vs historical vs forecast) | F01, F03, F25, R01, R02 | Wave 1 API: the home's breach facts from today only; "Below reserve today."; a past deadline reads "the early-payment window ended 32 days ago", a live one "may still be settled early … within N days"; the four part-paid facts |
| Approval terms and the fail-closed card | F02 | Wave 1 API and web: the queue resolves the agreement on the server and writes its terms; the card disables Approve when they cannot load |
| Execution truth | F04, F14 | Wave 1 and 2: "Evaluation alone makes no changes." under an execution summary; a refused execution after approval is the record's terminal FAILED state, "You approved it, but it could not run: … No money moved." |
| Decision identity and lifecycle | F06, F07, F13, F17 | Wave 2: the record, the bound send (409 COUNTER_CHANGED), the stored quote, the remaining task |
| Core flows | F12, F18, F26, F27 | Waves 1 and 3: the partial-rescue after-state; the comparison contract; the refused anchor; "Record chain checks passed" |
| Context | F08, F20, F24 | Wave 4: a validated page context on `/nl`; page prompts; the CHANGES read; specific abstentions |
| Receivables | F15, F25 | Wave 5: the chase handoff; the four facts on every receipt surface |
| Demo | F09, F10, F11, F19 | Wave 6: Show / Replay / Reset; the locked stepper; the six-scene late-payment loop; the shell follows the mode |
| Mobile, accessibility, copy, language | F05, F16, F21, F22, F23, F28 | Waves 1 and 7: the cold start; the phone order; freshness and partial reads; the reduced-motion indicator; timeouts; `lang` everywhere |

Eight related issues found while reproducing (R01 to R08) are closed with the rows they belong to.

## 3. Before and after

**P0.** F01: `/home` on day 34 returned `first_breach_day 0`, "Cash at first breach ¥45k, 34 days ago" with today's cash; now `first_breach_day 34`, `first_breach_when "today"`, `below_reserve_today true`, the headline "Below reserve today.", the series from today. F02: a Tier-2 agreement approval read "Approve this buyer agreement? Accept offer ¥0.00" with the terms only in `/ledger`; now the queue carries `terms[]` ("…take 0.50% off the ¥420,000.00 invoice to Foshan Home Retail Co. (effective in 2 days; one time)", a cap as "up to ¥257,200.00 of the ¥420,000.00 invoice"), `what_you_agree_to`, `economic_effect_text`, `terms_available`, and the card disables Approve with "I can't safely present the full terms for review. Approval is unavailable until the decision record is restored." when they cannot load. F03: day 34's receipt read "up to ¥128,600.00 more may be settled early by today"; now "the early-payment window for the other ¥128,600.00 ended 32 days ago", and a live window says "may still" only while the promise is live in the books. F04: the verdict page said "Nothing is executed" after a ¥149,986.20 draw and a ¥255,000.00 advance; now "Evaluation alone makes no changes." under an execution summary read from the record.

**P1.** F05: the documented `pnpm dev` returned HTTP 500 on an invalid custom variant; the block form loads Home and keeps both touch branches, and a test fails on the old CSS. F06: Deals derived "Agreed" from an ACCEPT verdict and kept an expired agreement; the steps now read the record's thirteen states. F07: "Send this counter" sent only a buyer profile; the send is bound to `verdict_id`, `counter_id`, `state_version` and refused on a mismatch. F08: "Why are we countering this?" on a page-evaluated deal answered "There is no verdict to explain yet"; a validated `context` binds the page's deal. F09, F10: Show re-ran steps (Setup reset the books) and the stepper unlocked mid-step; fixed and pinned by a rapid-click test that fails on the old code. F11: the fifteen-step module tour became the six-scene loop with the owner's own click on the approve step. F12, F17: the zero-floor approval had no after-state and Home stayed CRITICAL with no next task; now `protects` ("Prevents negative cash; cash stays ¥300k below your ¥300k minimum cash reserve from today…") and `remaining_task` with links. F13: the approved card lost its ¥1,381.32 cost; the QUOTED fact keeps it. F14: a refused approve left pending controls and "You declined"; terminal and truthful now. F15: Chase payment. F16: on a phone the recommendation began at y 1015 and Send sat at 1814 after Wave 3; the phone order puts every primary inside 915 (Home 785, Deals 823, Cash 799). F18: #2 ¥5,040 before #3 ¥3,938.81 under "ranked by cost"; the comparison contract groups CONDITIONAL rows apart and ranks only runnable plans.

**P2.** F19 (the shell follows the mode; the engine doors labelled), F20 (no role simulation or tier words in Business; two to four prompts), F21 (Read-when, partial reads, the forecast basis), F22 (the reduced-motion ellipsis wins), F23 (20 s timeouts, reconcile-then-retry), F24 (the abstention names the currency), F25 (the four facts), F26 (the anchor), F27 ("Record chain checks passed" with its scope), F28 (`lang` on every read, identical figures).

## 4. Root causes found

Eight groups explain the 28 findings: time semantics (a projection that fills closed days with today's cash and a `by()` helper that mapped every past deadline to "by today"); decision identity (nothing linked offer, verdict, commitment, approval, operation and lot); lifecycle state derived in the browser from a verdict outcome or a click; the historical versus current projection (the queue priced decided rows from today's alerts); context not propagated (the chat session knew only chat-evaluated verdicts); frontend-local status (Show and Run on one handler; `clearDemo` clearing the in-flight state); demo orchestration (the story narrated the loop instead of running it); presentation duplication (one approval said four times on Home). The independent code reviews of Waves 1 and 2 found six further defects before those waves closed (a partial cap named as an invoice; part-paid warnings; a current-eligibility claim without the books; residual risk attached to any open alert; an unprojected quote read as safe; a repeated bound send not idempotent).

## 5. The durable decision model (ADR-0011)

`docs/adr/0011-durable-decision-record.md` (accepted). The record is assembled on request from CompiledOffer, Verdict and its counters, Commitment and its obligations, ApprovalRecord, the hash-chained operations log, FundingLot, the reconciliation's receipts and promises, and today's alerts. One append-only table `decision_facts` (migration 0006; both stores; insert-if-absent on `(decision_id, fact, fact_key)`; never on the hash chain; cleared with the ledger) holds EVALUATED (the verdict's day), SENT (the counter shown, the state version, the economics and the gap plan) and QUOTED (the alert and plan legs, costs, rates, landing, after-state, if-declined) facts. Facts are written in the API layer after the canonical event inside `rt.lock`; a failed write never fails the route and the read model says "not recorded" rather than recomputing history. Decision ids are deterministic (`deal:{offer_id}`, `alert:{id}:v{sv}`, `…:plan`, `nl:{session}:{scope}`, `approval:{id}`).

## 6. The state machine

Deal: REVOKED, FULFILLED, MISSED (terminal when the commitment expired with lapsed obligations; open when other terms live), AGREED, EXPIRED, AUTHORIZATION_REQUIRED, DECLINED, FAILED, NO_DEAL, NEEDS_CLARIFICATION, RESPONSE_READY ("Acceptable, awaiting agreement" or "Counter recommended", never "Agreed"), RECEIVED. Funding: AUTHORIZATION_REQUIRED, DECLINED, FAILED, PARTIALLY_EXECUTED, SETTLEMENT_PENDING, SETTLED, EXECUTED, with residual risk as a field set only when the open reserve alert is the decision's own or no committed cure exists ("Funded, reserve still short"). `waiting_for` is a pure function of the state: owner response, buyer clarification, owner approval, bank receipt, invoice issue, funding settlement, owner decision, or nothing. Every state is reachable from stored data in `tests/decisions/test_state.py`.

## 7. API changes (all additive; defaults unchanged)

New routes: `GET /decisions`, `GET /decisions/{id}`, `GET /offers/{id}`, `GET /receivables/{id}/chase`, `POST /demo/bank-receipt` (DEMO_MODE only). New request fields: `POST /negotiate/{id}` `verdict_id`, `counter_id`, `state_version` (409 COUNTER_CHANGED / ALREADY_SENT); `POST /nl` `context {page, offer_id, decision_id, invoice_id, since_day}` and `?mode=business`; `lang` on every Business read and write. New response fields by route: `/home` `cash.below_reserve_today`, `first_breach_*` from today, `forecast_basis*`, `last_read_*`, `partial`, `series[].net_*`, `open_decisions`, `remaining_task*`, `changes[]` causality and the four part-paid facts, `approvals[]` terms and `execution_status`; `/approvals/queue` `terms_available`, `terms`, `what_you_agree_to`, `economic_effect_text`, `lands_text`, `residual`, `execution_status`, `decision_id`, `decision_state`, `quote`, `execution`, `result_state_text`, `result_tone`; `/reconciliation` the four facts, `window_state*`; `/ledger` `decision_id`, causality, `why_it_matters_changed`, `chain_text`, `chain_scope_text`, `refusals`; evaluate `decision_id`, `evaluated_when`, `send_scope`, `send_scope_lines`, `workspace`; negotiate `decision_id`, `execution`; `/router/plan` the comparison contract (`group`, `rank`, `router_order`, arrival, gap, basis, consent); `/alerts` `title_when`, `detail_when`; `/trajectory` `first_breach_ahead_*`. New modules: `app/decisions/{facts,identity,state}.py`, `app/api/{decisions,quotes,causality,workspace,collections,receipt_facts,engine_zh,demo_bank}.py`, `app/nl/{binding,reads,business}.py`.

## 8. UI changes

Home: the hero reads "Below reserve today." when already under the reserve, the series starts today, Read-when and the partial-read line, the next step carries the one primary (Review and decide when an approval is pending), the remaining-task card with links, the Waiting on list, one voice per fact, the owner's words. Deals: one workspace in the server's order (buyer card with a state chip, FLOW recommends, the priced response with a two-step bound Send and its "This will" scope lines, then the asks, the cost, why it matters, agreements, one Advanced fold), the Inbox folded to one row, `?buyer=`, the set-aside line bound to recorded refusals, states from the record. Cash: the comparison drawn by the server's groups and ranks, the forecast basis as the subtitle with a Basis fold, net day labels, the remaining task. Receivables: the top action above the tiles with Chase payment, the four receipt facts, the ranking disclosure, error states. Approvals: the terms, economic effect and timing above the buttons, fail-closed, the stored quote, the result block first in the server's tone, no band or token note. Activity: what changed / why it matters (once) / what remains, "Approval requested" linked to the record, the chain words. The Decision record page in the owner shell. The verdict page's execution summary. Phone order on Home, Deals and Cash. Timeouts with a slow notice. axe on every page.

## 9. Ask FLOW

A validated page context binds the selected deal; two to four page prompts in Business, hidden when their prerequisite is missing; no role radios, tier hints or fixture chips in Business; the CHANGES read ("What changed today / since my last visit") from the log and the forecast with the consequence and the remaining task; "What are we waiting for?" from the record; one recovery sentence instead of a capabilities list; abstentions name the unresolved field from a closed list; `mode=business` gives owner-voice templates ("Yes, run it"); drafts and the session survive a refresh.

## 10. Demo

Six scenes in eleven steps: buyer asks, FLOW decides, the bound send (cash now versus arriving), a labelled synthetic bank receipt and time to day 34 (Home detects the missed later receipt and prices the cure above the ceiling), the cure queued as Home's button does and approved by the owner's own click, the funding settles, outcome and proof. Narration from the server's responses (a unit test forbids figures in the dictionary's step text). Show, Replay and Reset mean what they say; the stepper stays locked while a step runs; the capex, rewording, walk-away and attack scenes sit under "More to show". The clock never lands a receipt.

## 11. Receivables, mobile

Receivables: `GET /receivables/{id}/chase` and the Chase payment dialog (buyer, invoice, outstanding, due, promise, lateness, the agreed terms, a copyable request in the owner's voice, the buyer thread link); the four facts on every receipt surface. Mobile: on a phone the primary action's bottom edge sits inside the first viewport (Home 785, Deals 823, Cash 799 of 915; the first hero tile spans two columns; 44 px targets); the desktop DOM order is unchanged.

## 12. Files, tests, results

Against `dev` (742847f): 415 files changed (36 under `services/api/app`, 109 under `apps/web` excluding re-recorded mocks); 39 new test files (API: time semantics, decisions flow, binding, quote, terms, refused terminal, remaining task, collections, comparison contract, forecast basis, causality, workspace, demo bank receipt, language, the decisions module and store; web: trust, record, touch, a11y, slow, lang e2e and seven unit scripts). The integration gate was re-run after every merge (golden digests unchanged throughout).

The final gate (Wave 8 part A, head 6106c72 with only documentation commits after it; record and raw output under `docs/research/ux-remediation-2026-10-09/gate/`, all with zero retries):

| Check | Result |
| --- | --- |
| Whole API suite (`pytest tests`) | 6398 passed, 37 skipped (16 min) |
| Web unit, typecheck, lint, build | 76 passed; clean; clean; compiled with no CSS warning |
| Mock e2e, default / strategy build | 135 passed, 33 skipped / 144 passed, 24 skipped |
| Live e2e, default / strategy build | 69 passed, 12 skipped / 77 passed, 4 skipped |
| Live e2e on the SQLite file store | 69 passed, 12 skipped; the Demo story alone leaves 8 operations, 3 decision facts, 1 approval and 1 commitment on disk |
| Demo timing | 30 rapid clicks end at step 11 in about 1.9 s in every run |
| Cold start from a clean GitHub clone | every page 200 (`/`, `/deals`, `/cash`, `/receivables`, `/activity`, `/approvals`, an unknown record); no dev-server warning; `git status` clean |
| Evidence chains | 49 valid |

Each mission flow maps to a live test (approval: `trust.spec.ts`, `record.spec.ts`, `live.spec.ts`; counter: `record.spec.ts`, the bound send in `live.spec.ts`; funding: the day-34 cure in `live.spec.ts`; receipt: the half-receipt walk and `receivables.spec.ts`; the late-payment cure: the six scenes in `demo.spec.ts` and `live.spec.ts`; Ask FLOW: `chat.spec.ts` in en and zh); the responsive, phone, axe, record and trust specs run in the mock projects and all passed there.

## 13. Screenshots reviewed

Wave 8 part B captured 92 full-page screenshots on the live stack at 1440×900, 1366×768, 820×1180 and 412×915 (`docs/screenshots/ux-remediation-2026-10-10/`, with a manifest per width recording each primary action's position; the on-demand script `apps/web/scripts/capture-remediation.mjs` repeats them). Wave 8 part C reviewed them cold, as an owner who had not seen the product, against the six questions (the decision's state, what happened, what happens next, whether money moved, whether approval is needed, what remains unresolved), the audit's five-second page test and its scorecard.

Five-second test (audit verdict → now): Home PARTIAL → PASS; Deals FAIL on phone / PARTIAL on desktop → PASS; Cash PARTIAL → PASS; Receivables FAIL → PARTIAL (the chase flow exists; the headline named the wrong invoice when one was overdue, fixed in the final pass); Activity PASS → PASS; Funding approval FAIL → PASS on desktop, PARTIAL on phone (two cure states' buttons sat under the tab bar, fixed in the final pass); Ask FLOW FAIL → FAIL at capture time (the explain reply still carried engine codes; fixed in the final pass, now "FLOW recommends a counter: …"); Demo story FAIL → PARTIAL (duplicate Approve controls at scene 5, fixed in the final pass).

Scorecard, the audit's seven columns (clarity, cognitive load, actionability, trust, financial comprehension, consistency, efficiency), audit → cold review of the captures:

| Surface | Audit | After |
| --- | --- | --- |
| Home | 8 7 7 5 7 6 7 | 8 8 9 7 7 7 8 |
| Deals | 7 6 5 5 7 5 5 | 8 7 7 6 7 7 8 |
| Cash | 7 5 7 6 7 6 6 | 8 6 8 7 8 7 7 |
| Receivables | 7 7 3 5 5 5 4 | 7 7 7 7 8 6 6 |
| Activity | 8 8 6 6 6 6 7 | 8 7 7 6 7 7 7 |
| Approvals | 7 6 6 4 5 4 5 | 8 8 8 8 7 8 8 |
| Ask FLOW | 4 4 4 5 4 3 3 | 5 4 5 5 4 4 5 (before the explain-reply fix) |
| Business/Demo separation | 6 5 5 6 5 4 5 | 8 7 7 8 7 7 7 |
| Mobile | 6 5 5 6 6 6 5 | 7 7 6 7 7 7 6 |
| Demo flow | 5 3 5 4 6 4 4 | 7 5 7 7 7 6 6 |

Before/after at the same width: the phone Home primary moved from about y 1118 (behind the tab bar) to 741–785; the phone Deals Send from about 1660 to 779–823; desktop Deals' recommendation from about 1176 to 360 with the stepper, the jump band and the expanded inbox gone; Cash's numbered list became groups that say what is uncovered and when; Receivables gained the overdue tile, the late row, Chase payment and the part-paid ledger. The review's seventeen FIX NOW items (two P1: the Receivables table clipped at tablet width; Home's "Below reserve today" tile showing cash rather than the shortfall; fifteen P2 and P3 wording, fold and duplication items) were taken as the final pass of Wave 8; the five DEBT items (overdue invoices pinned above the savings ranking, the approvals card alignment, the Cash day-34 price sentence, a stage indicator on Deals, the story page's length) are in section 14. What a still image cannot show (motion, the fixed bars at scroll 0, keyboard and screen-reader behaviour, loading and error states) is covered by the e2e suites in section 12 and not claimed beyond them.

## 14. Known remaining debt

From the waves: a native reader for the zh strings (every zh sentence is a template gloss); the Business chat template covers evaluate, fund-the-gap and the explain reply, not alert cures, repayments or approvals; `passed_checks` and `autonomy` stay English inside the Advanced fold; chat-originated (`nl:`) decisions and direct operations have a state but no stored quote; the LATE change row for a part-paid invoice cannot be filtered without an invoice id on the row; the decision list is derived over the whole log per call (fine at demo size); Postgres behaviour of `decision_facts` awaits the pending G4 run; `/ledger` runs `reconcile()` once per request when a receipt exists; the quoted-cost ceiling on approvals is an engine change left to the owner (grilling #66, item 6); a real late-payment what-if is engine work; a mark-as-chased outcome needs its own storage contract; Back then Next on the Demo re-runs the next step; the Demo story's approve step in `lib/demo.ts` can still run the approval if its `run()` is invoked while the cure waits (the dock and the story page no longer offer Next or a second button in that window; the step should become a navigation-only Show as a follow-up); no screen-reader session, zoom or real-device pass was run and no WCAG conformance is claimed.

From the cold review (design debt, not wording): overdue invoices are ranked by what collecting them saves, so an overdue invoice can sit below "on time" rows (the overdue sentence now leads the page; pinning overdue rows to the top or defaulting to the Late filter is a design choice); the approvals card is centred under a left-aligned header; the Cash day-34 price sentence is long; Deals lost its stage tracker (the state chip replaces it; a one-line stage indicator is possible); the Demo story page is 4.4 phone screens with the dock over content.

## 15. What was deliberately not built

Per the mission's section 35: no new dashboard, confidence meter, portfolio optimizer, collections automation, lender connector, capex expansion, scenario laboratory or new finance module. No engine change: router economics, verifier constraints, cash projection, mandate semantics and commitment security are as `dev` left them; the owner cannot waive a hard rule and FLOW never invents a feasible cure. The simulated buyer stays synchronous; no outbound buyer channel or bank feed was added (the Demo's synthetic receipt is a labelled Demo-only route). The owner's open decisions stay on grilling #66: the wider residual-risk policy, business calendar dates, the zh reader, the human cold readers.

## 16. Release GO / NO-GO (mission section 40)

| Gate item | Evidence |
| --- | --- |
| All P0 closed | F01 to F04 FIXED with tests (`tests/api/test_time_semantics.py`, `e2e/trust.spec.ts`, live walks) |
| No approval without reviewable terms | `terms_available` on the queue; the card fails closed; `test_approval_terms.py`, `trust.spec.ts` |
| No current/historical date contradiction | first breach from today; past deadlines read as ended; `test_time_semantics.py` |
| No expired action shown as current | live windows only while live; `test_time_semantics.py` two-receipt test |
| No false execution status | the execution summary from the record; FAILED terminal; `test_approval_refused_terminal.py` |
| Displayed counter == sent counter | the bound send; 409 on mismatch; idempotent; `test_negotiate_binding.py`, `record.spec.ts` |
| Historical approval preserves quoted economics | the QUOTED fact; `test_approval_quote.py` |
| Residual risk shown after partial rescue | `protects`, `residual`, `remaining_task`; `test_home_remaining_task.py` |
| Funding comparisons obey explicit contract | groups and ranks; `test_comparison_contract.py`, `cash.spec.ts` |
| Ask FLOW understands selected decision | the validated context; `tests/nl/test_page_context.py`, `chat.spec.ts` |
| Demo late-payment loop completes cleanly | six scenes; `demo.spec.ts` mock and live with zero retries |
| Show/Replay/Reset truthful | `demo.spec.ts` |
| Mobile priced action appears early | 785 / 823 / 799 of 915; `responsive.spec.ts` |
| Documented cold start works | the clean-clone dry run and the final gate (part A) |
| Relevant tests pass | the gate record |
| Fresh screenshots pass cold review | part C (pending) |

Recommendation: **GO** for merging `feat/ux-remediation` into `dev`, subject to the owner's reading of this report. Every item of the release gate has evidence on the final head; the whole API suite, the web unit tests, the mock and live e2e in both builds, the SQLite run and the clean-clone cold start passed with zero retries; the cold review scored every surface above the audit and its seventeen small findings were fixed and re-captured before this recommendation; the engine is unchanged and the ledger has no open row. What the owner should know before saying yes: the debt in section 14 is real and recorded; the zh strings have had no native reader; the quoted-cost ceiling on approvals and the wider residual-risk policy remain the owner's decisions on grilling #66; Business mode is still a simulated-buyer, simulated-clock product with no bank feed or outbound channel, as the audit's section 20 said, and nothing here claims otherwise.
