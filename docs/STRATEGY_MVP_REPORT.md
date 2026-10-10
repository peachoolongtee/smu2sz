# FLOW strategy MVP: report

8 October 2026. Wayfinder map #47 built the synthesis's BUILD NOW set (`docs/STRATEGY_RESEARCH.md`, branch
`research/strategy`) as a read-only, feature-flagged MVP on the integration branch `feat/strategy-mvp` (from `dev` at
`bcc67d4`), in seven waves and three fix passes, with the delegation model of `docs/handover/05_strategy_and_ux_handoff.md`
section 2: the lead architected, specified, reviewed and merged; `sonnet` implementers coded; `verifier` agents reproduced
every displayed figure from the kernel; a `code-reviewer` and two cold readers reviewed. The contract is
`docs/STRATEGY_MVP_BRIEF.md` (section 12 holds the Wave 7 decisions that supersede the earlier sections).

## 1. What was built

Three read-only answers over the existing kernel (`evaluate`, `plan`, `project`, `alerts`), each a thin layer of sweeps,
deltas and rankings on labelled copies of the books. The engine is untouched: outside `services/api/app/strategy/`,
`app/api/strategy*.py` and `app/api/features.py`, the diff against `dev` is three default-off flags in `config.py`, the
router mount in `main.py`, and the what-if builder's generalisation to a buyer id in `app/whatif/offer.py` (its default
path byte-identical over 540 parameter combinations; `tests/whatif` and `tests/verifier` unchanged).

| Answer | Module and route | Where it shows (web flag `NEXT_PUBLIC_STRATEGY_MVP=1`) |
| --- | --- | --- |
| What can we offer this buyer? The Safe Deal Envelope as approved packages | `app/strategy/envelope.py`; `GET /buyers/{id}/envelope?zone=0|1&lang=en|zh` (`FEATURE_ENVELOPE`) | Deals: the card "The most you can give" after the buyer's asks: "You can live with: …", the reason, the money line, two secondary pills that open the existing Option A and B cards, a Details disclosure with the lever table, the packages within your limits and the terms-and-price table |
| What is cash arriving earlier worth to me? The cash price curve | `app/strategy/price_curve.py`; `GET /cash/price-curve?lang=` (`FEATURE_PRICE_CURVE`) | Cash & funding: one sentence under the headroom line |
| Whom should I chase first, and how? Collections marginal value with its action set | `app/strategy/collections.py`; `GET /receivables/worth?lang=` (`FEATURE_COLLECTIONS_WORTH`) | Receivables: the "Worth collecting" and "Action" columns and the ranking caption; Home: the top action in the receivables block |

Shared: `app/strategy/types.py` (`ScenarioState`, `CandidatePackage`, `MarginalImpact`), `impact.py` (`marginal_impact`,
`scenario_received`, `scenario_inflow`), `faces.py` (`option_a_face`, the one early-payment face every page quotes),
`cache.py` (one 32-entry single-flight answer cache for the three routes, computed outside the runtime lock), the spikes and
their recorded oracle under `fixtures/strategy/`, and the backtest harness `services/api/scripts/strategy_backtest.py`.
`Capacity` was deferred (map decision 2): the envelope names the wall each lever hits from the verifier's violation codes.

With every flag off (the default) the API answers 403 `FEATURE_DISABLED` on the three routes and nothing else changes; the
web mounts none of the components and calls none of the client functions, the mock recordings and the 64 existing mock e2e
tests are unchanged, and the demo path is untouched.

## 2. The figures (every one verified from the kernel by a second agent)

Golden day-0 books (cash ¥400,000, floor ¥300,000, RCV-A ¥420,000 due day 32, a ¥420,000 monthly invoice on 45-day terms,
¥5,000 forward budget, standing plan ¥3,113.93):

- Envelope: "You can live with: up to 55-day terms if the price rises 0.30%, or early payment at up to 0.85% on
  ¥257,200.00; a rebate up to 1.25%; not 60 days without an early payment." Reason: "60 days leaves a shortfall in 47 days
  that no fix covers; the ¥5,000.00 budget buys no terms without a price rise." Money: "Cost to you ¥0.00 with the price
  rise, or ¥3,027.77 with the early payment; without a deal your current funding plan costs ¥3,113.93." Levers: terms
  alone 45 (50 fails the budget at ¥8,108.97); budget ignored 55 (60 breaches day 47 with no fix); with a price rise 55 at
  0.30% (smallest passing 0.25%); early payment 0.70% on ¥420,000 and 0.85% on ¥257,200 (0.90% fails the break-even); rebate
  1.25% (¥5,000 exactly). The ten interaction packages of the deep dive reproduce to the fen (`fixtures/strategy/
  envelope_packages.json`); the thirty-package full grid matches the oracle; 70 verifier runs, 6.4–6.8 s cold for the
  default grid.
