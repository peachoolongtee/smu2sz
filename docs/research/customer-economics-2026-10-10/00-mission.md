# The owner's mission (pasted 10 October 2026): FLOW's next layer

Role: principal product architect, financial systems engineer, commercial finance lead, implementation owner. Investigate, design, validate, and where justified implement the next major layer of FLOW. The central question moves from "Can this business afford this deal?" toward "Is this customer relationship worth the capital it consumes, what can we safely offer them, and what flexibility do we give up by saying yes?" Not five unrelated feature requests: look for shared financial primitives and a coherent architecture.

## 0. Current product context
FLOW is an AI working-capital agent for SME suppliers with FinancialState, current books, receivables, commercial terms, commitments, deterministic cash projection, funding facilities, funding optimisation, concession valuation, owner mandates, verifier/admissibility logic, counter-offers, approvals, execution, monitoring, receipts, reconciliation, auditability. Stay grounded in deterministic financial logic. The LLM must not become the financial calculator or execution authority.

## 1. Do not destabilise current hardening
Read the latest UX audit, UX remediation work, SYSTEM_WALKTHROUGH, FINANCIAL_SEMANTICS, CONTINUOUS_OPTIMIZATION, relevant ADRs, repository state; inspect branches and recent changes. Do not regress: decision lifecycle, approval scope, current vs historical time, execution truth, settlement, counter binding, contextual Ask FLOW, Demo correctness. New capabilities are initially READ-ONLY, EXPLAINABLE, FEATURE-FLAGGED unless there is a compelling reason otherwise.

## 2. Product hypothesis
"This buyer request creates ¥28k of concessions and exceeds a ¥5k owner limit" is useful but incomplete. An owner may ask "What if this buyer gives me ¥2M of annual business at 20% margin?" Annual contribution ≈ ¥2,000,000 × 20% = ¥400,000; a ¥28,000 concession ≈ 7% of annual customer contribution. That context may change the owner's BUSINESS judgment. But CUSTOMER VALUE MUST NOT SILENTLY OVERRIDE OWNER AUTHORITY. MANDATE = what FLOW may approve or execute autonomously. ECONOMICS = whether going outside it might still be commercially rational. Correct: "Outside your autonomous limit. The concession costs ¥28.3k, approximately 7.1% of Foshan's estimated annual contribution. Owner review recommended." Not: "Foshan is valuable, therefore FLOW ignores the ¥5k limit."

## 3. Five starting capabilities (hypotheses, not mandatory designs)
A customer value / customer economics; B accept vs counter vs customer-loss scenarios; C safe commercial / negotiation envelope; D opportunity cost / financial capacity consumption; E late-payment + customer-concentration risk. Look for shared infrastructure.

## 4. A: customer economics
Add the customer context needed to judge whether concessions are economically significant. Potential customer-level data: annual revenue; gross or contribution margin; estimated annual contribution; current AR; share of total AR; share of annual revenue; share of annual contribution; historical payment behaviour; strategic classification; commercial history. MVP: annual contribution = annual customer revenue × contribution margin (¥2.0m × 20% = ¥400k; concessions ¥28.3k = 7.1%). Investigate whether "gross margin" or "contribution margin" is the better default term and measure. Do not pretend gross profit equals true customer profitability.

## 5. Longer-term customer profitability (explore, not necessarily build)
Working-capital-adjusted customer contribution: gross contribution minus financing cost caused by payment terms, minus recurring rebates/concessions, minus observed late-payment financing impact, minus other measurable commercial costs (e.g. ¥400k − ¥42k − ¥16k = ¥342k). Do not invent hard-to-measure costs (relationship effort) without data. Decide MVP vs future.

## 6. Provenance
Every important customer-level figure identifies its source: ACCOUNTING_HISTORY, INVOICE_HISTORY, OWNER_ENTERED, ERP, DERIVED, ESTIMATED, PROJECTED. E.g. annual sales derived from last 12 months of invoices; margin owner-entered; average payment delay calculated from receipts; strategic account owner-classified. Never present estimates as observed facts.

