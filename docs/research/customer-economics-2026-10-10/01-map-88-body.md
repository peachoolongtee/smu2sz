# Wayfinder: FLOW customer economics and negotiation intelligence (is the relationship worth the capital, what can we safely offer, what flexibility do we give up)

Charted 10 October 2026 from the owner's mission ("principal product architect, financial systems engineer, commercial finance lead, implementation owner": the next layer of FLOW). The central question moves from "can this business afford this deal?" to "is this customer relationship worth the capital it consumes, what can we safely offer them, and what flexibility do we give up by saying yes?". The mission names five capabilities (A customer economics, B accept / counter / customer-loss scenarios, C the safe commercial envelope, D opportunity cost and capacity consumption, E late payment and customer concentration) and asks for shared primitives, not five features.

**This map is planning first.** The owner's instruction on 10 October: no commits until told. Every ticket below resolves on the tracker (resolution comments) and in the session scratchpad; nothing lands in the repository until the owner says go. The build phases are filed so the way is visible, and stay blocked.

## Goal

A deal surface that can say, with every figure traceable to canonical state and every estimate labelled as one: what the request costs over twelve months, what that is as a share of the customer's estimated annual contribution, where cash goes and what capacity it consumes, how concentrated the receivables are, what a late payment would need, what the owner can safely offer instead, and that the signed mandate still decides what FLOW may do alone. Customer value never overrides owner authority: MANDATE (what FLOW may approve or execute) and ECONOMICS (whether going outside it is commercially rational) stay two separate statements.

## Done when (the way is clear)

- Deliverables A to L of the mission's section 50 exist as resolved tickets: the current capability map, the data availability matrix, the customer economics spec, the scenario comparator spec, the safe envelope spec, the capacity / opportunity-cost spec, the late-payment / concentration spec, the shared architecture, the UX proposal, the test strategy, the implementation phases, the risks and kill criteria.
- Every proposed metric has a definition, units, a time horizon, source data, a rounding rule, edge cases and the tests that would prove it (section 35); no formula is duplicated between modules or between server and browser (INVARIANT 13).
- Every input is classified AVAILABLE NOW / DERIVABLE NOW / NEEDS OWNER INPUT / NEEDS ACCOUNTING IMPORT / NEEDS PAYMENT HISTORY / NOT AVAILABLE, with the fixture or store that holds it named (section 32).
- The shared architecture states which existing primitives are reused (the strategy MVP's `ScenarioState` / `CandidatePackage` / `MarginalImpact` and `marginal_impact()`, the Safe Deal Envelope, the what-if sandbox, the router's comparison contract, the decision record) and which new ones are justified by at least two capabilities sharing them (sections 24, 25, 47).
- The owner has decided which capabilities proceed, what they will enter by hand for the prototype (annual sales, margin, classification) and the kill criteria; the build phases are specified from the synthesis and wait for the owner's go.

## Scope

In: investigation, specification and validation of the five capabilities; the reconciliation with what the strategy MVP (map #47) and the remediation (map #65) already built; the data audit; the UX proposal under the remediation's progressive disclosure (one headline, two to four decisive facts, one recommendation, one action; evidence on demand). Out (sections 23, 49): AP optimisation and supplier-payment delay (deferred until payables are modelled), generic ERP, tax, payroll, accounting, churn prediction or acceptance probabilities, opaque importance scores, the full portfolio optimiser, collections automation, any new execution authority (section 44). The engine stays in stability mode (the optimisation log's section 0, an internal note, in the git history): `app/financial`, `verifier`, `funding`, `alerts`, `operations`, `clock`, `books`, `mandate` do not change; the new work is read-only, explainable and feature-flagged, built over labelled copies of the books like the strategy MVP.

## Reconciliation: the five capabilities against the repository (the lead's reading on 10 October, corrected by #90, #92 and #93)

- **A Customer economics: nothing exists in the books, and the books already bound the answer.** `Counterparty` holds `id`,
  `name`, `role` and `known` and is `extra="forbid"` (`domain/models.py:454-458`). There is no annual sales, margin,
  contribution or classification. The buyer profiles in `fixtures/counterparties/buyers.yaml` are hidden state under INVARIANT 7,
  and the decision record's `SentFact.outcome` / `buyer_profile` are simulated outputs of the same kernel
  (`decisions/facts.py:72-74`). Neither is a source.
  What exists:
  - the forward run rate from `RecurringInvoice`, counted by the concession window's own issue days: golden Foshan ¥5,460,000,
    13 invoices (PROJECTED; VAT status unset on `dev`);
  - `monthly_ebitda_fen`, which floors any margin (Σ contribution ≥ 12 × EBITDA; Foshan's margin ≥ 19.78%, so the ¥28,326.92
    request is at most 2.62% of Foshan's contribution, not the mission's 7.1%);
  - invoice history from day 0 only, in `state.receivables` and the clock's `ADVANCE_CLOCK` payload (13 days golden, 96 days
    public; open invoices only).

  `ExpectedOrder` is a rebate base only. It never reaches the cash projection, carries no cost or timing, and is not firm in
  either fixture. It does **not** define the demand section 15 requires. The public SME's per-buyer sales and 23.76% company
  gross margin exist only in `public_sme.SOURCES.md`; contract terms exist only on the unmerged `feat/upgrading`.