- Cash price curve: "Cash in the next 30 days saves you ¥89.11 of funding cost per ¥10,000 (0.89%); after that, earlier
  cash saves nothing." (bands: ¥0 on day 0, ¥89.11 for arrival days 1–30, ¥0 from 31; verified for every arrival day).
- Collections: RCV-A "Saves ¥1,250.06 at 0.40% (¥86.16 at the 0.85% limit)" on the ¥257,200 Option A face; received by
  day 12 it would save ¥3,113.93 and remove the breach.

Day-34 books (the demo path after Option A: cash ¥300,000, need ¥200,000, three open receivables):

- Collections, ranked: RCV-A (¥162,800, 2 days late) "Saves ¥1,374.61", call now, the only free action (¥37,200 left to
  cover at ¥331.49, needing approval); RI:BUYER-1:2 (¥420,000 due in 13 days) "Saves ¥1,288.28 at 0.20% (¥788.28 at the
  0.45% limit)", offer early payment on ¥200,000 or fund it instead; RI:BUYER-1:32 (due in 43 days) "Saves nothing extra
  now", wait: the invoices due before it already cover the need. The 0.45% ceiling is the mandate's APR cap on an 11-day
  early payment (the spike's plan-only 0.80% is a rate the verifier rejects with MAX_APR_EXCEEDED).
- Cash price curve: "Cash in the next 8 days saves you ¥178.22 of funding cost per ¥10,000 (1.78%), then ¥89.12 (0.89%)
  for the 18 days after; later, nothing." ¥178.22 is exactly two whole fee periods of FAC-IF.
- Envelope: "You can live with: up to 80-day terms if the price rises 0.95%, or early payment at up to 0.40% on
  ¥420,000.00; a rebate up to 1.25%; not 85 days." The deep dive's "no extension passes on day 34" was wrong: the verifier
  judges the offer's own effect, and a price rise buys terms; the test pins the engine.

Corrections to the research recorded on the way: the spike's early-pay ceiling ignored the APR cap; the deep dive's
day-34 envelope was unverified; the curve is cost(d + 30) − cost(d), not an inflow-and-outflow pair (the plan is not
linear in the flows); a later-day receipt is modelled by moving the copy's `terms_days` (an IMMEDIATE_DISCOUNT at 0 bp
settles the invoice early and mis-prices it).

## 3. The backtest (`docs/research/strategy/06-backtest-2026-10-08.md`)

PASS, 0 failures, 239 s: the 49 e2e scenarios replayed turn by turn (87 turns) for collections and the curve; a clock
sweep of every scenario's end state to days 10, 20, 34, 47 and 60 (245 states; every action produced; 737 rows checked;
0 failures); the differential against the spikes' oracle (409 checks to the fen; three expected differences, each with
its reason); the envelope over 180 fixture and held-out offers (128 checked; 89 of 90 verifier counters inside the
envelope, 76 listed as grid packages; 29 of 29 probes agreeing with the verdict; 39 re-checked packages with 0
disagreements; 6 of 6 lever maxima confirmed by the neighbour check; the exhaustive 273-cell scan agreeing with bisection
17 of 17; one offer skipped because its rebate base is stated in the offer, not on the books).

## 4. Tests and the gate

On `feat/strategy-mvp` (the flags-off API run at 7473efb, everything else at ae85cbf, the last wording pass):