## 7. B: accept vs counter vs customer-loss scenarios
"What happens if I push back and this customer walks?" is valid, but FLOW must not pretend to know the customer WILL leave. SCENARIO ANALYSIS, not CHURN PREDICTION, unless historical data supports a model. Scenarios: accept original request; send recommended counter; send alternative counter; customer-loss scenario; buyer pays late; buyer accepts counter; buyer rejects counter. Label assumptions.

## 8. Scenario comparison output
ACCEPT BUYER REQUEST: expected annual customer contribution ¥X; concession cost ¥28.3k; funding cost ¥Y; lowest cash ¥Z; facility capacity remaining ¥N. FLOW COUNTER: contribution if accepted ¥X; concession cost ¥3.0k; lowest cash ¥Z; capacity remaining ¥N. CUSTOMER-LOSS SCENARIO: revenue lost ¥2.0m; contribution lost ¥400k; cash impact. The customer-loss scenario is NOT a prediction: "Scenario assumes Foshan stops buying from you."

## 9. No invented acceptance probabilities
Never "65% chance Foshan accepts" or "30% churn probability" without defensible history. Prefer SCENARIO A if buyer accepts / SCENARIO B if buyer walks away. Negotiation likelihood is a later, separate investigation.

## 10. C: safe deal / negotiation envelope
Today: buyer asks 60 days, FLOW may say No. Better: "At current pricing, FLOW can support up to 52 days" / "60 days becomes acceptable if price increases at least 0.4%" / "60 days becomes acceptable with 20% upfront." From DEAL GATEKEEPER to NEGOTIATION INTELLIGENCE.

## 11. Do not present independent maximums unsafely
Avoid "maximum terms 52 days / maximum rebate 0.5% / maximum discount 0.8%" if they cannot be combined. Terms interact; the feasible region is multidimensional. Prefer SAFE COMMERCIAL PACKAGES: option 1 52-day terms, current pricing, no rebate; option 2 60-day terms +0.4% price; option 3 60-day terms, 20% upfront; option 4 55-day terms +0.2% price. The user must not combine individually safe maxima into an unsafe package.

## 12. Safe envelope algorithm
Use the existing verifier in reverse: given current_books, buyer, candidate package → evaluate financial outcome, mandate, concession cap, cash reserve, funding capacity, covenants; search the commercial parameter space. One dimension: enumeration or binary search (max D such that verify(terms=D) admissible; min P such that verify(60 days, price_adjustment=P) admissible; min upfront U such that 60 days + U admissible). Do not over-engineer: if the domain is small, exhaustive enumeration may be safer and easier to explain.

## 13. Two things to distinguish
FINANCIALLY FEASIBLE vs AUTONOMOUSLY PERMITTED. "60 days + 0.3% price" may be financially safe but outside an owner concession rule. Show both: FINANCIALLY SAFE but NEEDS OWNER APPROVAL.

## 14. D: opportunity cost / capacity consumption
An affordable decision can still consume valuable future flexibility. Show WHAT CAPACITY THIS DECISION USES: cash-buffer, credit-line, invoice-finance, concession, covenant, customer-credit capacity. E.g. available line capacity ¥300k before, ¥54k after: "This deal uses 82% of your remaining credit-line capacity through 30 November." More defensible than "You won't be able to fund another order in November."

## 15. No unsupported future claims
Do not say "If another order comes in November, you cannot fund it" unless the hypothetical order is defined. Say "Remaining funding capacity through 30 Nov falls from ¥300k to ¥54k" or, if defensible, "After accepting, FLOW estimates you could support approximately ¥70k of additional working-capital need without another facility or owner action." A capacity statement, not speculative forecasting.

## 16. Shadow cost / optionality (investigate)
Marginal cost of consuming scarce financial capacity: what is one additional ¥1 of line headroom worth; when does using cheap capacity today force expensive funding later; can one profitable deal reduce the feasible set of future deals? May later support PORTFOLIO OPTIMIZATION. Do not force formal shadow-price mathematics if it does not improve the product.

## 17. E: customer concentration
Make AR concentration visible where material (Foshan ¥420k of ¥420k = 100%). Metrics: % current AR; % annual sales; % annual contribution; % upcoming 30-day receipts. Do not collapse into one "customer importance score"; each tells a different story.

## 18. Concentration affects context, not rules
"Foshan represents 100% of current receivables" influences risk communication, stress analysis, owner attention; it does not change the mandate unless owner policy says so.

