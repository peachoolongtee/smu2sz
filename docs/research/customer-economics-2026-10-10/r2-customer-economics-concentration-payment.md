# R2 (ticket #91 of map #88): customer economics, AR concentration, payment behaviour, late-payment stress

Researcher's specification for deliverables C and G of the mission (sections 4, 5, 6, 17, 18, 19, 20, 35, 36, 39, 45, 46).
Read-only against `/Users/ianpong/Hackathons/smu2sz` at `dev` 0cd60cb. Every figure in section 8 is computed by hand from
fixture values and checked with one read-only script (`scratchpad/map-econ/r2_stress.py`, which imports the engine, plans
and projects copies of the Demo books, and writes nothing). Afterwards `git checkout -- services/api/evals` ran and
`git status --short` was empty.

## 0. What the repository changes in the mission's picture (read this first)

1. **The mission's "¥2.0M at 20% = ¥400k, so 7.1%" contradicts the Demo books.** The Demo books schedule Foshan at
   ¥420,000 every 30 days (`fixtures/scenarios/golden_sme.json:47-52`). That is 13 invoices, ¥5,460,000, in the same
   365-day window the concession is valued over. At the mission's 20% margin, contribution is ¥1,092,000. The EX01
   concession (¥28,326.92, `fixtures/offers/offers.yaml:13`) is then **2.6%** of contribution, not 7.1%. If the Demo
   is seeded with ¥2M of owner-entered sales, FLOW has to say that the figure disagrees with its own books (§3, case 10).
2. **A concession share is meaningful only when both sides cover the same window.** The concession counts dated
   invoices in W = [today, today + H) (`app/financial/concessions.py:95-107`). Projected sales must count the same invoice
   list, through the same function. A 12 × monthly or 365/30 run rate would count 12 or 12.17 invoices against the
   concession's 13.
3. **An honest late-payment stress has to remove the late buyer's own early-payment offer.** Delay Foshan by 30 days and
   the router covers the gap with a ¥404,858.30 EARLY_PAY from `FAC-EARLYPAY`, whose lender is Foshan itself
   (`golden_sme.json:133-146`). In effect it assumes the buyer who pays a month late pays early when asked. With that
   facility removed from the stress copy, **no admissible committed plan covers the ¥550,000 shortfall**: that is the
   headline of the Demo's stress (§8.7).
4. **The existing move-a-receipt helper changes contractual terms on the copy** (`app/strategy/impact.py:81-88`). That is
   harmless for a cash projection. It is wrong for two other uses:
   - **Evaluating a package.** "Terms in force" become 45 + 30 = 75, so a 60-day request would read as a shortening.
   - **Financing eligibility.** The router could finance the invoice up to the stressed day, past its contractual due day.

   The stress therefore needs the rules of §6.3, and possibly a small engine affordance (owner question Q6).
5. **No customer-level economic data exists** in either fixture (`Counterparty` holds id, name, role and known;
   `app/domain/models.py:454-458`). The fixtures have no margin. The Demo has 13 days of invoice history. The
   public-record SME has accounting-history sales per top-five buyer and a firm-level gross margin, but no per-customer
   margin (§8.9).
6. **VAT.** Invoice faces carry VAT where the business charges it (public SME: +13%, `fixtures/scenarios/public_sme.SOURCES.md:98`).
   Revenue and margin are ex-VAT. So sales derived from invoices overstate revenue by the VAT rate, unless the source
   says it is net.

## 1. Customer-economics metrics

### Where the formulas live (INVARIANT 13; no formula in two places)

- **One new server module, `app/strategy/customer.py`**, owns customer economics and concentration.
- **One new module, `app/strategy/payments.py`**, owns payment behaviour. It replays the log through the same replay
  `app.alerts.reconcile` uses, never a second matcher.
- **The stress copies** are a new `scenario_paid_late` beside `scenario_received` in `app/strategy/impact.py`.

What the new code reuses:
- The concession value is always the verifier's own `forward_concession_total_fen`. It is never recomputed.
- Projected invoices come from `concessions.window` and `recurring_issue_days`.
- The carrying cost (§1.5) uses `_terms_extension`'s formula (`concessions.py:186-206`), made public rather than copied.

Every sentence is written server-side in en and zh. Every `_fen` and `_bp` field gets its `_display` sibling from
`app/api/display.py:24-41`. The browser renders strings only.

Nothing in `app/financial`, `verifier`, `funding`, `alerts`, `operations`, `clock`, `books` or `mandate` changes, apart
from the optional engine affordance in Q6. All of it sits behind a feature flag and is read-only.

### 1.1 Annual sales (MVP)

