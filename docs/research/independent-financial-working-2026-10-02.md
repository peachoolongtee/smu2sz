# Independent financial audit working evidence — 2 October 2026

Scope: actual `financial/`, `funding/`, `covenants/`, `capex/`, `books/`, and relevant verifier code read before financial ADRs and golden arithmetic. No prior audit report or NEXT_FIXES/HANDOVER conclusions used. Implementation unchanged. This is evidence for the principal report, not an implementation plan approved by the owner.

Labels: **REPRODUCED** means an independent executable case produced the result; **CODE-INSPECTED** means traced implementation; **INFERENCE** means economic consequence inferred from these facts. Existing test success is not financial validation.

## Actual economic model reconstructed

FinancialState has integer-fen cash, signed dated flows, issued and partially settled receivables, a recurring-invoice forecast, fixed DebtPosition principal/service, Facility drawn balances, and forward concession values. `current_books` adds live commitment obligations. The projection creates invoices, changes their terms/prices, schedules receipts, posts finance cash and charges, then derives monthly ratios. The router evaluates incremental posted interest + fees + discounts against a baseline, with a discrete amount search. It checks daily closing cash and monthly ratios on the full projection for candidate plans.

There are multiple debt representations: fixed `state.debts`, facility `drawn_fen`, projection lots, and executor logged draw lots. There is no shared contractual loan schedule in the FinancialState. Capex separately builds annuities and a fixed baseline debt-service numerator/denominator. The daily projection and capex do not read the same debt balances. A projection is an expected schedule, not an actual bank statement.

## Reproduction command and results

Pure script written to `/tmp/termsledger_financial_audit.py`. Run from `services/api`:

```sh
TERMSLEDGER_NO_DOTENV=1 PYTHONPATH=. .venv/bin/python /tmp/termsledger_financial_audit.py
TERMSLEDGER_NO_DOTENV=1 .venv/bin/python -m pytest tests/financial tests/capex tests/covenants tests/funding/test_properties.py tests/funding/test_differential.py
```

Focused suite: **436 passed, 18 skipped in 74.06 seconds**. The cases below expose assumptions those tests do not establish. No fixture/eval outputs were overwritten. The script uses fixtures for input shape, not expected answers.

### F-FIN-01: gains outside the valuation horizon offset current concessions

**HIGH | FINANCIAL / AUTHORITY | REPRODUCED | BUILD NOW | effort M | regression risk medium | confidence high.**

Evidence: `financial/concessions.py:63-86` counts recurring invoices as `horizon // every_days` without applying `effective_day` for perpetual or invoice-count-bounded changes; `:120-133` values the price gain from that count. Cash projection selects issues after the effective day, so valuation and cash disagree.

Reproduction: golden recurring face ¥420,000/every 30 days. Firm +1% price adjustment effective day 1000; 365-day horizon. `value_concessions` reports **−¥50,400** gain. Projected cash change through day 365 is **¥0**. Add a ¥6,000 rebate and a ¥5,000 aggregate forward cap: `check_concession_caps` reports no breach because the nonexistent in-horizon gain offsets the cost. Script output: `FUTURE_GAIN_OFFSET [-5040000, 600000] cash_increment_by365 0 cap5000_pass True`.

Business consequence: cap headroom and autonomous commitment size can be overstated using gains from another period. Hackathon consequence: a typed offer can defeat the financial cap while the presentation says it uses a 365-day valuation. Full natural-language compilation of this precise day-1000 case was not tested; the reachable typed valuation/cap path is reproduced.

Fix: derive affected invoice IDs, dates and amounts once from the same obligation binding used by projection. Define whether valuation follows invoice issue or cash collection inside `[as_of_day, as_of_day + horizon]`; prevent any offset without qualifying evidenced, dated cash flows on that basis. Test delayed effective dates, today > 0, bounded counts, late start, and simultaneous existing/new obligations.

### F-FIN-02: rolling projection posts debt payments into already closed days

**HIGH | FINANCIAL / EXECUTION | REPRODUCED | BUILD NOW | effort L | regression risk high | confidence high.**

Evidence: `financial/trajectory.py:604-611` calls `_amortise(f, 0, drawn_fen)` and dates bullet maturity at `30 * term_months`, even with nonzero as_of_day. Unlike ordinary flows (`:701-706`), these postings are not excluded before today.