| Check | Result |
| --- | --- |
| ruff on the strategy files, mypy on the 13 strategy and route modules | clean |
| Full API suite, flags off (`pytest -o addopts= services/api/tests`) | 5,746 passed, 37 skipped, 13 min |
| Full API suite, flags on | 5,746 passed, 37 skipped, 12.5 min |
| `tests/strategy` alone (ae85cbf) | 195 passed, 4 skipped (the wall-clock pins under SKIP_PERF_BENCH) |
| Scenarios `run_scenarios.py --inproc` | 49/49, 87 turns |
| `demo_run.py` | exit 0 (cure executed and alert cleared on day 34) |
| `app.security.attacks --report` | 0 attacks with harm, 0 commitments activated, ¥0 moved |
| Web typecheck, lint, unit | clean; 29 unit tests |
| Mock e2e, flag off | 65 passed, 27 skipped (the 64 of `dev` plus the flag-off compare test) |
| Mock e2e, flag on | 73 passed, 19 skipped |
| Live e2e, flag off | 36 passed (as on `dev`) |
| Live e2e, flag on | 43 passed |
| `e2e/strategy.spec.ts` on ae85cbf, mock and live | 9 and 7 passed |
| Design detector over the eight changed components | no findings |
| Backtest | PASS, 0 failures, 239 s |
| Verification of displayed figures (`docs/research/strategy/07-verification-2026-10-08.md`) | 555 rows, 0 mismatches |

## 5. Review and cold reads

The independent code review (P0: the `zone` query did not coerce; P1: routes under the global lock, a 500 path on the
curve route, unguarded ValueErrors, unguarded timing asserts, a flag-off change of the Deals compare state) and the first
cold read (`docs/research/strategy/cold-walk-strategy-2026-10-08.md`: the curve read as a rate charged; the card read as an
offer of the maximum; four early-payment ceilings for one invoice; a confusing worth cell) were fixed in Wave 7 (brief
section 12). The second cold read: section 10.

## 6. Design