- **B Scenario comparator: the primitive exists; the buyer scenarios need two new labelled copies, both in the strategy layer.**
  `ScenarioState`, `read_books` / `marginal_impact` (no funding actions in `read_books`, so its lowest headroom is cash before
  funding), the what-if, the router's comparison contract and the counters exist.
  - **Customer loss:** a copy that ends the buyer's recurring invoices. Removing expected orders changes no cash. Issued
    receivables stay. Costs stay too, because no outflow carries a counterparty: the row shows receipts removed and gross profit
    foregone, never a cash figure net of avoided costs.
  - **Late payment:** `scenario_received` deliberately refuses a receipt past the due day (`strategy/impact.py:108-110`, pinned in
    `test_impact.py`). The late case is a new, separately named transform that replaces each moved receipt with one dated cash
    flow, so it is counted once and is not financeable past its contractual day. It is strategy-layer work, not engine work.
- **C Safe commercial envelope: built (map #47 Wave 3), flagged off, and closer to the mission than stated.** The minimum
  compensating price per term exists (`ZoneRow.min_price_bp`, `zone=1` since `0cd60cb`). So does "financially feasible over the
  caps" (`liquidity_only`, the lever "terms, budget ignored": golden 45 days within the limits, 55 days on liquidity alone).
  Authority is **three** classes, not two:
  1. FLOW alone (Tier 1: an early payment on a named invoice);
  2. within the signed limits, needs the owner;
  3. over a signed cap, which is a hard REJECT that only a new signed mandate moves (`verifier/evaluate.py:94, 190-193`;
     `operations/executor.py:500-510`; `mandate/tiers.py:43`). "Owner approval" cannot lift a cap.

  "20% upfront" is not the early-pay face. A deposit has no obligation type and is engine work; on golden, 60 days needs ¥240,200
  paid early plus +0.40%, and no price alone works. Terms move on a 5-day grid. Monotonicity is tested on the bisection path only:
  `top_first` assumes it, and the early-pay face is non-monotone at 0.85%. Weekly reads run 6.8 to 8.1 s on the public-record SME
  after `ba79762` / `0cd60cb`; the 17 to 78 s figure was the dry pilot's.
- **D Capacity and opportunity cost: the state exists and reconciles; the statement does not, by map #47's decision.** Per-facility
  balances are computed inside the trajectory but only their total leaves it (`DayPoint.debt_outstanding_fen`). Rebuilt from
  `drawn_fen`, the plan's actions and the REPAYMENT events, they reconcile to it exactly; `covenants.line_balances` must not be
  used, because it double-counts an unlanded lot on a line with lead time. Concession headroom must be read from the verdict:
  `MarginalImpact.budget_used_delta_fen` reads ¥4,000 where the verifier counts ¥28,326.92. `posted_cost_delta_fen` excludes the
  package's own discount. `marginal_cost_annual` is a tariff, not a shadow price. "The additional need FLOW could still support"
  is defensible as a router search on labelled copies with the buyer's early-pay source removed: on the Demo, ¥81,000 today,
  ¥14,000 as asked, ¥0 under Option A (¥13.80 of line until 1 Nov), ¥62,000 under Option B. Customer-credit capacity has no
  field and is refused.
- **E Late payment and concentration: detection exists; concentration and the stress are derivable now; history does not exist.**
  Alerts detect an invoice past due and a missed promised early payment; nothing judges a receipt as late when it arrives. Days
  late are computed for open invoices only. **Every fixture holds zero receipts**, and the pilot runbook removes paid invoices from
  the next week's books. AR concentration (golden Foshan 100%; the public SME's largest row, 48.63%, is an aggregate) and the
  30-day receipts share are sums nobody computes yet. The +30-day stress needs no history and no engine change; on the Demo, with
  Foshan's own early-payment facility removed, it leaves a ¥550,000 shortfall with no admissible committed plan. A "typical"
  delay waits for 3 completed invoices.