Reproduction: as_of_day 61, actual cash ¥1,000,000, zero-rate drawn amortising principal ¥120,000, term 12 months. A projection posts ¥10,000 payments on days 30 and 60, and reports **cash at today ¥980,000**. Those closed days must already be represented by state.cash_fen. Requested 30-day horizon also becomes day 361. Script output `CARRIED_AMORT` includes the two past payments.

Business consequence: current cash/debt is silently changed by a forecast; a plan can be rejected or sized from invented past obligations. For bullets whose synthetic maturity is before today, the projection also treats them as repaid in the past. The parent audit separately traces the clock not servicing scheduled debt.

Fix: persist each draw's settlement date, remaining principal, interest/accrual basis and contractual payment schedule; project only unpaid dated movements from today. Actual receipt/payment transitions and projection must consume the same schedule. For legacy balances without a schedule, mark debt service unknown and prevent autonomous recommendations rather than inventing day 0.

### F-FIN-03: capex drops existing drawn facility debt and service

**HIGH | FINANCIAL / COMPLETENESS | REPRODUCED | BUILD NOW | effort M | regression risk medium | confidence high.**

Evidence: `capex/evaluate.py:94-103` baseline debt/service includes state.debts plus credit-line full limits, but no drawn non-line facilities. `:258-265` uses this baseline for new loan DSCR and leverage.

Reproduction: existing zero-rate 12-month amortising loan drawn ¥1.2m; proposed zero-rate ¥600k loan over 12 months; EBITDA ¥100k/month + uplift ¥20k. Capex reports **DSCR 2.40 and leverage 0.50**, selects NEW. The contractual payments imply **DSCR 0.80** and initial debt / annualised base EBITDA **1.50**. This is not a rounding issue.

Business consequence: recommends investment despite service it cannot cover under the stated ratio. Hackathon consequence: entering a facility draw can improve the apparent capex balance sheet relative to entering equivalent debt in `state.debts`.

Fix: construct every capex structure as dated contractual actions and the purchase over current books, then evaluate the same cash/debt/ratio engine. Do not maintain a second capex baseline. Treat DSCR uplift as EBITDA only if that is the actual meaning of the owner input.

### F-FIN-04: capex cost ordering reverses when fees are included

**HIGH | FINANCIAL / UX | REPRODUCED | BUILD NOW (narrow claim) | effort S to narrow, M for full comparison | regression risk medium | confidence high.**

Evidence: `capex/evaluate.py:247-249` payment and total_interest ignore upfront_fee; `:457-470` selects and explains the minimum nominal interest. Fee affects only the menu tariff screen, not liquidity or cost ranking.

Reproduction: ¥600k / 12 months; ZERO loan has 0% interest and 10% upfront fee; ONE loan has 1% interest and zero fee. With a permissive mandate both are feasible. Capex selects ZERO (interest ¥0) over ONE (interest **¥3,254.95**) while omitting **¥60,000** fee.

Business consequence: calls the much more expensive structure cheapest. Hackathon consequence: a CFO can disprove the recommendation in one calculation.

Fix now: label output “lowest modelled nominal interest among these hypothetical annuity schedules”; remove “cheapest” and “finance with” until all-in contractual cash flows, dates, cash contribution and fees are compared. Next compare PV of all supplier financing outflows at a common valuation date/basis, with upfront fees, lease residual/buyout/return costs and the asset ownership result explicit. Residual/tax features are post-hackathon unless materially present in the offered alternatives.

### F-FIN-05: capex cash+line is called feasible despite prohibited borrowing/APR

**HIGH | FINANCIAL / AUTHORITY | REPRODUCED | BUILD NOW | effort S/M | regression risk medium | confidence high.**

Evidence: `capex/evaluate.py:342-405` calls project and checks reserve plus clean-down; it never calls borrowing/APR or covenant predicates for its generated actions.

Reproduction: committed no-clean-down credit line at 50%, max APR 1%, allow_new_borrowing false; zero initial cash, enough line capacity; cash+line capex result has **feasible=True**. No selected ID because line-financed cost is None, but it is still reported admissible/feasible. The script output `CAPEX_CASH_LINE_RULE_BYPASS` shows the flags.