## 19. Late-payment stress
Evaluate important deals and receivables under payment-delay scenarios: CONTRACTUAL PAYMENT DATE; TYPICAL HISTORICAL PAYMENT DATE; STRESSED PAYMENT DATE. E.g. on time lowest cash ¥320k; typical +11-day delay lowest cash ¥245k, funding required ¥X; +30-day stress lowest cash −¥135k, additional funding ¥Y, estimated financing cost ¥Z.

## 20. Use observed payment behaviour
Not "owner says they are usually 15 days late" forever. From receipt history: average days late; median; P75 / P90; on-time %; maximum recent delay; recent trend. Observed data outranks subjective estimates. If history is insufficient, say so.

## 21. Input model (investigate; fit the repo)
CustomerProfile: customer_id, annual_sales, sales_source, contribution_margin, margin_source, annual_contribution, current_ar, ar_concentration, revenue_concentration, contribution_concentration, payment_statistics, strategic_classification, notes, as_of_date, provenance. Do not blindly create this schema.

## 22. Strategic importance
"How important is this customer?" is useful context but dangerous as opaque arithmetic. No importance_score = 8.7 silently multiplying recommendations. Explicit classification NORMAL / IMPORTANT / STRATEGIC, possibly with owner-defined policy: "Outside normal autonomous limits. Foshan is marked Strategic. Owner review recommended." Later, classifications may connect to explicit mandates.

## 23. Supplier flexibility ("can suppliers wait?")
A real lever but it introduces AP semantics. Without supplier due dates, contractual terms, penalties, credit-hold risk, criticality, supply interruption, relationship consequences, FLOW cannot treat supplier delay as free liquidity. DEFER as an optimisation action until AP is properly represented; document as future expansion.

## 24. Shared architecture
Four shared systems: 1 CUSTOMER ECONOMICS PROFILE; 2 SCENARIO COMPARATOR; 3 SAFE COMMERCIAL ENVELOPE; 4 FINANCIAL CAPACITY / OPPORTUNITY-COST ENGINE. Not five one-offs if four reusable primitives serve.

## 25. Potential general abstraction
CURRENT STATE + CANDIDATE COMMERCIAL ACTION → PROJECTED STATE → ECONOMIC IMPACT, LIQUIDITY IMPACT, CAPACITY CONSUMPTION, MANDATE RESULT. Products become searches over it: DEAL VERIFIER (one candidate); SAFE ENVELOPE (boundary of acceptable candidates); SCENARIO COMPARATOR (several candidates); PORTFOLIO OPTIMIZER (combinations); COLLECTIONS PRIORITIZER (rank receipts/actions by marginal impact). Do not create an abstract framework because it sounds elegant; prove reuse first.

## 26. Customer economics + mandate UX
COUNTER RECOMMENDED. Foshan request: 60-day terms + 1% rebate + early-pay discount. 12-month concession cost ¥28.3k. Estimated Foshan annual contribution ¥400k. This request equals 7.1% of annual customer contribution. Owner autonomous concession limit ¥5k. Status: outside autonomous limits. Then: cash impact: below minimum in 47 days; concentration: Foshan = 100% of current AR; 30-day late-payment stress: additional funding required ¥X.

## 27. Safe-offer UX
WHAT YOU CAN SAFELY OFFER. At current pricing: up to 52 days. If the buyer requires 60 days: option A +0.4% price; option B 20% upfront; option C 55 days + 0.2% price. Recommended: option A, explain why. Do not show options that fail their own recheck.

## 28. Accept / counter / loss UX
ACCEPT ORIGINAL: annual contribution after concessions ¥X; lowest cash ¥Y; funding usage ¥Z. FLOW COUNTER: contribution if accepted ¥X; lowest cash ¥Y; funding usage ¥Z. CUSTOMER-LOSS SCENARIO: contribution foregone ¥400k; cash impact ¥Y. "Customer-loss scenario assumes Foshan stops purchasing." No implied probability.

## 29. Product principle
From "This violates policy" to "This violates your autonomous policy, but here is the complete business trade-off."