## Decisions so far

1. **Plan, then build on the owner's go.** The research and synthesis tickets resolve on the tracker and in the scratchpad; no branch, no commit, no repository file until the owner lifts the hold. The build phases (1 to 6) are filed blocked by the synthesis and the owner's decisions.
2. **The strategy MVP is the base, not a rival.** No second envelope, no second scenario primitive, no second cache: the mission's section 25 primitive (current state + candidate action → projected state → economic, liquidity, capacity and mandate result) is tested against `marginal_impact` / `ScenarioState` / `CandidatePackage` first; a new abstraction is justified only when two capabilities demonstrably share it.
3. **Mandate and economics stay separate statements** on every surface; a classification (NORMAL / IMPORTANT / STRATEGIC) is owner-entered and explicit, never a multiplier; no acceptance or churn probability is shown.
5. **Reconcile, keep, develop, lead with one (the owner, 10 October).** The synthesis keeps every idea that makes sense on the repo's evidence, develops every avenue that adds value (not only the five named capabilities: the portfolio and collections links, the shadow cost, the contract-ingestion data source, the adjacent open items), ranks them by added value against cost and risk, and recommends the one avenue to lead with; the build phases follow that ranking.
4. **Research runs on Opus-class agents** (the owner's instruction), read-only against the repository; implementation, when it comes, follows the lead-specifies / implementer-codes rule of the earlier maps.

6. **Research done (10 Oct; #90–#94 resolved on their tickets, outputs in the scratchpad `map-econ/`, nothing committed).** The five reports converge: the mission's own example does not fit the books (the Demo bills Foshan ¥420,000 every 30 days, 13 invoices, ¥5.46M a year; at an assumed 20% margin the ¥28,326.92 request is 2.6% of contribution, not 7.1%; annual EBITDA is ¥1.08M; faces carry 13% VAT; no margin exists anywhere; there is no payment history anywhere, 0 receipts in every fixture, and the pilot runbook removes paid invoices weekly). The concession cap is a hard violation: "financially safe but over a signed cap" means a new signed mandate, so authority has three classes, not two. `ExpectedOrder` is a rebate base, never in the cash projection; removing a buyer's recurring invoices overstates a loss because no cost is linked to a customer. The late-receipt refusal is a strategy-layer guard, not engine work, but the helper that moves a receipt rewrites the copy's terms (fine for a projection, wrong if the copy feeds the verifier or financing). A minimum compensating price already exists as the envelope's zone rows; "20% upfront" is not the partial early payment (no obligation type: engine, deferred); on golden no price rise makes 60 days pass (only ¥240,200 paid early plus 0.40%); the envelope's `top_first` leaves a non-monotone window untested; packages are listed by `passes`, not `approved`. Capacity can be stated now from canonical state with a 0-mismatch reconciliation; `covenants.line_balances` double-counts an unlanded draw (engine ticket, owner's call); the "additional need FLOW could still support" is a search over the router (Demo: ¥81k today, ¥0 after FLOW's own Option A, which uses all but ¥13.80 of the line until 1 Nov; no surface says that today). Validation (no owner interviewed yet): owners know sales by customer and a company-wide gross margin, rarely a margin per customer; they think in gross profit; AR concentration demonstrably changes terms and financing (lenders cap one buyer at about 25 to 35% of a ledger); payment-delay assumptions should be the buyer's own median with the count, never a survey average; the market map's "Atradius China 2025" figures could not be verified. The four "lead with" verdicts (buyer exposure; the deal statement; capacity; late payment and concentration) agree on concentration, stress and capacity first.
7. **The lead's reconciliation (D1–D9 given to the synthesis #95):** lead with BUYER EXPOSURE ON THE DEAL (concentration as separate shares, the +30-day stress with the typical delay only when history allows, capacity before / after with the recovery day and the router search), read-only and flagged, no new data, no engine change; then customer economics as owner-entered context with the envelope's zero-cost additions (authority class, re-check filter, "at today's price"); then the scenario comparator from the same rows; then the envelope's answer to the buyer's ask with the weekly monotonicity scan; then validation. Deferred or killed: the upfront lever, supplier flexibility, probabilities, importance scores, the portfolio optimiser, collections automation, adjusted profitability, a recommendation among packages, the line-balance fix (engine) and any new approval path past a hard cap.

8. **Synthesis done (#95, 10 Oct): the way is clear up to the owner's go.** The specification (deliverables A to L; scratchpad `map-econ/t6-synthesis.md`, to become `docs/CUSTOMER_ECONOMICS_BRIEF.md` when the hold lifts) carries the lead's order: Phase 1 buyer exposure (#96, absorbing #99), Phase 2 customer economics as context plus envelope P1–P3 (#97), Phase 3 the comparator (#100), Phase 4 envelope P4–P6 (#98), Phase 5 validation (#101), plus the small pilot-books ticket (#102); estimates 6 / 4 / 3 / 3 / 3 agent-days (planning). Three shared systems (labelled readings of the books with capacity and the scenario transforms; customer facts with provenance; the existing envelope), the comparator a presentation over them; no new framework. The lead's adjustments: the Demo's 2.6% is stated with its VAT treatment as a labelled assumption; the post-decision stress is computed and pinned in Phase 1; agent cold reads are acceptance inside Phases 1 and 4. The 26 deduplicated owner questions are on #89 with the assumption that holds while each is open. **Nothing starts until the owner lifts the commit hold and answers #89.**

## Notes

Adjacent open items the owner asked to reconcile, not folded into this map's tickets: the owner's grillings #66 (residual-risk policy, the quoted-cost ceiling, business dates, the zh reader, human cold readers) and #59 (the pilot's SMEs, interviewers, three readers) stay open and owner-only; the Postgres run for `decision_facts` and the funding router's cost at hundreds of lots (engine) are environment and engine work outside this map; Chromo369369's contract-ingestion work and haoencheo2025's reskin **were merged into `dev` on 12 Oct 2026** (owner's decision, the commit hold lifted for that merge only; `int/contracts`; ADR-0012; debt on #103, the money-chart branch on #104): Phase 1 builds on that `dev`, its customer-inputs migration becomes 0008, and the contract record is the source for contractual revenue and the termination notice the data matrix named; the small follow-ups recorded on closed tickets (`/nl/opener` Business mode, the zh warning title for a part-paid invoice, receipts for mid-run recurring invoices, a quote for chat draws without a proposal turn) remain where they are.

The standing rules of maps #26, #47, #58 and #65 apply when building starts: the lead specifies, reviews and merges; implementers (sonnet) code; verifiers reproduce figures; INVARIANT 13; plain one-line commits; `git checkout -- services/api/evals` after scenario runs; `rm -f apps/web/AGENTS.md apps/web/CLAUDE.md; git checkout -- apps/web/tsconfig.json` before web commits; never touch port 3000; the engine stability gate holds.

## Tickets

- #89 (grilling) Owner decisions: which capabilities proceed, the inputs you will enter, customer value on the deal card, strategic policy, kill criteria, when the build may start; the 26 questions from the research (owner closes)
- #90 (research) Capability map and data availability matrix (A, B; resolved)
- #91 (research) Customer economics, AR concentration and payment-behaviour spec; the late-payment stress (C, G; resolved)
- #92 (research) The Safe Deal Envelope against the mission (E; resolved)
- #93 (research) Capacity consumption and the scenario comparator (D, F; resolved)
- #94 (research) Validation: what SME owners know and do (section 42, part of L; resolved)
- #95 (task) Synthesis: deliverables A to L in one specification (resolved)
- #96 (task) Phase 1: buyer exposure on the deal: concentration, the +30-day stress, capacity before and after (blocked by #95 resolved, #89)
- #97 (task) Phase 2: customer economics as context, envelope authority classes and package wording (blocked by #96)
- #100 (task) Phase 3: the scenario comparator (blocked by #97)
- #98 (task) Phase 4: envelope P4 to P6: answer the ask, guard monotonicity, fewer packages (blocked by #100)
- #101 (task) Phase 5: validation (blocked by #98)
- #102 (task) Keep paid invoices and their receipt days in the pilot's books (blocked by #89)
- #99 closed: folded into #96