Business consequence: owner sees feasible finance that mandate forbids and which the other funding comparison rejects. Hackathon consequence: capex breaks the claim that all structures satisfy mandate/covenants.

Fix: one shared action admissibility check; cash+line must pass it and the contractual payment/cash schedule, or be explicitly “liquidity-only scenario, authority/covenants not evaluated.”

### F-FIN-06: perpetual extension valuation changes quadratically with horizon

**HIGH | FINANCIAL | REPRODUCED | BUILD NEXT (NOW before non-365 horizons) | effort M | regression risk medium | confidence high.**

Evidence: `financial/concessions.py:100-109` perpetual cost `face * floor(H/every) * Δ/365 * r * H/365`; bounded cost for identical N invoices `face * N * Δ/365 * r`. At H=365 the extra multiplier cancels and golden tests cannot see it.

Reproduction at 10% funding, face ¥420k, Δ15 days, same invoice count: H90 perpetual **¥1,276.79**, 3 bounded invoices **¥5,178.08**; H180 **¥5,107.15** vs 6 invoices **¥10,356.16**; H365 both **¥20,712.33**; H730 perpetual **¥82,849.32**, 24 invoices **¥41,424.66**.

Business consequence: mandate horizon changes concession decisions for reasons unrelated to economic exposures. Hackathon consequence: changing the horizon shows the same invoices acquiring different cost because the word perpetual changed.

Fix: pick and state one basis. Per-invoice delay funding cost is `Σ face_i * Δ_i * r / 365`. A steady-state structural working-capital estimate is `invoice face * Δ / invoice interval`; its annual funding cost is balance*r and its H-day cost is balance*r*H/365. Do not use sales during H as annual sales then multiply by H again. Actual ramp-up, lead time and whole-period fees require the dated path rather than this approximation.

### F-FIN-07: pro forma monthly service assumes every invoice is monthly

**HIGH | FINANCIAL | REPRODUCED | BUILD NEXT | effort M | regression risk medium | confidence high.**

Evidence: `verifier/evaluate.py:372-380` computes invoice frequency for extra debt but adds one `per_invoice_fen` as monthly service, regardless of frequency. Similar estimates feed capex extension debt.

Reproduction: 10% funding, face ¥420k, Δ15d. Reported extra monthly debt service is always **¥1,726.03**. With invoice intervals of 15/30/60/365 days, consistent annualised monthly costs are **¥3,500.01 / ¥1,750.00 / ¥875.00 / ¥143.84** (using posted per-invoice cost; exact rounding basis should be defined). At 15d service is undercounted by approximately half. Monthly EBITDA remains fixed, so a near-threshold covenant can wrongly pass.

Fix: sum dated incremental charges by covenant period; for a clearly marked steady-state estimate annualise using `365/every_days` then divide by 12. Distinguish invoice-frequency service from a contractual monthly loan payment. Do not reuse forward concession horizon as the borrowing principal basis.

### F-FIN-08: APR and financing tariff are different concepts

**HIGH | FINANCIAL / AUTHORITY / UX | CODE-INSPECTED plus independently calculated | BUILD NOW (rename/define) | effort M | regression risk high | confidence high for arithmetic; contract interpretation requires owner decision.**

Evidence: `funding/rates.py:75-100` IF uses rate + period fee*365/period regardless actual holding days; loans spread upfront fees over facility term, not actual cash dates/outstanding balance; bills show face discount rate; early pay uses cost/net proceeds at actual tenor. `funding/search.py` `action_rate` uses these heterogeneous measures for max_apr.

Example: ¥100k IF for 1 actual day, 30-day minimum billing, 7.8% rate + 0.25% period fee. Cash charges **¥891.10**, tariff **10.8417%**, actual simple annualised cost/net amount approximately **325.2515%**. A maxAPR12% predicate therefore passes the tariff. Even at 29d, realised simple rate ≈11.22%, not10.84%. Upfront-fee loans with early repayment or amortisation also fail same-basis comparison; a bill face-discount rate r corresponds to a net-proceeds yield `r/(1-r*n/365)`.

