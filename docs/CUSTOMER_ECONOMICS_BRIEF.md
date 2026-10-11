# Ticket #95 (map #88): synthesis, deliverables A to L in one specification

Drafted 10 October 2026 for the lead, from the five research reports. Repository `/Users/ianpong/Hackathons/smu2sz`, `dev` at
`0cd60cb`, read-only; nothing was written there. Nothing here is committed until the owner lifts the hold of 10 October; when
it lifts, this file becomes `docs/CUSTOMER_ECONOMICS_BRIEF.md` on a research branch (ticket #95's output rule).

**Sources and how they are cited.** Every figure comes from one of the five reports, cited by ticket and by the report's own
line, then by the repository file:line the report gives:

| Cite | Ticket | File (this directory) |
| --- | --- | --- |
| #90 | capability map, data matrix | `r1-capability-map-and-data-matrix.md` (written "r1:NN" below) |
| #91 | customer economics, concentration, payment behaviour, stress | `r2-customer-economics-concentration-payment.md` ("r2:NN") |
| #92 | the envelope against the mission | `r3-envelope-against-the-mission.md` ("r3:NN") |
| #93 | capacity, the additional-need search, the comparator | `r4-capacity-and-scenarios.md` ("r4:NN") |
| #94 | validation (desk research; no owner interviewed) | `r5-validation.md` ("r5:NN") |

A figure marked **[synthesis arithmetic]** is computed here from report figures (the inputs are cited); nothing else is new.
Repository paths are relative to `services/api/app/` unless they start with `services/`, `apps/`, `docs/` or `fixtures/`.
Demo calendar (r4:6-8): day 0 = 1 Oct 2026; day 12 = 13 Oct; day 31 = 1 Nov; day 32 = 2 Nov; day 47 = 17 Nov; day 60 = 30 Nov;
day 61 = 1 Dec; day 62 = 2 Dec; day 120 = 29 Jan 2027.

**The lead's decisions D1 to D9 are carried, not reopened.** Where the evidence strains one of them, it is said where it bites
and gathered in section L.4.

---

## 0. The answer in brief

1. Lead with **buyer exposure on the deal** (D1): one read-only, flagged block on the deal surface and the decision record giving, for the selected decision's buyer, AR concentration as separate shares, a fixed +30-day stress on labelled copies of the books, and capacity before and after across five dimensions with the additional-need search.
2. It needs no new data and no engine change. It reuses `ScenarioState`, `read_books` / `marginal_impact` and the router (#90 r1:399-422; #93 r4:12-31).
3. Demo facts no surface states today. Option A leaves ¥13.80 of the credit line until 1 Nov, and no further payment is coverable without the owner (r4:190, :387-389). Foshan is 100% of open receivables (r2:464). Paid 30 days late, Foshan's books have no admissible committed plan for a ¥550,000 shortfall (r2:446).
4. Phase 2 adds **customer economics as context under the verdict** (D2): about 2.6% of an estimated ¥1,092,000 a year at an assumed 20% (r2:411), never the mission's 7.1%. In the same phase come the envelope's zero-cost P1 to P3, with authority shown in three classes (D7).
5. Phase 3 is the **scenario comparator** (D3): five rows plus a late overlay, all composed from rows Phase 1 already produces (r4:250-258). The customer-loss row removes revenue once and refuses any "net of costs" figure.
6. Phase 4 is **envelope P4 to P6** (D4). P4 answers the buyer's ask; on the Demo that answer is "no price makes 60 days work; ¥240,200 paid early plus 0.40% does" (r3:21-23). P5 adds a weekly monotonicity scan; P6 puts fewer packages on the card.
7. Phase 5 is **validation** (D5): historical cases, property tests, cold readers and a financial review. The behavioural interview questions go to #89 and #59 (r5:194-198).
8. Deferred or killed (D6): the upfront lever, supplier flexibility, probabilities, scores, the portfolio optimiser, collections automation, adjusted profitability, a recommendation among packages, the `line_balances` fix (an engine ticket) and a new approval path over a cap.
9. The ¥5,000 limit is a signed hard cap, not an approval threshold (r1:374-380; `verifier/evaluate.py:94, 190-193`, checked). So the surface says "needs a new signed mandate", and mandate and economics stay two separate sentences.
10. Agent-day estimates for phases 1 to 5: 6, 4, 3, 3, 3 (section K). The six build tickets are re-titled and #99 is merged into Phase 1 (section K.0).

---

## A. Current capability map (from #90, corrected by #92 and #93)

Gap kinds (#90 r1:50-51): **P** the figure exists and nobody shows it; **D** a derivation over existing state; **N** new data.

### A.1 Customer economics: no customer figure exists; a run rate and a floor do

| Exists | Where (as the report cites) |
| --- | --- |
| `Counterparty` holds only `id`, `name`, `role`, `known`; stored with a `payload_json`, but `Contract` is `extra="forbid"`, so a new field is a model change | r1:57-59; `domain/models.py:454-458`, `persistence/tables.py:48-57`, `domain/models.py:32-33` |
| A forward 12-month invoiced run rate per buyer, from the concession window's own issue-day function: golden Foshan ¥5,460,000, 13 invoices | r1:60-63; `financial/concessions.py:95-108` |
| Settled receivables kept; the clock issues recurring invoices as receivables. Invoice history accrues from day 0 only | r1:64-67; `domain/models.py:360-389`, `clock/__init__.py:89-102` |
| `monthly_ebitda_fen`: one company figure. Σ customer contributions ≥ 12 × EBITDA gives a floor on any margin the owner types | r1:68-70; `domain/models.py:492` |
| EX01's forward concessions are exact: ¥28,326.92 | r1:71-74; `fixtures/golden/golden_values.json:31`, `fixtures/offers/offers.yaml:13` (r2:14) |
| `per_buyer_caps_fen`: the per-buyer policy hook, which only tightens | r1:75-76, :252; `domain/models.py:322` |

Missing (r1:87-95): forward revenue (D); trailing 12-month revenue (N: the books start at day 0); ex-VAT revenue (D given a VAT
rate, which is N); margin (N); contribution and the concession share (D once a margin exists); classification (N); a deal-card
line (P). No test touches a customer-level figure (r1:81-83).

### A.2 Scenario comparator: the delta primitive exists; no comparator, no buyer scenarios

Exists:
- `ScenarioState` (`strategy/types.py:26-34`);
- `read_books` / `marginal_impact` (`strategy/impact.py:159-209`), with 21 tests in `tests/strategy/test_impact.py`;
- `scenario_received` / `scenario_inflow` (`impact.py:91-143`);
- the what-if sandbox (`whatif/simulate.py:272`);
- the router's comparison contract (`api/decide.py:536-542`, `funding/router.py:331`);
- the verdict's counters and the decision record (ADR-0011).

All cited at r1:99-111.

Missing (r1:115-121; r4:75-89):
- a table over three or more candidates (D + P);
- a late receipt past the due day. `scenario_received` refuses it by design (`impact.py:108-110`, confirmed on `dev`; pinned in `tests/strategy/test_impact.py` near :209-216). Lifting the refusal is strategy-layer work, not engine work (r1:306-310), contrary to `docs/UX_REMEDIATION_REPORT.md:109`;
- customer loss: derivable for receipts, but no outflow carries a counterparty (r1:119, :299-305);
- any contribution figure (N).

Caveats:
- `read_books` projects with no funding actions, so its "lowest headroom" is cash before funding (r1:123; `impact.py:168`).
- `ExpectedOrder` never reaches the cash projection (r1:281-287; r4:80-84).
- A NO_DEAL means the current terms continue, not that the buyer leaves (r1:125-126).

### A.3 Safe commercial envelope: built, flagged off, richer than the map credits

Built: `strategy/envelope.py`, `GET /buyers/{buyer_id}/envelope?zone=0|1&lang=`, `FEATURE_ENVELOPE` default off
(`config.py:55`, confirmed), the web card `apps/web/components/deals/before-they-ask.tsx`. Tests: 51 in `test_envelope.py`, plus
the oracle, search-economy and backtest suites (r1:130-136). It has:
- per-lever maxima with the boundary's neighbours checked;
- whole-package re-evaluation;
- the minimum compensating price per term (`ZoneRow.min_price_bp`);
- `liquidity_only`, which is section 13's FINANCIALLY FEASIBLE (r1:138-152).

#92's corrections (r3:13-27):
1. Monotonicity is tested only on the bisection path. `top_first` assumes it (`envelope.py:210-211`), and online enumeration is too
   slow (273 cells, 53 s on golden).
2. "20% upfront" is not `early_pay_face_fen`. No deposit obligation type exists (`domain/models.py:79-86`); adding one is engine
   work.
3. On golden, no price rise makes 60 days pass. 60 days needs at least ¥240,200 of the open invoice paid early plus +0.40% [#92
   probe].
4. Authority is three-way. A cap breach is a hard REJECT, and only a new signed mandate moves the cap (r1:321-327;
   `operations/executor.py:500-510`, `mandate/tiers.py:43`).

Also: terms move on a 5-day grid, so "52 days" cannot be said (r1:159; `whatif/params.py:11`). The performance figure is now 6.8
to 8.1 s per weekly read on the public-record SME after `ba79762` and `0cd60cb` (r1:332-334). #93's 17-78 s (r4:204) is the
stale dry-pilot figure (see L.3).

### A.4 Capacity and opportunity cost: every number is in the state; no statement exists, by decision

Exists (r1:167-182):
- facility room today (`funding/menu.py:47-48`);
- lots (ADR-0010);
- the per-day `debt_outstanding_fen` total (`trajectory.py:1055`);
- the concession budget (`alerts/engine.py:631-672`);
- covenant headroom (`alerts/engine.py:373-436`);
- `marginal_cost_annual` (`domain/models.py:677`);
- the price curve.

Map #47 deferred a `Capacity` type on purpose (`docs/STRATEGY_MVP_REPORT.md:28`).

#93's corrections (r4:37-71):
1. No per-facility balance leaves the engine. The one canonical rebuild, `covenants.line_balances`
   (`covenants/clean_down.py:52-66`), counts only DRAW/REPAYMENT, and it **double-counts an unlanded lot on a line with lead
   time**. This was reproduced: ¥100,000 read for a ¥50,000 lot. It cannot bite on today's fixtures.
2. The router draws today for a later need. For accept-as-asked it draws ¥135,040 on day 0 for a day 47-61 gap
   (`funding/search.py:155`).
3. The trajectory's forward-concession series is not the mandate budget. `read_books` sees ¥4,000 for Foshan's request where the
   verifier counts ¥28,326.92 (`impact.py:172, 178`, checked: `budget_used_fen = max(trajectory forward, booked)`). Concession
   headroom must therefore be read from the verdict.
4. "Posted cost" excludes the package's own discount. Accepting reads ¥1,468.05 against today's ¥3,113.93, so
   `posted_cost_delta_fen` is −¥1,645.88 and must never stand alone (`funding/search.py:328-329`).
5. `marginal_cost_annual` is a tariff computed before the plan (≈10.8417%, FAC-IF), not a shadow price (`funding/rates.py:203-212`).

#93 also confirmed what #90 left "to verify". The per-facility path rebuilt from `drawn_fen`, the plan's actions and the
REPAYMENT events reconciles to `debt_outstanding_fen`, with 0 mismatches over 4 Demo cases × 121 days (r4:132).

### A.5 Late payment and concentration: detection and lateness exist; history does not

Exists:
- past-due detection (`alerts/engine.py:560-588`);
- the missed promised early payment (`:589-621`);
- days late of open invoices on Home, the envelope, the worth ranking and the chase handoff;
- `ReceivePayment` with `bank_reference` and `reported_day`, replayed by `reconcile()` into `ReceiptMatch` rows. These rows carry
  no due day and no lateness;
- the conservative trajectory, which counts nothing from an overdue invoice (`financial/trajectory.py:916-917`).

All at r1:193-203.

Missing (r1:209-213):
- AR concentration and 30-day receipts concentration (D);
- revenue concentration (D, PROJECTED);
- contribution concentration (N);
- stress (D: #90's probe ran it with the engine untouched, r1:215-222);
- payment statistics (N). There are **zero receipts in every fixture**, one e2e scenario posts two, and the pilot runbook deletes
  paid invoices from the next week's `state.json` (r1:388-391; `docs/pilot/RUNBOOK.md:236-237`).

### A.6 What the map body got right and wrong, in one line each (replacement text in section N)

- A: right that nothing exists. Wrong that `ExpectedOrder` defines demand (r1:281-287).
- B: right on the pieces. Wrong on customer loss: removing orders changes no cash, and removing recurring invoices removes
  receipts and keeps costs (r1:299-305). Half-right on late payment: the move is written and refused (r1:306-310).
- C: right that it is built. Wrong on the authority classes (r1:321-327), the upfront dimension (r1:328-331) and the cost
  (r1:332-334).
- D: right. Add: per-facility balances are internal, `MarginalImpact.budget_used_delta_fen` is wrong for an unbooked package,
  and `line_balances` double-counts (r4:37-71).
- E: right, but understated. There is no history at all, not too little (r1:355-357).

---

## B. Data availability matrix (from #90, with #91's additions)

Statuses follow mission section 32. Provenance labels follow section 6 and #91's ranking (r2:156-177). "Store" is where the
input lives now, or where it would live (H.4 names the new store).

| Input | Status | Store / fixture | Fixture coverage | Provenance | Notes |
| --- | --- | --- | --- | --- | --- |
| Annual sales per buyer, forward | **DERIVABLE NOW** | `recurring_invoices` × issue days in W = [today, today+H), through `recurring_issue_days` (the concession's own list) | golden ¥5,460,000 (13 invoices); public 4 of 6 buyers | PROJECTED | r1:241; r2:63, :383-390. Omits one-off invoices. A buyer with no recurring invoice reads ¥0. 12 × monthly (¥5,040,000) and 365/30 (¥5,110,000) are refused because they count different invoices (r2:386-390, P5) |
| Annual sales, trailing 12 months | **NEEDS ACCOUNTING IMPORT** (or 12 months of FLOW's own invoices) | `receivables` from day 0 | golden 13 days, public 96 days | INVOICE_HISTORY / ACCOUNTING_HISTORY | r1:242. Used only when the books cover the whole window; never annualised from a short history (r2:63, :188) |
| Annual sales, owner-entered | **NEEDS OWNER INPUT** (optional) | new `customer_inputs` (H.4) | none | OWNER_ENTERED | Shown beside the books' figure when they differ by >10% (r2:143-146). Which wins is M.3 |
| VAT rate (to net invoice faces) | **NEEDS OWNER INPUT** (one firm setting) | new `customer_inputs` (firm row) | public 13% in its sources; golden: no VAT statement on `dev` (grep of `golden_sme.json` finds none) | OWNER_ENTERED | r1:243; r2:35-37, :151-152. #90 reads golden as VAT-inclusive from the unmerged `feat/upgrading` contract (r1:91, :241). See L.3 and M.2 |
| Company gross margin (the D2 default) | **NEEDS OWNER INPUT / ACCOUNTING IMPORT** | nowhere in the books; public SME's 23.76% lives only in `public_sme.SOURCES.md:19, 112` | golden: none | ACCOUNTING_HISTORY (firm-level, so ESTIMATED when applied to one buyer) | r1:244; r2:95, :474-476; r5:27. **D2's default has no source in either fixture's books** (L.4) |
| Margin per buyer | **NEEDS OWNER INPUT** (prototype) / **NEEDS ACCOUNTING IMPORT** (real) | new `customer_inputs` | none | OWNER_ENTERED / ESTIMATED (firm default) | r1:244; r5:24-40. Contract ingestion carries no cost (r1:244) |
| Margin basis (GROSS / CONTRIBUTION) | **NEEDS OWNER INPUT** | new `customer_inputs` | none | OWNER_ENTERED | r2:76, r5:57 |
| Annual contribution / gross profit | **DERIVABLE** once a margin exists | derived | as sales | DERIVED, carrying the weakest input | r2:104-110 |
| Books' EBITDA floor | **AVAILABLE NOW** | `monthly_ebitda_fen` | golden ¥90,000/month → ¥1,080,000; public ¥9,771,555.24 a year | ACCOUNTING_HISTORY (fixture) | r1:42, :68-70 |
| Current AR per buyer | **AVAILABLE NOW** | `receivables.outstanding_fen`, `reconcile().outstanding` | golden ¥420,000; public ¥37.06m | INVOICE_HISTORY (observed) | r1:246 |
| Share of current AR | **DERIVABLE NOW** | sum by `counterparty_id` | golden 100%; public 48.63 / 14.57 / 14.56 / 9.13 / 6.88 / 6.22% | DERIVED (observed) | r1:247; r2:210. Public's largest row is an aggregate (below) |
| Share of next 30 days' receipts | **DERIVABLE NOW** | RECEIPT / EARLY_RECEIPT events of the conservative projection | 120-day projection | PROJECTED | r1:250; r2:211. Golden day 0: none due in [0, 30) (r2:465) |
| Share of annual sales | **DERIVABLE NOW** (forward) when every buyer with invoices has a figure from one source | run rate by buyer, or accounting revenue | golden 100%; public 51.72 / 24.33 / 15.88 / 8.07% | PROJECTED / weakest input | r1:248; r2:212. Public fixture drops ¥11,019,398.60 (10.5%) of the filing's revenue, so its shares are biased (r1:385-387) |
| Share of annual contribution | **NEEDS OWNER INPUT** (every buyer's margin) | | | DERIVED from OWNER_ENTERED | r1:249; r2:213 (future) |
| Aggregate counterparty marker | **NEEDS OWNER INPUT** (or a fixture seed) | new `customer_inputs` flag | public "Other buyers (aggregate)" | OWNER_ENTERED | #91 addition, r2:205-206, :195, M.10. Excluded from per-customer statements, kept in the totals |
| Payment behaviour (days late mean / median / P75 / P90, on-time share, trend) | **NEEDS PAYMENT HISTORY** | `RECEIVE_PAYMENT` log entries replayed as `reconcile` does, joined to the due day in force | **zero receipts in every fixture** | INVOICE_HISTORY + bank feed | r1:251; r2:232-286. History minimums (#91, r2:259-265): **3** completed invoices for average, median and on-time share; **4** for P75; **10** for P90; **12** for a trend; trailing 365 days. Lateness is measured against the terms in force (ADR-0009), not `base_terms_days` |
| Owner's typical-delay estimate | **NEEDS OWNER INPUT** (optional) | new `customer_inputs` | none | OWNER_ENTERED | Used only while fewer than 3 completed invoices exist (r2:277-281) |
| Receipt instrument (cash vs acceptance bill) | **NOT CURRENTLY AVAILABLE** | none | public SME pays suppliers in endorsed bills | — | r5:157, :170 |
| Strategic classification | **NEEDS OWNER INPUT** | new `customer_inputs` (not `Counterparty`, which is `extra="forbid"`) | none | OWNER_ENTERED | r1:252 |
| Commercial history (offers, verdicts, counters, commitments) | **DERIVABLE NOW**, short | `offers`, `verdicts`, `commitments`, `decision_facts` | from day 0 | DERIVED | r1:253. `SentFact.outcome` / `buyer_profile` are simulated (`decisions/facts.py:72-74`): never acceptance or churn evidence |
| Facility headroom today | **AVAILABLE NOW** | `menu_row.available_fen` | | DERIVED | r1:254. Uncommitted facilities count as zero |
| Facility headroom by day, before and after, recovery day | **DERIVABLE NOW** | rebuilt per facility from `drawn_fen` + plan actions − REPAYMENT events | 120 d | PROJECTED | r1:255; r4:132 (reconciled, 0 mismatches). **Not** through `line_balances` (r4:39-47) |
| Invoice-finance headroom by day | **DERIVABLE NOW** | eligible receivables × advance rate − advances | 120 d | PROJECTED | r4:133. TODAY and AS-ISSUED readings |
| Concession headroom | **AVAILABLE NOW** | cap − the verdict's `forward_concession_total_fen` (after); cap − booked `ForwardConcession` (before) | 365-d window | DERIVED | r4:134. #90 lists `MarginalImpact.budget_used_delta_fen` as a source (r1:256); #93 shows that is wrong for an unbooked package (r4:53-60). **Trust #93** (L.3) |
| Covenant headroom (DSCR, leverage, clean-down) in money | **DERIVABLE NOW** | `covenant_limits` + `Trajectory.months` | 4 months | PROJECTED | r1:257; r4:135 |
| Customer-credit capacity | **NOT CURRENTLY AVAILABLE** | no credit limit anywhere | | | r4:136: refused until the owner enters a per-buyer credit limit |
| Single-debtor cap on an invoice-finance facility | **NEEDS OWNER INPUT** (facility letter) | facility terms | fixture: 80% advance, no cap | | r5:130 |
| Expected demand | **AVAILABLE NOW as a rebate base only** | `expected_orders` | one, not firm | OWNER_ENTERED (fixture) | r1:258, :281-287 |
| Receipt history | **AVAILABLE NOW from day 0, empty in fixtures** | hash chain, `reconcile()` | 0 receipts | bank feed (observed) | r1:260. The pilot's ingestion is `pilot_dry_run.py --receipts` |
| Contract terms (price, cadence, payment basis, notice) | **on `feat/upgrading`, not `dev`** | `ContractRecord` | 3 demo documents | OWNER_CONFIRMED | r1:261. It gives customer loss a grounded earliest stop date (90 days' notice, cl. 2.2) and cross-checks revenue; it gives no margin and no behaviour |
| `fixtures/counterparties/buyers.yaml` | **NOT A SOURCE** | hidden state, INVARIANT 7 | | | r1:262; it is the buyer's economics anyway |

---

## C. Customer economics spec (from #91 and #94; Phase 2)

### C.1 What it is and what it never does

It is owner-entered context placed under the verdict. It **never changes a verdict, tier, code, counter, cap or plan**: property
P8 (r2:352). Mandate and economics are two sentences (D7). The words "profit", "profitable" and "worth" are never used of
either figure (r2:89; r5:58).

### C.2 Metrics

**Annual sales.** Pick the best available, in this order (r2:63-69):
1. trailing 12 months observed, only when the books cover the window;
2. accounting or ERP;
3. owner-entered;
4. otherwise PROJECTED over W = [today, today + H), counting the same invoices the concession counts.

Rules:
- Expected orders are named apart: they are not firm.
- Integer fen, with a `vat_inclusive` flag.
- The horizon is always printed beside the figure.
- Refused: annualising a short history; an undated projection; mixing VAT-inclusive sales with ex-VAT margins silently;
  `buyers.yaml` as a source.

**VAT is excluded from faces (D2).** When a VAT rate is set and sales are invoice-derived, they are divided by (1 + VAT) inside
the one exact expression, then posted once (r2:104, :151-152). When no VAT rate is set, the figure is labelled "as invoiced (VAT
status not set)". FLOW never assumes a rate. This is a synthesis rule that follows #90's matrix status (NEEDS OWNER INPUT, r1:243).

**Margin.** Integer bp, signed, from −10,000 to 10,000 (r2:93). The default follows D2 and #94 (r5:35, :56): the
**company-wide gross margin, labelled ESTIMATED ("company average")**, prefilled and editable; once edited it becomes
OWNER_ENTERED.

Two disagreements are settled here:
- **Basis.** #91 recommends naming the measure *contribution* (r2:73-88). #94 recommends *gross profit* (毛利) as the default word,
  because that is the line statutory accounts and banks show (r5:46-58). Rule: store `margin_basis: GROSS | CONTRIBUTION`, and let
  the printed word follow the basis ("gross profit" / 毛利; "contribution" / 边际贡献). The default basis is GROSS (D2). Never
  relabel one as the other (r5:57). Say once which way gross errs: it is conservative for the concession share (the share comes
  out larger) and non-conservative for customer loss (the loss comes out smaller) (r2:84-88).
- **When the firm average applies.** #91 would apply it only after a click (r2:193); D2 and #94 prefill it. D2 governs. The label
  ESTIMATED and "not Foshan's own margin" travel with it.

**Where the default comes from.** Neither fixture's books hold a company gross margin. The public SME's 23.76% is in
`public_sme.SOURCES.md` only (r1:244). So the default needs a firm-level `customer_inputs` row: OWNER_ENTERED, or imported as
ACCOUNTING_HISTORY. On the Demo it is seeded as **20%, ESTIMATED, "Demo assumption"**. Demo seeds are never OWNER_ENTERED
(r2:174).

**Contribution / gross profit** (r2:104). `post(sales × margin_bp / 10,000)`: one exact product, posted once half-up. It is
negative when the margin is negative, and DERIVED with the weakest input's label.

**Concession share** (r2:116-121):
- `share = C / K_H`, an exact Fraction.
- C is the verdict's own `forward_concession_total_fen`, never recomputed (P4).
- K_H is the gross profit over the same window W. With projected sales, use the very invoices in W. Otherwise use
  sales × margin × H/365 exactly.
- Defined only when K_H > 0.
- The API carries `concession_share_bp`, the headline at 1 dp ("2.6%") and the evidence at 2 dp ("2.59%").
- "under 0.1%" and "more than 10 times" are the bounds.
- Shown only after the verdict, and only on a package with a C: the request, a class-3 envelope package, a counter.

**Consistency checks**, shown as sentences (r2:143-152, D2):
1. Books versus owner sales, beyond 10%: both are shown.
2. **The EBITDA floor**: when the buyer holds every invoice in the books and its gross profit is below 12 × EBITDA, FLOW names the
   contradiction.
3. VAT: "Sales include VAT; the margin does not."

**Sensitivity line** (evidence layer only, #94 r5:37). One alternative margin, never a slider on level 1. On a buyer that holds
every invoice, it is replaced by the floor: "your books imply a margin of at least 19.8%" (r2:421-422).

**Working-capital-adjusted profitability** (mission §5) is **deferred** (D6; r2:129-139; r5:38-40). The MVP lists only the
committed concessions already booked to the buyer, as their own line, never netted. On the Demo that is ¥0
(`forward_concessions` is empty, r2:431).

### C.3 Provenance (r2:156-177)

Rank: ACCOUNTING_HISTORY = ERP > INVOICE_HISTORY > OWNER_ENTERED > PROJECTED > ESTIMATED.
- A DERIVED figure carries `inputs` and `weakest`, and its tense follows the weakest input.
- If the weakest input is not observed, the sentence contains "estimate", "about", "you entered" or "scheduled", and never an
  observed-tense verb (P2).
- Stored with every figure: `provenance`, `source_ref`, `as_of_day`, `window`, `entered_by` and `entered_day`.
- The en and zh wording per label is in #91's table (r2:156-164).

### C.4 Edge cases (mission §36): FLOW shows / refuses

#91's twelve cases (r2:185-196) are adopted verbatim as the test table (J). They cover:
- negative and zero margin: no share, the cost alone;
- a new customer: ask for inputs;
- three months of history: never ×4;
- seasonal;
- large revenue with tiny contribution;
- good contribution but a terrible payer: two separate facts;
- multiple currencies: no FX;
- a missing margin: the cost alone, or the firm average offered;
- estimated versus observed sales disagreeing;
- an aggregate counterparty: excluded;
- a share above 100%: a sentence, not "141.6%".

### C.5 Strategic classification

NORMAL / IMPORTANT / STRATEGIC, owner-entered, **context only**. It never multiplies anything (mission §22). It only changes a
wording ("Foshan is marked Strategic") until the owner signs a mandate rule (grilling #89 Q4).

---

## D. Scenario comparator spec (from #93, with #90's customer-loss corrections; Phase 3)

### D.1 The scenario set: the mission's seven collapse to five rows plus one overlay (r4:250-258)

| Row | Produced by | Assumption sentence |
| --- | --- | --- |
| Current books ("buyer rejects the counter and keeps buying") | the `Books`; no copy | "Your books as they stand: Foshan keeps buying on today's terms." |
| Accept as asked | the verdict's `VerdictBundle` | "If you accept Foshan's request as asked." |
| Counter k ("buyer accepts counter k") | the verdict's `CounterProposal.obligations`, as the counter re-check evaluates them. An envelope package may be an extra "alternative counter" row | "If Foshan accepts Option A." |
| Customer loss ("buyer rejects and walks") | a `ScenarioState` that ends the buyer's `RecurringInvoice` rows and removes its `ExpectedOrder` rows. Issued receivables **stay** (they are owed). Booked concessions stay until released | "Scenario assumes Foshan stops buying from you after today; the ¥420,000 already invoiced (RCV-A, due 2 Nov) is still paid. This is not a prediction." |
| Late receipt (an overlay on any row) | Phase 1's `scenario_paid_late` transform (G.3), never a second mechanism | G.3's sentence |

### D.2 Fields per row (r4:264-274)

- `outcome`, `required_tier`, `codes`: packages only, from the same verdict call.
- `concession_forward_fen`: the verdict's figure, never added to funding cost.
- `immediate_discount_fen`.
- `funding_cost_fen`: the router's SELECTED plan, named as such. The verdict's cure is a different plan (¥2,406.67 against
  ¥1,468.05 for accept-as-asked).
- `need_fen`, `lowest_cash_fen` / day, `first_breach_day`.
- `plan_flags`.
- `capacity`: the Phase 1 block.
- `contribution_context`: Phase 2, labelled.
- `marginal_impact(current, row)`.

### D.3 Customer loss: #90's corrections are binding (r1:299-305; r4:286-292)

- Removing expected orders changes no cash. Removing recurring invoices removes receipts and **keeps every cost**, because no
  outflow carries a counterparty.
- The row therefore shows three things, each once:
  - **billings removed** (DERIVED);
  - **receipts removed within the 120-day horizon** (DERIVED from the unfunded projection);
  - **gross profit foregone** (ESTIMATED when the margin is).
- It refuses any cash figure "net of avoided costs". It must say "costs that would also stop are not modelled; the economic
  loss is the gross-profit figure, not the cash figure".
- The cash view states its 120-day horizon beside any annual figure (r1:121, :426).
- The contract's 90-day notice is a grounded earliest stop date once contract ingestion is merged (r1:304-305). It is not on
  `dev`.

### D.4 What is refused

- Any probability, or any expected value weighting the rows.
- "If you counter, Foshan walks".
- Summing concession and funding cost.
- Adding capacity across rows (the portfolio must re-run them jointly through `evaluate_many`).
- "Future order cannot be funded" without a defined order.
- A late overlay on a financed invoice.

All at r4:286-296.

### D.5 The Demo rows (from #93's worked table, r4:362-376)

| | Current books | Accept as asked | Option A | Option B | Customer loss |
| --- | --- | --- | --- | --- | --- |
| Verdict | — | REJECT (AGG, RESERVE_BREACH day 47, DISCOUNT_ABOVE_BREAK_EVEN, EARLY_PAY_DEARER_THAN_PLAN) | passes its re-check; Tier 1 (r3:101) | passes its re-check | — |
| Forward concession (budget ¥5,000) | ¥0 | ¥28,326.92 | ¥0 | ¥0 added | — |
| Immediate discount | ¥0 | ¥5,040 | ¥2,186.20 | ¥0 | — |
| Funding cost (router) | ¥3,113.93 | ¥1,468.05 | ¥841.57 | ¥3,706.46 | no admissible plan |
| Lowest cash unfunded | −¥105,000 (31 Oct) | ¥164,960 (30 Nov) | ¥150,013.80 (31 Oct) | −¥105,000 | −¥105,000; below the floor on 94 days |
| Additional need supportable (S1, R-TODAY) | ¥81,000 | ¥14,000 | ¥0 | ¥62,000 | none |
| Receipts within 120 days | ¥1,680,000 | | | | ¥420,000; ¥1,260,000 removed once |

Contribution context for customer loss (r4:394-399; r2:396):
- billings foregone ¥5,460,000 a year (DERIVED);
- gross profit foregone about ¥1,092,000 (ESTIMATED: 20%, a Demo assumption);
- receipts removed ¥1,260,000.

---

## E. Safe envelope spec (from #92: three classes, P1 to P6, sentences)

### E.1 Three classes of authority on every package and scenario, never two (D7; r3:96-114)

| Class | Derivation (no new computation) | Demo instance |
| --- | --- | --- |
| 1 `flow_may`: FLOW may act alone | Tier 1, `outcome == ACCEPT`, `approved`, no flags. In practice an early payment on a named invoice (`verifier/evaluate.py:731-738`) | 45 days + 0.85% on ¥257,200 (Option A), the one Tier-1 package of 11 (r3:101) |
| 2 `needs_owner`: safe within the signed limits, needs the owner | `approved` and (Tier 2 or `cure_needs_owner`) | the other ten default packages, e.g. 55 days + 0.30% |
| 3 `over_your_limits`: financially safe, over a signed cap | `liquidity_only and not passes` | 55 days at today's price: REJECT for AGG at ¥16,217.95, a curable day-47 cure of ¥1,570.36 (r3:107-109) |

Class 3 is not an approval. The owner cannot approve it in the flow; only a newly signed mandate moves the cap (r3:109-110;
`nl/offers.py:578`, `alerts/engine.py:522`). #94's two labels ("Safe and within your limits / Safe, needs your approval", r5:84)
cover only classes 1 and 2. D7 and #90/#92 govern.

### E.2 Additions

| Id | What | Evals | Phase |
| --- | --- | --- | --- |
| P1 | `authority` field per package. The `terms_budget_ignored` maximum is listed as one class-3 package in its own group, with the cap it breaks and by how much. This is where the economics attach | 0 | 2 |
| P2 | Display and the zone's smallest price filtered by `approved`, not `passes` (`envelope.py:651, 667, 671`), with failures kept only in `full_grid`. A test on books where a cure cannot land in time. Fix the covenant wall label: `wall_of(..., ignore_caps=True)` names any unknown code "the cap for this buyer" (`envelope.py:551-552`) | 0 | 2 |
| P3 | "At today's price: up to 45 days within your limits", and name packages, not maxima. Drop the rebate maximum from the joined sentence unless its package is the one quoted | 0 | 2 |
| P4 | `compensate(T)` for the buyer's asked terms: (1) the smallest *approved* price at T, with the rule price beside it; (2) if none, the smallest early payment of the open invoice (face searched at 5 bp, where it is monotone), then the smallest price with it, then the largest rate at that face by `descend`. Each result is `v.probe`d whole and re-checked; on demand, cached apart like the zone | 2 to 7 (price only); about 25 to 30 with the fallback. Golden about 2 s; public 6 to 12 s | 4 |
| P5 | Replace `top_first`'s untested middle with one probe and the neighbour rule (+1 to +3 evals per terms lever). Add the exhaustive terms × price scan, plus the face column for any ask, to the pilot's weekly run, failing loudly on disagreement | +3 to 9 online; 55 to 110 s per buyer weekly | 4 |
| P6 | Fewer packages on the card: the verifier's counters and the ask's answer first, the rest behind disclosure. Golden shows 11 today (r3:140) | 0 | 4 |

Sources: r3:243-271 (costs r3:226-237).

The non-monotone finding binds P4's design. At 60 d + 0.40% + 0.85%, the face passes only from ¥244,000 to ¥286,000 (below:
RESERVE_BREACH; above: EARLY_PAY_DEARER_THAN_PLAN). A `first_true` at 0.85% would answer "none" (r3:161-165). Search the face only
at the smallest rate.

### E.3 Sentences (#92 r3:280-298, house style, existing zh terms)

- **Class 2.**
  - EN: "55-day terms with a 0.30% price rise: within your limits and your cash floor holds, but FLOW cannot agree longer terms on its own. It needs your approval."
  - ZH: "55 天账期并加价 0.30%：在您的底线内，现金底线也守得住，但 FLOW 不能自行同意延长账期，需要您批准。"
- **Class 3.**
  - EN: "55-day terms at today's price: your cash floor holds, but it uses ¥16,217.95 of your ¥5,000.00 budget for what you give buyers. FLOW will not send it under the limits you signed; only you can decide, and raising the limit means signing a new mandate."
  - ZH: "按现价给 55 天账期：现金底线守得住，但会占用您给买家让利预算中的 ¥16,217.95（预算为 ¥5,000.00）。在您签署的授权范围内，FLOW 不会发送此方案；只有您能决定，提高上限需要签署新的授权。"
- **Class 3 plus economics** (Phase 2; [synthesis arithmetic]: ¥16,217.95 / ¥1,092,000 = 1.49%):
  - EN: "That is about 1.5% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit."
  - ZH: "约相当于我们估计佛山订单每年为您带来的 ¥1,092,000 毛利的 1.5%。"
- **P4, no price works** (golden, 60 days):
  - EN: "No price rise makes 60 days work: the longer terms leave your cash short in 47 days. 60 days works only if ¥240,200 of the open ¥420,000.00 invoice is paid now and the price rises 0.40%; that needs your approval."
  - ZH: "任何加价都无法让 60 天账期可行：账期延长会让您的现金在 47 天后不足。只有在 ¥420,000.00 的未结发票中先支付 ¥240,200，并加价 0.40% 时，60 天才可行；这需要您批准。"
- **P4, price works:**
  - EN: "55 days works if the price rises at least 0.25%; at 0.30% the price rise pays for the longer terms in full. Either needs your approval."
  - ZH: "价格至少上调 0.25%，即可接受 55 天账期；上调 0.30% 时，加价可完全抵消延长账期的成本。两者都需要您批准。"
- **Refused (D6, r3:270-271; r3:61-62):**
  - the mission's "60 days with 20% upfront": false on these books and not representable;
  - "Recommended: option A" among packages: it reverses the MVP's wording rule (`docs/STRATEGY_MVP_BRIEF.md:155, 187-188, 431-435`).
  The verifier's own counter remains the recommended response; that is the existing verdict, not an envelope ranking.

The zh twins go through `t(lang, en, zh)` and are pinned like `test_envelope.py:63-65, 304-340`. #92 notes an existing
inconsistency, 让步 (`_WALL_TEXT`) against 让利 (`_WALL_WORDS`), for the native reader (#66; r3:304-306).

---

## F. Capacity / opportunity-cost spec (from #93; Phase 1)

### F.1 Common semantics (r4:108-125)

- **Books.** BEFORE is the current `Books`. AFTER is the books plus the package's bound obligations, or a counter's obligations
  (the `MarginalImpact` semantics).
- **Series.** Two `project(..., CONSERVATIVE, horizon, min_cash)` runs:
  - U: unfunded;
  - F: with the actions of the COMMITTED router plan.
- **Statement.** One sentence per maximal run of days where before ≠ after: "from ‹first› to ‹last› ‹dimension› falls from h_b to
  h_a".
- **Recovery day.** The first day after the run on which h_after ≥ h_before. It is labelled "assumed" when it rests on a
  discretionary repayment (ADR-0010 §5). If there is none: "not within the 120-day horizon (to 29 Jan 2027)".
- **Need window** ([U.first_breach, last day below the floor]), always shown beside a plan-based series, because the router draws
  today for later needs (r4:50-52).
- Integer fen. The server writes every string.

### F.2 The five dimensions, plus one refused (r4:129-136)

| Dimension | Formula | Reconciliation test |
| --- | --- | --- |
| Cash buffer above the floor | `closing_fen − min_cash_fen`, on U (on F it is 0 whenever a plan is needed) | min over U = `Reading.lowest_headroom_fen` = Home's `cash.lowest_headroom_fen` (`api/home.py:1123`) |
| Credit-line headroom per facility | `limit − bal_f(d)`, where bal_f = `drawn_fen` + plan actions on f (counted from `FundingAction.day`, as the executor counts lots) − \|REPAYMENT\| events with `ref == f.id`. **Not `line_balances`** | Σ bal_f + debt principal = `DayPoint.debt_outstanding_fen` every day; peak ≤ limit; with no plan, today's figure = Home's `available` (`home.py:1095`) |
| Invoice-finance headroom per facility | min(limit − bal_f, Σ eligible open receivables × advance rate − advances). Eligible: confirmed, not FINANCED, not under a live early-payment agreement, not yet due. Two readings: TODAY, and AS-ISSUED (labelled) | TODAY = Σ `FINANCE_INVOICE` candidates of `alerts.engine._candidates` − the plan's advances. Demo: ¥336,000 − ¥255,000 = ¥81,000 |
| Concession headroom | before: cap − Σ booked FC; after: cap − the verdict's `forward_concession_total_fen`; per buyer likewise. A point value over the 365-day window | = the what-if's `forward.headroom_fen` (`whatif/simulate.py:203`) and the counter builder's headroom; AGG fires iff after < 0 |
| Covenant headroom in money | DSCR room_m = ⌊EBITDA_m × 10000 / DSCR_min⌋ − debt service_m; leverage room_m = ⌊LEV_max × 12 × EBITDA_m / 10000⌋ − total debt_m; clean-down from the corrected line balance | room ≥ 0 iff no DSCR/LEVERAGE breach and no critical `COVENANT_HEADROOM_LOW` |
| Customer-credit capacity | **Refused**: no credit limit exists. Exposure is a concentration fact (G), not a capacity | — |

Edge rules (r4:141-151):
- uncommitted, REFERENCE_ONLY and Tier-3 sources count as 0;
- `allow_new_borrowing = false` makes every borrowing headroom 0, with the reason stated;
- EBITDA ≤ 0 leaves leverage undefined;
- **a negative headroom is shown as "over by", never clamped**;
- an unlanded lot is counted from its request day.

Single-debtor concentration caps on invoice finance (#94 r5:130) would become a capacity input if a facility carries one. None
does in the fixtures.

### F.3 The additional working-capital need FLOW could still support (r4:162-215)

**Definition.** X\*(shape, criterion) is the largest X on a ¥1,000 grid for which the router, run on a labelled copy (the books
+ the package's obligations + a hypothetical need X), returns a plan that is `admissible`, not `needs_owner_approval`, and
`executable_now` (R-TODAY, the headline). R-AS-ISSUED is labelled as an assumption.

- **Shape S1** (the default): "a one-off payment of X today that does not come back within the horizon". The shape and criterion
  sentence is always printed.
- **The `BUYER_EARLY_PAY` facility is removed from the copy.** Otherwise the cheapest plan can be an early payment that needs the
  buyer (r4:177-180).
- Reported with it: the plan at X\*, the plan at X\* + ¥1,000, and the binding reason (already worded by the router,
  `router.py:136-143`).
- **Search rule.** Bisection, with both neighbours of the boundary re-checked and a full coarse scan on disagreement (the
  envelope's rule). Monotonicity is not assumed: whole-period billing steps the effective rate (r4:198-201).
- **Why a search and not a sum.** Under Option B the per-dimension headrooms add to ¥81,000; the search says ¥62,000, because
  repayment timing and the reserve interact (r4:193-196).
- **Cost.** 0.2 to 2.5 s per search on golden, about 10 to 20 router runs (r4:203). On the public SME, at #92's 0.2 to 0.4 s per
  verifier eval (r3:222), roughly 2 to 8 s **[synthesis inference; to measure in Phase 1]**. It runs on request behind the
  strategy cache's single-flight, never on page load.
- **Refused.** A figure without its shape; "you could fund another order" unless a defined order is the need; any X\* when today's
  books already have no admissible plan ("none: today's books already need the owner or a new facility").

**Demo** (r4:186-191):

| Books | X\* (S1, R-TODAY) | Binding |
| --- | --- | --- |
| Current | ¥81,000 | the IF advance-rate cap on RCV-A. The next yuan is an advance on RI:BUYER-1:2 at 15.49% effective, above the 15% ceiling, so it needs the owner |
| Accept as asked | ¥14,000 | the line: ¥14,960 of room from day 0 to day 61 |
| Option A | **¥0** | line room ¥13.80 to day 31; the part-early-paid RCV-A is wholly ineligible (`docs/FINANCIAL_SEMANTICS.md:30`) |
| Option B | ¥62,000 | the line in the second gap, 17 to 26 Nov |

### F.4 Shadow cost: no surface now (r4:217-246)

`marginal_cost_annual` is a tariff, and it is already inside the concession cost: the extension priced as a loan, ¥24,326.92.
One derived sentence only, from the search's binding leg: "The next yuan would come from ‹source› at ‹effective rate›, and needs
‹the owner / the buyer›". The staircase stays a research note for portfolio work: line 6.4% → IF 10.84% → a later-invoice advance
at 15.49% (owner) or the buyer's early payment at 14.78% (buyer). Joint feasibility belongs to `evaluate_many` / `reserve.py`,
which already shrink later deals' room.

---

## G. Late-payment / concentration spec (from #91, #93, #94)

### G.1 Concentration: separate shares, never a score (r2:200-226; r5:129)

| Share | Definition | Phase |
| --- | --- | --- |
| Current AR | Σ outstanding of the buyer's OPEN or FINANCED receivables ÷ the same over all buyers. Overdue counts; unissued does not | 1 |
| Next 30 days' receipts | the buyer's RECEIPT / EARLY_RECEIPT events on [today, today+30) of the conservative projection ÷ all. Overdue invoices are absent | 1 |
| Annual sales | only when every buyer with invoices has a figure from one source and window; otherwise "not shown", with a sentence | 2 |
| Annual gross profit | needs every buyer's margin | future |

Rules:
- Exact Fractions, displayed at 1 dp; "100%" only when the share is exactly 1. Parts are never adjusted to sum to 100.
- Aggregates are excluded from per-customer statements and kept in totals.
- Concentration may only add a fact line, order which buyer's stress appears first, and raise an existing alert's wording. It
  never changes outcome, tier, codes, counters, caps or plan (P8; mission §18).

### G.2 Payment behaviour (r2:228-286; Phase 1 module, shown only above the minimums)

- **Replay.** Only EXECUTED `RECEIVE_PAYMENT` entries, through `reconcile`'s replay (no second matcher). The receipt day is
  `reported_day`, else the entry day. The due day is the one in force.
- **Unit.** A completed invoice. `L_i` is the face-weighted signed lateness. Agreed early-payment portions are excluded and
  counted apart. Open overdue invoices are listed as "at least N days" (censored).
- **Statistics.** Average of max(0, L_i); median / P75 / P90 by nearest rank; on-time share with counts; maximum recent delay;
  trend. Minimums are 3 / 4 / 10 / 12 over 365 days. A survivorship warning applies when an open invoice is later than P75.
- **Below the minimum, the sentence:** "FLOW has 1 completed payment from Foshan in the last 12 months, too few to say how Foshan
  usually pays. The stress test uses your contractual dates and a 30-day delay."
- **Observed outranks owner-entered.** An owner estimate is used only below 3 completed invoices, and is shown beside the observed
  median only when they differ by ≥ 5 days.
- **Median, not mean** (#94 r5:166). Macro figures (NBS 72 to 76 days, Coface 65 days) never enter a projection; at most they
  appear as labelled context (r5:169).

### G.3 Late-payment stress: the two variants reconciled

The reports built two different stresses:

| | #90 / #91: buyer-wide | #93: one receivable (the comparator's overlay) |
| --- | --- | --- |
| What moves | every open, not-yet-due invoice of the buyer, and every recurring invoice issued in the horizon, by the same D (r2:327) | one receivable (RCV-A) (r4:258) |
| Mechanism | moves `terms_days` on the copy, as `_received_on` does (r1:215-216; r2:25-29) | removes the receivable and adds one confirmed `CashFlow` of its outstanding on the late day (r4:258) |
| Financing of the moved invoice | **optimistic**: financeable up to the stressed day. #91 flags this itself and asks for an engine affordance (r2:326, Q6) | **conservative**: not financeable on the copy, understating capacity by at most advance rate × outstanding (r4:258) |
| The buyer's own early-pay facility | removed (#91 r2:324; with it kept the result is "wrong", r2:445) | **kept**: the ¥4,727.85 plan uses "the buyer's early payment on RI:BUYER-1:2" (r4:367), contrary to #93's own X\* rule (r4:177) |
| Live early-pay agreement on a moved invoice | treated as lapsed; the whole outstanding moves (r2:323) | refused (r4:258) |
| Demo figures | −¥250,000 on day 60 (30 Nov) before funding; 65 breach days (20 contractual); need ¥550,000; **no admissible committed plan** (r2:441-446). #90's probe matches with the facility kept: need ¥405,000 → ¥550,000, cost ¥3,113.93 → ¥6,488.98, +45 breach days, not executable today (r1:220) | lowest −¥105,000; below the floor on days 12 to 61; ¥4,727.85; cannot run today (r4:367-368) |

**The headline is the buyer-wide fixed +30-day stress, with the buyer's own early-payment facility removed.** Its Demo figures are
#91's. Four reasons:
1. D1(b) asks for a fixed +30 always.
2. Concentration is a buyer fact, and the owner's question is "if this buyer pays late", not "if this one invoice does" (mission
   §19; r5:168).
3. #93's overlay keeps the buyer's early payment in its plan, which D1(b) and both reports' own rules forbid. **Its ¥4,727.85
   must not be shown.**
4. The buyer-wide stress is the one that shows the Demo's real exposure: no committed plan covers it.

**The mechanism is #93's, not #90's/#91's.** Each moved receipt becomes one confirmed `CashFlow` (counterparty = the buyer) on its
due day in force + D, with no engine change. Three consequences:
- The unfunded figures (lowest cash, breach days, need) depend only on receipt days, so #91's −¥250,000 / 65 days / ¥550,000
  stand.
- With fewer financing sources on the copy, "no admissible committed plan" should hold a fortiori **[synthesis inference]**. Phase 1
  pins it with a test before the sentence ships.
- #91's engine affordance (Q6: a receipt day separate from the due day, plus recourse) is not needed. It goes to the owner as
  declined-for-now (M.7).

Rules for the transform `scenario_paid_late(state, buyer_id, days)`, new and separately named in `strategy/impact.py`.
`scenario_received`'s refusal and its test stay (r1:424-425).
- **Exactly once.** Only the outstanding moves; the settled part stays. Each moved invoice has exactly one receipt in each copy,
  of equal amount, with day + D. A receipt pushed past the horizon is named ("¥420,000 … moves past the 120-day horizon")
  (r2:306-315).
- **Overdue invoices** are not moved and not re-added; the conservative projection already counts nothing from them (r2:322;
  INVARIANT 11).
- **Live early-pay agreement on a moved invoice:** lapsed on the copy, the whole outstanding moves, no discount (#91's rule
  r2:323, preferred to #93's refusal r4:258). The Demo's day-34 path has RCV-A under an agreement, and a refusal would leave the
  Demo without a stress.
- **The buyer's own facility** (lender = the buyer) is removed from the copy (r2:324; P12).
- **Financed invoices:** MVP fallback, not moved, and said ("RCV-B is financed; its delay is not modelled"). The two reports agree
  (r2:325; r4:258).
- **Recurring invoices:** each issue in the horizon becomes one dated `CashFlow` at issue + terms in force + D. The copy says
  "assumes the platform does not finance these invoices; this understates what could be financed by at most ‹advance rate ×
  outstanding›" (r4:258).
- **Combined with a decision.** The package is applied first, as the verifier binds it (terms in force after acceptance, ADR-0009),
  then the delay (r2:328). D = 0 must reproduce the decision's own unfunded projection exactly (P10). **No report computed an
  after-decision stress figure**, so the Demo sentence (I.3) uses the current books. The after-decision figure is computed and
  verified in Phase 1, not quoted here (L.4).
- **"Typical"** is built only when the minimums are met. A median of 0 means "usually pays on time", and no row is built. The
  stressed delay is the observed P90 when ≥ 10 invoices exist and it exceeds 30 (r2:303-304).
- **Non-payment** is explored, not MVP (r2:329).

**What the lowest-cash figure hides** (r2:453-454): on the Demo the trough is the day-12 payroll, before any Foshan receipt. The
informative figures are breach days, the plan's need and cost, and the owner flag. The sentence leads with those.

---

## H. Shared architecture

### H.1 The primitive (D8)

Mission section 25's "current state + candidate action → projected state → economic, liquidity, capacity, mandate result" already
exists. It is **`ScenarioState` + `read_books` / `marginal_impact` + the router**, with the verifier for packages. No new
framework. Each product is a search or a composition over it:

| Product | Over the primitive |
| --- | --- |
| Deal verifier | one candidate (exists) |
| Exposure (Phase 1) | three transforms of the books (paid late; + package; + hypothetical need X), each read once. X\* is a router search |
| Envelope (exists; P1 to P6) | boundary search with the verifier |
| Comparator (Phase 3) | composition of rows exposure and the verdict already produce |
| Collections (exists) | `receivables_worth` ranks by `marginal_impact` and gains the capacity delta for free (r4:311-314) |
| Portfolio (future) | rows keep their *inputs* (obligations), and combinations re-run through `evaluate_many` (r4:300-309) |

### H.2 Four shared systems, or fewer: three, plus one composition

1. **Labelled readings of the books** (`strategy/impact.py`, `strategy/capacity.py`): `Reading` extended with capacity, the
   transforms `scenario_paid_late`, `scenario_customer_loss`, `scenario_need`, and the X\* search. This *is* the mission's
   "capacity / opportunity-cost engine" and the scenario substrate.
2. **Customer facts** (`strategy/customer.py`, `strategy/payments.py`, the `customer_inputs` store): economics, concentration,
   payment behaviour, provenance.
3. **The envelope** (`strategy/envelope.py`, existing).

The **comparator is not a system**. It is a presentation over 1, 2 and the verdict (`strategy/comparator.py`, no new
computation).

### H.3 The candidate types: justified, extended, refused

| Mission type | Decision | Why (reuse proven by two or more phases) |
| --- | --- | --- |
| CapacitySnapshot | **Justified, as a field of the existing `Reading`** (`impact.py:146-156`): `Reading.capacity: CapacitySnapshot \| None`, holding per-facility day series, IF readings, concession and covenant rooms | Phases 1 and 3, collections; #93's own recommendation (r4:155-160) |
| CapacityImpact | **Refused as a type**. It becomes optional fields on `MarginalImpact` (`strategy/types.py:69-93`) plus a small value type `CapacityWindow` (dimension, from, to, before, after, recovery day, assumed) | two snapshots subtracted (r4:155-156); collections and the price curve already call `marginal_impact` |
| PaymentBehavior | **Justified (new)**, in `strategy/payments.py` (British spelling to match the code: `PaymentBehaviour`) | Phase 1 (gates "typical"), Phase 2 (edge case 7), Phase 3 (the overlay delay), Ask FLOW |
| CustomerEconomics | **Justified (new)**, in `strategy/customer.py`: sales, margin, basis, VAT flag, gross profit, share, classification, consistency findings | Phase 2, Phase 3 (`contribution_context`), the envelope's class-3 line, Ask FLOW, the decision record |
| (support) `SourcedFigure` | **Justified (new, small)**: fen or bp value + `provenance`, `source_ref`, `as_of_day`, `window`, `inputs`, `weakest` | every figure of C and G; P2 is written against it |
| CommercialPackage | **Refused**: it is `CandidatePackage` (`strategy/types.py:37-45`) and the verifier's `CounterProposal` | no second package type |
| SafePackage | **Refused**: it is `EnvelopePackage` (`envelope.py:826-841`) gaining `authority` (P1) | — |
| CommercialEnvelope | **Refused**: it is the envelope answer | — |
| DecisionScenario | **Refused**: it is `ScenarioState` (copies) or `Books` + `VerdictBundle` (packages) | — |
| ScenarioResult | **Refused as a primitive**: it is `Reading` / `MarginalImpact` plus verdict fields. The comparator's row is an API response model (`ComparatorRow`) in `strategy/comparator.py`, keeping its obligations for the portfolio | — |

### H.4 Where the customer profile is stored

- **Not in `FinancialState` or `Counterparty`.** The state is cash truth, and `Counterparty` is `extra="forbid"` in
  `domain/models.py`, which the phases do not touch (r1:57-59).
- **A new append-only table `customer_inputs`, migration `services/api/migrations/versions/0007_customer_inputs.py`.** It follows
  the pattern of `0006_decision_facts.py` and `0005_pilot_journal.py` (`persistence/tables.py:250-290`). Columns: `_row_id()`,
  `org_id`, `counterparty_id` (nullable: a null means a firm row such as the VAT rate or company gross margin), `field` (enum:
  `annual_sales_fen`, `margin_bp`, `margin_basis`, `classification`, `typical_delay_days`, `aggregate`, `vat_rate_bp`,
  `company_gross_margin_bp`), `value_json`, `provenance`, `source_ref`, `entered_by`, `entered_day`, `state_version`,
  `recorded_at`.
- Latest row per (counterparty, field) wins; the history stays (versioned and attributable, r2:175-177).
- A record `CustomerInputRecord` in `persistence/records.py`, port methods in `domain/ports.py`, and both stores
  (`memory_store.py`, `sql_store.py`).
- Written only by `POST /buyers/{buyer_id}/inputs` (owner auth). The firm row goes through `POST /firm/inputs`. Never written to
  the state, the operations or the hash chain.
- It is ledger data, so `reset()` clears it. `/demo/reset` re-seeds the Demo's rows from a new fixture
  `fixtures/customers/golden_inputs.json` as **ESTIMATED, "Demo assumption"** (r2:174), never from `buyers.yaml`.
- Lands in Phase 1, carrying only `aggregate` and `typical_delay_days`. Phase 2 adds the economics fields, with no second
  migration because `field` is an enum over one table.
- **"Read-only" is kept in substance.** The table holds context, not books. No route here changes `FinancialState`, a verdict, an
  approval or an execution. Owner question M.9.

### H.5 Flags

| Flag | Default | Gates | Phase |
| --- | --- | --- | --- |
| `FEATURE_EXPOSURE` (`config.py`, `api/features.py` message) | off | `GET /offers/{offer_id}/exposure`, `GET /decisions/{decision_id}/exposure`, `POST /buyers/{id}/inputs` (aggregate and typical-delay fields) | 1 |
| `FEATURE_CUSTOMER_ECONOMICS` | off | the economics fields of the inputs route, `GET /buyers/{id}/economics`, the economics lines in exposure / envelope / decision record | 2 |
| `FEATURE_ENVELOPE` (existing) | off | P1 to P6 (P4 as `?ask=T`) | 2, 4 |
| `FEATURE_COMPARATOR` | off | `GET /offers/{offer_id}/compare` | 3 |
| Web `NEXT_PUBLIC_STRATEGY_MVP` (existing, `apps/web/lib/config.ts`) | unset | every new block; the browser also honours the server's 403 `FEATURE_DISABLED` | 1 to 4 |

`tests/strategy/test_flags.py` is extended: all new flags default off, 403 when off, listed on health.

---

## I. UX proposal

### I.1 The primary deal view in the remediation's order

Level 1 is one headline, two to four decisive facts, one recommendation and one action (mission §41). Lines marked *existing*
are not rewritten; new lines are given exactly, with the phase that adds them.

| Order | Line | Source |
| --- | --- | --- |
| 1 Conclusion | *existing* verdict headline (EX01: REJECT, counter recommended) | verdict |
| 2 Recommended response | *existing*: Option A, keep 45 days and accept early settlement of up to ¥257,200 at 0.85% (Tier 1, r3:101) | verdict counter |
| 3 Complete cost | *existing*: Option A costs ¥3,027.77 (the ¥2,186.20 discount + ¥841.57 funding, r4:366-367, :387) | verdict / router |
| 4 Timing | *existing*: as asked, cash falls below your minimum in 47 days (RESERVE_BREACH day 47) | verdict |
| 5 Consequence | **NEW (Phase 1)**: the capacity line for the recommended response (I.3 a), and the concentration fact (I.3 b) | exposure |
| 6 Authorisation | **NEW wording (Phase 2, P1)**: the mandate statement in its class (I.3 c). **Directly under it, a separate sentence**: the economics (I.3 d) | envelope P1; customer.py |
| 7 Result | *existing* | |
| 8 Remaining task | *existing* | |
| 9 Evidence (disclosure) | four closed sections, in this order: **"If Foshan pays late"** (Phase 1, I.3 e); **"What this uses"** (Phase 1: five dimensions with windows and recovery days, X\* for the current books / as asked / each counter, the next-yuan sentence); **"Foshan's business"** (Phase 2: inputs with provenance, the EBITDA floor, the sensitivity line, the committed concessions line, the payment-behaviour sentence); **"What you can safely offer"** (envelope packages grouped by class, at most three shown, P6); then **"Compare responses"** (Phase 3) | |

The decision record shows the same block. A decided decision states "as at the decision (state version N)" only if that version
can be re-read from `states` (`persistence/tables.py:119-129`; whether it keeps every version is **to verify** in Phase 1).
Otherwise it shows nothing rather than today's reading mislabelled. This keeps current time and historical time apart (mission §1).

### I.2 Figures used: the Demo's own, never the mission's ¥400k / 7.1%

| Fact | Figure | Source |
| --- | --- | --- |
| Request's 12-month concessions | ¥28,326.92 | r2:407; `offers.yaml:13` |
| Annual sales, scheduled | ¥5,460,000 (13 × ¥420,000) | r2:383-385 |
| Gross profit at an assumed 20% | ¥1,092,000 | r2:396 |
| Share | 2.6% (2.59%) | r2:411 |
| EBITDA floor on the margin | 19.78% | r2:421-422 |
| Upper bound on the share from the books | 2.62% = ¥28,326.92 / ¥1,080,000 | r1:382-384 |
| Open AR | ¥420,000, 100% | r2:464 |
| Next 30 days' receipts (day 0) | none due | r2:465 |
| +30 stress | −¥250,000 on 30 Nov before funding; 65 days below ¥300,000; ¥550,000 shortfall; no admissible committed plan | r2:446, :456-458 |
| Option A capacity | line ¥13.80 to 1 Nov; X\* ¥0 | r4:190, :370, :387-389 |
| As asked capacity | ¥135,040 of ¥150,000 (90%) to 1 Dec; free 2 Dec (assumed); X\* ¥14,000 (today ¥81,000); need window 17 Nov to 1 Dec | r4:379-381 |

**VAT caveat on the 2.6%.** It treats the Demo's invoice faces as ex-VAT; `golden_sme.json` on `dev` states no VAT.
- If the owner sets 13% (as #90 reads golden, r1:241): ex-VAT sales are ¥4,831,858.41, gross profit at 20% is ¥966,371.68, and
  the share is **2.9%**.
- The EBITDA floor then rises to **22.35%**, so the Demo's own 20% seed would trip D2's sanity check **[synthesis arithmetic]**.
- The upper bound of 2.62% is the same either way.

This is M.2 for the owner.

### I.3 The exact sentences for the Demo (Foshan, EX01, day 0)

House style: "your limits", "needs your approval", distances from today with the date where it helps, no codes, no "day N"
(r3:277-278). The zh twins await the native reader (#66).

**(a) Consequence: capacity of the recommended response** (Phase 1; r4:387-389)
- EN: "Option A keeps your cash above your minimum, but it uses all but ¥13.80 of your credit line until 1 Nov, and the part-paid invoice can no longer be financed. Until then FLOW could not cover any further payment without you."
- ZH: "方案 A 能让现金保持在最低线以上，但在 11 月 1 日之前会用掉您信用额度中除 ¥13.80 以外的全部额度，部分提前付款的发票也不能再融资。在此之前，没有您的批准，FLOW 无法再支付任何额外款项。"

**(b) Consequence: concentration** (Phase 1; r2:225, :465)
- EN: "Foshan is 100% of what you are owed today (¥420,000). No customer receipts are due in the next 30 days."
- ZH: "佛山占您目前全部应收款的 100%（¥420,000）。未来 30 天内没有客户回款到期。"

**(c) Authorisation: the mandate statement, class 3, for the request as asked** (Phase 2, P1; rewording r2:120 per r1:321-327 and r3:286-290)
- EN: "Over the ¥5,000.00 limit you signed for what you give buyers: this request would use ¥28,326.92 of it over the next 12 months. FLOW will not send it under the limits you signed; raising the limit means signing a new mandate."
- ZH: "超出您签署的买家让利上限 ¥5,000.00：此请求在未来 12 个月会占用其中 ¥28,326.92。在您签署的授权范围内，FLOW 不会发送此方案；提高上限需要签署新的授权。"

**(d) Authorisation: economics, a separate sentence** (Phase 2; r2:415-417, with the D2 word "gross profit")
- EN: "For context: that is about 2.6% of the ¥1,092,000 a year we estimate Foshan's orders bring you in gross profit (¥420,000 every 30 days as your books schedule it × a 20% margin, a Demo assumption). It does not change what FLOW may do."
- ZH: "供参考：这约相当于我们估计佛山订单每年为您带来的 ¥1,092,000 毛利的 2.6%（按账上排期每 30 天 ¥420,000 × 20% 毛利率，演示假设）。这不改变 FLOW 可以执行的范围。"
- Evidence line, EN: "Your books' EBITDA (¥1,080,000 a year) means Foshan's margin is at least 19.8%, so this request is at most 2.6% of what Foshan's orders bring you."
- Evidence line, ZH: "按您账上的 EBITDA（每年 ¥1,080,000），佛山的毛利率至少为 19.8%，因此此请求最多占佛山订单为您带来收益的 2.6%。"

**(e) Evidence: "If Foshan pays late"** (Phase 1; r2:456-458)
- EN: "If Foshan paid every invoice 30 days late (a test, not a forecast): before funding, cash would fall to −¥250,000 on 30 Nov and stay below your ¥300,000 minimum on 65 days, and your committed facilities could not cover the ¥550,000 shortfall. FLOW does not count on an early payment from Foshan in this test."
- ZH: "如果佛山的每张发票都晚付 30 天（这是测试，不是预测）：在安排融资之前，现金将在 11 月 30 日跌至 −¥250,000，共有 65 天低于您 ¥300,000 的最低现金，您已承诺的融资额度也无法弥补 ¥550,000 的缺口。此测试不假设佛山会提前付款。"
- History line, EN: "FLOW has no payments from Foshan yet to measure how it usually pays, so there is no 'typical' case."
- History line, ZH: "FLOW 尚无佛山的付款记录，无法衡量其通常的付款时间，因此不提供"通常情况"。"

**(f) Evidence: "What this uses", as asked** (Phase 1; r4:379-381)
- EN: "Accepting as asked keeps ¥135,040 of your ¥150,000 credit line in use until 1 Dec (90%); without the deal it is free from 2 Nov. It is free again on 2 Dec, the assumed repayment day. FLOW could still cover a one-off payment of up to ¥14,000 today without your approval (today: ¥81,000). The extra funding is needed from 17 Nov to 1 Dec; FLOW's plan draws it today."
- ZH: "按原样接受会让您 ¥150,000 信用额度中的 ¥135,040 一直占用到 12 月 1 日（90%）；不做这笔交易，额度在 11 月 2 日即可释放。按假设的还款日，额度在 12 月 2 日恢复。今天，FLOW 仍可在无需您批准的情况下支付最多 ¥14,000 的一次性款项（目前为 ¥81,000）。额外资金需求在 11 月 17 日至 12 月 1 日之间，FLOW 的方案今天就会提款。"

**(g) The two sentences the surface never prints**:
- the mission's "Owner approval is still required for anything outside the signed mandate" (r1:363-366);
- "60 days with 20% upfront" (r3:61-62).

### I.4 What Ask FLOW's context gains

The binding already carries `offer_id` / `decision_id` and trusts ids only (`nl/models.py:102-115`, `nl/binding.py:1-8`). The
gain:
- new read intents ("how exposed am I to Foshan?", "what if Foshan pays late?", "what does this use of my line?", and in Phase 2
  "what is this against Foshan's business?");
- each answered by quoting the server-written sentences of the cached exposure or economics answer for the bound offer or
  decision, through the egress guard.

Limits:
- No figure is computed in `/nl`, and the LLM never does arithmetic.
- No new authority.
- When the flag is off, the intent says the feature is off.
- Facts the chat context may add: concentration shares, the stress sentence, X\* with its shape, and the economics with
  provenance. **Never the hidden `buyers.yaml` profiles** (INVARIANT 7).

---

## J. Test strategy

### J.1 Property invariants (mission §46 and #91's P1 to P14), with hypothesis

Hypothesis is already a dev dependency (`services/api/pyproject.toml:25`, used in `tests/financial/test_dated_valuation.py`).

| Invariant | Test file | Phase |
| --- | --- | --- |
| P1 contribution = post(sales × margin), sign, posted once | `services/api/tests/strategy/test_customer.py` | 2 |
| P2 provenance: tense follows `weakest`; Demo seeds never OWNER_ENTERED | `tests/strategy/test_customer_provenance.py` | 2 |
| P3 share × K_H = C; defined iff K_H > 0; "100%" only at exactly 1 | `test_customer.py` | 2 |
| P4 C byte-identical to the verdict's `forward_concession_total_fen` (differential) | `test_customer.py` | 2 |
| P5 projected sales count `recurring_issue_days(window)`: 13 on the Demo | `test_customer.py` | 2 |
| P6 AR shares in [0,1], Σ = 1, monotone, settled-neutral, partial counts outstanding only (mission: "AR concentration in [0,100%]") | `tests/strategy/test_concentration.py` | 1 |
| P7 30-day share from events; day +29 in, +30 out; overdue never counts | `test_concentration.py` | 1 |
| **P8 mandate independence**: outcome, tier, codes, counters, `forward_concession_total_fen` and plan byte-identical with every new flag on and off, for random economics, concentration and statistics (mission: "customer value never bypasses owner authority") | `tests/strategy/test_mandate_independence.py` | 1, extended in 2 and 3 |
| P9 payment statistics: early never offsets late; refused or duplicate entries inert; minimums enforced | `tests/strategy/test_payments.py` | 1 |
| **P10 stress moves, never duplicates**: one receipt per moved invoice in each copy, equal amount, day + D; Σ equal over the extended horizon; books' hash unchanged; D = 0 reproduces exactly (mission: "late payment moves rather than duplicates") | `tests/strategy/test_stress.py` | 1 |
| P11 unfunded closing cash non-increasing in D for unfinanced invoices (funding cost *not* asserted monotone) | `test_stress.py` | 1 |
| P12 no overdue receipt re-added; no facility whose lender is the stressed buyer; no live early-pay obligation on a moved invoice | `test_stress.py` | 1 |
| P13 customer loss removes recurring invoices and orders in W exactly once, open receivables stay, receipts removed = removed faces (Demo ¥1,260,000) (mission: "removes future contribution exactly once") | `tests/strategy/test_comparator.py` | 3 |
| P14 INVARIANT 13: the web reads only `_display`, `text` and sentence fields; no `fmt`, `toFixed`, `Intl.NumberFormat` or `_fen` arithmetic | `apps/web/scripts/exposure.test.mjs`, the pattern of `apps/web/scripts/strategy.test.mjs:208` | 1 to 4 |
| **Capacity after = canonical** (mission): Σ bal_f + debt principal = `debt_outstanding_fen` daily; line today = Home `available`; IF TODAY = `_candidates` − advances; concession after = what-if headroom and AGG iff < 0; covenant room ≥ 0 iff no breach (r4:131-135) | `tests/strategy/test_capacity.py` | 1 |
| **No headroom negative unnoticed**: a negative room renders "over by" | `test_capacity.py` | 1 |
| **Time-based recovery**: the recovery day = the plan's `repay_day`, labelled assumed | `test_capacity.py` | 1 |
| X\* criterion: the plan at X\* passes the criterion; X\*+¥1,000 fails or flips the reason; the buyer's early-pay source is absent from the copy; neighbour re-check and full scan on disagreement | `tests/strategy/test_need_search.py` | 1 |
| **A displayed safe package passes the verifier** (mission): on randomised books, every displayed package is `approved` on a fresh `_evaluate` re-check; the zone's minimum is by `approved` | `tests/strategy/test_envelope_authority.py` | 2 |
| **A displayed unsafe package cannot execute autonomously** (mission): every class-3 package, compiled and sent to the executor, is refused (`operations/executor.py:500-510`); class 2 needs an approval; only class 1 executes alone | `test_envelope_authority.py` | 2 |
| One step past the boundary fails where monotone; the middle probe replaces `top_first`'s assumption | extend `tests/strategy/test_envelope.py` | 4 |
| P4: the answer is the smallest approved price, or the fallback; the face is searched at 5 bp; the non-monotone column at 0.85% is pinned (¥244,000 to ¥286,000) | `tests/strategy/test_envelope_ask.py` | 4 |
| **Scenario totals reconcile** (mission): each row's Δ = row − current, field by field; `funding_cost_fen` = `/router/plan` SELECTED for those books; the concession is never added to funding cost | `test_comparator.py` | 3 |

### J.2 Example and pin tests (Demo figures, from the reports)

- `tests/strategy/test_exposure_demo.py` (Phase 1):
  - 100% AR; "no receipts due in 30 days";
  - +30 → −¥250,000 day 60, 65 days, ¥550,000, no admissible plan (r2:446);
  - X\* ¥81,000 / ¥14,000 / ¥0 / ¥62,000 (r4:186-191);
  - line ¥13.80 to day 31;
  - the day-34 path: RCV-A 2 days overdue and not moved; "one agreed early payment arrived on time" (r2:468).
- `tests/strategy/test_customer_demo.py` (Phase 2): ¥5,460,000; ¥1,092,000; 259 bp / "2.6%"; the EBITDA check passes at 20% and
  fails at the mission's ¥2,000,000 (r2:419-424); the twelve edge cases of r2:185-196, as en and zh sentences.
- `tests/strategy/test_comparator_demo.py` (Phase 3): the rows of D.5.
- zh parity and Business words: extend the patterns of `test_envelope.py:63-65, 304-340, 368-391` to each new answer.
- API: `tests/api/test_exposure_routes.py`, `tests/api/test_customer_inputs.py` (owner auth, append-only, latest wins, reset
  clears, Demo seed ESTIMATED), `tests/persistence/test_customer_inputs_store.py` (memory and SQL parity).
- Web e2e: `apps/web/e2e/exposure.spec.ts` (mocked; the block absent when the flag is off; the order of I.1; disclosure closed by
  default; zh), and extend `apps/web/e2e/strategy.spec.ts` for P1 and P6.
- The stability gate: `git diff --stat dev -- services/api/app/{financial,verifier,funding,alerts,operations,clock,books,mandate,covenants} services/api/app/domain/models.py`
  is empty, run in each phase's review.

### J.3 Validation tests (Phase 5)

- **Historical cases.** The 8-week public-record dry pilot books, with the weekly exhaustive scan (P5) and X\* per week.
- **Cold readers.** Agent readers first, human readers when #59 / #66 allow, on sentences (a) to (f), the class-3 sentence, P4's
  fallback and X\*.
- **Financial review.** Every Demo figure hand-recomputed by a verifier; #93's method (r4:431-445).

---

## K. Implementation phases (the lead's order)

### K.0 Ticket mapping (six build tickets into five phases)

| Ticket | Was | Becomes |
| --- | --- | --- |
| #96 | Phase 1: customer economics profile | **Phase 1: buyer exposure on the deal (concentration, +30-day stress, capacity before and after)** (re-titled; takes #97's concentration and stress scope and #99's capacity scope) |
| #97 | Phase 2: payment behaviour, stress, concentration | **Phase 2: customer economics as context, and envelope P1 to P3** (re-titled; takes #96's old scope and #98's P1 to P3) |
| #98 | Phase 3: envelope additions | **Phase 4: envelope P4 to P6 (answer the ask, monotonicity guard, fewer packages)** |
| #99 | Phase 4: capacity consumption | **closed as merged into #96** |
| #100 | Phase 5: comparator | **Phase 3: the scenario comparator** (blocked by #96, not #99) |
| #101 | Phase 6: validation | **Phase 5: validation** |

#96 and #97 are swapped in content rather than merged. Their numbers keep the build order (#96 then #97), and #99's scope goes
into #96. One extra small ticket follows from #90 (r1:427): **"Keep paid invoices and their receipt days in the pilot's books"**,
against `docs/pilot/RUNBOOK.md:236-237`. It is owner-gated (M.21).

Standing rules for every phase (map body; D9):
- one branch from `dev`; the lead specifies, an implementer (sonnet) codes, a verifier reproduces every figure, then code review,
  the gate and a `--no-ff` merge;
- read-only and flagged; INVARIANT 13; every displayed package re-checked;
- `git checkout -- services/api/evals` after scenario runs; never touch port 3000.

**Must not touch, any phase:**
- `services/api/app/{financial,verifier,funding,alerts,operations,clock,books,mandate}`;
- `app/covenants` (`line_balances` stays as it is; D6);
- `domain/models.py`;
- `fixtures/counterparties/buyers.yaml`;
- `scenario_received` and its refusal test.

### Phase 1 (#96): Buyer exposure on the deal. Concentration, a +30-day stress and capacity before and after, read-only and flagged

- **Files, new:**
  - `services/api/app/strategy/capacity.py` (`CapacitySnapshot`, `CapacityWindow`, the per-facility rebuild, IF readings,
    concession and covenant rooms, the X\* search);
  - `strategy/payments.py` (`PaymentBehaviour`);
  - `strategy/exposure.py` (assembles the block and writes en/zh sentences through `t(lang, en, zh)`);
  - `strategy/concentration.py` (or inside `customer.py` if the lead prefers one module; one owner of the formula either way);
  - `api/strategy_exposure.py`;
  - `persistence` additions plus `migrations/versions/0007_customer_inputs.py`;
  - `apps/web/components/deals/exposure.tsx`;
  - mocks under `apps/web/mocks/`.
- **Files, changed:**
  - `strategy/impact.py`: `scenario_paid_late`, `scenario_need`; `Reading.capacity`;
  - `strategy/types.py`: optional capacity fields on `MarginalImpact`;
  - `config.py`, `api/features.py`;
  - the deal surface (`apps/web/components/deals/decision.tsx` or `workspace.tsx`, at the consequence line and evidence) and
    `apps/web/app/decisions/[id]/page.tsx`;
  - `apps/web/lib/dictionary.ts`;
  - `nl` read intents (I.4).
- **Routes:** `GET /offers/{offer_id}/exposure?response=asked|counter:<k>&lang=`, `GET /decisions/{decision_id}/exposure?lang=`
  (cached by books, mandate, day, buyer and response through `strategy/cache.py`, single-flight), and
  `POST /buyers/{buyer_id}/inputs` (aggregate, typical delay).
- **Flag:** `FEATURE_EXPOSURE`. **Types:** `CapacitySnapshot` (in `Reading`), `CapacityWindow`, `PaymentBehaviour`,
  `SourcedFigure`.
- **Tests:** P6, P7, P8, P9, P10, P11, P12, P14, capacity reconciliation, X\*, the Demo pins, the routes, the store, e2e (J).
- **Stability gate:**
  - no engine file changes; the gate diff (J.2) is empty;
  - the existing suites pass unchanged (`tests/strategy/test_impact.py` 21 tests, `test_envelope.py`, the golden values);
  - the new transform is a separate function.
- **Lead checks before merge:**
  - the "no admissible plan" inference of G.3 is pinned by a test;
  - the after-decision stress reconciles at D = 0;
  - X\* cost is measured on the public SME.
- **Must not:** reuse `line_balances`; read concession headroom from `MarginalImpact.budget_used_delta_fen`; show #93's ¥4,727.85
  overlay; show a "typical" row below the minimums.
- **Estimate:** 6 agent-days (planning estimate, not from the reports).

### Phase 2 (#97): Customer economics as context under the verdict, plus envelope authority classes and package wording (P1 to P3)

- **Files, new:** `strategy/customer.py` (`CustomerEconomics`, the consistency checks, the edge-case sentences); the economics
  section of `apps/web/components/deals/exposure.tsx` or a sibling `customer.tsx`; `fixtures/customers/golden_inputs.json`.
- **Files, changed:**
  - `strategy/envelope.py`: `authority`; the class-3 package; `approved` filters at :651, :667, :671; the wall label at :551-552;
    the `primary` and "at today's price" sentences;
  - `apps/web/components/deals/before-they-ask.tsx`: grouped by class;
  - the demo reset seeding;
  - `nl` intents.
- **Routes:** `GET /buyers/{buyer_id}/economics?lang=`; the economics fields on `POST /buyers/{buyer_id}/inputs` and
  `POST /firm/inputs`; the economics lines added to the exposure and envelope answers.
- **Flags:** `FEATURE_CUSTOMER_ECONOMICS`; `FEATURE_ENVELOPE` (existing). **Types:** `CustomerEconomics`; `authority` on
  `EnvelopePackage`.
- **Tests:** P1 to P5, P8 extended, the edge-case table, the Demo pins, `test_envelope_authority.py`, zh parity.
- **Stability gate:** as Phase 1. The envelope's existing pins stay green, except P2's intended change (a cell that passes but
  fails `infeasibility` is no longer displayed). That change is listed in the PR.
- **Must not:**
  - let any economics value reach `verifier`, a counter, a tier or an approval;
  - print "profit", "profitable" or "worth";
  - add a recommendation among packages;
  - add an approval path for class 3;
  - make `_terms_extension` public (a WC-adjusted figure is deferred).
- **Estimate:** 4 agent-days.

### Phase 3 (#100): The scenario comparator, five rows and a late overlay, no probabilities

- **Files, new:** `strategy/comparator.py` (`ComparatorRow`, keeping the obligations), `scenario_customer_loss` in `impact.py`,
  `api/strategy_compare.py`, `apps/web/components/deals/compare.tsx` (behind disclosure).
- **Route:** `GET /offers/{offer_id}/compare?lang=`. **Flag:** `FEATURE_COMPARATOR`. **Types:** no new primitive.
- **Tests:** P13, scenario reconciliation, P8 extended, the Demo rows, e2e.
- **Stability gate:** as Phase 1.
- **Must not:** net avoided costs; sum concession and funding cost; add capacity across rows; build a second late-payment
  mechanism; print a probability or a weighted total.
- **Estimate:** 3 agent-days.

### Phase 4 (#98): Envelope P4 to P6. Answer the buyer's ask, guard monotonicity, fewer packages on the card

- **Files:**
  - `strategy/envelope.py`: `compensate(T)`, the middle probe replacing `top_first`'s untested middle, the P6 ordering;
  - `api/strategy_envelope.py`: `?ask=T`, cached apart like the zone;
  - the pilot weekly job script (the offline exhaustive scan, under `services/api/scripts/`);
  - `before-they-ask.tsx`.
- **Flag:** `FEATURE_ENVELOPE`.
- **Tests:** `test_envelope_ask.py`, the extended `test_envelope.py`, the weekly scan's disagreement failure.
- **Stability gate:** as Phase 1. Measured costs: P4 under 0.5 s price-only and about 2 s with the fallback on golden; 6 to 12 s on
  the public SME, on demand only (r3:233-234).
- **Must not:** bisect the face at a high rate; show "20% upfront"; rank packages.
- **Estimate:** 3 agent-days.

### Phase 5 (#101): Validation. Historical cases, property tests at scale, cold readers and a financial review

- **Work:**
  - run J.3;
  - run each phase's property suites at raised example counts;
  - record the kill-criterion readings of L.2;
  - send the behavioural questions to #89 / #59 (r5:194-198).
- **Files:** a report under `docs/research/` (on the research branch when the hold lifts). No product code.
- **Estimate:** 3 agent-days, plus owner and pilot calendar time.

---

## L. Risks and kill criteria

### L.1 Risks

| Risk | Source | Mitigation |
| --- | --- | --- |
| The margin is the weakest input. Owners rarely measure it per customer (no SME survey found), and gross and contribution differ by about 2× on the public SME (23.8% against about 47.5%) | r5:24-61 | basis stored; ESTIMATED default; the EBITDA floor; economics never a headline |
| The Demo's own seed conflicts with D2 once VAT is netted at 13% (2.9%; floor 22.35%) | I.2 [synthesis arithmetic]; r1:241 | M.2 before Phase 2 |
| No payment history anywhere, and the pilot procedure deletes it | r1:388-391 | stress without history; the runbook ticket (K.0) |
| The stress copy's financing semantics (conservative mechanism) | r4:258; r2:326 | said in the sentence; M.7 |
| X\* misread as a promise about future orders | r4:428-429 | the shape sentence; kill criterion below |
| X\* and P4 cost on large books | r3:233-234; r4:203-205 | on demand, cached, single-flight |
| Non-monotone feasibility (the face at 0.85%; receipt-date cost; horizon edge) | r3:160-178 | face searched at 5 bp; middle probe; weekly scan |
| `line_balances` double count | r4:39-47 | bypassed in Phase 1; an engine ticket (D6) |
| The price lever is weak in a deflationary market (PPI −1.1% in 2024; 年降) | r5:73 | lever ordering, terms then early payment then price (r5:83); Set 5 Q6 before promoting price |
| Concentration can be a financing constraint (debtor caps "usually 25% to 35%" in UK practice), or in the PRC an opening (core-buyer certificates under 银发〔2025〕77号) | r5:117-122 | the facility input (F.2); never a rule |
| Acceptance bills recorded as cash receipts | r5:157, :170 | receipt instrument NOT AVAILABLE; say so |
| zh sentences unread by a native reader | r3:302; #66 | the native reader before any flag goes on |

### L.2 Kill and defer criteria

| Capability | Criterion | Source |
| --- | --- | --- |
| Exposure: X\* | if pilot owners read "up to ¥14,000 today" as a promise about future orders, show only the windows and drop X\* | r4:428-429 |
| Exposure: typical delay | never shown below 3 completed invoices; P90 only at 10 or more | r2:259-265; r5:174 |
| Economics | adjusted profitability deferred while inputs are owner guesses; the economics line is withdrawn from level 1 if cold readers take it as permission ("small, so acceptable") | mission §51; r2:138-139; r5:40 |
| Comparator | customer loss stays a scenario; no probability without churn history (none exists; `SentFact.outcome` is simulated) | r1:253; r4:286-292 |
| Envelope P4 | if the ask's answer is usually "no price works" (as on golden), present the early-payment fallback only if owners understand it in the cold read; otherwise keep today's yes/no | r3:327-329 |
| Envelope overall | kill if the owner's chosen response is outside the zone or packages on more than half of the first ten real offers (the existing gate) | r5:88 |
| Portfolio | stays VALIDATE FIRST: build only if two or more deals are open in most pilot weeks *or* in a recurring busy season | r5:102-107 |

### L.3 Disagreements between the reports, and which to trust

1. **Stress variant and mechanism** (#90/#91 against #93). Settled in G.3: #91's buyer-wide scope and figures, #93's CashFlow
   mechanism, #91's lapse rule. #93's ¥4,727.85 overlay is not used because it keeps the buyer's early payment.
2. **Concession headroom source.** #90 lists `MarginalImpact.budget_used_delta_fen` (r1:256). #93 shows it reads ¥4,000 against
   the verifier's ¥28,326.92 (r4:53-60). **Trust #93**: the code confirms `budget_used_fen = max(trajectory forward, booked)`
   (`strategy/impact.py:172`).
3. **"Outside your autonomous limit … Owner review recommended"** (#91 r2:120, the mission's wording) against "a hard cap; a new
   signed mandate" (#90 r1:321-327; #92 r3:107-110). **Trust #90/#92**: confirmed at `verifier/evaluate.py:94` (`CAP_CODES`) and
   `:190-193` (`_is_hard`).
4. **Envelope cost.** #93 cites 17 to 78 s (r4:204). #90/#92 cite 6.8 to 8.1 s after `ba79762` / `0cd60cb` (r1:332-334;
   r3:218). **Trust #90/#92**: #93's figure is the dry pilot's, from before the fix.
5. **Gross against contribution** (#91 r2:73-88 against #94 r5:46-58). Both are kept: the basis is stored, the word follows it,
   the default is gross (D2).
6. **Firm-average margin: click or prefill** (#91 r2:193 against #94 r5:35). D2 decided prefill.
7. **Two labels against three classes** (#94 r5:84 against #90/#92). D7 decided three. #94 did not consider class 3.
8. **VAT on golden.** #90 reads the Demo's ¥5.46M as VAT-inclusive, from the unmerged contract on `feat/upgrading` (r1:241).
   #91 and #93 compute 2.6% on the gross faces (r2:411; r4:396). `golden_sme.json` on `dev` has no VAT statement. **Not settled by
   evidence: an owner decision (M.2).**
9. **Upfront.** #94 calls the missing upfront dimension "worth adding", since 35% of PRC sellers gave no terms in 2024 (r5:70,
   :83). #90/#92 show it is engine work (r1:328-331; r3:44-54). D6 defers it. The value is recorded for when the engine opens.
10. **Lead avenue.** #90 and #94 chose E, #92 chose A plus the envelope, #93 chose D. D1 composes E and D, with A second. No
    report's figure contradicts that.

### L.4 Where the evidence strains the lead's decisions

1. **D2 "margin defaults to the company-wide gross margin".** No company gross margin exists in either fixture's books. The
   public SME's 23.76% is in a markdown source (r1:244). The default needs a firm-level input (H.4); on the Demo it is a Demo
   assumption.
2. **D2 "VAT excluded" together with the Demo's 20%.** If golden is VAT-inclusive at 13%, the 20% seed fails the books' EBITDA floor
   (22.35%) and the share becomes 2.9% (I.2). The lead's "2.6% at an assumed 20%" holds only if the Demo's faces are treated as
   ex-VAT.
3. **D1(b) "taken off the copy as #91 and #93 do".** #93's X\* search removes the buyer's facility (r4:177). #93's late overlay
   does not (r4:367).
4. **D1 "for the buyer of the selected decision".** No report computed the stress *after* a decision. The available Demo figures
   are on the current books (r2:436-446). Phase 1 must compute and verify the after-decision stress before quoting it.
5. **D5 "validation last".** The kill criteria for X\* (r4:428) and P4 (r3:327-329) need cold readings that Phase 5 supplies after
   both are built. Agent cold reads should therefore run as acceptance inside Phases 1 and 4, and owner readings in Phase 5.
6. **D6 "`line_balances` before any capacity code reads line balances".** This holds and is not blocking: #93's capacity formula
   rebuilds balances without `line_balances` (r4:132). The engine ticket can wait for the owner without delaying Phase 1.

---

## M. Owner questions for #89 (deduplicated), each with the assumption that holds while open

| # | Question | Assumption while open | Raised by |
| --- | --- | --- | --- |
| 1 | Demo seed: (a) the books' ¥5,460,000 with a 20% Demo-assumption margin (2.6%); (b) change the books to make ¥2M / 7.1% true; (c) seed ¥2M and show the contradiction | (a) | #91 Q1 (r2:494-499); #93 (r4:85-89) |
| 2 | Are the Demo's invoice faces VAT-inclusive? Is VAT a firm setting FLOW divides out? | Demo faces treated as ex-VAT (no VAT on `dev`); the VAT rate is an owner setting, unset means "as invoiced" | #91 Q4; #90 (r1:243); L.3.8 |
| 3 | Owner-entered against the books' sales, beyond 10%: which drives the share? | observed > owner > projection, both shown | #91 Q2 |
| 4 | Do you think in 毛利率 or contribution? May FLOW accept either, labelled, defaulting to gross? | the basis stored, default GROSS, the word follows it | #91 Q3; #94 Q2 |
| 5 | Where does the company gross margin come from (your accounts, typed once, or an import)? | a firm row in `customer_inputs`, OWNER_ENTERED; Demo ESTIMATED | D2; L.4.1 |
| 6 | Stressed delay: a fixed 30 days, your own figure, or the observed P90 when larger? | +30, or P90 when ≥ 10 invoices and larger | #91 Q5; #94 Q6 |
| 7 | The engine affordance (a receipt day apart from the due day, plus recourse) for the stress? | declined: the conservative CashFlow mechanism with the two caveats stated | #91 Q6; G.3 |
| 8 | Does the stress remove the stressed buyer's own early-payment facility? | yes | #91 Q7 |
| 9 | Where do owner-entered customer facts live, and is entry a logged owner action? | `customer_inputs`, append-only, attributable, outside the state and the chain | #91 Q8; H.4 |
| 10 | Mark aggregate counterparties explicitly? | yes, an `aggregate` field | #91 Q9 |
| 11 | Minimum history: 3 / 4 / 10 / 12 completed invoices over 365 days? | yes | #91 Q10; #94 Q6 |
| 12 | Working-capital-adjusted contribution now, or only the committed-concessions line? | the committed-concessions line only; the adjusted total deferred | #91 Q11; D6 |
| 13 | Show the EBITDA consistency check to the owner? | yes, as a sentence when it fires | #91 Q12; D2 |
| 14 | Does STRATEGIC change anything FLOW does? | context only, until a signed mandate rule exists | grilling Q4 |
| 15 | May FLOW recommend one envelope package (reversing the MVP's "never what to offer")? | no | #92 (r3:270); D6 |
| 16 | The upfront / deposit lever (engine work)? | deferred | #92; #94 (r5:83); D6 |
| 17 | The `line_balances` fix as an engine ticket with a test? | open; Phase 1 bypasses it | #93 (r4:425-426); D6 |
| 18 | Over a cap: the surface says "needs a new signed mandate". Replace the mission's "owner approval is still required for anything outside the signed mandate"? | yes, reworded | #90 (r1:363-366); D6 |
| 19 | Kill criteria: X\* (r4:428), P4 (r3:327), economics on level 1 (L.2) | as in L.2 | #92; #93 |
| 20 | Do your invoice-finance facilities cap a single debtor? Has a bank or platform ever capped or refused one buyer's invoices? | no cap (fixture terms) | #94 Q5 (r5:130-132) |
| 21 | May the pilot keep paid invoices and receipt days in the books (`RUNBOOK.md:236-237`)? | the ticket is filed and waits | #90 (r1:427) |
| 22 | Do buyers pay in cash or in 承兑汇票? Should FLOW record the instrument? | cash assumed, and said | #94 Q6 (r5:157, :170) |
| 23 | Contract ingestion (`feat/upgrading`) as a source for sales cross-check and the customer-loss notice date: when? | not on `dev`; not used | #90 (r1:261) |
| 24 | When may the build start, and are #66 / #59 decided first? | nothing starts until the hold lifts | grilling Q6 |
| 25 | **Interview questions for #59 / #89** (behaviour, not opinion): (a) "What did you make on [largest buyer]'s orders last year, and where would you look it up?"; (b) "When you last forecast cash, which date did you use for [buyer]'s invoice … how late did it arrive, and in cash or in bills?"; (c) the deals-open probe "… and in your busiest month last year?"; (d) "Has a bank or platform ever capped or refused financing on one buyer's invoices?"; (e) the existing Set 5 Q6 before the price lever is promoted | routed; no design waits on them | #94 (r5:194-198); D5 |
| 26 | The zh native reader for every new sentence, and the 让步 / 让利 inconsistency | sentences ship flagged off until read | #92 (r3:302-306); #66 |

---

## N. Corrections to the map body's Reconciliation section (replacement text for its five bullets)

Replace the heading's parenthesis with "(the lead's reading on 10 October, corrected by #90, #92 and #93)" and the five bullets
with:

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
