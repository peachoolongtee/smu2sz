# Ticket #92 (map #88): the Safe Deal Envelope against the mission (deliverable E)

Researcher's resolution, 10 October 2026. This repository, branch `dev` at 0cd60cb, read-only.
Paths below are relative to `services/api/` unless they start with `docs/`, `apps/` or `fixtures/`. "Eval" = one setting put
through `verifier._evaluate` by the envelope's `_Verifier` (the unit `evaluations` counts, `app/strategy/envelope.py:329-331`).

**What I ran (read-only).** `SKIP_PERF_BENCH=1 pytest tests/strategy/test_envelope.py -k "zone_pins or interaction or neighbour
or monotone or all_approved or needs_the_owner or day_34"`: 9 passed. A scratchpad script (`scratchpad/map-econ/r3probe/probe.py`)
that builds the golden day-0 in-memory runtime exactly as `tests/strategy/conftest.py:25-28` does and calls the envelope's own
`_Verifier`, `first_true` and `envelope_facts` (no repository file written). Afterwards `git checkout -- services/api/evals`;
`git status --short` empty. New figures from that probe are marked **[probe]**; everything else cites code or a committed report.

**The lead's reading of capability C (map body, Reconciliation) is confirmed, with four corrections:**
1. The envelope's own ranges are not "small enough to enumerate" online on the pilot's books (273 terms x price cells cost
   242 extra evals, 53 s on golden, `r3_spikes` 1.2; per-eval cost is 3 to 6 times higher on the public-record SME,
   `docs/research/strategy/08-perf-2026-10-10.md:103`), and one search in the code *assumes* monotonicity without testing it
   (`top_first`, `envelope.py:210-211`). "Monotonicity is tested, not assumed" holds for the bisection path only.
2. "20% upfront" is **not** `early_pay_face_fen`. The early-pay lever is a one-off discounted settlement of the open invoice;
   a deposit share on every future invoice has no obligation type, and adding one is engine work (stability mode).
3. On the golden books the mission's own example is false: **no price rise makes 60 days pass** (the wall is the day-47
   cash shortfall, which a price rise on later invoices cannot reach). 60 days passes only with at least **¥240,200** of the
   open ¥420,000 invoice paid early plus **+0.40%** [probe]. A first-class "compensate the ask" answer must therefore fall
   through from price to early payment, and its face search is non-monotone above the smallest rate (section 2).
4. Section 13's split is three-way in this engine, not two-way: autonomous (Tier 1), inside the signed limits but needing the
   owner (Tier 2), and financially safe but **over a signed cap**, which the owner cannot approve in-flow (a cap breach is a
   hard REJECT; only a newly signed mandate moves it). The envelope computes the third class (`liquidity_only`) but lists no
   such package.

---

## 1. Requirement by requirement

Status: BUILT (the requirement is met by code on `dev`), PARTLY (the facts exist, the answer or the words do not, or it holds
only on the golden books), MISSING.

### Section 10: from gatekeeper to negotiation intelligence