Business consequence: “maximum APR” is not the actual rate experienced by supplier cash flows. Whether 1-day borrowing should be forbidden is a policy choice, but the displayed/enforced metric must name its basis. Hackathon consequence: straightforward net-proceeds/time calculation contradicts “same basis.”

Fix: retain a labelled contractual tariff for menu comparison; derive action-specific realised simple annualised net cost for single bullets and actual cash-flow IRR for amortising choices. Decide which metric is an autonomy cap, and do not apply an unlabeled number to mixed shapes.

### F-FIN-09: upfront IF fee repeats in break-even estimate

**MEDIUM | FINANCIAL | REPRODUCED | BUILD NEXT | effort S | regression risk low | confidence high.**

Evidence: `rates.py:80` folds one-off upfront fee into a period annual rate, then break_even_cost_share multiplies that rate by every billed period. Ledger `charges.upfront_fee` posts only once.

Reproduction: 1% upfront fee on ¥100k: days1/29/30 estimate matches one billed period; days31/59/60 estimated break-even borrowing cost exceeds actual charges by **¥1,000**; days61/89/90 by **¥2,000**; day91 by **¥3,000**. Script prints the exact series. Tests2/3 of early-pay acceptance may still reject a dear offer, so this is not independently shown to cause wrong acceptance.

Fix: derive break-even cost share from `finance_invoice_charges(P,n) + upfront_fee(P)` and actual net funding; compare without injecting one-off fee into repeated period tariff.

### F-FIN-10: bullet DSCR is a synthetic reserve ratio, not scheduled monthly debt service

**HIGH | FINANCIAL / UX | REPRODUCED | BUILD NOW (narrow covenant claim) | effort M | regression risk high | confidence high, contractual interpretation conditional.**

Evidence: `financial/trajectory.py` `_TermLot` and month_ds spread principal+interest+fees evenly over term although cash leaves at maturity. ADR0008 explicitly chooses this convention. Facility covenant strings remain source evidence, not executable ratio definitions.

Reproduction: ¥500k, 5%, 12mo bullet, EBITDA¥100k, no other debt service. Reported maturity-month DSCR **2.2872×** from synthetic monthly service ¥43,721.47. Contractual maturity cash payment **¥524,657.53** gives monthly scheduled-service ratio **0.1906×**. The daily cash test may independently reject insufficient cash; it does not make the reported covenant definition correct.

Fix: keep an explicitly named “level monthly debt reserve coverage” analytical ratio if wanted. A covenant called monthly scheduled principal+interest must use contractual dated payments. If covenant is annual or rolling twelve months, implement that observation window. Never imply bank covenant compliance from a ratio whose observation window was invented.

### F-FIN-11: effective lease rate is treated as nominal annual / 12

**MEDIUM | FINANCIAL | CODE-INSPECTED / independently calculated | BUILD NEXT | effort S | regression risk medium | confidence high for semantic mismatch.**

`domain/models.py:Facility.rate_bp` states “lease: effective rate”; amortisation/capex divide by12. A stated effective annual7.2% should have monthly rate `(1.072)^(1/12)-1`; dividing7.2% by12 produces effective annual **7.4424168%**. Clarify contract rate convention and regenerate schedules/golden values if effective is intended.

### F-FIN-12: nonpositive EBITDA takes uncaught error paths; negative ratios display incorrectly

**MEDIUM | FINANCIAL / UX | CODE-INSPECTED; ratio display REPRODUCED | BUILD NEXT | effort S | regression risk low | confidence high.**

Monthly projection leverage correctly becomes undefined and covenant code breaches when positive debt exists. But `covenants/ratios.py:ratios` raises ValueError for EBITDA <=0; capex `_financed`/final `pro_forma` and extension pro forma call it without a structured financial abstention. Even a debt-free business with zero EBITDA cannot get an explanatory capex result. Separately `domain/money.py:Ratio.text` uses negative floor division: exact −0.50 displays **−1.50**, exact−1.23 displays **−2.23**. `covenants.fmt_x` correctly handles sign.

Fix: use shared signed ratio formatting; return an explicit undefined/breach state for nonpositive EBITDA and quantify the debt/service rather than crash. Exclude autonomous lending decisions with undefined ratio basis.

## Material formula audit