| | |
| --- | --- |
| Definition | What the customer is invoiced in one year, in one of three forms, best first: (a) **trailing 12 months observed**: Σ `face_fen` of the buyer's receivables with `issue_day` in [today − 365, today), status OPEN, FINANCED or SETTLED (FAILED excluded and named), only when the books cover the whole window (the earliest issue day in the books ≤ today − 365); (b) **accounting or ERP**: the annual revenue per customer from an imported ledger or report; (c) **owner-entered**: one figure. When none exists, a **projected** figure: Σ face of the buyer's open receivables and recurring invoices with issue day in W = [today, today + H), counted by `recurring_issue_days` (the concession's invoice list), plus expected orders in W, which are named separately because they are not firm. |
| Units | integer fen; a `vat_inclusive: bool` flag on the figure (invoice-derived: true unless the source says net) |
| Horizon | trailing 365 days (observed) or W (projected); always printed with the figure ("12 months to 30 Sep" / "next 12 months") |
| Source | `state.receivables` and the log (INVOICE_HISTORY); imported statement (ACCOUNTING_HISTORY); ERP export (ERP); owner entry (OWNER_ENTERED); `state.recurring_invoices` and `expected_orders` (PROJECTED) |
| Rounding | none: a sum of integer fen |
| Shows | "Foshan: ¥5,460,000 of invoices over the next 12 months, as your books schedule them (¥420,000 every 30 days)." / "Foshan was invoiced ¥4,980,000 in the 12 months to 30 Sep (from your invoices)." |
| Refuses | Annualising a short history by multiplying it up ("3 months × 4"). Calling a projection "sales" without its window. Mixing VAT-inclusive invoice totals with ex-VAT margins without saying so. Using `fixtures/counterparties/buyers.yaml` (hidden negotiation state, INVARIANT 7). |

### 1.2 Margin: recommend "contribution margin" as the measure, and accept gross margin as a labelled input

**Recommendation.**
- The measure FLOW names is **contribution**: sales less the costs that rise and fall with that customer's sales
  (materials, freight, piece-rate labour, packaging, commissions, payment and financing fees).
- FLOW stores which basis the owner gave (`margin_basis: CONTRIBUTION | GROSS`).

**Reasoning.**
- Both questions FLOW answers are incremental: "is this concession large against what the customer adds?" and "what
  goes if the customer goes?". Contribution is the incremental measure. Gross margin under PRC accounting (营业成本)
  carries allocated fixed production overhead (salaried production staff, depreciation), which do not move with one
  customer.
- Most SME owners know gross margin (毛利率) from their accounts, not contribution (validation question for #94).
  Gross margin is lower than contribution, so it errs in a known direction:
  - **conservative** for the concession share (the share comes out larger);
  - **non-conservative** for a customer-loss figure (the contribution lost comes out smaller).

  FLOW says so on both surfaces.
- Neither is profit. The words "profit", "profitable" and "worth" are never used of either figure (mission §4).

| | |
| --- | --- |
| Units | integer bp, signed, range −10,000 to 10,000 (owner entry: a percentage to two decimals is an exact bp); a margin derived from accounts is kept as an exact Fraction and displayed to 2 dp |
| Horizon | the same period as the sales figure it multiplies |
| Source | OWNER_ENTERED (MVP); ACCOUNTING_HISTORY firm-level gross margin applied to one customer is **ESTIMATED** (the firm's average is not the customer's); ERP per-customer margin (future) |
| Rounding | none on entry; derived from accounts: exact Fraction, display half-up 2 dp |
| Shows | "Margin: 20%, as you entered it (contribution: what Foshan's sales leave after costs that vary with them)." / "Margin: 23.76%, your company's average gross margin from the 2025 accounts, not Buyer A's own; Buyer A's contribution is probably higher." |
| Refuses | A default or industry margin applied silently. "Foshan's margin is 20%" for an owner's number. Gross margin called contribution. |

### 1.3 Annual contribution (MVP)

| | |
| --- | --- |
| Definition | `contribution_fen = post(sales_fen × margin_bp / 10,000)` (exact product, posted once half-up, `app/domain/money.py:25-37`). Negative when the margin is negative. When `vat_inclusive` is true and a VAT rate is known, sales are first divided by (1 + VAT) exactly inside the same expression, then posted once. |
| Units | integer fen |
| Horizon | that of the sales figure |
| Source / label | DERIVED, carrying the weakest input's label (§2) |
| Rounding | one `post` of the exact product |
| Shows | "Estimated annual contribution: about ¥1,092,000 (¥5,460,000 of scheduled invoices × the 20% margin you entered)." |
| Refuses | "Foshan generates ¥1.09M" or any observed-tense verb, unless both inputs are observed. A contribution next to a deal without its inputs one disclosure away. |

### 1.4 Concession as a share of contribution over the mandate's forward horizon (MVP)

| | |
| --- | --- |
| Definition | `share = C / K_H` (an exact Fraction). C = the verdict's `forward_concession_total_fen` (already posted; contingent concessions at maximum, INVARIANT 5). K_H = contribution over the same window W = [today, today + H), H = `mandate.forward_concession_horizon_days`. If sales are PROJECTED, K_H is the contribution of the very invoices in W. If sales are trailing or annual, K_H = sales × margin × H / 365 exactly (no intermediate rounding; with H = 365 it is the annual contribution). Defined only when K_H > 0. |
| Units | exact Fraction. The API carries `concession_share_bp = post(share × 10,000)` for `displayed()` (2 dp) plus a server-written headline string |
| Horizon | W, the concession's own window; printed ("over the next 12 months") |
| Rounding | Comparisons on the exact fraction. Headline 1 dp half-up ("2.6%"); evidence 2 dp ("2.59%"). A positive share that rounds to 0.0 shows "under 0.1%"; one above 999.9% shows "more than 10 times". |
| Shows (after the verdict, never before it) | "Outside your autonomous limit (¥5,000 of concessions over 12 months). This request costs ¥28,326.92 over the next 12 months, about 2.6% of the ¥1,092,000 a year we estimate Foshan contributes. Owner review recommended." |
| Refuses | Any wording that turns the share into permission ("small against Foshan's value, so acceptable"). A share on mismatched windows. A share of a zero or negative contribution. A share when the margin is missing. Anything that changes outcome, tier, counters or codes (property P8). |

### 1.5 Working-capital-adjusted contribution (mission §5): mostly future

Every component is shown **beside** contribution as its own line, never silently netted. The adjusted total appears
only when every component is observed or derived from the books. A component resting on a guess is shown alone and
labelled.

| Component | Formula (one place) | Data | Phase |
| --- | --- | --- | --- |
| Forward concessions already committed to the buyer | Σ `state.forward_concessions[counterparty].value_fen` (booked at maximum at acceptance) | books: DERIVED | **MVP** (a plain sum, already canonical) |
| Accepted terms and price adjustments in force | already inside the invoices' contractual face and terms (ADR-0009); listed, not re-valued | books | **MVP** (listed) |
| Early-payment discounts given in the trailing 12 months | Σ `agreed_discount_fen` of MATCHED receipts (`app/alerts/reconcile.py`) | log: INVOICE_HISTORY | **future** (Phase 2, with payment history) |
| Financing cost of the contractual terms | Σ over invoices in W of face × terms × r / 365, r = the marginal tariff (`_terms_extension`'s formula with Δ = terms) | books + DERIVED rate: ESTIMATED (the marginal tariff is a planning rate, not a posted cost) | **future** |
| Financing cost of observed late payment | Σ over invoices in W of face × median days late × r / 365 | needs ≥ 3 completed invoices (§5) | **future** |
| Service cost, returns, bad-debt expectation, relationship effort | none | no data | **excluded** (mission §5: never invented) |

The Demo illustration is in §8.6. Kill criterion (mission §51): if the margin is an owner guess, the adjusted total is
false precision. The MVP shows contribution and the committed concessions; the adjusted total waits for observed inputs.

### 1.6 Consistency checks FLOW runs before showing a contribution (MVP, cheap)

1. **Books versus owner.** If owner-entered annual sales differ by more than 10% from the projected invoices in W (or
   the trailing observed sales), both are shown: "You entered ¥2,000,000 a year for Foshan. Your books schedule
   ¥5,460,000 of invoices to Foshan over the next 12 months. FLOW uses ¥5,460,000 and shows yours beside it." Which one
   wins is owner question Q2.
2. **EBITDA bound.** When a customer's contribution is below annual EBITDA (12 × `monthly_ebitda_fen`), and that customer
   holds every invoice in the books, the sales or margin cannot both be right: "Foshan is the only customer with invoices
   in your books, but its estimated contribution (¥400,000) is below your company's annual EBITDA (¥1,080,000). Check
   Foshan's sales or margin."
3. **VAT.** If the sales are invoice-derived and the margin is from accounts: "Sales include VAT; the margin does not.
   FLOW divides by 1.13 before applying it."

## 2. Provenance: the enum, the wording each label earns, the derived rule

| Label | Meaning | Observed? | Wording it earns (en) | zh |
| --- | --- | --- | --- | --- |
| ACCOUNTING_HISTORY | imported statements or filing, a closed period | yes | "from your 2025 accounts" | "来自您2025年账目" |
| ERP | an imported system export, dated | yes | "from your ERP export of 30 Sep" | "来自您9月30日的ERP导出" |
| INVOICE_HISTORY | receivables and receipts in FLOW's own books and log | yes | "from the invoices in FLOW (12 months to 30 Sep)" | "来自FLOW中的发票（截至9月30日的12个月）" |
| OWNER_ENTERED | typed by the owner, dated, attributable | no | "as you entered it on 10 Oct" / "your estimate" | "您于10月10日录入" / "您的估计" |
| PROJECTED | forward from the books' schedules (recurring invoices, expected orders) | no | "as your books schedule it (¥420,000 every 30 days)" / "if Foshan keeps buying as scheduled" | "按您账上的排期" |
| ESTIMATED | an assumption no one observed: a firm average applied to one customer, a demo seed, a planning rate | no | "an estimate:" / "about" / "we estimate" | "估计" / "约" |
| DERIVED | FLOW computed it from labelled inputs | inherits | the sentence names the weakest input: "estimated from the margin you entered" | "根据您录入的毛利估算" |

Rules:
- **Rank, best first:** ACCOUNTING_HISTORY = ERP > INVOICE_HISTORY > OWNER_ENTERED > PROJECTED > ESTIMATED.
- **A DERIVED figure** carries `inputs: [label...]` and `weakest`.
- **Tense follows the weakest input.** When `weakest` is not observed, the sentence contains "estimate", "about" or
  "you entered", and never an observed-tense verb such as "generates", "is", "paid" or "earned" (property P2).
- **Observed outranks owner-entered.** Where an observed figure meets the minimum (§5 for payments, the 12-month
  coverage rule for sales), it is used. The owner's figure is shown beside it only if they differ by more than 10%
  (sales) or 5 days (delay).
- **Demo-seeded figures are ESTIMATED,** with "Demo assumption" in the sentence, never OWNER_ENTERED. Nobody entered them.
- **Stored with every figure:** `provenance`, `source_ref` (file, log seq, or entry id), `as_of_day`, `window` and,
  for owner entries, `entered_by` and `entered_day`. Where owner-entered customer inputs live (not in `FinancialState`,
  which holds cash truth) is Q8.

## 3. Edge cases of mission §36: exact wording

Concession for the examples: ¥28,326.92 over 12 months (EX01). Buyer: Foshan.

| # | Case | FLOW shows | FLOW refuses to show |
| --- | --- | --- | --- |
| 1 | Negative margin (−5%) | "On the margin you entered (−5%), Foshan's sales lose about ¥273,000 a year before fixed costs. This request adds ¥28,326.92 over 12 months to that. FLOW cannot show it as a share of a contribution that is negative." | any percentage of contribution; "small"/"large" |
| 2 | Zero margin | "On the margin you entered (0%), Foshan's sales add nothing before fixed costs, so this request cannot be shown as a share of contribution. It costs ¥28,326.92 over the next 12 months." | "0%", "infinite", a division |
| 3 | New customer, no history and no entry | "FLOW has no invoices from Foshan yet and no annual sales entered. The request costs ¥28,326.92 over the next 12 months. Enter Foshan's expected annual sales and margin to see it against Foshan's contribution." | any sales or contribution figure |
| 4 | Three months of history | "Foshan's invoices in FLOW cover 3 months (¥1,260,000 since 10 Jul). FLOW does not multiply that up to a year. Your books schedule ¥5,460,000 over the next 12 months; FLOW uses that, labelled as scheduled." | "¥5,040,000 a year" from ×4; "observed annual sales" |
| 5 | Seasonal (12 months observed, largest month more than twice the smallest; or a flat schedule) | Observed: "Foshan's last 12 months include a peak of ¥900,000 (Nov) and a low of ¥150,000 (Jun); the share uses the full year." Flat schedule: "Your books schedule Foshan at a flat ¥420,000 a month; if Foshan buys seasonally, enter its annual sales." | a monthly figure × 12 presented as the year |
| 6 | Large revenue, tiny contribution (1%) | "Foshan buys ¥5,460,000 a year as scheduled, but on the 1% margin you entered contributes about ¥54,600. This request is 51.9% of that." | "large customer", "important", revenue as a proxy for value |
| 7 | Good contribution, terrible payer | Two separate facts: "Estimated contribution: about ¥1,092,000 a year." and "Foshan paid its last 8 invoices a median 34 days late (from your receipts)." The stress test follows (§6). | one blended "customer score"; a late-payment cost netted into contribution in the MVP |
| 8 | Multiple currencies | "FLOW works in yuan. Enter Foshan's sales in yuan; FLOW does not convert currencies." (The compiler already abstains on a non-yuan amount, `docs/FINANCIAL_SEMANTICS.md:106`.) | any FX conversion |
| 9 | Missing margin | "Enter a margin for Foshan to compare this request with what Foshan contributes. Without it, FLOW shows the cost alone: ¥28,326.92 over the next 12 months." If accounts hold a firm average: "Your company's average gross margin is 23.76% (2025 accounts). Use it for Foshan? It is not Foshan's own margin." The firm average is used only after a click, and labelled ESTIMATED. | a silent default margin |
| 10 | Estimated versus observed sales disagree | "You entered ¥2,000,000 a year for Foshan; FLOW's invoices show ¥4,980,000 in the 12 months to 30 Sep. FLOW uses the invoices." (observed outranks owner-entered) | the owner figure as if confirmed; a quiet average of the two |
| 11 | Aggregate counterparty ("Other buyers (aggregate)" in the public SME) | "Other buyers (aggregate) is a group, not one customer: it is left out of customer concentration." | a 48.6% "customer concentration" |
| 12 | Contribution share > 100% | "This request costs more over 12 months (¥28,326.92) than Foshan's estimated contribution in that time (¥20,000)." | "141.6%" as a headline |

## 4. AR concentration

**Shared rules.**
- **Four shares, never combined into one score** (mission §17). Each is a buyer's part of a firm total, an exact
  Fraction in [0, 1].
- **Display:** 1 dp half-up; "100%" only when the share is exactly 1; "over 99.9%" or "under 0.1%" when rounding would
  hide that. Σ over buyers = 1 exactly. Rounded parts may not add to 100.0%, and nothing is adjusted to make them.
- **Aggregate counterparties are excluded** from per-customer statements but stay in the totals. This needs a
  `Counterparty.aggregate` flag or a naming rule (Q9).

| Metric | Definition | Source and label | Zero denominator | Phase |
| --- | --- | --- | --- | --- |
| Share of current AR | Σ `outstanding_fen` (face − settled) of the buyer's OPEN or FINANCED receivables, ÷ the same over all buyers. FINANCED invoices count (the buyer still owes them; the advance is the owner's liability). Overdue invoices count (they are AR). Unissued recurring invoices do not. | books, as of today: INVOICE_HISTORY (observed) | "No invoices are open, so there is no receivables concentration to show." | **MVP** |
| Share of next 30 days' receipts | Σ of the buyer's RECEIPT and EARLY_RECEIPT events on days [today, today + 30) in the CONSERVATIVE projection of current books (read from the engine's events, as `_books_due_days` does; no second date formula), ÷ all buyers' events in that window. Overdue invoices are absent (the engine counts no receipt from them). | PROJECTED (conservative) | "No customer receipts are due in the next 30 days." | **MVP** |
| Share of annual sales | the buyer's annual sales ÷ the firm's: ACCOUNTING_HISTORY revenue, or Σ of every buyer's figure, all from one source and window. If any buyer with invoices has no figure, the share is not shown. | weakest of the inputs | as above | **MVP** if all figures exist, else omitted with "Annual sales are not known for every customer, so Foshan's share of sales is not shown." |
| Share of annual contribution | the same with contributions; needs every customer's margin | DERIVED; usually ESTIMATED | as above | **future** (rarely all present) |

**Concentration affects context, not the mandate (mission §18).** Concentration may do three things only:
- add a fact line to the verdict;
- order which buyer's stress appears first;
- raise the attention level of an existing alert's wording.

It never changes the outcome, tier, counters, codes, caps or plan (property P8). A rule that did would have to be a
signed mandate field the owner adds (#89, Q4).

| Shown | Refused |
| --- | --- |
| "Foshan is 100% of your open receivables (¥420,000)." | "Foshan is critical, so FLOW recommends accepting." |
| "Foshan is 100% of the receipts due in the next 30 days." | "High concentration: FLOW will not…" (unless a signed rule says so) |

## 5. Payment behaviour from RECEIVE_PAYMENT history

### 5.1 The observation

**Replay.** The log is replayed in order, as `reconcile` does (`app/alerts/reconcile.py:1-30`, `_match` at 115). Only
EXECUTED `RECEIVE_PAYMENT` entries count; DUPLICATE and REFUSED entries are ignored.

**Receipt day.** `reported_day` when set, else the entry's day (`app/alerts/ledger.py:37-41`). This is the same rule the
executor and reconciliation use for the early-pay deadline (`app/operations/executor.py:1182`).

**Due day.** The invoice's contractual due day in force (`issue_day + terms_days` after ADR-0009 adjustments; not
`base_terms_days`). A buyer who agreed 60 days and paid on day 60 paid on time.

**Each receipt settles a portion of face.** The receipt amount, or the solved early-pay portion P. Signed lateness of a
portion = receipt day − due day.

**Portions excluded from lateness:**
- portions matched to an agreed early-payment obligation. They are a deal, not payment discipline, and are counted
  apart: "paid early under agreement: N times, all on time / M missed";
- receipts outside the trailing 365 days.

**Unit: a completed invoice** (status SETTLED, every receipt in the log, its last receipt in the trailing 365 days).
For each completed invoice i:
- `L_i` = face-weighted mean of its portions' signed lateness. An exact Fraction, so partial receipts count by amount.
- `last_i` = last receipt day − due day. Fully paid on time when `last_i ≤ 0`.
- **Financed invoices are included.** The buyer paid; that the lender was paid first is the owner's matter.
- **Open overdue invoices are not completed.** Each is listed beside the statistics as "open, N days overdue so far"
  (a lower bound, censored).

### 5.2 Statistics

| Statistic | Definition | Minimum completed invoices |
| --- | --- | --- |
| Average days late | mean of max(0, `L_i`): early payment never offsets lateness | 3 |
| Median, P75, P90 days late | nearest-rank on max(0, `L_i`) (no interpolation: the value is one observation) | median 3, P75 4, P90 10 |
| On-time share | count with `last_i ≤ 0` ÷ n, shown with the counts ("7 of 9"), and by face as a second figure | 3 |
| Maximum recent delay | max `last_i` over invoices completed in the last 90 days, and today − due of any open overdue invoice ("at least") | 1 (it is a single fact, labelled) |
| Trend | median of the 6 most recent completed invoices against the 6 before; "later", "earlier" or "about the same" (difference under 5 days) | 12 |

**Rounding.** Days are integers per portion. Averages and weighted means are exact Fractions, displayed in whole days,
half-up. Shares are displayed to 0 dp beside the counts.

**Survivorship.** If any open overdue invoice's days-so-far exceeds the P75 (or the median, below 4 invoices), the
sentence adds "these figures may understate how late Foshan pays: RCV-A is already 40 days overdue."

**Below the minimum** (the sentence FLOW shows): "FLOW has 1 completed payment from Foshan in the last 12 months, too few
to say how Foshan usually pays. The stress test uses your contractual dates and a 30-day delay." No average, median or
percentile is shown, and no "typical" scenario is built.

**Observed outranks owner-entered.**
- An owner figure ("Foshan is usually 15 days late") is OWNER_ENTERED. It is used for the typical scenario only while
  completed invoices < 3: "Typical delay: 15 days, your estimate (FLOW has too few receipts to measure it)."
- From 3 completed invoices up, the observed median replaces it. The owner's figure reappears only if it differs by 5 or
  more days: "You estimated 15 days late; Foshan's last 6 payments were a median 4 days late."

**Shown:** "Foshan paid its last 9 invoices a median 11 days late (from your receipts); 2 of 9 on time; the latest
delay was 19 days."
**Refused:** "Foshan usually pays 11 days late" from fewer than 3 invoices; a percentile from fewer than its minimum;
"reliable payer"; any probability of default.

## 6. Late-payment stress: labelled copies of the books

### 6.1 The three scenarios

Each scenario is a `ScenarioState` (`app/strategy/types.py:26-34`: `hypothetical=True`, an `assumption` sentence, the
source state version) read through `read_books` / `marginal_impact` (`app/strategy/impact.py:159-206`). So each one
reports the same quantities, from the same functions as every other strategy figure:
- lowest closing cash before funding, and its day;
- first breach day and breach days;
- the committed plan's need and cost;
- needs owner, executable now, or no admissible plan.

| Scenario | Delay D on the buyer's receipts | Assumption sentence |
| --- | --- | --- |
| Contractual | 0: current books, no copy | "Every Foshan invoice paid on its contractual due day." |
| Typical | observed median days late (§5), whole days. Not built below the minimum. With an owner estimate and fewer than 3 completed invoices: that estimate, labelled. A median of 0: not built; FLOW says "Foshan usually pays on time." | "Assumes Foshan pays 11 days late, its median over the last 9 invoices." |
| Stressed | 30 days, the mission's figure and an owner policy (Q5). Or the observed P90 when there are 10 or more invoices and it is larger. | "Assumes Foshan pays every invoice 30 days late. A test, not a forecast." |

### 6.2 The no-double-count rule

Each moved receipt leaves its contractual day and lands once, on due + D, for its **outstanding** amount
(face − settled). Concretely:
- **The settled part never moves.** It is history.
- **Count per invoice.** For every moved invoice, the number of RECEIPT events with its ref is 1 in both copies, the
  amount is equal and the day differs by exactly D, over a horizon long enough to hold both.
- **Past the horizon.** A receipt pushed past the horizon leaves the projection, and the sentence names it: "¥420,000
  (the invoice issued on day 62) moves past the 120-day horizon."
- **Books untouched.** The books' own state is unchanged (it is a `model_copy`).

### 6.3 Edge cases of mission §39

| Case | Rule in the stress copy | Sentence |
| --- | --- | --- |
| Partial receipts | only the outstanding residual moves | "The ¥291,400 still owed on RCV-A moves; the ¥128,600 already paid stays." |
| Already overdue invoices | not moved and not re-added in any scenario: the conservative projection already counts nothing from them (`app/financial/trajectory.py:914-916`), and adding them back on a stressed day would make the stress look better than the base (INVARIANT 11) | "RCV-A is already 2 days overdue; no scenario counts on it." |
| Live early-payment agreement on a moved invoice | the buyer who pays late is assumed not to pay early: the obligation is treated as lapsed on the copy, the whole outstanding moves to due + D, and no discount is earned (an early-pay discount is earned only on or before the promised day, `docs/FINANCIAL_SEMANTICS.md:31`) | "Assumes Foshan also misses the early payment agreed for day 2." |
| The buyer's own early-payment facility (lender = the buyer) | removed from the stress copy | "FLOW does not count on an early payment from a buyer assumed to pay late." |
| Financed invoices | the advance is repaid by the owner on the contractual due day (recourse, the convention ADR-0006 already uses for an overdue financed invoice, `docs/adr/0006-current-books-and-clock.md:97-98`); the buyer's cash lands on due + D. Today `scenario_received` refuses a later receipt on a financed invoice (`impact.py:107-108`), and expressing recourse-then-receipt needs an engine affordance (Q6). MVP fallback: not moved, and said. | "RCV-B is financed: the lender is repaid on its due day and Foshan's cash comes 30 days later." (or MVP: "RCV-B is financed; its delay is not modelled.") |
| Financing eligibility of a moved invoice | must stay the contractual due day. Moving `terms_days` on the copy (`impact.py:81-88`) would let the router finance it up to the stressed day: optimistic. Needs a receipt-day field on the copy that the engine reads for the receipt only (Q6). MVP fallback: report the plan with "assumes the platform still finances invoices that are late". | |
| Several receipts and recurring invoices | every open, not-yet-due invoice of the buyer, and every recurring invoice issued inside the horizon, moves by the same D (a uniform delay, stated) | "Assumes all 4 Foshan invoices in the next 120 days arrive 30 days late." |
| Combined with a candidate package | the package is applied first (verifier or what-if, on the real books), then the delay to the result. A package is never evaluated on a delay copy: terms in force would read 45 + D. | |
| Non-payment (explored, not MVP) | a fourth scenario: the invoice FAILED on the copy; a financed one is repaid by the owner on its due day | "Assumes Foshan never pays RCV-A." |

**Sentence (mission §19 shape):** "If Foshan pays 30 days late (a test, not a forecast): cash falls to −¥250,000 on day 60
before funding, below your ¥300,000 minimum on 65 days, and your committed facilities cannot cover the ¥550,000
shortfall."
**Refused:** "Foshan will pay late"; any probability; a typical scenario without history; a stress that adds an
overdue receipt back.

## 7. Property tests (mission §46) that apply

Randomise: sales, margin (−10,000 to 10,000 bp), basis, provenance, buyers (1 to 8), receivables (face, issue, terms,
settled, status), recurring invoices, facilities, delays (0 to 60), receipt histories (amounts, days, partials, agreed
early-pay portions, refused and duplicate entries).

| Id | Invariant |
| --- | --- |
| P1 | `contribution_fen == post(Fraction(sales) × margin_bp / 10000)`; its sign equals the margin's; posted exactly once (no intermediate rounding when VAT or H/365 scaling apply). |
| P2 | Provenance: a DERIVED figure's `weakest` is the lowest-ranked input. If `weakest` is not observed, every sentence about it matches /estimate\|about\|you entered\|scheduled/ and none matches an observed-tense verb list. Demo seeds are never OWNER_ENTERED. |
| P3 | Share: `share × K_H == C` exactly; defined iff K_H > 0; scaling sales by k divides the share by k; the headline shows "100%" only when the share is exactly 1, never "0.0%" for a positive share. |
| P4 | C is byte-identical to the verdict's `forward_concession_total_fen` (differential test: customer.py never values a concession). |
| P5 | Projected sales count exactly the invoices `recurring_issue_days(window(state, H))` returns, the same list a perpetual-scope extension values (13 on the Demo at H = 365). |
| P6 | AR concentration: each share in [0, 1]; Σ over buyers == 1 exactly when total AR > 0; one buyer gives 1; zero AR gives "not shown" (no division); adding a receivable to X never lowers X's share; a settled receivable changes nothing; a partial receipt counts only the outstanding face. |
| P7 | 30-day receipts share: read from the projection's events; Σ == 1; a receipt on day today + 30 is outside, on today + 29 inside; an overdue invoice never contributes. |
| P8 | **Mandate independence:** for any customer economics, concentration or payment statistics, the verdict's outcome, tier, codes, counters, `forward_concession_total_fen` and the plan are byte-identical with the feature on and off. Customer value never bypasses owner authority (mission §45, §46). |
| P9 | Payment statistics: average days late ≥ 0 (early never offsets late); adding an on-time completed invoice never raises the median; refused and duplicate entries change nothing; agreed early-pay portions never enter `L_i`; for an invoice paid in portions `L_i` equals Σ(portion × lateness) / face; below 3 completed invoices no statistic field is present; reordering receipts on different invoices changes nothing. |
| P10 | **Stress moves, never duplicates:** for every moved invoice, exactly one RECEIPT event in each copy over the extended horizon, same amount, day + D; Σ of the buyer's receipts over the extended horizon is equal; the books' state hash is unchanged; D = 0 reproduces the contractual reading exactly. |
| P11 | Unfunded closing cash is pointwise non-increasing in D for invoices that are not financed (cumulative inflows by any day can only fall); funding cost is **not** asserted monotone. |
| P12 | No scenario adds an overdue receipt back; no stress copy contains a facility whose lender is the stressed buyer; no live early-pay obligation on a moved invoice survives in the copy. |
| P13 | Customer loss (shared with #93): removes the buyer's recurring invoices and expected orders in W exactly once; open receivables stay; contribution foregone == K_H. |
| P14 | INVARIANT 13: the web reads only `_display`, `text` and sentence fields of these answers (the existing pattern: a grep test over the web client for arithmetic on `_fen` and `_bp` fields). |

## 8. Worked example: the Demo books (golden SME, Foshan Home Retail, BUYER-1)

### 8.1 Inputs (file:line, `fixtures/scenarios/golden_sme.json` unless named)

| Input | Value | Where |
| --- | --- | --- |
| Cash day 0 | 40,000,000 fen | :5 |
| Payroll, supplier, bill | −34,000,000 day 12; −12,000,000 day 20; −10,000,000 day 47 | :9-10, :18-20, :27-28 |
| RCV-A | 42,000,000, issue −13, terms 45, so due 32, OPEN | :37-42 |
| Recurring | 42,000,000 every 30 days from day 2, terms 45 | :48-52 |
| FAC-LINE | limit 15,000,000 at 640 bp | :63, :66 |
| FAC-IF | limit 35,000,000, advance 8,000 bp, 780 bp + 25 bp per 30 days | :115-120 |
| FAC-EARLYPAY | lender BUYER-1, 120 bp, lead 2 days | :133-146 |
| Expected order | 40,000,000 "next quarter" days 92 to 182, not firm | :291-297 |
| Buyers | BUYER-1 Foshan; BUYER-2 Dongguan, with no receivable | :301-311 |
| Monthly EBITDA | 9,000,000 | :344 |
| Mandate | min cash 30,000,000; concession cap 500,000; H 365; horizon 120 | :350-352, :361 |
| EX01 request | 60-day terms + 1% off next quarter + early pay at 1.2%; `forward_concession_total_fen` 2,832,692 | `fixtures/offers/offers.yaml:8`, `:13` |
| **Margin** | **does not exist anywhere in the fixtures.** Assumed 20% (2,000 bp), the mission's figure, labelled ESTIMATED ("Demo assumption") | none |
| **Annual sales** | **no 12-month history:** the earliest invoice is issued on day −13. Derived as PROJECTED from the recurring invoice | — |

### 8.2 Annual sales (PROJECTED)

- **Window.** W = [0, 365). Issue days from `recurring_issue_days` (`concessions.py:100-107`): 2, 32, …, 362, which is
  13 invoices. RCV-A was issued on day −13, outside W, and is AR, not future sales.
- **Sum.** 13 × 42,000,000 = **546,000,000 fen = ¥5,460,000.00**.
- **Alternatives, not used:**
  - run rate 42,000,000 × 365/30 = 511,000,000 (¥5,110,000);
  - 12 × monthly = 504,000,000 (¥5,040,000).

  Both count a different number of invoices from the concession (P5).
- **Trailing observed** (INVOICE_HISTORY): RCV-A only, ¥420,000 over 13 days of books. Not usable; FLOW says so
  (§3, case 4).

### 8.3 Contribution (DERIVED; weakest input ESTIMATED)

post(546,000,000 × 2,000 / 10,000) = **109,200,000 fen = ¥1,092,000.00**.

### 8.4 The EX01 concession and its share

**Extension cost.**
- The marginal rate is FAC-IF's: r = 780/10,000 + 25/10,000 × 365/30 = 1,301/12,000 (10.8417%).
- 15 days on each of the 13 invoices: 13 × 42,000,000 × 15 × 1,301 / (12,000 × 365) = 177,586,500/73
  = 2,432,691.78…, posted **2,432,692**. (Per invoice 187,130, ¥1,871.30, matching `docs/FINANCIAL_SEMANTICS.md:94`.)

**Rebate.** 1% × 40,000,000 = **400,000**: contingent, so counted at maximum (INVARIANT 5).

**Total.** C = **2,832,692 fen = ¥28,326.92**, which equals `offers.yaml:13`. The cap is 500,000, so the request is outside
the autonomous limit.

**Share.**
- 2,832,692 / 109,200,000 = 0.0259404…: `concession_share_bp` = **259**, headline **"2.6%"**, evidence "2.59%".
- On the mission's illustrative ¥2,000,000 × 20% = 40,000,000: 2,832,692 / 40,000,000 = 0.0708173 = "7.1%".
  That is reproducible only by seeding sales that contradict the books.

**Sentence.** "Outside your autonomous limit (¥5,000 of concessions over 12 months). This request costs ¥28,326.92 over
the next 12 months, about 2.6% of the ¥1,092,000 a year we estimate Foshan contributes (¥420,000 every 30 days as your
books schedule it × a 20% margin, a Demo assumption). Owner review recommended."

### 8.5 Consistency checks

- **EBITDA.** Annual EBITDA is 12 × 9,000,000 = 108,000,000 (¥1,080,000). Foshan holds every invoice in the books, so
  the margin must be at least 108,000,000 / 546,000,000 = 19.78%. The 20% assumption passes, narrowly.
- **The mission's figures fail.** ¥2M × 20% = ¥400,000 < ¥1,080,000 triggers the §1.6 check. Seeding ¥2M would also
  trigger the >10% books-versus-owner check (¥2,000,000 against ¥5,460,000).

### 8.6 Working-capital adjustment (future; illustration only)

- **Carrying cost of the 45-day terms on the 13 invoices:**
  post(13 × 42,000,000 × 45 × 1,301 / (12,000 × 365)) = **7,298,075 fen = ¥72,980.75** (ESTIMATED: the marginal
  tariff is a planning rate).
- **Committed concessions:** 0 (`forward_concessions` is empty, :289).
- **Late-payment cost:** not measurable (no history).
- **Illustrative adjusted figure:** ¥1,092,000.00 − ¥72,980.75 = ¥1,019,019.25. Not shown in the MVP (§1.5 kill
  criterion: the margin is an assumption).

### 8.7 Late-payment stress on the day-0 books

The script copies the books and moves BUYER-1's open, not-yet-due receivable and its recurring invoices. It then reads
the CONSERVATIVE projection over the 120-day horizon (lowest cash before funding) and the COMMITTED plan.

| Scenario | Lowest cash before funding | First breach | Breach days (< ¥300,000) | Plan need | Plan cost | Plan |
| --- | --- | --- | --- | --- | --- | --- |
| Contractual | −¥105,000.00, day 30 | day 12 | 20 | ¥405,000.00 | ¥3,113.93 | line ¥150,000 + invoice finance ¥255,000; Tier 1 |
| +11 days (an illustration only: there is no history, so FLOW would not build a "typical" case) | −¥105,000.00, day 30 | day 12 | 42 | ¥405,000.00 | ¥6,070.07 | same legs, now needs the owner |
| Stressed +30, buyer's own early-pay facility kept (wrong) | −¥250,000.00, day 60 | day 12 | 65 | ¥550,000.00 | ¥6,488.98 | line + **EARLY_PAY ¥404,858.30 from Foshan**; cannot run today |
| **Stressed +30, buyer's facility removed (the rule of §6.3)** | **−¥250,000.00, day 60** | day 12 | **65** | **¥550,000.00** | — | **no admissible committed plan** |

**Receipts.**
- Contractual: RCV-A day 32, RI:BUYER-1:2 day 47, RI:BUYER-1:32 day 77, RI:BUYER-1:62 day 107, each ¥420,000.
- +30: the same receipts on days 62, 77, 107 and **137**. The last is beyond the horizon, so the in-horizon receipts
  fall from ¥1,680,000 to ¥1,260,000. A 400-day run shows each of the four receipts exactly once, shifted by 30 (P10).

**What this shows.** The lowest-cash figure alone hides the +11 effect: the trough is the day-12 payroll, before any
Foshan receipt. The informative figures are breach days, cost and the owner flag.

**Sentence.** "If Foshan pays 30 days late (a test, not a forecast): cash would fall to −¥250,000 on day 60 before
funding, below your ¥300,000 minimum on 65 days, and your committed facilities cannot cover the ¥550,000 shortfall.
FLOW does not count on an early payment from Foshan in this test."

### 8.8 Concentration and payment behaviour

| | Day 0 | Day 34 (Demo path after the half receipt, `apps/web/mocks/home_reconciliation_day34_half.json`) |
| --- | --- | --- |
| Share of current AR | 42,000,000 / 42,000,000 = **100%**: "Foshan is 100% of your open receivables (¥420,000)." | (29,140,000 + 42,000,000 + 42,000,000) = 113,140,000, all Foshan: **100%** (:39-40, :49, :58) |
| Next 30 days' receipts | none in [0, 30) (RCV-A due 32; RI:2 due 47): "No customer receipts are due in the next 30 days." | [34, 64): RI:BUYER-1:2 day 47, ¥420,000: **100%**; RCV-A is overdue and not counted |
| Share of annual sales | Foshan is the only customer with invoices; BUYER-2 has none and no figure: "Foshan is the only customer with invoices in your books." | same |
| Share of contribution | not shown (no margin for anyone else) | same |
| Payment behaviour | no receipts: "FLOW has no payments from Foshan yet to measure how it pays." | One receipt on day 2: ¥127,506.90 settling ¥128,600 under the agreed 0.85% early payment (:8, :11, :13). It is excluded from lateness. Completed invoices 0: "FLOW has no completed payments from Foshan in the last 12 months, too few to say how Foshan usually pays. One agreed early payment arrived on time (day 2). ¥291,400 of RCV-A is 2 days overdue." |

### 8.9 A second check on the public-record SME (where accounting history exists)

- **Buyer A 2025 sales (ACCOUNTING_HISTORY):** ¥22,866,510.19, 21.78% of revenue ¥105,009,214.00
  (`public_sme.SOURCES.md:70`, `:19`).
- **Firm gross margin:** (105,009,214.00 − 80,055,781.69) / 105,009,214.00 = 23.763%, using 营业成本 at `:112`. It is
  firm-level, so applied to Buyer A it is ESTIMATED. Buyer A's estimated gross contribution: exact product
  543,378,902.15 fen, posted ¥5,433,789.02, "probably higher on a contribution basis".
- **AR shares** (total 3,706,094,754 fen):

  | Buyer | Share |
  | --- | --- |
  | A | 14.56% |
  | B | 14.57% |
  | C | 9.13% |
  | D | 6.88% |
  | E | 6.22% |
  | Other buyers (aggregate) | 48.63%, excluded from per-customer statements (§3, case 11) |

  The shares sum to exactly 1.
- **VAT:** the recurring invoices carry 13% VAT (`:98`). Invoice-derived sales would be 1.13 × revenue unless divided
  back (§1.6, check 3).

## 9. Open questions for the owner (grilling, for #89 and #95)

1. **Demo seed.**
   - (a) Use the books' projection, ¥5,460,000, with a 20% "Demo assumption" margin: the share is 2.6%.
   - (b) Change the Demo books to make the mission's ¥2M and 7.1% true.
   - (c) Seed ¥2M and let FLOW show the contradiction.

   Recommended: (a).
2. **Owner-entered versus the books' projection,** when they disagree by more than 10%: which does FLOW use for the share?
   (Recommended: observed history > owner > projection, with both shown.)
3. **Gross or contribution.** Do you think in 毛利率 or contribution? May FLOW accept either, labelled, and say which
   direction gross errs?
4. **Is VAT inside your invoices,** and should FLOW divide it out before applying a margin?
5. **Stressed delay:** a fixed 30 days, your own policy figure, or the observed P90 when larger?
6. **The engine.** The engine is in stability mode. May it gain one scenario-only affordance: a receipt day separate from
   the contractual due day, plus recourse repayment of a financed invoice on its due day? Or should the MVP ship with the
   two stated caveats (financed invoices not moved; the platform assumed to finance late invoices)?
7. **Does the stress remove the stressed buyer's own early-payment facility?** Recommended: yes. Without it, the Demo's
   +30 stress looks fundable by Foshan itself.
8. **Where do owner-entered customer facts live,** and is their entry a logged owner action (attributable, versioned)
   outside `FinancialState`?
9. **Aggregate counterparties.** Mark them explicitly (`aggregate: true`) so they never appear as one customer's
   concentration?
10. **Minimum history:** 3 completed invoices for average and median, 4 for P75, 10 for P90, 12 for a trend, over a
    trailing 365 days. Acceptable?
11. **Working-capital-adjusted contribution:** future only (recommended), or show the committed-concessions line in the
    MVP?
12. **Should the EBITDA consistency check (§1.6) be shown to the owner,** or kept as an internal warning on the seed?
