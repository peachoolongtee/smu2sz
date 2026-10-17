# FLOW feature inventory, gaps and the video plan

Built from the code on `dev` at `3bd440a0` (17 Oct 2026), not from memory. Each claim was read in the code; the
own-books and buyer-channel claims were also run through the API in process (TestClient, `DEMO_MODE=1`,
`DATABASE_URL=memory`, `LLM_MODE=cache`, `TERMSLEDGER_NO_DOTENV=1`, the `pnpm demo` flags). Paths are relative to the
repository root; web paths are under `apps/web`, API paths under `services/api`.

**Status words.** *works*; *demo books only* (works on the golden demo books from `pnpm demo`, not on books opened with
the setup wizard); *flag off* (behind a flag that `pnpm demo` leaves off); *partial*; *known issue* (with the issue or
the code that shows it). **Tech doc** says whether `docs/deliverables/technical_document.md` mentions the feature.

**Books.** *Golden books*: `pnpm demo` (scenario `golden_sme`). *Own books*: `pnpm demo:blank`, then the setup wizard.

## 0. Flags: what `pnpm demo` turns on

`scripts/demo.mjs` (and `scripts/dev-api.sh`) start the API with `DEMO_MODE=1`, in-memory books, cached readings, and
the web app with `NEXT_PUBLIC_API_MODE=live`, `NEXT_PUBLIC_DEMO=1`.

| Flag (where read) | Default | Under `pnpm demo` | What it gates |
| --- | --- | --- | --- |
| `FEATURE_TERMS_GUARD`, `FEATURE_DEBT_DESK`, `FEATURE_BUYER_NEGOTIATION`, `FEATURE_ALERTS`, `FEATURE_EXPECTED_PLANS`, `FEATURE_CONTRACTS`, `FEATURE_SECURITY_SCENES`, `FEATURE_CAPEX`, `FEATURE_BORROWER_FILE` (`app/config.py`) | on | on | evaluate/negotiate, router, alerts and reconciliation, documents and deals, the security scene's fixtures, capex quick check, borrower file |
| `FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH` | off | **on (API)** | the strategy MVP routes; the web hides them anyway (next row) |
| `FEATURE_EXPOSURE` | off | **on** | buyer exposure, Business consequences, Cash `?stress=`, the customer inputs routes |
| `FEATURE_CAPEX_CONTRACTS` | off | **on** | the buy side: Capex hub, purchases, financial health, loan eligibility, long-term plans |
| `FEATURE_CONTRACT_TERMS` | off | **on** | "Set up in my books" from a confirmed customer contract (ADR-0014) |
| `FEATURE_CUSTOMER_ECONOMICS` | off | **off** | the six economics fields on `/customers/[id]/inputs` |
| `FEATURE_PILOT_JOURNAL` | off | **off** | `GET/POST /pilot/journal` |
| `NEXT_PUBLIC_STRATEGY_MVP` (web, `lib/config.ts`) | off | **off: `scripts/demo.mjs` does not set it** | hides, even though their API flags are on: the cash price sentence on Cash (`cash-price-sentence`), "Before they ask" (envelope) on the Deals Cash impact tab (`components/deals/before-they-ask.tsx`, `decision-pane.tsx:817`), the envelope packages panel (`components/deals/flow/investigate.tsx`), every `useStrategyAsync` read (`lib/use-async.ts:61`; the receivable worth cells of `components/business/strategy.tsx`), and the pilot journal on Activity (`app/activity/page.tsx:98`) |
| `DEMO_MODE` (`app/config.py`) | **off** (SEC-07) | on | demo credentials, seeded books, `POST /demo/reset`, `/demo/bank-receipt`, the setup wizard's open step, `/docs` |

Collections worth is visible in no live build even with `NEXT_PUBLIC_STRATEGY_MVP=1`: only `app/receivables/legacy.tsx`
reads it, and that page loads only when `GET /receivables` is missing (`app/receivables/page.tsx:65`).

## 0b. Own books against golden books: what the story needs (verified in process)

- **Buyer channel keys.** The setup wizard names customers `BUYER-1`, `BUYER-2`, … in the order entered
  (`app/setup/__init__.py:514`). The demo channel keys exist only for `BUYER-1` and `BUYER-2` (`app/api/auth.py:28`), so
  the **first two customers** of own books can send buyer messages; a third cannot.