Notation: P/F/Q are fen principal/face/required net cash; r,d,f,u are fractions (bp/10000); n is actual days, p fee-period days, k=ceil(n/p), N invoice count, H horizon days; ebitda/service in fen/month. Money post = half-up to fen, away from zero. Ratios compare exact fractions. Unless stated, rates are nominal simple and year is365 days.

| Formula / economic interpretation | Units, day count, timing, rounding, boundary / assumptions | Implementation assessment |
|---|---|---|
| Daily cash `C_d=C_(d-1)+Σ signed cash events` | Fen; dated daily closings; amounts posted once. Inflows before outflows, then settlement on same day; no bank posting intraday liquidity test. No postings before today should change actual starting state. | Algebra correct; carried debt violates closed-day premise; forecast receipts do not equal actual cash. |
| Early-pay discount `D=post(dF)`, proceeds`F-D` | Fen; receipt/discount same promised settlement date. Requires0<=d<1, positive outstanding face, settlement before due. Larger d cannot increase supplier proceeds at fixed face. | Correct basic cash algebra; fixed discount bound and executor receipt timing handled in principal audit. |
| Implied early-pay rate `d/(1-d)*365/n` | Cost divided by NET accelerated proceeds, actual days saved. Exact Fraction; display only rounded. n<=0 invalid; d=1 singular, d>1 economically invalid. | Correct conditional formula; mixed tariff denominator comparisons and insufficient source constraints noted above. |
| Break-even `c=borrowing cost/principal`; `d*=c/(1+c)` | Same net cash/tenor needed. IF cost`rkp/365+fk+u` before net-upfront adjustment. Equality fails strict cheaper test. floor basis points is display/ticket constraint, not exact comparator. | Matches no-upfront IF convention; repeats upfront fee, does not ensure equal eligible/funded cash amount. C0/C1 cross-check helps. |
| Partial early-pay face `F=Q/(1-d)` | Fen; rounded at face and actual D then posted. Integer minimal face must satisfy`F-post(dF)>=Q`, not assume division alone guarantees it. Whole ¥100 counter face rounds upward. | Counter/current post algebra confirmed by independent golden calculation; test 1-fen through full invoice and each d tick independently. |
| IF charges `I=post(P*r*k*p/365)`, `fee=post(P*f*k)` | Fen; min1 period even0days; positive advance normally requires n>0. Charge at repayment, upfront`post(Pu)`at funding. Boundaries1/29/30→1period;31/59/60→2;61/89/90→3;91→4. | Ledger formula matches explicitly whole-period contract; treating it Actual/365 on actual n would be incorrect. Contract evidence must substantiate minimum-period billing. |
| Line/bullet interest `post(P*r*n/365)` per FIFO lot | Fen; actual settlement/draw date to repayment; posted at repayment. Partial repayments carry their lot amount, no double interest. Zero days/rate=>0. | Primitive correct; projection carried dates reset, executor logged dates differ. |
| Bullet term maturity `arrival+30*M` | Days; 30-day synthetic months, Actual/365 makes12-month tenor360days. No calendar business-day adjustment. | Matches fixture convention; not automatically an actual bank maturity. Persist explicit contractual due day. |
| Annuity `A=post(P*j/[1-(1+j)^(-M)])`,j=r/12 | Fen/month; end-of-month day30m; r0=>post(P/M). Interest`post(balance*j)` each month; final clears balance; totals sum posted interest. Small P may produce zero early payments. | Correct nominal monthly amortisation with disclosed final adjustment. Effective rate needs j=(1+r)^(1/12)-1. |
| DSCR`monthly EBITDA / monthly scheduled debt service` | Fen/month cancel. Service0=>undefined/no service; negativeEBITDA with positive service breaches positive minimum. Contract measurement period and EBITDA vs CFADS matter. | Basic division correct; bullet reserve distribution and capex omissions violate claimed scheduled-service meaning. Existing DebtPosition service is fixed indefinitely. |
| Leverage`debt / (12*monthly EBITDA)` | Fen/fen; exact month-end debt; EBITDA<=0 undefined/breach with debt. Does not use peak daily debt; capex uses full committed line LIMITS instead of drawn debt. | Algebra correct per named inputs, measurement scope differs across modules; headroom is not one comparable value. |
| Clean-down`longest consecutive zero-balance run>=required days` | Day closing balance; draw+repay same day not clean; today/history/window must be specified. If projection horizon shorter than requirement returns no violation. | Works for supplied window. It is not a contractual annual/rolling clean-down test without period/history; unsupported window should be unknown, not compliant. |
| Tariff IF`r+f*365/p` | Annualised fee-period tariff on principal, whole period assumed. Upfront added`u*365/p`. | Useful tariff, not realised APR. |
| Tariff loan`r+u*12/M` | Annual principal-based spread of upfront fee; assumes full principal carries term; ignores amortisation/net proceeds. | Not all-in amortising APR or early-repayment cost. |
| Bill discount`post(F*r*n/365)`; netF-D | Fen; discount upfront; r quote on face. Net borrowing yield`[D/(F-D)]*365/n`. Held bill inventory/maturity receipt must be removed once. | Primitive discount correct; same-basis rate display is face-rate, and inventory semantics reviewed in principal report. |
| Marginal cost`min usable committed tariff` | Annual; positive facility headroom; owner-approved, not Tier3, no clean-down/purpose-bound source, APR screen. | Ignores amount needed, actual invoice eligibility, age/pledges, actual tenor and facility maturity; cannot alone prove marginal available funding price for perpetual need. |
| Per-invoice extension cost`F*Δ*r/365` | Fen; simple opportunity/funding cost during delay, rounded once. NegativeΔ gain requires firm/evidenced earlier performance. | Correct simple approximation; IF minimum billing and actual funding strategy can materially differ. |
| Structural extension WC`F*Δ/every_days` | Fen average steady-state tied-up cash for recurring stream, not a cash expense. H does not change steady-state stock. Ramp-up/discrete max is a separate calculation. | UsesF*floor(H/every)*Δ/365; it conflates H-period sales with annualised throughput. |
| Perpetual H cost`stock*r*H/365` or`Σ qualifying invoice delay costs` | Fen; choose explicitly horizon-average steady state or dated invoice exposure; count dates/seasonality. | Current formula inconsistent with identical bounded invoices exceptH365; may square horizon. |
| Price adjustment`−Σ post(rate*invoice face)` as supplier cost | Fen; positive price gain negative cost; effective dates, duration, outstanding/settled amounts, and discount date matter. | Valuation ignores start/settled amount in some bindings and rounds aggregate vs cash per invoice; futuregain exploit reproduced. |
| Rebate`post(rate*evidenced purchase base)`or fixed fen | Fen maximum contingent liability; underlying period/order basis matters. Cash on evidenced settlement date, otherwise liability. | Core multiplication correct, timing accrual vs cash path separate; does not create proof of purchase completion. |
| Operational concession`cost_per_event*events_per_year*H/365` | Fen expectation; discrete contractual events might require integer schedule. One report rounding; actual payments on event dates. | Valuation prorates H; trajectory with one effective date posts one full year of events independently ofH. Same economics only under declared approximation. |
| Router objective`incremental posted interest+fees+discounts` | Fen; candidate cost minus baseline. Includes complete action repayment horizon, counts nominal costs across different dates; <=3action search, ¥10k grids, ¥1kminimum, expected budget. | Defensible as labelled deterministic nominal-cost search on represented actions. Does not certify global mathematical optimum or PV cheapest finance; cross-horizon existing costs/forecast extension need consistent comparison. |
| Early-pay acceptance C1<C0 | Fen total posted economic finance cost on exact same current books and non-earlypay package. No cash need and cost>0 rejects; if only offer makes plan admissible, pricing tests waive appropriately. | Improvement in logical formulation; relies entirely on completeness/coherence of projection, sources, bounded search. No independent correctness implied by passing encoded goldens. |
| Capex NPV`−price+Σ uplift/(1+h)^(m/12)` | Fen; h effective annual owner hurdle, monthly end periods;50-digitDecimal then once half-up tofen. h0 linear, uplift0=-price; start>life no benefits. No taxes/residual/working-capital/startup costs unless already in netuplift. | Mathematical implementation correct for stated cash-flow model. Owner input operating cash flow is also added to EBITDA inDSCR without demonstrating equivalence. |
| Payback smallestmwith`−price+Σuplift>=0` | Months undiscounted; equal0 qualifies; no payback within life=>None; omitted terminal residual not considered. | Correct conditional calculation. Does not measure discounted payback or substitute for NPV. |
| Financing comparison PV`PV(net dated finance outflows)-net received principal` | Fen common valuation date/rate; include cash contribution, fees, rentals, residual/ownership and cash tax treatment when comparing. | Not implemented; capex orders nominalinterest and treats lease as equivalent annuity loan. Narrow claims. |