## 30. Future portfolio link
Design so primitives can later support MULTI-DEAL PORTFOLIO OPTIMIZATION ("five pending negotiations: which to accept, counter, reject?"), needing customer contribution, capacity consumption, deal alternatives, scenario impacts, concession usage, liquidity, facility usage. Do not build it now unless a tiny prototype validates the architecture.

## 31. Future collections link
COLLECTIONS PRIORITIZATION ("call Buyer C first: collecting ¥90k there avoids ¥3,200 of funding cost"). Do not build full automation; do not make it impossible.

## 32. Data availability audit
For each input: AVAILABLE NOW / DERIVABLE NOW / NEEDS OWNER INPUT / NEEDS ACCOUNTING IMPORT / NEEDS PAYMENT HISTORY / NOT CURRENTLY AVAILABLE. An explicit matrix. Do not pretend data exists.

## 33. MVP data strategy
Manually seeded customer data is acceptable for the prototype, labelled. MVP inputs: annual customer sales; contribution margin; strategic classification. Derive: current AR concentration; deal economics; cash; facility consumption. Payment delay: observed receipt history if available, else explicitly configured demo history.

## 34. Real product data strategy
Accounting/invoice history → annual sales; COGS / contribution model → margin; bank/receipt history → payment behaviour; current books → AR concentration. Owner input mainly for strategic classification, policy, missing assumptions. Do not make the owner maintain data FLOW can calculate.

## 35. Mathematical validation
Every new metric: definition, units, time horizon, source data, rounding rule, edge cases, independent tests (concession as % of contribution; AR concentration; remaining facility capacity; late-payment cash effect; minimum compensating price; maximum safe terms). No duplicated financial formulas across UI/backend modules.

## 36. Customer-profitability edge cases
Negative-margin customer; zero margin; new customer with no history; seasonal; three months of history; large revenue tiny contribution; large contribution terrible payer; multiple currencies; missing margin; estimated vs observed sales. Fail transparently.

## 37. Safe-envelope edge cases
Non-monotonic feasibility; terms interactions; rebate + days + price; facility exhaustion; covenant boundary; rounding; invoice not yet eligible for funding; stale counter; equal-economics ties. Do not assume binary search works unless monotonicity is proven; enumeration may be safer.

## 38. Opportunity-cost edge cases
Capacity recovers over time; show time: line headroom today ¥300k, after accepting ¥54k, recovers above ¥200k on 18 Dec.

## 39. Late-payment stress edge cases
Do not double-count: the contractual receipt leaves its original day and lands on the stressed day. Test partial receipts; already overdue invoices; invoice financing; early-pay discounts; multiple receipts; default / non-payment if explored.

## 40. Business mode presentation
Do not overload the Deals view; progressive disclosure. Primary: COUNTER RECOMMENDED. This package costs ¥28.3k. That's 7.1% of Foshan's estimated annual contribution. It pushes cash below your minimum in 47 days. Foshan currently represents 100% of receivables. SAFE ALTERNATIVE: 52-day terms, or 60 days + 0.4% price increase. Behind disclosure: compare scenarios; customer economics; late-payment stress; capacity impact.

## 41. Not a six-screen laboratory
The UX is being simplified; new intelligence should REDUCE uncertainty, not increase density: one headline; two to four decisive facts; one recommendation; one action; evidence on demand.

## 42. Research / validation
Before production: would an SME owner know their customer margin? Think in annual gross profit or contribution? Would sales use "safe packages"? How often do simultaneous negotiations occur? Does AR concentration influence negotiation behaviour? How are payment-delay assumptions used today? Validate with historical business cases, existing SME interviews, real invoices, real deal histories; behavioural questions over hypothetical "would you use this?".

## 43. Implementation phases (adjust on repo evidence)
PHASE 0 research + specification (customer economics, scenario, capacity, safe-envelope semantics; data audit). PHASE 1 customer economics (CustomerProfile or equivalent: annual sales, margin, annual contribution, AR concentration, provenance; into Deal analysis; no change to autonomous mandate behaviour). PHASE 2 late payment + concentration (payment statistics; on-time / typical / stress; concentration). PHASE 3 safe commercial envelope (read-only search: max safe days; minimum compensating price; selected safe packages; every package passes its own canonical verifier recheck). PHASE 4 capacity / opportunity cost (cash capacity; facility headroom before/after; concession headroom; time until recovery; additional working-capital capacity if defensible). PHASE 5 scenario comparator (accept original; recommended counter; other safe counter; customer-loss hypothetical; late-payment stress). PHASE 6 validation (historical cases; property tests; cold-user review; financial review).