- **Simulated buyer.** Profiles are keyed by id (`fixtures/counterparties/buyers.yaml`: `BUYER-1`, `BUYER-1-HARDLINE`,
  `BUYER-2`; `app/api/decide.py:simulated_profile`). On own books the first customer negotiates against the **golden
  Foshan profile** (its invoice ¥420,000 due day 32). **Defect:** in a NO DEAL run on own books the simulated buyer's
  counter text named "invoice RCV-A (¥420,000.00)", an invoice that does not exist there (own books call it `RCV-1-1`).
  A customer without a profile gets 409 `NO_SIMULATED_BUYER` ("Copy the message to the buyer instead").
- **Readings.** Recorded (cache) readings exist for the golden texts only; on own books the same message is read by the
  rules grammar. EX01 reads fine on books with one open Foshan invoice; with three Foshan invoices it asks the buyer
  which invoice (NO_VERDICT).
- **The verdict depends on the books' shape.** Same EX01 text through `POST /nl` with `demo-buyer-1-key`:
  - Golden books: REJECT with Option A (¥260,000 at 0.85%) and Option B (55 days + 0.30%); the cooperative buyer accepts A.
  - Own books shaped like golden (cash ¥400k, line ¥150k, invoice financing ¥350k, Foshan ¥420k due day 32, payroll
    ¥340k **once**, equipment loan ¥45k monthly): REJECT with Option A (¥180,000 at 0.85%) and Option B (60 days +
    0.45%); the cooperative buyer accepts A; ¥146,530 funded; `POST /demo/bank-receipt` posts the early payment and
    reconciliation reports it MATCHED; after the clock reaches day 34 the past-due alert, the reserve alert, the alerts
    turn ("What needs my attention?") and Ask FLOW all answer.
  - The same books with payroll **monthly**: REJECT with **no counters**, because no standing funding plan is admissible
    ("No price-adjustment counter: … no committed plan keeps cash at the reserve"); the buyer reads "We are not able to
    accept these terms."
  - With larger limits (line ¥300k, invoice financing ¥1m): only a terms counter; the simulated buyer refuses: NO DEAL.
- **The cure depends on timing.** On golden books day 34 offers the ¥200,000 invoice-financing cure (¥1,782.19, 32.5% a
  year, above the 15% ceiling, so "go ahead" queues it for approval). On the golden-shaped own books the breach starts on
  day 34 itself and financing lands three days later, so the alert says "No committed facility can cure it".
- **Receipts.** `POST /demo/bank-receipt` books only an **agreed early payment** that is still awaited (409
  `NO_PROMISED_RECEIPT` otherwise).
- **Demo chat labels.** The Demo shell's buyer picker labels `BUYER-1` "Foshan Home Retail" and `BUYER-2` "Dongguan
  Office Supplies" from the dictionary (`lib/dictionary.ts:959`), whatever the owner named them in setup.
- **Capex on own books** is partial: the quick check's financed structures name `FAC-ETL`/`FAC-LEASE`, which only the
  seeded scenarios have, so only "cash + credit line" can pass and Apply and the borrower file stay disabled (section 10).
- **The Demo story** runs on golden books only; on own books the page says so and offers Restore (section 11).

**Conclusion for the video.** Record the negotiation, funding, late-payment and cure story on the golden books. Show the
setup wizard as a short clip on blank books. Own books can carry the story only with figures prepared and rehearsed in
advance (the shape above).

<!-- SECTIONS 1-7 FOLLOW -->

