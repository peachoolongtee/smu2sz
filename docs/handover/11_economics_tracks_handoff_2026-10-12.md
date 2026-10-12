# Handoff: the three customer-economics tracks (Phase 2 Inputs sheet #97, Phase 3 comparator #100, Phase 4 envelope #98)

Written 12 October 2026 for an engineer joining cold. Everything needed is in this file or in the files it names in this
repository. No conversation history is required. Read the sections in order; the three specs are at the end.

## 1. What FLOW is, in one paragraph

FLOW is a treasury and working-capital agent for a small manufacturer. It reads the owner's books, projects cash day by day,
plans funding within a signed mandate, verifies what a buyer asks for (longer terms, rebates, early-payment discounts), and
explains every figure in plain English and Chinese. The owner sees five pages: Home, Deals, Cash & Funding, Receivables,
Activity, plus a Customer overview drill-down. The three tracks here extend the Deals verdict with customer economics (what the
relationship brings, as context), a scenario comparator (what each answer does to cash), and a negotiating envelope (what FLOW
may safely offer, and how it answers the buyer's actual ask).

## 2. Repository, branches, setup

- Repo: https://github.com/peachoolongtee/smu2sz. Work branches from `dev` (never `main`). `dev` is at or after d6bc9611.
- Base branches (pushed): `dev` (the Home hybrid, the exposure API, #107 net collection, the Customer overview read on its own
  branch); `feat/connected-words` (b2f18942 + one review-fix commit landing soon: the buyer-keyed exposure read, the Customer
  overview read, the per-path words). Phase 3 and Phase 2 branch from `feat/connected-words`; Phase 4 branches from `dev`.
- API: `services/api` (FastAPI, Python 3.13, `uv`). Tests from that directory:
  `SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/strategy tests/api tests/deals`
  Run the API: `FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CUSTOMER_ECONOMICS=1 SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" uvicorn app.main:app --port 8197`
- Web: `apps/web` (Next 16, pnpm, Playwright). `pnpm install`, then `pnpm typecheck`, `pnpm lint`, `pnpm test:unit`,
  `E2E_TARGET=mock E2E_PORT=3197 pnpm exec playwright test <specs>`. Never port 3000. Mocks under `apps/web/mocks` are recorded, never
  hand-edited: `node apps/web/scripts/record-mocks.mjs --api http://localhost:8197` (plus the flag for the read you add, e.g.
  `--buyer-exposure`, `--overview`; add a flag for any new read). Commit only the mock files your read produces.
- Feature flags (services/api/app/config.py): `FEATURE_ENVELOPE` (the envelope), `FEATURE_EXPOSURE` (Phase 1: exposure,
  stress, capacity, the comparator), `FEATURE_CUSTOMER_ECONOMICS` (Phase 2: the economics fields and the sheet). All default off.
- Environment quirks: macOS has no `timeout`; zsh expands a leading `=` and `[0-9]` globs (quote them); the cwd of tool shells
  resets between calls (use absolute paths); never a bare `git stash` (shared stash); never an unscoped `pkill` (kill by your own
  port or PID; an unscoped `pkill -f "playwright test"` killed another engineer's gate three times).
- Commits: on your branch only, plain one-line messages, no attribution lines, no "Co-authored-by". One commit per spec item.

## 3. House rules that every reviewer checks

1. **INVARIANT 13.** The browser computes no money or date words. Every figure, label, "in N days", tone word and sentence is a
   server display string built through `t(lang, en, zh)` (services/api/app/strategy/words.py and app/api/*words*.py), in the
   您 voice in Chinese. No codes, ids or day numbers in Business mode (a contract reference as the document's own name is allowed;
   a bank reference or an internal id is not).
2. **The stability set is read-only:** `app/financial`, `app/verifier`, `app/funding`, `app/alerts`, `app/operations`, `app/clock`,
   `app/books`, `app/mandate`, `app/covenants`, `app/domain/models.py`. Everything here lives in `app/strategy/*` and `app/api/*`.
   Check with `git diff --stat dev...HEAD -- <those paths>`; it must be empty.
3. **Additive only.** Existing response fields are never renamed or removed; new fields are optional and typed optional on the web.
4. **Compose, never recompute.** The verdict's own figures (`forward_concession_total_fen`, the counters, the tiers), the router's
   selected plan, `net_at_collection`, `state_of` (financing state), the one margin/contribution function on
   `app/api/customer_overview.py`, the exposure assembly (`buyer_exposure`), `scenario_paid_late` (the one late-payment
   mechanism). A second computation of any of these is a review failure.
5. **Mandate and economics are two sentences.** Economics never changes a verdict, tier, code, counter, cap or plan (property P8).
   The words "profit", "profitable", "worth" are never used of either figure; "gross profit" / 毛利 is the default basis word.
6. **Three authority classes, never two:** `flow_may` (FLOW may act alone), `needs_owner` (safe, needs the owner),
   `over_your_limits` (safe for cash, over a signed cap: only a new signed mandate moves it). The verifier's own counter is the
   recommended response; the envelope never ranks packages as "recommended".
7. **No probabilities, no expected values, no "if you counter, Foshan walks", no summing concession and funding cost, no adding
   capacity across rows, no undefined future order, no multidimensional search** (the owner's five kill criteria, confirmed).
8. Tests pin behaviour on the golden books (`fixtures`, `golden_sme`) in both languages, with the no-English-leak helper in
   `tests/api/test_w7_language.py`. Every new zh string gets a test. No `test.skip`, no loosened matchers.
9. Timing: a full read stays under 3 s on golden (assert as `tests/api/test_exposure_routes.py` does, SKIP_PERF_BENCH-aware).

## 4. Owner decisions in force (12 Oct, ticket #89)

Sales projected from the books with the owner's override; gross margin, 20% on the Demo as a Demo assumption (provenance DEMO,
never OWNER_ENTERED), one firm-wide figure for the pilot, per-buyer optional; classification (Normal / Important / Strategic)
entered, context only, no rule until signed into the mandate; customer value appears after the verdict, as context, never as a
reason to say yes; recourse: a shortfall on a financed invoice is owed by the owner; a late receipt on a financed invoice keeps
the financing running with per-period charges from the facility record; an early-payment agreement lapses when paid late;
"due soon" = 7 days before due, "chase" from the day after due; the 15-day stress row waits (only 0 and 30 days now); three
packages on the card in Phase 4; all five kill criteria hold.

## 5. Where things live (read these first)

- `docs/CUSTOMER_ECONOMICS_BRIEF.md`: the research synthesis. §C (economics, Phase 2), §D (comparator, Phase 3), §E (envelope,
  Phase 4), §G.3 (the late-payment stress), §H (shared architecture, flags, storage). The three specs below cite it by section.
- `docs/research/customer-economics-2026-10-10/`: the mission, the map body and the five research reports (r1–r5) the brief cites.
- `docs/STRATEGY_MVP_BRIEF.md`: the envelope as built and its wording rules.
- `docs/design/connected-views-2026-10-12/`: the plan and specs of the three connected pages (for context: Deals queue,
  Receivables, Customer overview) and `docs/design/mockups-connected-2026-10-12/` (the boards: `Inputs.dc.html` is the sheet).
- `docs/handover/08_session_handoff_2026-10-12.md` and `10_session_handoff_2026-10-12b.md`: the protocol and the state.
- Code: `services/api/app/strategy/envelope.py` (the envelope), `exposure.py` (the Phase 1 assembly, `buyer_exposure`),
  `impact.py` (`scenario_paid_late`, `stress`), `capacity.py`, `concentration.py`, `payments.py`, `net.py`
  (`net_at_collection`), `inputs.py` (customer inputs, provenance, digest), `words.py`; `services/api/app/api/strategy_exposure.py`
  (the exposure and buyer routes), `customer_overview.py` (the overview read, the margin function, `context.back`),
  `customer_inputs.py` (POST /buyers/{id}/inputs, POST /firm/inputs, GET /buyers/{id}/inputs; `PHASE_1_FIELDS`), `offer_picture.py`
  and `deal_offers.py` (the verdict picture, `open_offer`); `apps/web/components/customer/overview.tsx`, `components/deals/queue/*`
  (on `feat/deals-queue`), `lib/api.ts`, `lib/types.ts`, `lib/dictionary.ts`, `DESIGN.md`.

## 6. The Demo figures you will meet (golden books, Foshan Home Retail)

Open invoice ¥420,000 due in 32 days; the ask: 60-day terms + 1% rebate + 1.2% early settlement; as asked: ¥28,326.92 forward
concession over 12 months against a ¥5,000 budget, immediate discount ¥5,040; Option A: 45 days + 0.85% early settlement on
¥257,200, ¥3,027.77 once, Tier 1 (FLOW may send it); spare capacity today ¥81,000, as asked ¥14,000, Option A ¥0 until 1 Nov,
Option B ¥62,000; the 30-day stress: lowest −¥250,000 on day 60, 65 days below the ¥300,000 minimum, ¥550,000 uncovered, no
admissible plan; with the invoice financed (¥255,000 arranged, lands day 3): lowest ¥5,000, 57 days, ¥295,000. Annual sales
projected ¥5,460,000; contribution about ¥1,092,000 at the 20% Demo margin; the request is about 2.6% of it. These are pinned in
`tests/strategy/test_exposure_demo.py`, `test_stress.py`, `tests/api/test_customer_overview.py`; if your change moves one, say
why in the report and re-pin.

## 7. Definition of done, per track

Spec items delivered in order with their tests; gate green (the pytest command above, plus `ruff check` and `mypy` on touched
files; for the sheet also the web gate and the recorded mocks); the stability-set diff empty; a report under 250 words: each
item as shipped, the golden sentences in both languages, timings, what you refused and why. Then a code review by someone who
did not write it (the checklist is section 3), fixes in one commit, and a merge into `dev` with `--no-ff` by the lead.

## 8. Order and dependencies

Phase 4 (envelope) first: it is server-only, from `dev`, and the largest. Phase 3 (comparator) next, from
`feat/connected-words`, after its pending fix commit lands (merge it in). Phase 2 (the sheet) last or in parallel on a second
machine; it is web with a small server part, from `feat/connected-words`. None of the three depends on another, but the
comparator's "Class 3 plus economics" sentence and the envelope's economics sentence both read the one margin function, so merge
the envelope before the comparator to avoid two edits of the same words.

---

## 9. Spec: Phase 4 envelope (#98 with #97's envelope items)

# #98 (with #97's envelope items): the envelope answers the buyer's ask; authority classes; fewer packages (server)
Branch `feat/envelope-ask` from dev. Strategy layer and API only (app/strategy/envelope.py and its words; app/api/strategy_envelope.py or wherever the envelope route lives: find it); the stability set (app/financial, verifier, funding, alerts, operations, clock, books, mandate, covenants, domain/models.py) is read-only; FEATURE_ENVELOPE stays the gate. INVARIANT 13 (t(lang, en, zh), 您, no raw ids). Read first: docs/CUSTOMER_ECONOMICS_BRIEF.md §E (E.1 the three classes, E.2 P1–P6, E.3 the sentences: these are the spec, verbatim), §0 and §H.5; docs/STRATEGY_MVP_BRIEF.md (the envelope as built, its wording rule: the verifier's own counter is the recommended response, never an envelope ranking); app/strategy/envelope.py, app/strategy/types.py, tests/strategy/test_envelope.py; docs/research/customer-economics-2026-10-10/r3-envelope-against-the-mission.md for the evidence behind each item (r3 line refs in §E).
Deliver, in this order, each with its tests pinned on golden en and zh as test_envelope.py:63-65 and :304-340 do:
- P1: `authority` per package, one of the three classes (E.1, derived as the table says, never two); the `terms_budget_ignored` maximum listed as one class-3 package in its own group with the cap it breaks and by how much.
- P2: display and the zone's smallest price filtered by `approved`, not `passes`; failures kept only in `full_grid`; a test on books where a cure cannot land in time; the covenant wall label fix (`wall_of(..., ignore_caps=True)` must not name an unknown code "the cap for this buyer").
- P3: the sentence "At today's price: up to 45 days within your limits"; name packages, not maxima; drop the rebate maximum from the joined sentence unless its package is the one quoted.
- P4: `compensate(T)` for the buyer's asked terms, exactly as E.2 P4 and the non-monotone note say (search the face only at the smallest rate; each result `v.probe`d whole and re-checked; cached apart like the zone). Sentences E.3 "P4, no price works" and "P4, price works", verbatim.
- P5: replace `top_first`'s untested middle with one probe and the neighbour rule; the exhaustive terms × price scan plus the face column as a weekly script under services/api/scripts (not in the online path), failing loudly on disagreement.
- P6: fewer packages: the verifier's counters and the ask's answer first, the rest behind `more[]`; at most three packages on the card (owner's decision 15, #89).
- Class-2 and class-3 sentences from E.3 verbatim; the "Class 3 plus economics" sentence only when FEATURE_CUSTOMER_ECONOMICS is on and the contribution exists (read it through the one margin/contribution function on dev: app/api/customer_overview.py / app/strategy; never a second computation; the share from the verdict's `forward_concession_total_fen` over the 12-month contribution, §C.2's bounds "under 0.1%" / "more than 10 times").
- Refused (E.3): "60 days with 20% upfront"; "Recommended: option A" among packages. Fix the 让步 / 让利 inconsistency noted in §E.3 (one term, the existing one in `_WALL_WORDS`).
Also keep the eval budget: golden about 2 s for P4 price-only; assert it under SKIP_PERF_BENCH-aware timing as the exposure tests do. Gate: `SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/strategy tests/api tests/deals` from services/api, ruff, mypy on touched files. Absolute paths; macOS has no `timeout`; zsh expands a leading `=` and `[0-9]` globs; never an unscoped pkill. Commit on your branch only (one commit per item P1…P6, plain one-line messages, no attribution lines). Report under 250 words: each item as shipped, the golden sentences, eval counts and timings, what you refused.

---

## 10. Spec: Phase 3 scenario comparator (#100)

# #100 Phase 3: the scenario comparator, five rows and a late overlay, no probabilities (server)
Branch `feat/comparator` from feat/connected-words (it carries the buyer exposure, net at collection, the Customer overview and the Home hybrid). Strategy layer and API only; the stability set read-only; FEATURE_EXPOSURE gates it (no new flag). INVARIANT 13. Read first: docs/CUSTOMER_ECONOMICS_BRIEF.md §D (D.1 rows, D.2 fields, D.3 customer loss with #90's corrections binding, D.4 refused, D.5 the Demo rows: these are the spec), §G.3, §H; app/strategy/{exposure,impact,capacity,concentration,net}.py, app/api/strategy_exposure.py (the per-path blocks and the appended `do_nothing` path: the comparator's "current books" row is that path's full treatment), app/strategy/scenario.py or wherever `ScenarioState`/`marginal_impact`/`evaluate_many` live (find them), the verdict's `VerdictBundle` and `CounterProposal`.
Deliver `GET /offers/{id}/compare?lang=&late=0|30` (and `GET /decisions/{id}/compare`): `rows[]` in D.1's order (current books; accept as asked; each counter k; customer loss), each with D.2's fields (outcome/required_tier/codes for packages only; `concession_forward_fen` the verdict's figure never added to funding cost; `immediate_discount_fen`; `funding_cost_fen` the router's SELECTED plan named as such; `need_fen`, `lowest_cash_fen`/day, `first_breach_day`; `plan_flags`; `capacity` the Phase 1 block; `contribution_context` labelled, only when the contribution exists; `marginal_impact(current, row)`), each with D.1's assumption sentence verbatim (en and zh), display strings for every figure, and `late` as an overlay on every row through `scenario_paid_late` (G.3) and never a second mechanism; the late overlay on a financed invoice is modelled as #107 does (D.4's old refusal is superseded by #107: say so in the docstring). Customer loss exactly as D.3: billings removed, receipts removed within the 120-day horizon, gross profit foregone (ESTIMATED when the margin is), the refusal sentence about costs not modelled, the horizon printed beside any annual figure. D.4's refusals hold: no probability or expected value, no "if you counter, Foshan walks", no summing concession and funding cost, no adding capacity across rows (joint re-run through `evaluate_many`), no undefined future order. Pin D.5's Demo table on golden (the figures as the brief lists them; if one differs on today's dev, state why in the report and pin the real one). The 15-day late row is NOT built (owner's decision 11): `late` accepts 0 or 30 only. Cache like the exposure read; the full read must stay under 3 s on golden (assert as the exposure tests do). Tests tests/api/test_compare.py and tests/strategy/test_customer_loss.py, en and zh, no English leak in zh. Gate: `SKIP_PERF_BENCH=1 uv run --project "$PWD" --directory "$PWD" pytest -o addopts= -p no:cacheprovider tests/strategy tests/api tests/deals` from services/api, ruff, mypy on new files. Absolute paths; no `timeout` on macOS; zsh `=`/`[0-9]`; never an unscoped pkill. Commit on your branch only, plain messages, no attribution. Report under 250 words: the shape, the Demo rows as pinned, anything refused or not composable.

---

## 11. Spec: Phase 2 Inputs sheet (#97)

# #97 Phase 2: the owner's Inputs sheet (web) and its reads (server words), behind FEATURE_CUSTOMER_ECONOMICS
Branch `feat/inputs-sheet` from feat/connected-words. Read first: common-web.md (../map-econ/common-web.md: the rules), the board ../mock-econ/project/Inputs.dc.html (its words and order are the spec), docs/CUSTOMER_ECONOMICS_BRIEF.md §C (C.2 metrics and rules, C.3 provenance, C.4 the twelve edge cases, C.5 classification) and §H.4 (storage); services/api/app/api/customer_inputs.py (POST /buyers/{id}/inputs, POST /firm/inputs, GET /buyers/{id}/inputs; PHASE_1_FIELDS and the 422 behind the flag), app/strategy/inputs.py (fields, provenance, digest), app/api/customer_overview.py (`edit_href` null until the flag is on; the margin function with DEMO provenance; `economics[].entered`), apps/web/components/customer/overview.tsx (the "Edit these facts" link), lib/api.ts, lib/types.ts, lib/dictionary.ts.
Server (small, additive): GET /buyers/{id}/inputs gains, per field, `label`, `value_display`, `provenance_text` ("you entered", "projected from your books", "assumed for the Demo", "company average, estimated"), `entered_day_text`, `editable`, and the firm-level rows (gross margin, `margin_basis` GROSS | CONTRIBUTION, VAT rate) with the same words; a `vat_note` ("as invoiced (VAT status not set)" when none); `edit_href` on the overview becomes `/customers/{id}/inputs` when the flag is on. Validation words for the 422s in both languages (margin −10,000..10,000 bp; sales integer fen with `vat_inclusive`; classification one of three). Never a computation in the browser.
Web: the sheet at `/customers/[id]/inputs` (the board: annual sales with its source and the projected figure beside it; gross margin prefilled with the firm average labelled ESTIMATED, editable; basis; VAT; classification Normal / Important / Strategic as context only, with the sentence "this changes nothing FLOW does on its own"; the provenance word and the entered day on every row; one "Save" that writes through the existing POST routes field by field and shows the server's words; the C.2 consistency sentences from the server when present; the Demo's 20% shown as "assumed for the Demo"). Flag off: the route shows the server's 422 sentence as a quiet notice and no form. Every customer name's "Edit these facts" link lands here with context and the back link returns to the overview (`context.back`). Tests: `e2e/inputs-sheet.spec.ts` (mock; record `buyer_inputs[_zh]` and the firm read from your API on port 8197 with FEATURE_EXPOSURE=1 FEATURE_CUSTOMER_ECONOMICS=1; commit only new mock files): the rows and their provenance words; saving a margin changes the overview's qualifier from "assumed for the Demo" to "you entered" (re-read); the 422 sentence; flag off; zh; phone 390×844; keyboard; axe. Gate per common-web.md plus the API tests for the touched route (`tests/api/test_customer_inputs.py`). Web port 3197. Absolute paths; no `timeout`; zsh `=`/`[0-9]`; never an unscoped pkill; before every commit `rm -f apps/web/AGENTS.md apps/web/CLAUDE.md; git checkout HEAD -- apps/web/tsconfig.json`. Commit on your branch only, plain messages, no attribution. Report under 200 words.

---

## 12. Review checklist (what the reviewer looks for)

INVARIANT 13 and the 您 voice on every new string; no raw ids; compose-not-recompute (grep for a second margin, contribution,
share, net or late-payment computation); the stability set untouched; the three classes derived exactly as §E.1; the refusals in
§D.4 and §E.3 honoured; cache keys covering the books, the inputs digest, the mandate, the day, the language and the flag;
no partial result cached; tests that pin incidental values; exceptions swallowed; English leaking into zh; the eval budget and
the 3 s read; the owner's decisions in section 4.