The three surfaces follow `apps/web/DESIGN.md`: no new brand fill (Deals and Cash keep their one filled action; Receivables
has none), status colour only for status, section hues for wayfinding, pill radii, the motion kit; flag words the owner
must act on in ink-2; the Deals card's two actions are secondary pills; the design detector reports nothing on the changed
files. Screenshots: `docs/screenshots/strategy-mvp-2026-10-08/` (desktop and phone; `04b-deals-envelope-details` shows the
card's details open).

## 7. Deferred, and the pilot's instruments

Not built, as the synthesis classified: the multi-deal portfolio (VALIDATE FIRST; the enumeration spike and the oracle stay
under `fixtures/strategy/portfolio_default.json` for the gate), conditional deals, days-late averages, the dispute flag,
the early-pay offer as a queued operation (controlled action waits for the pilot), stress-to-action, tripwires, the
learning ledger (the pilot's instrument, 90-day window), `Capacity`, funding capacity reservation, the exposure budget.
For the shadow pilot the three routes are the instrument: weekly, the pilot's books are entered, the three answers computed
and recorded against what the owner did (the chosen response against the envelope, the chase order against the ranking,
receipt dates against due dates); the comprehension test of the cash sentence runs on three owners.

## 8. Known limitations

The first envelope read is 6–11 s cold (the sweep is cached per state; a warm-up at deal read would hide it); the full
grid with the zone is about 44 s and is computed only on `?zone=1`; `price_curve` and `receivables_worth` read the store
(alerts, reconciliation) outside the runtime lock after the snapshot; the mock recordings are English only (zh in mock
mode shows English sentences; live mode is bilingual); a package for a buyer without a recurring invoice reads "30-day
terms · …" because the grid's minimum stands in for terms in force; the backtest's collections invariants do not yet assert
the APR cap on every ceiling (the differential and a unit test do); BUYER-2 has no expected order on the golden books, so
the rebate-only sentence appears only on books like the test's; the zh sentences await a native reader.

Two limitations the public-record fixture (`fixtures/scenarios/public_sme.json`, map #58) exposed: supplier payments by
endorsed bank-acceptance bills are a non-cash flow that the engine treats as cash (the filing's purchases line is far below
the cost of materials for that reason), so the books' supplier outflows are larger and earlier than the real cash; and the
public filing states no credit terms, so that fixture's 60-, 90- and 76-day terms are calibrated from surveys, not read from
the filing. The envelope's terms range now runs two steps past the terms in force (a buyer on 90-day terms is scanned to
100), where the what-if sandbox's range still stops at 90.

## 9. Remaining UX debt (for Wave 8, the Impeccable finish)

The phone tab bar and the Ask FLOW button overlap row text in full-page captures; the Action column is a paragraph inside a
table; three dense detail tables in the Deals card; chart label overlap on the day-34 forecast; the empty fourth tile on the
day-34 risk card; three rows with the same buyer name told apart by invoice codes; the sticky nav mid-page in full-page
shots.

## 10. The second cold read

`docs/research/strategy/cold-walk-strategy-2-2026-10-08.md`: all three questions now answer in one reading; the cash
sentence reads as a benefit ("saves you ¥89.11 of funding cost per ¥10,000"); the Deals card reads as limits ("Your limits,
not an opening offer"); the early-payment headline (0.85% on ¥257,200) is the same on the Deals card, Option A and
Receivables. Its three remaining wording items were fixed in the last pass (the worth cell leads with the limit and names
the lower rate as the buyer's choice; the wait row says it in one sentence; the terms table shows no counter price where no
terms work). Its visual items (the phone tab bar and the Ask FLOW button over content rows, the "Saves" value wrapping, the
chart label collision, the sticky nav in full-page captures) and the cluster of near-identical percentages in the Deals
details (0.70, 0.85, 0.88, 0.89, 0.90) go to Wave 8. One observation from the verifier for Wave 8 too: on the day-34 books
the terms-with-price lever shows the rule price (80 days, price up 1.05%) while the primary sentence shows the smallest
passing price (0.95%); one rule should decide both.

## 11. Wave 8: the finish (the Impeccable suite over the whole UI)

At the owner's request, after the MVP, the Impeccable suite ran over every page as a refinement of the incumbent
identity in `apps/web/DESIGN.md`, with the two reference dashboards in `docs/research/inspiration/` as the bar for
density, hierarchy and finish. `PRODUCT.md` was written by inference from the repository's documents (every line
labelled) and `.impeccable/config.json` names `apps/web`, so the launcher resolves both.

**Evaluate.** The critique (`docs/research/impeccable-critique-2026-10-08.md`) scored eleven pages (24–28/40 on the
Business pages) and ranked 25 findings: two P0s (engine terms on the Business Activity page; Cash & funding ranking a
plan #1 that was not the recommended one), eleven P1s, twelve P2s, nine cross-page inconsistencies, and the reference
patterns mapped to FLOW (what to take, and what not: the dark variant, gradients, browser sparklines, a sidebar, bulk
checkboxes). The audit (`docs/research/impeccable-audit-2026-10-08.md`) walked 246 page views with axe at 412, 768,
1024 and 1440 (15/20): one P0 (the floating Ask FLOW over the phone demo stepper), six P1s (titles lost on hard loads,
the chart focus ring removed, 142 phone controls under 44 px, the account sheet ignoring Escape, English server strings on
zh pages in mock mode, Ask FLOW over content rows).

**Pass A, server words and fields (presentation reads, no engine change).** A clock move reads "4 days passed: the
¥45,000.00 debt payment went out and one invoice was issued." with "Time passed" as its label and ids in Audit details;
the comparison rows carry `role` and `role_reason` so the Cash page badges the recommended plan and chips the cheaper
two-approval alternative ("Cheapest in all, but it needs 2 separate approvals; the recommended plan needs one."); legs
carry names and the router total's offset is stated instead of a sum that did not add up; the approvals result is one
owner sentence; `POST /router/plan?lang=zh`. Every mock re-recorded through the demo path.

**Pass B, layout, typeset, distill.** One `Stat` (eyebrow, figure, caption, optional server delta; surface and deep) and
one `Disclosure` (one chevron, four fold verbs) replace five tile idioms and seven fold styles; status rails retired; 14 px
data and captions, 16 px card padding, 24 px between sections, the twelve-pixel floor; Receivables rebuilt as the
references do it (rank numeral, monogram, right-aligned tabular amounts, one worth figure, the action chip, a chevron
opening the sentence and the ids, pill filters All / Late / Due soon); the Deals envelope as three fact tiles with the
sentence as caption, the two pills gone; Home says the pending approval once; Cash's status header is one compact row;
Approvals one band and a centred card; the Demo story keeps one brand fill. Heights: Receivables day 34 1.5 → 1.2
screens, Cash day 0 2.5 → 2.3, Home pending 1.9 → 1.7, phone Home pending 3.1 → 2.7.

**Pass C, adapt, harden, optimize, clarify.** Ask FLOW docks as the phone bar's last cell and the content clears the bar
and the Demo strip (a measured `--dock-h`); 44 px touch targets on every Business control (compact chips keep their look
through a transparent hit area); the phone Demo header's four rows fold into the account sheet; chart labels placed in
pixels, alternating, dropping into the tooltip when crowded, marks only on the phone; tablet widths fixed (768, 1024);
route titles survive a hard load (server metadata per route); the recharts focus ring restored; the account sheet closes
on Escape and outside press; error strings through the dictionary in both languages; the Tour as a native dialog with no
polling; first paint in the owner's mode and language; the backdrop drifts once then rests; `color-scheme: light`;
recharts lazy-loaded (`/cash` 372 → 264 KB gzipped); the "Estimate" chip explained ("Priced on today's books;
re-checked before sending."). axe: 0 serious and 0 critical at every width after (13 target-size at 412 before).

**Pass D, polish, the finish review and the documentation.** One inspection round over all 54 after-screenshots, one
fix batch (Activity's empty sections as one quiet line each; one shared label for a buyer's duplicate receipts with the
tooltip naming the second; the Tour's focus returned to the account button; one `when` voice for the lots; chips that
wrap; the reduced-motion spinner as an ellipsis; the kit's durations and easing as Tailwind's transition defaults; link
hover; balanced headlines; text selection and caret in brand), one confirmation round, then stop. The
`impeccable-finish-reviewer` agent judged the shipped build against DESIGN.md, PRODUCT.md and the references: every P0,
every adapt finding and every mechanical audit item closed; eight local fixes left, done in pass E (forecast labels off
the gridlines and the reserve line; a fold on a page with a "Details" names its subject; the Receivables worth cell as
one figure with the sentence behind the chevron; the recommended funding row titled by the server's plan name and the
duplicate "cheaper option" note dropped; the envelope drawn once as its three tiles; Activity rows as divider-separated
list rows, the cash sentence inside the status card, the debt readings as the Forecast's footer; "Expired 27 days ago",
no "Executed" chip on time passing, "Debt readings, this month", a recovered promise as a full sentence, "of the
invoice" for "of face"; the decision title at 20 px). Heights: Activity day 34 1,553 → 1,182 px, Deals evaluated 1,890 →
1,842, Cash day 34 2,048 → 2,003. The `impeccable-documenter` agent rewrote `apps/web/DESIGN.md` from the shipped build
(56 tokens with computed contrast ratios, the type and radius scales, density, motion, thirteen named rules) with its
sidecar `apps/web/.impeccable/design.json`; `impeccable doctor` reports the coverage check cleared. The reviewer's verdict:
the Business pages carry the references' hierarchy and finish while staying unmistakably FLOW; what fell short (density on
Cash and Deals, a last layer of copy, one chart) is what pass E addressed, and the remaining density gap is structural
(the chart, the folds and the required copy), recorded below.

**Left after the finish (debt).** Forecast labels may still cross the series lines; the Demo-shell engine views keep two
primaries on some empty states (inbox, security, capex, verdict) and their dense formula tables; two Cash day-34 rows share
the server's facility name (told apart by their legs and chip); `--font-sans` names Inter first (no file is fetched; a
decision for the owner); Chinese pages show English server strings in mock mode (the recordings are English); the
Receivables outstanding split bar, the Deals concession bar in Business mode and Activity filters with paging were not
taken (no server percentages, and the owner's bar did not require them); the reference's density target of 1.8 screens is
not reached on Cash (2.3 desktop screens) and Deals (2.1).

**Gate after the finish** (`feat/strategy-mvp` at ba3c7a5 and after): full API suite 5,753 passed / 37 skipped after
pass A (one golden-digest test then taught the new display fields; the digest returned to its golden value, proving the
engine's figures and order unchanged); api, books, funding, strategy and alerts suites 1,618 passed / 26 skipped after
pass E; scenarios 49/49; demo run exit 0; attacks 0 harm; web typecheck, lint, 29 unit; mock e2e 73 (flag off; the 65
plus eight new responsive and compare tests) and 81 (flag on); live e2e 36 (off) and 43 (on); axe 0 serious and 0
critical at 412, 768, 1024 and 1440; the design detector clean over every changed component and stylesheet; before and
after screenshots in `docs/screenshots/impeccable-before-2026-10-08/` and `impeccable-after-2026-10-08/`.