## 8. Ask FLOW chat

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chat surfaces | Ask in words on any page | `app/chat/page.tsx`, `components/chat/chat-view.tsx`, `chat-panel.tsx` (the "Ask FLOW" slide-over), `components/ask-header.tsx` (header input, typewriter examples, scope chip); `POST /nl` (`app/api/nl.py`) | none | Header "Ask FLOW anything…", Enter | `e2e/chat.spec.ts`, `ask-header.spec.ts`, `ask-header-live.spec.ts` | works | partly (Appendix B "Ask FLOW chat"); the header input, slide-over and scope chip: **no** |
| 23 intents | One closed list of things chat can do | `app/nl/models.py` `Intent`; `rules.py` first, `classifier.py` only when no rule matches (10 intents, never approve/reject/buyer) | none | see the intent table below | `tests/nl/test_rules.py`, `test_intents.py`, `test_intent_coverage.py`, scenarios S01–S49 (`evals/e2e/scenarios.yaml`) | works | yes (§03, "23 intents") |
| ASK_BOOKS (question bank) | Questions answered from the books, never acted on | `app/nl/ask.py`, `app/nl/answers/answers.py` (30 `QUESTIONS`), `answers/metrics.py` | none | "Are we safe?", "How much do we need to raise to stay safe?", "What does FLOW recommend we do about cash?", "Can we make payroll?", "How much more can we borrow?", "What if Foshan pays 30 days late?", "Should we take Foshan's early-payment offer at 1.2%?", "Are we inside our covenants?"; zh: 我们安全吗？, 下次发工资的钱够吗？ | `tests/nl/test_ask_books.py`, `test_answers.py`; `evals/owner_questions/` (122 questions, 503 turns: 288 answered, 38 partial, 0 wrong, 177 can't) | works | yes (§03, Table 1, Table 9); the 30 ids: no |
| Plans and "go ahead" | A plan shows its exact operations and cost; "go ahead" runs exactly those | `app/nl/sessions.py` `PendingPlan`, `plans.py`, `service._confirm`; web Go ahead / Cancel buttons (`components/chat/assistant-turn.tsx`) | none | Demo shell: "Fund the cash gap", then Go ahead | `tests/nl/test_plan_binding.py`, `test_plan_flags.py`, `test_goal_and_corrections.py`; `e2e/chat.spec.ts` | works | yes (§03 "Propose, then confirm") |
| Consent rules | Money moves only on an unambiguous command | `app/nl/consent.py` (money command: one line, ≤ **160** characters, one RMB amount); `service._direct_command` (approve, reject, go ahead, cancel: ≤ **80** characters, no counterparty name, no paste or forward marks) | none | "Draw ¥50,000 on the credit line" executes; "Don't draw ¥50,000" does not | `tests/nl/test_consent.py` (41 consent attacks) | works | yes (§03 "Consent"); the 80/160 limits: **no** |
| Approvals by sentence | "approve APR-000002"; a bare "approve it" binds only to the approval this session just showed | `consent.approval_verdict`, `bare_verdict`, `session.shown_approvals` | none | after a queued cure: "approve it" | `test_consent.py`, S10, S13 | works; **known issue**: the approval card hides its id (`assistant-turn.tsx` `showId={false}`), which the exact sentence needs | yes (exact sentence); the bare "approve it": **no** |
| Corrections and goals | "actually make it 0.8%"; "Get paid early on the Foshan invoice without giving anything away next quarter" | `service._correct`, ACCELERATE_RECEIPT | none | Demo prompts "goal", "amend" | `test_goal_and_corrections.py`, S17, S19 | works | yes (§03 "Planning examples") |
| The opener (FLOW speaks first) | After time moves, FLOW names what needs the owner and proposes a priced cure | `POST /nl/opener` (`app/api/nl.py`), `nl/alerts.py` `alerts_turn` | alerts | **No UI caller since 8 Oct** (commit `218a3be1` removed `needs-card.tsx`; `nlOpener`, `appendOwnerOpener` and `mocks/home_opener_*.json` are unused). In the UI use Home's prompt "What needs my attention?" (same `alerts_turn`). `scripts/demo_run.py` still calls the route | `tests/nl/test_alerts_opener.py`, `test_queued_cure_opener.py`, `test_repay_opener.py`; no e2e | partial (API only) | yes (§01, §03 "Acting first", Appendix C); that the UI no longer calls it: **no** |
| New conversation | Starts over here and on the server; a later "go ahead" runs nothing | "New conversation" (`data-testid=chat-new`), `lib/chat.ts newConversation`; `POST /nl/session/reset`, `POST /nl/reset` | none | Ask FLOW → New conversation | `tests/api/test_nl_session_reset.py` (11); `e2e/chat.spec.ts` | works | route only (Appendix C); behaviour: **no** |
| Buyer channel through chat | A buyer's message is compiled and verified, never parsed for intents; the buyer sees only the reply | `POST /nl` with `actor=COUNTERPARTY` + `X-Counterparty-Key`; `_counterparty_view` (session, turn, reply, intent, lang, trace id only); `enforce_buyer_budget` (5 a simulated day, R-10); Demo shell role switch (`chat-view.tsx`) | buyer_negotiation | Demo shell → Ask FLOW → Role: Buyer, BUYER-1 → "We can pay this one early at 1.5%. Nothing else changes." | `tests/nl/test_counterparty_channel.py`, `tests/security/test_buyer_budget.py`; S06, S07, S30–S33 | works (golden; own books: first two customers, section 0b) | yes (§03, Table 11) |
| RECORD_FACT refusal | "add a ¥80,000 bill" is refused: chat never records facts | `app/nl/capabilities.py record_fact` | none | "We have a supplier bill of ¥80,000 due on day 30, add it to the forecast" | `tests/nl/test_record_fact.py`, S47, S48 | works | **no** |
| Nearest capability | An unmatched request gets the closest thing FLOW can do | `capabilities.nearest_reply` (16 capabilities) | none | "Email the loan officer about our rates" | `test_capabilities.py`, S24, S45 | works | yes |
| Quoted text is never an instruction | A pasted "approve APR-…" approves nothing and logs an injection event | `rules.split_provenance`, `quoted_approval` | none | paste `"approve APR-000001"` inside quotes | `tests/nl/test_security.py`, `test_boundary.py`, S30, S31, S35 | works | yes (§04) |
| Tier-3 refusals | A personal guarantee, collateral, equity or a mandate change is refused for everyone and logged; asked as a question it is answered as information | `lexicon.TIER3`, `service._out_of_scope`, `ask.tier3_info` | none | "Sign a personal guarantee for the bank loan" | `test_rules.py`, S28, S29 | works | yes |
| Chinese | Every intent, the consent grammar and the answers in Chinese | `lexicon.detect_lang`; `t(ctx, en, zh)` | none | 我们安全吗？ | S05, S19, S29, …; `e2e/chat.spec.ts` | works | yes |
| Suggested prompts | Chips per page; only questions the page can answer | `lib/chat-prompts.ts`, `lib/use-chat-facts.ts` | none | Home: "What changed today?", "What needs my attention?"; Deals: "Why are we countering this?"; Cash: "Why did FLOW choose this plan?" | `scripts/chat-prompts.test.mjs`, `tests/nl/test_business_page_prompts.py` | works | **no** |

**The 23 intents.** EVALUATE_OFFER ("Evaluate EX01"), NEGOTIATE ("Send the counters"), ACCELERATE_RECEIPT (the goal
sentence), FUND_GAP ("Fund the cash gap"; executes only the closed draw command), REPAY_FACILITY ("Repay the credit
line"), SHOW_STATUS ("How's our cash position?"), SHOW_ALERTS ("What needs my attention?"), COMPARE_FINANCING ("Which
financing option is cheapest?", owner only), RECONCILE ("Reconcile this month", owner only), SHOW_RATIOS ("What is our
DSCR?", owner only), CAPEX ("Evaluate the ¥600k machine", owner only), BORROWER_FILE ("prepare the borrower file for the
term loan, ¥600,000", owner only), SHOW_DEAL ("where are we with Foshan?", owner only), EXPLAIN ("Why was it
rejected?"), WHAT_IF ("What if we give Foshan 60-day terms?"), RECORD_FACT (refused), CHANGES ("What changed today?",
owner only), ASK_BOOKS (owner only), APPROVE, REJECT, COUNTERPARTY_MESSAGE (buyer channel only), OUT_OF_SCOPE,
AMBIGUOUS ("help me sort out our cash"). With the agent key alone every reply passes the `agent_view` allow-list
(`app/api/agent_view.py`, R-11): no cash, limits or reserve figures.

## 9. What-if sandbox and strategy

| Feature | For the owner | Where | Flag (`pnpm demo`) | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What-if sandbox | Move terms, discount, rebate, price rise and early-settled amount on a real buyer invoice; see the verdict, lowest cash, concession cost and covenants; nothing is written | `/whatif` (nav "Sandbox"; phone bar omits it), `app/whatif/page.tsx`, `components/whatif-controls.tsx`, `whatif-results.tsx`; `GET /whatif/presets`, `POST /whatif` (`app/api/whatif.py`) | none (visible) | Golden: Deals → EX01 → "Check against my limits" → "Try other terms"; terms 60 → 45 days gives COUNTER; preset Option A gives ACCEPT | `e2e/whatif.spec.ts`, `slice-b.spec.ts`; `tests/whatif/test_api.py`, `test_simulate.py` | works; **known issue**: presets are hard-coded to EX01 (60 days / 1.2% / 1%, Option A ¥260,000, `app/whatif/params.py`), so on other offers they mislead or give 422; rates off the 5 bp grid give 422 | the chat intent and Appendix B only |
| Late-payment stress on Cash | Cash redrawn with a buyer 30 days late: lowest cash, days under the reserve, what no facility covers | `/cash?stress=BUYER-1:30` (`app/cash/page.tsx`, `lib/cash-stress.ts`); link from the customer page "Stress-test payment"; `GET /buyers/{id}/exposure` | exposure (on) | Customers → Foshan → "Stress-test payment" | `e2e/cash-stress.spec.ts` (mock only); `tests/api/test_buyer_exposure.py`, `tests/strategy/test_stress.py` | works, golden and own books | **no** (Table 10 is the offline stress) |
| Buyer exposure and Business consequences | Concentration, how the buyer pays, the 30-day-late stress, capacity before and after, three consequence cards | Deals decision pane, Cash impact tab (`components/deals/flow/cash-tab.tsx` BusinessConsequences), Receivables aside, customer "Financial exposure"; `GET /offers|decisions|buyers/{id}/exposure`, `GET /offers/{id}/scenarios` | exposure (on) | Deals → EX01 → check → Cash impact → Business consequences | `deals-queue.spec.ts`, `customer-overview.spec.ts`; `tests/api/test_exposure_routes.py`, `tests/strategy/test_concentration.py` | works | **no** |
| Cash price curve | What ¥10,000 arriving 30 days earlier is worth | Cash header `cash-price-sentence`; `GET /cash/price-curve` | API on, **web off** (STRATEGY_MVP) | needs a `NEXT_PUBLIC_STRATEGY_MVP=1` build | `e2e/strategy.spec.ts` (`E2E_STRATEGY=1`); `tests/strategy/test_price_curve.py` | flag off | **no** |
| Collections worth | Rank invoices by what collecting each saves | `app/receivables/legacy.tsx` only; `GET /receivables/worth` | API on, web unreachable | API only, or a mock build with the fallback forced | `e2e/strategy.spec.ts`; `tests/strategy/test_collections.py` | **dead in live builds** | **no** |
| Safe Deal Envelope ("Before they ask") | What the owner can live with for a buyer before it asks | `components/deals/before-they-ask.tsx`, `deals/flow/investigate.tsx`; `GET /buyers/{id}/envelope` | API on, **web off** | STRATEGY_MVP build → Deals → EX01 → Cash impact | `e2e/strategy.spec.ts`; `tests/strategy/test_envelope*.py` | flag off | **no** |
| Customer economics | Sales, margin and classification as context for deals | `/customers/[id]/inputs` (`components/customer/inputs-sheet.tsx`); `POST /buyers/{id}/inputs`, `/firm/inputs` | **off** | — | `e2e/inputs-sheet.spec.ts`; `tests/api/test_customer_inputs.py` | flag off | **no** |
| Pilot journal | What the owner did against what FLOW said | Activity (`components/business/pilot-journal.tsx`); `GET/POST /pilot/journal` | **off** (API and web) | — | `tests/pilot/*` | flag off | **no** |

## 10. Capex & purchases

Nav label "Capex" (Demo: "Capex & purchases"); the phone bar omits it. Cash's "Need more funding?" card links to it.

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Capex hub | Health figures, every vendor contract with its stage, the chosen contract worked through, a quick check | `/capex` (`app/capex/page.tsx`, `components/capex/health-figures.tsx`); `GET /finance/health`, `GET /purchases` | capex + capex_contracts (on) | Capex → "Read the demo vendor contract" → confirm on Documents → row READY | `e2e/buyside.spec.ts` (mock only); `tests/api/test_purchases.py` | works | page named in §05; the hub: no |
| Evaluate a machine, financing structures, apply | ¥600k machine: NPV, payback; cash + line, 18/36-month loan, 48-month lease screened daily and monthly; Apply queues one Tier-2 application | `components/capex/quick-check.tsx` (fixed ¥600k request); `POST /capex/evaluate`, `POST /capex/apply` | capex (on) | Capex → "Test a machine without a contract" → Evaluate → lease selected (¥92,327.32) → Apply → approve | `e2e/capex.spec.ts` (mock only); `tests/capex/test_evaluate.py`, `test_api.py` | **demo books only** (needs `FAC-ETL`/`FAC-LEASE`) | yes (§03 item 8, Appendix C, limitations) |
| Purchase contracts and commit | A vendor contract's payment schedule from its reading and the owner's timeline; the vendor's early-payment discount priced; Commit is Tier 2 and books the payments on approval | `/buy`, `/buy/contract?id=`, `components/capex/contract-workbench.tsx`; `POST /capex/contracts/{id}/evaluate`, `/commit`, `GET /purchases/{id}`; fixture `fixtures/capex/gzpm-2026-114-equipment-purchase.md` | capex + capex_contracts (on) | Capex → the GZPM row → "Work out the payments" → "Commit, paying early" → Approvals → "Authorize the purchase" | `e2e/buyside.spec.ts`; `tests/capex/test_schedule.py`, `tests/api/test_capex_commit.py` | works (own books: fewer financed structures); a committed purchase cannot be cancelled | yes (§02, Appendix C) |
| Financial health | Cash coverage, current and quick ratios (owner estimates), covenant room, capacity per facility | `/finance`; `GET/POST /finance/health` (`app/api/buyside.py`) | capex_contracts (on) | Capex → "Financial health and loans" | `e2e/buyside.spec.ts`; `tests/health/test_health.py` | works | **no** |
| Loan eligibility | Four illustrative catalogue loans read against the books; "Add to my funding menu" queues a Tier-2 AddFacility (counts as zero until committed) | `/finance`; `GET/POST /lending/eligibility`, `POST /lending/products/{id}/add-to-menu`; `fixtures/lending/catalogue.json` | capex_contracts (on) | `/finance` → months trading 36 → Read eligibility → Add | `e2e/buyside.spec.ts`; `tests/lending/test_eligibility.py` | works (indicative) | **no** |
| Long-term plans | Projects × structures × start months over 60 months, top five by NPV | `/plans`; `POST /capex/plans` | capex_contracts (on) | Capex → "Long-term plans" → Run | `e2e/buyside.spec.ts`; `tests/capex/test_plans.py` | works | **no** |
| Borrower file | A lender-style file from the verified books, prepared and never sent; HTML, DOCX (PDF only with WeasyPrint) | quick check `#file`, `components/business/borrower-file.tsx`; `POST /borrower-file`, `GET /borrower-file/{id}.html|.docx|.pdf` | borrower_file (on) | after the quick check: "Prepare the borrower file" | `e2e/capex.spec.ts`; `tests/borrower_file/*` | **demo books only** | one bullet in §02; routes: no |

## 11. Records, evidence and the Demo story

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Receivables | Customer list, then one customer's invoices: what each nets after financing, what it rests on, a late stress aside, "Chase payment" (a request to copy; nothing is sent) | `/receivables` (`?customer=`), `components/receivables/*`, `components/business/chase-payment.tsx`; `GET /receivables`, `GET /receivables/{id}/chase` | none (stress aside: exposure) | Receivables → Foshan; after day 34 → Chase payment → Copy | `e2e/receivables-layers.spec.ts`, `receipt-basis.spec.ts`; `tests/api/test_receivables_net.py`, `test_collections.py` | works; drops `from` (#163) | page named only; chase and net view: **no** |
| Activity log | Every operation and security event newest first, filters that hide but never remove, chain badge, evidence fold per row; Reconciliation tab | `/activity` (`components/activity/activity-read.tsx`, `components/business/reconciliation-section.tsx`, `#reconciliation`); `GET /activity`, `GET /reconciliation` | alerts for the tab | Activity → Reconciliation | `e2e/activity.spec.ts` (no test clicks the Reconciliation tab); `tests/api/test_activity_read.py` | works | page named only |
| Hash-chained evidence and export | Every executor outcome chained `sha256(prev + payload + result)`; Download JSONL; offline verification | `/trust?view=evidence` (`components/trust/evidence-view.tsx`), `/evidence`, `/ledger`; `GET /evidence`, `GET /ledger`; `scripts/verify_evidence.py` | none | Demo → Proof → "The full record" → Download JSONL; `python scripts/verify_evidence.py e.jsonl` | `e2e/trust.spec.ts`; `tests/security/test_evidence_verifier.py`, `tests/api/test_read.py` | works (no verify route: offline only) | yes (§04 "The record"); `/trust`: **no** |
| Security events and the FastCapital scene | The hostile message with flagged spans, a zero-harm scoreboard, the buyer's fixed reply, circuit resets | `/trust?view=security`, `/security` (`components/trust/security-view.tsx`); `GET /audit`, `GET /security/summary`, `POST /circuit/{id}/reset` | security_scenes (hides fixtures only; the button works with it off) | Account menu → Security and evidence → Security → "Run the FastCapital scene" | `e2e/trust.spec.ts`; `tests/security/test_scoreboard.py` | works; **known issue**: `GET /audit` called without `lang`, so event words stay English in zh | events yes; the page: **no** |
| Demo story | Six scenes, one next control, the owner's approval only by the owner's click; Proof block; operator tools (clock, books, four more scenes) | `/demo` (`app/demo/page.tsx`, `components/demo/books-cards.tsx`, `lib/demo.ts`); `GET /demo/story`, `POST /demo/restore`, `POST /demo/reset?scenario=` (golden_sme, short_facilities, public_sme, busy, blank), `POST /demo/bank-receipt` | DEMO_MODE | Demo → Golden story → the filled button through six scenes | `e2e/demo.spec.ts`, `tour.spec.ts`; `tests/api/test_demo_story.py` | **demo books only** | yes (§05) |
| Judge tools | One offline command for 49 tasks, the attack catalogue, the demo walk and the chain check | `scripts/judge_eval.py` (writes `services/api/evals/judge/judge-report.md`), `scripts/verify_evidence.py`, `scripts/demo_run.py`, `scripts/export_demo_evidence.py`, `scripts/run_scenarios.py`; `docs/deliverables/JUDGING_QUESTIONS.md` | — | `uv run --project services/api python scripts/judge_eval.py` | `tests/nl/test_runner.py`, `tests/security/test_evidence_verifier.py`; nothing tests `judge_eval.py` itself | works | judge_eval, verify_evidence, demo_run, run_scenarios: yes; export_demo_evidence and JUDGING_QUESTIONS.md: **no** |

## 12. Security a user can see

| Feature | What the user sees | Where | Test | Tech doc |
| --- | --- | --- | --- | --- |
| Sign-in and the landing page | "Access FLOW" / "Join FLOW now!" on `/welcome`; the owner token is kept for the tab only (sessionStorage), the account flag never holds it; `pnpm demo` prefills the demo token | `app/welcome/page.tsx`, `components/landing/landing.tsx`, `lib/auth.ts`, `lib/account-flag.ts`, `components/owner-auth.tsx`; `app/api/auth.py` (constant-time, refusals logged, 300 an hour) | `tests/security/test_route_policy.py`, `test_sec26_refusal_budget.py`; no e2e for `/welcome` | sign-in yes; `/welcome`: **no** |
| Demo credentials off by default | Without `DEMO_MODE` the published keys are refused, nothing is seeded, `/docs` is not served | `app/config.py`, `app/main.py:50` | `tests/security/test_demo_mode_default.py` | yes |
| Rate limits | 429 with a retry time: owner 3000, agent 1200, bank feed 600, buyer 120, anonymous 300 a minute; anonymous intake 200 and a keyed buyer 5 a simulated day | `app/api/ratelimit.py`, `app/api/offers.py` | `tests/security/test_rate_limits.py`, `test_buyer_budget.py`, `test_intake_cap.py` | yes |
| Tier 3 never | Refused for everyone, logged | `app/operations/executor.py` | `tests/operations/test_tiers.py` | yes |
| CSP and headers | A nonce per request; no framing | `apps/web/proxy.ts`, `lib/csp.ts`, `app/main.py` | `scripts/csp.test.mjs`, `tests/security/test_headers_and_docs.py` | yes |
| Outbound guard with canaries | A message that would leak a protected value is replaced by a fixed reply and logged | `app/egress/guard.py`, `canaries.py`, `app/outbound/message.py` | `tests/egress/*` | yes |
| Buyer channel boundary | A buyer sees its reply only; a key decides who it is | `app/api/nl.py _counterparty_view` | `tests/nl/test_counterparty_channel.py` | partly |
| Redaction before a live model | Accounts, phones, IDs and addresses replaced before text leaves | `app/compiler/redaction.py` | `tests/compiler/test_redaction.py` | yes |