## 44. Do not autonomise
Initially ANALYZE, COMPARE, RECOMMEND. Customer value, strategic status, scenario output, safe-envelope search create no new execution authority. The signed mandate remains authoritative.

## 45. Test strategy
CUSTOMER ECONOMICS: revenue × margin; missing margin; negative contribution; provenance. CONCENTRATION: one customer = 100%; several sum correctly; zero AR. PAYMENT HISTORY: average/median/P90; partial receipts; late vs early. SCENARIOS: accept; counter; customer loss; late payment; no original cash-flow double count. SAFE ENVELOPE: every output passes the canonical verifier; one step beyond the boundary fails where monotonic; cross-term packages independently checked. OPPORTUNITY COST: capacity before/after reconciles to canonical facility state; no headroom goes negative unnoticed; time-based recovery correct. MANDATE: customer value never bypasses owner authority.

## 46. Property / differential testing
Randomise customer economics, terms, margins, receivables, facility capacity, delays. Invariants: a displayed safe package passes the verifier; a displayed unsafe package cannot execute autonomously; scenario totals reconcile; AR concentration in [0, 100%]; customer-loss removes relevant future contribution exactly once; late payment moves rather than duplicates a receipt; capacity after equals the canonical calculation.

## 47. Possible shared primitives (investigate, not blindly implement)
CustomerEconomics, PaymentBehavior, CommercialPackage, DecisionScenario, ScenarioResult, CapacitySnapshot, CapacityImpact, CommercialEnvelope, SafePackage. Introduce only when several capabilities share them.

## 48. Product opportunities
May combine into COMMERCIAL CAPITAL ALLOCATION: "Where should the next ¥1 of commercial and financial capacity go?" across customer contribution, buyer terms, collections, funding, facility capacity, concentration, future opportunities. Do not over-brand; validate first.

## 49. What not to build now
Full AP optimisation; supplier-payment delaying; generic ERP; tax; payroll; generic accounting; unproven churn ML; opaque customer value scores; full portfolio optimiser; full collections automation, unless research reveals a blocking need. Supplier flexibility stays deferred until payables and supplier consequences are modelled.

## 50. Initial deliverable (before major coding)
A current capability map; B data availability matrix; C customer economics spec; D scenario comparator spec; E safe envelope spec; F opportunity cost / capacity spec; G late-payment / concentration spec; H shared architecture; I UX proposal; J test strategy; K implementation phases; L risks / kill criteria. Then small implementation waves if the design is sound.

## 51. Kill / defer criteria
Customer economics: defer sophisticated adjusted profitability if input data is too weak. Customer-loss: scenario only, absent churn evidence. Safe envelope: avoid multidimensional search if the UX becomes impossible to explain; return a few validated packages. Opportunity cost: no "future order lost" without defined future demand. Supplier flexibility: defer without an AP model.

## 52. Final product standard
"Foshan's request costs approximately ¥28.3k over 12 months. That equals about 7.1% of the ¥400k annual contribution we estimate Foshan generates. The request also pushes cash below your ¥300k minimum and consumes 82% of remaining line capacity through November. Foshan represents 100% of current receivables. If its payment arrives 30 days late, you would need approximately ¥X of additional funding. This is outside your autonomous ¥5k concession limit. You can safely offer: 52-day terms at current pricing, or 60 days with at least a 0.4% price increase. FLOW recommends the first option. Owner approval is still required for anything outside the signed mandate." CUSTOMER VALUE + DEAL ECONOMICS + LIQUIDITY + CONCENTRATION + OPTIONALITY + NEGOTIATION GUIDANCE without sacrificing FINANCIAL TRUTH, OWNER CONTROL, EXPLAINABILITY. Begin by inspecting the actual repo and defining the shared financial semantics before implementing UI.

## The owner's later instruction (10 October)
"Reconcile this sensibly and retain all the things that make the most sense and develop all other avenues that have added value and utilise the one that makes the most sense." No commits to the repository until the owner says so: research resolves on the tracker and in the scratchpad.