## Independent golden arithmetic

Using rational arithmetic, not importing the golden oracle:

- Line¥150,000×6.4%×32/365 = posted **¥841.64**.
- IF¥210,000×7.8%×30/365 = **¥1,346.30** interest; 0.25%fee **¥525.00**; total **¥1,871.30**. Combined **¥2,712.94**.
- CounterA face¥211,900×0.85%=**¥1,801.15**; net¥210,098.85; remaining gap¥149,901.15; line32dayinterest **¥841.09**; total **¥2,642.24**.
- Per-invoice 15-day extension at IF tariff on¥420k = **¥1,871.30** reported (exact before rounding is¥1,871.30136986);12-invoice annual cost rounded once **¥22,455.62**. Correct execution total of12 individually posted equal charges would be¥22,455.60. These differ because valuation/report rounding is not the same quantity as summed cash postings, which must be labelled.
- NPV model conditional on owner estimates and fee-free annuity arithmetic is internally reproducible; this does not validate recommendation inputs or ranking objective.

## Properties to add (falsifiable)

1. No cash or debt event before as_of_day can change current cash or current debt in a fresh projection.
2. Close(actual events to t), then project must equal the remaining suffix of the original contractual schedule under unchanged exogenous assumptions.
3. Same qualifying invoice IDs/dates/amounts must produce same forward value regardless of equivalent bounded/perpetual wording.
4. No gain with all cash/effective dates outside valuation horizon can expand cap headroom.
5. A pure horizon extension over stationary invoice flows gives approximately linear cost, not quadratic; steady-state WC stock is invariant to H.
6. Monthly extension service respects invoice frequency; every15d versus30d approximately doubles aggregate costs.
7. Every capex feasible structure passes the same borrowing/APR/DSCR/leverage/purchase cash predicates as a routed plan.
8. Existing debt represented as a drawn facility versus a DebtPosition with the same schedule yields equal cash, debt and ratios; reject overlapping representation that double counts.
9. Add an upfront fee to an otherwise unchanged candidate: its all-in/PV cost must not fall; sufficiently large fee reverses nominal-interest ranking.
10. Every stated effective rate reproduces itself when compounded using the payment period rate.
11. Negative ratios display their exact sign/magnitude; undefined EBITDA produces a structured abstention/breach rather than an exception.
12. APR screen tests1/29/30/31/59/60/61/89/90/91day cash flows, net proceeds and fee shape, with exact threshold−1fen/threshold/+1fen andbp boundaries.
13. A quoted bank covenant must select an executable measurement basis/window; unknown covenant definitions must not be reported passed.

## Scope decisions

Build now: one actual balance and dated outstanding schedules, capex claim narrowing, dated valuation/binding, action-specific authority/admissibility. Build next: properly defined tariff/APR/IRR and shared financing PV comparison if capex remains in demo. Post-hackathon: tax/lease ownership/asset residual modelling only when alternatives actually need them; facility calendars, dispute/default/stress cases materially changing admission. Do not build more lender negotiations or autonomous cures on top of inconsistent books, a generic accounting ERP, unsupported bank-compliance certificates, or richer financing recommendations whose contract evidence is absent.

Open design questions: is EBITDA intended to proxy cash available for debt service, and under what covenant definition? Is a facility rate nominal, effective, a discount yield, or fee-inclusive quote? Is H a valuation period beginning today or an annual-sales proxy? Are future invoices firm contracts or forecasts? Is loan maturity day explicit? Does facility.drawn duplicate DebtPosition? What exactly is received and owned after a lease? Are rate caps tariff caps, realised simple-rate caps, or cash-flow APR caps? Does mincash apply intraday or closing balances? Each answer changes actual admissibility.