| Requirement | Status | Where | Current behaviour |
|---|---|---|---|
| "At current pricing, FLOW can support up to N days" | **PARTLY** | levers `terms_alone` and `terms_budget_ignored`, `envelope.py:585-589`; reason clause `envelope.py:1153-1166` | Both maxima are computed: golden day 0, 45 days within the limits (50 fails the ¥5,000 budget at ¥8,108.97) and 55 days if the budget is ignored (60 has a day-47 shortfall with no cure) (`tests/strategy/test_envelope.py:143-158`). The `primary` sentence leads with terms *with* a price rise (`envelope.py:1059-1074`); "at current pricing" appears only as the reason's "the ¥5,000.00 budget buys no terms without a price rise" (`envelope.py:1162-1163`, pinned at `test_envelope.py:58-59`). Nothing says "55 days is financially safe at current pricing but over your budget". Terms move on a 5-day grid (`app/whatif/params.py:11`, `app/strategy/types.py:47-52`): "52 days" cannot be said, only 50 or 55. |
| "60 days becomes acceptable if price increases at least X%" (minimum compensating price for a requested term) | **PARTLY** | zone table `_zone`, `envelope.py:648-655`; `envelope_zone`, `envelope.py:740-752`; Option B rule price `compensating_price`, `envelope.py:448-466` | The zone gives, per 5-day terms value, the smallest passing price (`first_true` over the 21 price steps) and the cost-neutral rule price beside it (golden: 50 d 0.10% / 0.15%, 55 d 0.25% / 0.30%, 60 d none / 0.45%; `test_envelope.py:206-215`). It is computed only on `?zone=1` (`app/api/strategy_envelope.py:80-86`), for the whole terms range rather than for the ask, it searches by `passes` and not by `approved` (`envelope.py:651` uses `v.ok`), and when no price works it stops at "none works" (`envelope.py:1016-1017`) instead of naming what would. The default answer for an ask one step past the longest approved terms is a yes/no: "not 60 days without an early payment" (`envelope.py:1088-1092`, from one probe at the top price with Option A's face, `envelope.py:807-809`); it gives neither the price needed with that early payment (0.40%) nor the smallest early payment that works. |
| "60 days becomes acceptable with 20% upfront" | **MISSING** | `CandidatePackage`, `app/strategy/types.py:37-45`; `whatif.offer.build`, `app/whatif/offer.py:156-166`; `ObligationType`, `app/domain/models.py:79-86`; `RecurringInvoice`, `models.py:392-399` | No upfront / deposit lever exists anywhere in the engine (a repository-wide search finds "upfront" only as a facility fee, `app/financial/charges.py:42-44`). See the upfront paragraph below. |

**The upfront dimension in detail.** `early_pay_face_fen` is a *one-off* `IMMEDIATE_DISCOUNT` on the buyer's earliest open
invoice (`offer.py:156-166`: base `INVOICE` with the receivable id, duration `ONE_OFF`), built only when the discount is at
least 5 bp (`offer.py:156`; a 0 bp setting drops its face, `envelope.py:333-336`). "20% upfront" in the mission is a
standing change to how every future invoice is paid (a deposit share at order, the rest at the new terms). The engine has one
`terms_days` per recurring invoice (`models.py:392-399`) and no obligation type that splits a future invoice's receipt
(`models.py:79-86`). What the verifier would need: a new obligation (for example a deposit share in bp and its lead in days
on `FUTURE_INVOICES`), its binding (`app/verifier/bind.py`), the projection of each generated receivable as two receipts
(`app/financial`), its valuation in `value_concessions` (a gain netted against the extension, so the forward-concession
budget sees it), and the tier rule (`app/verifier/evaluate.py:731-738`). All of that is `app/financial` and `app/verifier`:
**out of scope under stability mode**; it is an owner decision (#89), not a strategy-module change. A labelled-copy hack (two
recurring invoices in a `ScenarioState`) would bypass the verifier's own concession counting and is not recommended.

The honest proxy the code already supports is the **smallest early payment of the open invoice** that lets the asked terms
pass. On golden day 0 [probe]: 60 days needs at least ¥240,200 of RCV-A (57% of ¥420,000) settled early (at the smallest
rate, 0.05%) plus +0.40%; ¥240,100 fails RESERVE_BREACH on day 47; 20% (¥84,000), 30%, 40% and 50% all fail the same way at
any price and at 0.05%, 0.50% or 0.85%. The passing package is NEEDS_OWNER_APPROVAL, forward budget used ¥2,486.92, cure
¥2,939.19 on day 47 ("its funding cannot run today"). With Option A's ¥257,200 at 0.85% the same 60 days + 0.40% passes
with a ¥2,673.04 cure (`r3_spikes` 1.3, package 12). So the sentence the mission imagines ("60 days with 20% upfront") would
be **false** for Foshan on these books, and FLOW must not print it.

### Section 11: never present independent maxima unsafely

| Requirement | Status | Where | Current behaviour |
|---|---|---|---|
| Show packages, each evaluated whole, not per-lever maxima to combine | **BUILT** | `_grid` and `_cell`, `envelope.py:662-707`; packages in the answer, `envelope.py:1249` | Per terms value (terms in force, +5, +10: `MVP_TERMS_STEPS`, `envelope.py:69, 684`) and early-pay variant (none; Option A's face; the whole face at the largest rate that passes *inside the package*, `descend`, `envelope.py:691-694`), the smallest passing price, then the largest passing rebate at that price, then `v.probe` of the whole package (`envelope.py:673`). Golden: 11 packages, all approved [probe; pinned `test_envelope.py:267-272`]. The deep dive's interaction table is reproduced to the fen (`test_envelope.py:238-264`): e.g. the standalone maxima 50 days + 1.25% rebate fail AGG at ¥13,108.97, and the whole-face 0.70% standalone maximum never rides with 50+ days at any price (`r3_spikes` 1.4). |
| The per-lever maxima are still shown | **PARTLY (risk)** | `levers[]`, `envelope.py:1041-1049`; `primary`, `envelope.py:1056-1100` | The lever table lists each maximum alone with its wall (the mission's warned-against list) and `primary` joins three of them in one sentence ("up to 55-day terms if the price rises 0.30%, or early payment at up to 0.85% on ¥257,200.00; a rebate up to 1.25%"). The "or" between terms and early payment is safe; the rebate clause is joined by ";" and on golden the 55 d + 0.30% + 1.25% package does pass (¥4,837.95, `test_envelope.py:254-264`), but only because Option B nets the budget to zero (`r3_deep` 1.2). Nothing guarantees that the rebate maximum rides with the terms clause on other books. The sentence should name packages, not maxima (addition P3). |
| Price and rebate trade-off | **PARTLY** | `_cell`, `envelope.py:662-673` | A package is reported at the smallest passing price with the largest rebate at that price; the price-rebate curve (a 0.05% price step buys about ¥2,730 of budget, `r3_deep` 1.2) is not explored (`r3_spikes` 1.5). Acceptable for the MVP. |

### Section 12: the verifier in reverse

| Requirement | Status | Where | Current behaviour |
|---|---|---|---|
| Evaluate financial outcome, mandate, concession cap, cash reserve, funding capacity, covenants | **BUILT** | `_Verifier._verdict`, `envelope.py:364-374` | The real `_evaluate(..., plans="committed")` on the books, mandate, day and commitments; an engine error is worded by `evaluate` (a NO_VERDICT), never raised. Every figure is the verifier's (`envelope.py:10-12`). |
| max D such that verify(terms=D) admissible | **BUILT** | `last_true` with `gallop` and `top_first`, `envelope.py:585-589` | Two variants: within the caps, and with the caps ignored (`liquidity_only`, `envelope.py:403-404`). |
| min P such that verify(60 days, P) admissible | **PARTLY** | `first_true`, `envelope.py:235-256`, used by the zone and `terms_with_price` | The function exists and is right for a monotone lever; it is called for every terms value on `zone=1` and for the longest passing terms (`envelope.py:595-596`), never for "the ask". Cost of a first-class call: 2 evals when no price passes (it reads the bottom and the top, `envelope.py:243-246`), 6 to 7 when one does [probe: 50 d 6 evals, 55 d 7 evals, 60 d 2 evals]. |
| min upfront U such that 60 days + U admissible | **MISSING** (lever) / derivable proxy | see section 10 | The proxy "smallest early payment of the open invoice" is a `first_true` over the ¥100 face grid at the smallest rate: 14 evals on golden [probe], monotone at 0.05% on golden, **non-monotone at 0.85%** (section 2). |
| Enumeration when the domain is small | **PARTLY** | `--exhaustive` in `scripts/research/envelope_spike.py`; backtest, `docs/research/strategy/06-backtest-2026-10-08.md:70` | Enumeration exists offline only (golden BUYER-1: 273 cells, 17 of 17 comparisons agree). Never run on the public-record books (`fixtures/scenarios/public_sme.json`). |

### Section 13: FINANCIALLY FEASIBLE versus AUTONOMOUSLY PERMITTED

What the engine already says, per probe (`Probe`, `envelope.py:105-130`; `EnvelopePackage`, `envelope.py:826-841`):

| Field | Meaning in the code | Where |
|---|---|---|
| `tier` | the verifier's `required_tier`: TIER_1 autonomous, TIER_2 owner approval, TIER_3 never (`app/domain/models.py:308-311`) | `envelope.py:412` |
| `outcome` | ACCEPT / NEEDS_OWNER_APPROVAL / COUNTER / REJECT / NO_VERDICT | `envelope.py:412` |
| `passes` | ACCEPT or NEEDS_OWNER_APPROVAL with every reserve breach curable | `envelope.py:405-406` |
| `approved` | `passes` and the counter re-check (`counters.infeasibility`) finds nothing | `envelope.py:128-130, 420` |
| `liquidity_only` | every violation is a cap (AGG, per-buyer) or a curable reserve breach: **financially feasible, over a signed cap** | `envelope.py:403-404` |
| `cure_needs_owner` / `cure_cannot_run_today` | the reserve cure's plan needs the owner / cannot run today | `envelope.py:417` |
| `flags` (words) | "needs your approval" when NEEDS_OWNER_APPROVAL or the cure needs the owner; "its funding cannot run today" | `envelope.py:941-947` |

How the verifier assigns authority (`app/verifier/evaluate.py:726-758`): any hard violation (a cap breach is hard: `_is_hard`,
`evaluate.py:190-193`; caps are not price codes, `evaluate.py:91-94`) is REJECT; a price code is COUNTER/REJECT; otherwise
**any terms lengthening, any forward value above `tier2_single_commitment_fen`, or any obligation other than an early-payment
discount on a named invoice is NEEDS_OWNER_APPROVAL, Tier 2** (`evaluate.py:731-738`); unproven autonomy or a past-due
invoice from the buyer is also Tier 2 (`evaluate.py:750-756`). So on golden day 0, of the 11 default packages exactly one
(45 days + 0.85% on ¥257,200, Option A) is Tier 1 ACCEPT; the other ten are Tier 2 [probe]. Three classes follow:

1. **FLOW may do this alone** (Tier 1, `outcome == ACCEPT`, `approved`, no flags): in practice an early payment on a named
   invoice.
2. **Financially safe, inside your signed limits, needs your approval** (`approved`, NEEDS_OWNER_APPROVAL or
   `cure_needs_owner`): every terms, price or rebate package.
3. **Financially safe, over a limit you signed** (`liquidity_only and not passes`): e.g. 55 days at current pricing, REJECT
   for AGG at ¥16,217.95 with a curable day-47 cure of ¥1,570.36 [probe]. The owner cannot approve this inside the flow: a cap
   moves only with a newly signed mandate, which the agent can never do (`app/nl/offers.py:578`; renewal and re-signing are an
   offline owner step, `app/alerts/engine.py:522`).

| Requirement | Status | Current behaviour and gap |
|---|---|---|
| Show both statements per option | **PARTLY** | Classes 1 and 2 are distinguishable from `tier` / `outcome` / `flags` on every package, and the card renders the flags (`apps/web/components/deals/before-they-ask.tsx:84-87`). Class 3 exists only as the `terms_budget_ignored` lever and the reason clause; **no class-3 package is listed** (the grid keeps only cells whose `ok` passes, `envelope.py:667-669`). There is no single field naming the class; the surface would have to infer it from four. The mission's "FINANCIALLY SAFE but NEEDS OWNER APPROVAL" covers both 2 and 3, which this engine must keep apart (3 is not an approval, it is a limit). |

### Section 27: the safe-offer UX

| Requirement | Status | Where | Current behaviour |
|---|---|---|---|
| "At current pricing: up to N days" | **PARTLY** | see section 10 | Facts present, sentence absent. |
| "If the buyer requires 60 days: option A ..., option B ..., option C ..." | **PARTLY** | `primary`, `envelope.py:1088-1092` | "not 60 days without an early payment"; no options for the ask. |
| "Recommended: option A, explain why" | **MISSING (by design)** | wording rule, `docs/STRATEGY_MVP_BRIEF.md:155, 187-188, 431-435` | The MVP deliberately says "what you can live with, never what to offer"; the cost line names Option A's and Option B's cost (`_money`, `envelope.py:1188-1215`). A recommendation among packages reverses an owner-approved wording rule: owner decision (#89). |
| "Do not show options that fail their own recheck" | **PARTLY** | `_cell` uses `v.ok` (= `passes`), `envelope.py:667, 671`; the answer lists every cell, `envelope.py:1249`; the web renders every package, `before-they-ask.tsx:84` | A cell whose verdict passes but whose cure "cannot be funded in time" (`counters.infeasibility`, `app/verifier/counters.py:261-264`) is listed with `approved: false` and rendered. On golden every default package is approved (`test_envelope.py:267-272`) and the backtest re-checked 39 packages with 0 disagreements (`06-backtest:69`), but the guarantee is tested on the golden books only, and the zone's smallest price is by `passes` (`envelope.py:651`). Counters appended from the asks are filtered by `approved` (`envelope.py:796-798`), so the rule is applied in one place and not the other. |

### Section 37: see section 3 below.

### Section 45: test strategy, SAFE ENVELOPE

| Requirement | Status | Where |
|---|---|---|
| Every output passes the canonical verifier | **PARTLY** | `test_default_grid_packages_are_all_approved` (`test_envelope.py:267-272`, golden only); backtest re-check of 39 packages (`06-backtest:69`); verification 555 rows, 0 mismatches (`docs/research/strategy/07-verification-2026-10-08.md:3`). No property test on randomised books; the `passes`-vs-`approved` gap above is not tested on books where it differs. |
| One step beyond the boundary fails where monotonic | **BUILT** | `Maximum.beyond`, `envelope.py:556-563`; `test_envelope.py:143-190`; `test_a_neighbour_that_disagrees_sends_the_search_to_a_full_scan` (`:443-452`); `test_the_searches_agree_with_a_scan_when_the_lever_is_monotone` (`:461-478`) |
| Cross-term packages independently checked | **BUILT** | `test_the_ten_interaction_packages_are_reproduced_to_the_fen`, `test_the_interaction_packages_pin_the_brief_figures` (`test_envelope.py:238-264`); `probe_packages`, `envelope.py:1256-1273` |
| MANDATE: customer value never bypasses owner authority | **BUILT for the envelope** (it has no customer value input; nothing it outputs is executable, `envelope.py:10`, answer `hypothetical: True`, `envelope.py:888`). Must stay so when capability A adds contribution figures beside it. |

### Section 51: kill / defer for the envelope

| Criterion | Status | Current behaviour |
|---|---|---|
| Avoid multidimensional search if the UX becomes impossible to explain; return a few validated packages | **PARTLY** | The default grid is already capped at three terms values (`envelope.py:69, 684`), but that still yields 11 packages on golden, all rendered in one list (`before-they-ask.tsx:77-95`). The remediation's rule (one headline, two to four facts) suggests showing two or three (the verifier's own counters plus the answer to the ask) and the rest behind disclosure. The zone is already behind disclosure (`before-they-ask.tsx:106`). |

---

## 2. Monotonicity

**What the rule proves.** `last_true` (`envelope.py:196-232`) bisects (optionally galloping from the bottom), lands on `lo`
with `ok(lo)` and then requires `values[lo+1]` and `values[lo+2]` to fail; if either passes, it scans the whole lever
(`envelope.py:230-231`). `first_true` (`envelope.py:235-256`) mirrors it on the two values below the boundary. `descend`
(`envelope.py:263-279`) walks at most four steps down from a sibling maximum, then checks the two above. What this proves is
a **local** boundary: no passing value within two steps past it. It does not prove the lever monotone: an island two or more
steps past the boundary is missed, and the search never looks at it. Three paths prove less:
- `top_first` (`envelope.py:210-211`, used by all three terms levers, `envelope.py:585, 587, 592`): when the first and last
  values pass, the last is returned as `confirmed=True` **without testing anything between**. The docstring states the
  assumption (`envelope.py:205-207`). Added by ticket #78 for speed (`08-perf:57-58`).
- `first_true` returns "none" as soon as the top of the range fails (`envelope.py:245-246`): a window that passes in the middle
  and fails at both ends is reported as "none works". Conservative for display, but wrong as a "minimum" answer.
- `terms_with_price` searches terms at the top price only, on the stated assumption that "the price is monotone: the top of
  the range is the best chance" (`envelope.py:590-592`).

**Where non-monotone feasibility has been found.**
1. **Early-payment face inside a long-terms package, golden day 0 [probe].** 60 days + 0.40% + 0.85%: faces from ¥20,000 to
   ¥420,000 by ¥20,000 read `............PP.......`; by ¥2,000 from ¥240,000: fails to ¥242,000, **passes ¥244,000 to
   ¥286,000**, fails from ¥288,000 (below: RESERVE_BREACH, the early cash does not close the day-47 gap; above:
   EARLY_PAY_DEARER_THAN_PLAN, the discount on the larger face costs more than the plan). At 0.05% the same column is monotone
   (passes from ¥240,200 up). A min-upfront search by `first_true` at 0.85% would read the failing top and answer "none".
2. **The early payment changes which cure exists, in both directions** (`r3_deep` 1.2): it makes 60 days curable (Option A's
   cash closes the gap no cure could) and makes the 55-day cure dearer (¥2,673.04 instead of ¥1,570.36). The whole-face
   standalone maximum (0.70%) passes alone and fails in every package of 50 days or more (`r3_spikes` 1.4).
3. **The router's cost is not monotone in the receipt date** (`r3_spikes:682`: a receipt five days early on RI:BUYER-1:32
   costs ¥76.09 more than none). This bears on the plan-comparison wall (EARLY_PAY_DEARER_THAN_PLAN) and on any
   late-payment or upfront lever that moves a receipt.
4. A theoretical source, not observed: a longer term can push a receipt, and the shortfall it causes, past the projection
   horizon (`Mandate.horizon_days`, `models.py:330`), where the reserve check no longer sees it.

Every *single* lever found so far is monotone on the books it was scanned on: the 13 x 21 terms x price grid on golden
(`06-backtest:70`; `r3_spikes` 1.4: "it holds on this fixture only"), the early-pay rate at fixed face (0.05% to 0.85% pass,
0.90% up fail, at 60 d + 0.40% on ¥257,200 [probe]), the rebate (linear in the budget). Nothing in the engine guarantees it
(`r3_spikes:227`), and the public-record books have never had an exhaustive scan.

**Where enumeration is safer.**
- **The cross-lever face search** (any upfront or early-payment fallback): search the face at the *smallest* rate (monotone:
  more early cash only helps liquidity, and the discount at 0.05% is too small to lose the plan comparison), then the rate
  at that face with `descend`; never bisect the face at a high rate.
- **Offline, every pilot week**: run the backtest's exhaustive terms x price scan (and the face column for the ask) on the
  week's public-record books, as the monitor that monotonicity still holds there. 273 cells at 0.2 to 0.4 s is 55 to 110 s
  per buyer: acceptable in the weekly job, not in a request.
- **Online**: keep bisection with neighbours; replace `top_first`'s untested middle with one middle probe and the neighbour
  rule (about +1 to +3 evals per terms lever, section 4), or keep it and let the weekly scan be the guard. My recommendation is
  the middle probe: the terms levers are the headline figure.

---

## 3. Section 37 edge cases, current behaviour

| Edge case | Current behaviour | Where | Verdict |
|---|---|---|---|
| Non-monotonic feasibility | Bisection plus two neighbours, full scan on disagreement; `top_first` and the top-fails exit untested (section 2) | `envelope.py:196-279` | PARTLY |
| Terms interactions | Every package re-evaluated whole; terms x early payment explored with three variants; the whole-face rate searched inside the package (`descend`) | `envelope.py:676-707` | BUILT |
| Rebate + days + price | Smallest price, then the largest rebate at it, as one evaluated package; the budget is one pool the verifier counts | `envelope.py:662-673`; `test_envelope.py:254-264` | BUILT (trade-off curve not explored) |
| Facility exhaustion | Day 34: line ¥13.80 left, headroom ¥0; the verifier still passes terms with a price rise up to 80 days because it judges the offer's own effect (`test_envelope.py:481-519`; `docs/STRATEGY_MVP_REPORT.md:62-64`). No committed plan at all: terms and rebate withheld with a sentence (`envelope.py:718-727, 923-929`; `app/strategy/no_plan.py:21-29`) | as cited | BUILT |
| Covenant boundary | A covenant breach is hard (REJECT) and not `liquidity_only` (`envelope.py:403-404`), and `infeasibility` names it (`app/verifier/counters.py:265-267`). **Bug:** `wall_of(..., ignore_caps=True)` falls through to "buyer cap" for any binding code it does not know, so a covenant (or UNCOMMITTED_FACILITY, LEAD_TIME_TOO_LONG) wall on the `terms_budget_ignored` lever would be worded "the cap for this buyer" (`envelope.py:551-552`). Not binding on golden (DSCR 1.92x, leverage 1.72x at 60 days, `r3_deep` 1.1), so untested | as cited | PARTLY (fix: name covenant walls) |
| Rounding | Rates on 5 bp, faces on whole ¥100, terms on 5 days (`params.py:11-15`); off-grid terms in force carried unvalidated (`envelope.py:169, 301-307, 1029-1031`); the verifier rounds each forward total to the fen and the rebate hint divides exactly (`envelope.py:436`); the "minimum" price is the smallest 5 bp step that passes, and the true minimum lies in the step below it. Two prices coexist: smallest passing (0.25%) and the rule price that nets the cost to zero (0.30%, `counters.smallest_step_covering`, `app/verifier/counters.py:135-140`); `primary` uses the rule price (`envelope.py:1062-1066`, `test_envelope.py:393-398`) | as cited | BUILT; the surface must say which "minimum" it shows |
| Invoice not yet eligible for funding | A cure that advances on an invoice not yet issued is flagged "its funding cannot run today" (`envelope.py:417, 945-946`); one that cannot land by the breach day fails `infeasibility` (`counters.py:261-264`) and so is not `approved`; an overdue invoice is not used as the early-pay face (`offer.py:80-81`, `test_envelope.py:504-505`) | as cited | BUILT (but see section 27: a passing cell failing `infeasibility` is still listed) |
| Stale counter | The sweep is cached by books, mandate, day, buyer and commitments (`strategy_envelope.py:78-79`) and the answer carries `source_state_version` (`envelope.py:887`). Nothing it shows is executable: a package sent later is compiled and re-evaluated by the real path, which has its own stale codes (`STALE_VERDICT`, `TERMS_CHANGED`, `models.py:623, 630`). Whether the web drops an answer whose `source_state_version` is behind the books was **not checked** | as cited | BUILT server-side |
| Equal-economics ties | No ranking among packages exists: order is construction order (terms ascending, then variant none / counter face / whole face, then counters `sorted`, `envelope.py:688-706, 796-798`). Deterministic, but two packages with the same cost are not told apart, and no tie rule is written | as cited | MISSING (needed only if a recommendation is added) |

---

## 4. Cost: verifier runs per answer

**Today (after #78, `dev` 0cd60cb):**

| Books | Read | Evals | Seconds | Source |
|---|---|---|---|---|
| Golden day 0, BUYER-1 | default (`zone=0`), cold | 74 | 4.6 | [probe] |
| Golden day 0 | zone table alone | 31 | 3.6 | [probe] (`envelope_zone`) |
| Golden day 0 | one-shot `zone=1`, cold | 85 | 7.0 | [probe] |
| Public-record SME, week 1, buyers A/B/C/F | `zone=0` | not reported after #78 (61 settings for a `zone=0` read before it, `08-perf:28`) | 6.8 / 8.1 / 7.7 / 7.5 | `08-perf:116-127` |
| Same | + the zone table | 12 settings in the zone phase before #78 (`08-perf:21`) | +2.7 to 3.3 | `08-perf:122-125`; settings read A/B with the zone after #78: 49 / 37 (`08-perf:88`) |
| Public-record SME, weeks with no plan (terms and rebate withheld) | `zone=1` | not reported | 3.1 to 6.8 | `08-perf:78-80` |

Per eval: about 0.06 to 0.07 s on golden [probe: 228 evals in 16.6 s], 0.2 to 0.4 s on the public-record SME
(`08-perf:26, 103`); 98% of the time is the router's search (`08-perf:12-15`). A refused setting shown whole costs its
counters too (a price counter is 16 router searches, `08-perf:27-29`).

**What each proposed addition adds** (section 5 numbers):

| Addition | Extra evals | Golden | Public-record SME |
|---|---|---|---|
| P1 authority class per package; class-3 package from the existing `terms_budget_ignored` probe | 0 (fields already on every `Probe`; the lever's `at_max` is probed already, `envelope.py:560`) | 0 s | 0 s |
| P2 `approved`-only display; zone by `approved` | 0 (`approved` reads `recheck`, computed in `_read`, `envelope.py:420`) | 0 s | 0 s |
| P3 "at current pricing" sentence; packages-not-maxima `primary` | 0 | 0 s | 0 s |
| P4 compensate the ask, price only (min approved price at T, rule price beside) | 2 to 7 (+1 whole probe if shown) | under 0.5 s | 0.5 to 3 s |
| P4 with the early-payment fallback (min face at 5 bp, then price, then rate at that face) | about 25 to 30 more (14 face [probe], 7 price [probe], about 5 rate) | about 2 s | 6 to 12 s; read on demand, cached apart like the zone |
| P5 `top_first` middle probe | +1 to +3 per terms lever (3 levers) | +0.2 s | +1 to 3 s |
| P6 weekly exhaustive scan (offline) | 273 per buyer with terms (more with the face column) | about 20 s | 55 to 110 s per buyer, in the weekly job |
| Upfront lever (engine) | n/a | n/a | not proposed in stability mode |

---

## 5. Recommended additions, in priority order

All in `app/strategy/` and the web card; none touches the engine; each package shown stays a whole `v.probe` that passes
`infeasibility` (the counter property, `counters.py:14-22`).

1. **P1. One authority statement per package, and the class-3 package (0 evals; high value: section 13 and the mission's
   central "mandate versus economics" rule, section 2).** Add `authority: "flow_may" | "needs_owner" | "over_your_limits"`
   (derived, never computed: Tier 1 ACCEPT and no flag; `approved` and Tier 2 or `cure_needs_owner`; `liquidity_only and not
   passes`). List the `terms_budget_ignored` maximum as one package in its own group ("financially safe, over a limit you
   signed"), with the cap it breaks and by how much (`forward_budget_used_fen` against the mandate's cap, both already on the
   probe and the mandate). This is the hook capability A needs: "outside your autonomous limit; it costs ¥X, Y% of the
   estimated contribution" attaches to exactly these packages.
2. **P2. Show only what passes its own re-check (0 evals; correctness, section 27).** Filter displayed cells and the zone's
   smallest price by `approved`, not `passes` (`envelope.py:651, 667, 671`); keep failures only in `full_grid`; add a test on
   books where a cure cannot land in time. Also fix the covenant wall label (`envelope.py:551-552`).
3. **P3. Say "at current pricing" and name packages, not maxima (0 evals).** Lead with "At today's price: up to 45 days
   within your limits" and keep the price clause as a package ("55 days with a 0.30% price rise"); drop the rebate maximum
   from the joined sentence unless the named package containing it is the one quoted.
4. **P4. Answer the buyer's ask (2 to 30 evals, on demand; the mission's section 10 headline).** `compensate(T)` for the
   asked terms (from the inbound offer's `TERMS_EXTENSION` or a typed ask): the smallest *approved* price at T with the rule
   price beside it; if none, the smallest early payment of the open invoice that makes T pass (face searched at 5 bp, monotone
   there), then the smallest price with it, then the largest rate at that face (`descend`); each result `v.probe`d whole and
   re-checked. Cache apart like the zone. Golden answer: "60 days needs ¥240,200 of the open invoice paid now and a 0.40%
   price rise". Medium cost on the pilot books; read only when the owner opens a deal with an ask.
5. **P5. Monotonicity guard (+3 to +9 evals online, or 0 online plus the weekly job).** Replace `top_first`'s untested
   middle with one probe; add the exhaustive terms x price scan (and the face column for any ask) to the pilot's weekly run
   and fail loudly on a disagreement.
6. **P6. Fewer packages on the card (0 evals; section 41/51).** The verifier's own counters and the ask's answer first, the
   rest behind disclosure.
7. **Deferred to the owner (#89):** a recommendation among packages (reverses the MVP's "what you can live with, never what
   to offer" rule, `docs/STRATEGY_MVP_BRIEF.md:155, 187, 431`; needs a written tie rule); the upfront / deposit lever (engine).

---

## 6. Sentences for the surface

House style from the existing card: "your limits", "needs your approval", distances from today, no codes, no "day N"
(`docs/STRATEGY_MVP_BRIEF.md:179-191, 431-435`). Every figure below is a field the verifier already returns.

**Financially safe, inside the signed limits, needs the owner (class 2).**
- EN: "55-day terms with a 0.30% price rise: within your limits and your cash floor holds, but FLOW cannot agree longer terms
  on its own. It needs your approval."
- With a flagged cure, append: "Your cash dips in 47 days; a ¥1,570.36 advance covers it, and that funding cannot run today."
- ZH: "55 天账期并加价 0.30%：在您的底线内，现金底线也守得住，但 FLOW 不能自行同意延长账期，需要您批准。" / "47 天后现金会低于底线；一笔 ¥1,570.36 的垫款可以补上，但该资金安排今天无法执行。"

**Financially safe, over a limit the owner signed (class 3).**
- EN: "55-day terms at today's price: your cash floor holds, but it uses ¥16,217.95 of your ¥5,000.00 budget for what you give
  buyers. FLOW will not send it under the limits you signed; only you can decide, and raising the limit means signing a new
  mandate."
- ZH: "按现价给 55 天账期：现金底线守得住，但会占用您给买家让利预算中的 ¥16,217.95（预算为 ¥5,000.00）。在您签署的授权范围内，FLOW 不会发送此方案；只有您能决定，提高上限需要签署新的授权。"

**The compensating-price answer.**
- Price works: EN "55 days works if the price rises at least 0.25%; at 0.30% the price rise pays for the longer terms in
  full. Either needs your approval." ZH "价格至少上调 0.25%，即可接受 55 天账期；上调 0.30% 时，加价可完全抵消延长账期的成本。两者都需要您批准。"
- No price works (golden, 60 days): EN "No price rise makes 60 days work: the longer terms leave your cash short in 47 days.
  60 days works only if ¥240,200 of the open ¥420,000.00 invoice is paid now and the price rises 0.40%; that needs your
  approval." ZH "任何加价都无法让 60 天账期可行：账期延长会让您的现金在 47 天后不足。只有在 ¥420,000.00 的未结发票中先支付 ¥240,200，并加价 0.40% 时，60 天才可行；这需要您批准。"
- Nothing works: EN "Nothing within the ranges FLOW checks makes 60 days work on today's books." ZH "按今天的账面，在 FLOW 检查的范围内，没有方案能让 60 天账期可行。"

**zh parity.** Every envelope sentence has a zh twin through `t(lang, en, zh)` (`app/api/presentation.py`, used throughout
`envelope.py:893-1230`), pinned in tests (`test_envelope.py:63-65, 304-340`); the zh sentences still await a native reader
(`docs/STRATEGY_MVP_REPORT.md:140`; owner grilling #66). New sentences must ship with zh twins and the same Business-words
tests (`test_envelope.py:368-391`), and the web dictionary keys for any new labels (`apps/web/lib/dictionary.ts`). Terms to
keep consistent with existing zh: "需要您批准" (`envelope.py:944`), "其资金安排今天无法执行" (`:946`), "您给买家让利的预算" (`:902`);
note `_WALL_TEXT` says "让步" and `_WALL_WORDS` says "让利" for the same budget (`envelope.py:894, 902`), an existing
inconsistency the native reader should settle.

---

## 7. Verdict: should the map lead with the envelope?

**No, not as the lead build; yes as the base the lead draws on.** Capability C is the most finished of the five: the search,
the whole-package re-evaluation, the counter re-check, the walls, the words, the cache and the tests exist, and the mission's
remaining asks for C are mostly derivations of fields already computed (P1 to P3, P6 cost nothing in verifier runs). Its one
genuinely new answer (P4, the ask) is useful but medium-cost on the pilot's books, and on the golden books it says something
less appealing than the mission's example ("no price makes 60 days work; an early payment of ¥240,200 does"). Its most
quotable gap, "20% upfront", is engine work and stays deferred.

The mission's central product claim (section 2, section 52) is the *mandate versus economics* statement: "outside your
autonomous limit; it costs ¥28.3k, 7.1% of the estimated annual contribution". Nothing of that exists (capability A: no sales,
margin or contribution anywhere), it costs no verifier runs (the concession cost is the verifier's `forward_concession_total_fen`
already on every verdict and every envelope package), and it is what turns the envelope's class-3 packages from "over your
limits" into a business trade-off. Concentration (a sum) and capacity before / after (`MarginalImpact`) are similarly cheap.

Recommended lead: **one deal statement (A + the envelope's P1/P2/P3 + concentration), read-only and flagged**, with P4
(compensate the ask) as the next phase once the owner confirms (#89, #94) that owners negotiate from a stated ask, and P5's
weekly monotonicity scan added to the pilot run at the same time. Kill criterion for P4: if the pilot shows the ask's answer is
usually "no price works" (as on golden), present the early-payment fallback only if owners understand it in the cold read;
otherwise keep the yes/no it gives today.
