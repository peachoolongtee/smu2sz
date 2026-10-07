# 02 — Market and competitor map

Research ticket [#41](https://github.com/peachoolongtee/smu2sz/issues/41) of wayfinder map [#39](https://github.com/peachoolongtee/smu2sz/issues/39). 8 October 2026. Desk research only (web search and fetch, no interviews, no code changes). Every claim about a product is from that vendor's own pages or a trade source listed in section 7; every market number is from a named survey. Where a cell is my inference it is marked *(inf.)*.

**What FLOW is, for the comparisons below.** A supplier-side agent that reads a buyer's commercial offer, types the obligations, prices their financing cost against the supplier's own cash projection and committed facilities, verifies them against an owner-signed mandate, counters with priced alternatives, funds the gap, queues anything beyond the mandate for approval, and keeps the books, receivables, commitments and covenants current afterwards. The three candidate capabilities are the **Safe Deal Envelope** ("what can I offer this buyer"), the **multi-deal portfolio** ("which deals should we take together") and **collections prioritisation** ("who should I chase first and why"); the adjacent ideas are true customer profitability, a trade-credit budget, liquidity tripwires, stress-to-action and the cash value of a negotiation.

## 1. Who sells what

Legend. **Decides / displays**: does the product produce a decision (approve, limit, rank, route) or a view. **Terms ↔ capital**: does it connect a commercial term (payment days, discount, rebate, credit limit) to the cost or availability of the seller's capital. **Acts**: does it execute (send, fund, block, pay) rather than recommend. **Direct** means the product answers one of FLOW's three questions for a supplier; **adjacent** means it holds part of the data or the decision.

### 1.1 Trade credit, credit insurance, credit management

| Product | Type | Optimises | User | Data | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|---|---|
| Allianz Trade (Allianz Trade Online, Grade Check) | Adjacent | Insured exposure per buyer; non-payment loss | Credit manager, SME owner (policyholder) | Insurer's buyer grades (1–10), the policyholder's limit requests and exposure | **Decides** the insured credit limit per buyer; displays grades, exposures, top customers | Partly: the limit is a ceiling on exposure, not a price for payment days | Indemnifies after default; does not fund or negotiate | FLOW asks what the supplier *can afford to offer* given its own cash and facilities, not what the insurer will cover; the insurer's limit would be one input to the Envelope *(inf.)* |
| Coface (EasyLiner, @Credit Opinion, instant limits to £1m) | Adjacent | Same; SME policy priced on turnover, portfolio size, sector | SME owner, credit manager | Coface business information; 5 value ranges per buyer | **Decides** the insured limit; opinions on recurring small transactions | Same as above | Indemnifies, collects | Same |
| Sinosure 中国信保 (短期出口信用保险, 国内贸易信用保险) | Adjacent (China) | Insured export and domestic receivables; 14.5万 small-micro export clients; domestic cover ¥204.2bn (+45.2%) | Exporters, SME owners via city bulk policies (e.g. Shenzhen ≤ US$8m exporters) | Buyer limit applications, Sinosure buyer files | **Decides** buyer limits | Partly (ceiling, not price) | Indemnifies | Same; a Chinese supplier's insured limit is a hard constraint FLOW does not model today *(inf.)* |
| Creditsafe (reports, recommended limit) | Adjacent | Recommended total credit per company | Credit controller, sales (pre-qualification) | Risk score and banding, turnover, stock, cash, working capital, payment records of similar companies; daily | **Decides** a recommended limit; displays score | No: limit is about the *buyer's* strength, not the seller's capital | No | FLOW's Envelope is a function of the *seller's* liquidity, mandate and facilities; Creditsafe-type limits say how much the buyer can bear, not how much the seller can carry |
| 企查查 / 天眼查 / 启信宝 (启信慧眼 SaaS) | Adjacent (China) | Buyer risk admission; 启信慧眼 states it sets *initial 账期 and 授信额度* and warns on 账期客户 | Credit/risk staff, sales | Public registry, litigation, 失信, equity, tenders | **Decides** an initial term and limit by rule; alerts | Partly: sets payment days from buyer risk, not from seller capital | No | Same as Creditsafe; closest Chinese analogue to "what terms may I give this buyer", but one-sided |
| HighRadius Credit Cloud, Esker Credit Management, Serrala credit risk (SAP) | Adjacent | Credit decision throughput; limit changes; blocked-order release | Enterprise credit team | ERP AR, bureau and insurer feeds; scoring models | **Decides** low-risk approvals automatically; recommends limit changes | No (buyer-centric scoring) | Releases or blocks orders (HighRadius) | FLOW is supplier-SME-side, owner-mandated, and prices the *cost* of a term rather than scoring the buyer |
| 用友 U8 / 金蝶 K3 Cloud, 精斗云 credit modules | Adjacent (China) | Credit rating, limit control, reminders inside the ERP | Finance in Chinese SMEs | The ERP's own AR and sales orders | **Displays**, with hard limit blocks | No | Blocks orders over limit | These are where a Chinese SME's AR actually lives; FLOW would read from, not replace, them *(inf.)* |

### 1.2 Collections and AR automation (who ranks what, with what data)

| Product | Type | Ranks by | Data | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|---|
| HighRadius Collections | **Direct** (enterprise) | 0–100 collections score per customer; 100+ variables, 20+ customer factors; 30-day delinquency forecast; worklist sized to collector bandwidth | ERP AR history, promises, disputes | **Decides** the worklist | No: ranks by *likelihood and size of delinquency*, not by what each receipt does to the seller's cash floor or facility usage | Sends dunning; agentic outreach | FLOW would rank by **marginal effect on the projected cash trajectory and funding cost** (which receipt averts a reserve breach or a draw) and tie the chase to the mandate; none of the vendors below state a cash-projection or facility-cost objective |
| Sidetrade Aimie (incl. SME agent via ezyCollect) | **Direct** | Next-best action per account; late-payer spotting; credit-risk flags | Proprietary data lake: US$8.8tn of B2B payments, 42m buyers; invoice, company, previous and current action features | **Decides** next action | No | Autonomous dunning, calls, cash application, dispute triage | Network payment data is Sidetrade's moat; FLOW has none. FLOW's edge is the supplier's own cash state and facilities, which Sidetrade does not hold |
| Esker Collections (Synergy AI) | **Direct** (mid/enterprise) | Payment prediction per invoice; customer risk from current vs past behaviour; reprioritised call list | ERP AR | **Decides** the call list | No | Reminders, statements | Same |
| Billtrust Collections (Agentic Procedures, Nov 2025) | **Direct** (enterprise) | Segments buyers by risk and behaviour from network-wide data; recommends timing, frequency, channel | Billtrust network | **Decides** outreach sequence | No | Agentic email, cases, credit review | Same |
| Quadient AR (YayPay) | **Direct** (mid-market) | Two ML models: on-time prediction for current invoices, overdue prediction for overdue ones; claims 34% DSO cut | ERP/accounting AR | **Decides** priority | No | Reminders, portal | Same |
| Tesorio | **Direct** (mid-market) | Invoice-level inflow prediction feeding a 13-week forecast; agents extract promises | NetSuite/Intacct/Workday AR | Mixed: ranks collections and forecasts cash | Closest to FLOW: collections are tied to the **forecast**, but not to facilities, cost of funding or a mandate | Follow-ups, cash application | FLOW adds the funding side (what a late receipt costs in draws) and the owner mandate |
| Chaser (SME) | **Direct** (SME) | Payer rating Good/Average/Bad; late-payment probability per invoice; recommended chasing time | Xero/QuickBooks/Sage AR plus cross-Chaser trends | **Decides** who and when | No | Automated chasing, credit checks, payments | FLOW: same persona, but the rank would be by cash consequence, and chasing is one lever beside funding and counter-terms |
| Upflow, Agicap CashCollect (SME/mid) | **Direct** (SME) | Overdue dashboards, payment forecasts, reminder workflows | Accounting AR, bank feeds | **Displays** mostly | Agicap: AR sits beside a cash forecast but no funding optimisation | Reminders | Same |
| 账款管家, 合思 (China SME) | Adjacent (China) | Contract-centred AR tracking, 回款计划, automated 对账 and 核销, overdue triggers | Contracts, invoices, bank statements | **Displays**; rule triggers | No | Reminders | No Chinese SME AR SaaS found that ranks by cash consequence or links to funding |

### 1.3 Deal profitability, pricing and discount governance

| Product | Type | Optimises | User | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|---|
| Salesforce Revenue Cloud / legacy CPQ (end-of-sale Mar 2025) | Adjacent | Discount approvals by tier (typical 0–15% rep, 16–25% deal desk, 26–35% VP + Finance, 35%+ CFO) | Sales ops, deal desk | **Decides** routing; blocks out-of-policy quotes | No: payment terms are a field, not a priced cost | Routes approvals | FLOW prices the *financing cost* of days and discounts against the supplier's cash and facilities and counters with equivalents; CPQ enforces a static table |
| PROS, Vendavo, Zilliant Price IQ, Pricefx | Adjacent (enterprise) | Pocket price and margin waterfall; AI price guidance in the quote; deal scoring | Pricing team, sales | **Decides** guidance and thresholds | Not evidenced: I searched for payment terms or cost of capital in the waterfall and found none in the vendors' public material | Guidance only | Same; FLOW's "cash value of a negotiation" is the missing waterfall line (financing cost of terms) |

### 1.4 Working capital, treasury, cash forecasting

| Product | Type | Optimises | User | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|---|
| Kyriba Working Capital (SCF, reverse factoring, dynamic discounting, receivables finance, forecasting) | Adjacent (buyer-side) | Buyer's DPO and return on excess cash | Corporate treasury | **Decides** programme terms | Yes, but from the **buyer's** seat: terms extension financed by SCF | Funds suppliers via banks | FLOW is the counterparty's agent: it prices the buyer's programme offer against the supplier's own facilities |
| Trovata, Nomentia, GTreasury (Cashforce), HighRadius Treasury | Adjacent | Cash visibility, forecasting, payments across banks | Treasurer, mid-market to enterprise | **Displays**; forecasts | No | Payments | FLOW's forecast is deterministic from typed obligations and is wired to a verifier and a router; treasury tools forecast and stop |
| Agicap (Cashflow, CashCollect, Payment) | Adjacent (SME/mid) | Cash visibility, scenarios, collections, supplier payments | SME CFO / owner | **Displays**; scenario compare | No | Payments, reminders | Agicap is the closest SME "one living cash state", but it does not decide, does not price terms, does not route funding |
| Float, Fathom, Futrli (Predict, Flow), Finmark, Jirav, Pulse | Adjacent (SME) | Forecast accuracy, scenarios; Futrli Flow monitors customer credit scores | Owner, accountant/advisor | **Displays** | No | No | FLOW: deterministic projection as a *constraint* in a decision, not a report |
| Ramp (Intelligence, agents), Brex, Rho Treasury, Mercury Treasury, Payhawk, Pleo | Adjacent (SME/startup) | Spend policy enforcement; idle cash yield (Ramp: 26m decisions in a month, US$5.5m idle cash moved; Rho "sweep to zero"; Mercury sweep networks) | Controller, founder | **Decides** on spend and sweeps | No (spend side only) | Blocks transactions, sweeps cash | These are the proof that SMEs accept **agentic policy enforcement with a signed policy**, on the spend side; FLOW is the same pattern on the revenue and funding side *(inf.)* |

### 1.5 Invoice finance and lending platforms

| Product | Type | Optimises | User | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|---|
| C2FO ("Name Your Rate", "Express Accept"), Taulia (rate groups, DD and SCF), PrimeRevenue, Previse InstantPay | Adjacent (buyer-sponsored) | Clearing price of early payment; Previse predicts approval and pays day one | Supplier picks invoices and rate; buyer sets return target | Supplier **decides** manually; C2FO matches | Yes: the one place suppliers already trade days for discount, invoice by invoice | Pays early | FLOW would compute the supplier's reservation rate from its own cash floor and facility costs instead of leaving it to judgment; direct complement |
| Fundbox, Kabbage → American Express Business Blueprint (US$1k–150k lines), Kriya/MarketFinance (90% advance in 24h, 1–3% fee; into Allica Bank 2025) | Adjacent | Approval speed; advance rate | SME owner | Lender decides eligibility | No | Funds | FLOW routes *across* such facilities; they are candidate legs in the router |
| WeBank 微业贷 (online, no collateral, up to ¥10m enterprise / ¥500k owner, 2.88%–24% simple annualised, daily interest, tax and invoice data) | Adjacent (China) | Instant unsecured credit from tax/invoice data | Chinese SME owner | Lender decides | No | Funds | A FLOW facility leg; FLOW decides *when and how much* to draw |
| MYbank 网商银行 大雁系统 (supply-chain graph from invoices, contracts, flows; 中标贷, 采购贷, 分月付, 云资金; 1,000+ brands) | Adjacent (China) | Credit for suppliers and dealers of core brands | Suppliers and dealers around anchor brands | Lender decides | Partly: the anchor relationship *is* the credit | Funds | Same |
| JD 供应链金融科技 京保贝 (reverse factoring, minute-level disbursement, ¥200bn cumulative in 2024, 100k+ suppliers; non-recourse mode) | Adjacent (China) | Supplier liquidity against JD payables | JD suppliers | Lender decides | Yes, buyer-sponsored | Funds | Same; JD's terms are an input FLOW should price |
| Du Xiaoman 度小满 | Adjacent (China) | Licensed online micro-lending; public material is consumer-heavy; no SME invoice product detail found | Owner as individual | Lender decides | No | Funds | A possible personal-guarantee leg; low relevance |

### 1.6 "AI CFO" and FP&A

| Product | Type | What it does | Decides / displays | Terms ↔ capital | Acts | How FLOW differs |
|---|---|---|---|---|---|---|
| Zeni (AI Accountant and AI CFO agents), Digits (Ask Digits), Puzzle (AI ledger), Vic.ai (AP) | Adjacent (startup SME) | Books, categorisation, flux, forecasts, bill pay | **Displays** and answers questions; Zeni's CFO agent produces projections | No | Bill pay | FLOW's books are a by-product of decisions; these products' decisions are a by-product of books |
| Runway, Pigment, Datarails, Mosaic (acquired by HiBob 2025) | Adjacent (FP&A) | Models, scenarios, headcount, board reporting | **Displays** | No | No | Planning cadence (monthly), not deal cadence (today) |

### 1.7 The gap I looked for and did not find

I searched for a product that (a) tells a *supplier* what payment terms, discount or rebate it can afford to offer a named buyer given its own cash projection and facilities, (b) prices payment days as a financing-cost line in a deal, or (c) ranks collections by their effect on a cash floor and funding cost. The CPQ vendors' public waterfalls stop at pocket price; the collections vendors rank by delinquency risk and size; Tesorio ties collections to a forecast but not to funding; Agicap holds cash and AR but decides nothing; the early-payment marketplaces leave the supplier's rate to judgment; the Chinese credit SaaS (启信慧眼) sets terms from *buyer* risk only. This is a source gap, not a proof of novelty: the enterprise vendors' internals are not public, and a bank RM or a good credit manager does this in their head.

## 2. Market research questions per capability

Sources for the market facts, used across the tables: Coface China 2025 (average terms 76 days, delays 65 days, 141 days from delivery to cash; only 65% now grant terms; nearly half of those with >180-day delays report late payments above 2% of turnover); Atradius China 2025 (35% of B2B credit sales overdue, 4% bad debt); NBS Jan–Feb 2026 (industrial receivables ¥26.55tn, +7.1%; average collection period 76.4 days, +1.3); 保障中小企业款项支付条例 2025 revision (large enterprises must pay SMEs within 60 days, in force 1 June 2025); Intrum EPR 2025 (56% of executives accepted unfavourable terms to protect relationships; about half accepted longer terms to avoid customer bankruptcies; 9,150 executives); UK DBT 2025 (late payment costs £11bn a year, 38 closures a day, 86 hours a year chasing per affected business, 60-day cap and 8%-over-base interest announced); Hackett 2025 (US DSO degraded a second year as "customer bargaining power drove extended payment terms"; 18-day DSO gap between top and median); PwC (global DSO 47.3 → 50.0 days, 2015–2024); AFP 2025 (over 60% of treasurers call forecasting their hardest task; 96% of FP&A use spreadsheets weekly); Creditsafe sales-vs-credit survey (47% of sales have up to 10 deals a month rejected by finance; 44% would chase habitual late payers; 21% have no formal credit policy, 42% do not understand theirs).

### 2.1 Safe Deal Envelope — "what can I offer this buyer"

| Question | Answer | Grounding |
|---|---|---|
| Who has the problem | The SME owner (in China the 老板 negotiates big accounts personally), the sales director for routine accounts, the finance manager who discovers the terms after signature | Intrum: 56% accepted unfavourable terms; Creditsafe: deals rejected by finance monthly *(persona split inf.)* |
| How often | Every new or renewed anchor-buyer negotiation (monthly to quarterly per account) and every "can we do 90 days" email (weekly in B2B supply) | Coface: terms lengthened 70 → 76 days in a year, so renegotiation is live *(frequency inf.)* |
| Handled today | Gut feel; a static credit policy table if one exists (only 79% have one per Creditsafe); a call to the bank RM about the line; Excel on the financing cost, rarely; the CPQ approval tier in larger firms | Creditsafe; CPQ tier examples |
| Cost of getting it wrong | Financing cost of the days (≈ invoice × rate × days/360), reserve breach, facility exhaustion at the worst moment, hidden discount (an early-pay discount of 1.2% for 30 days is ≈ 14.6% a year), lost sale if the answer is a blanket no | economicsonline, lapasar calculators; FLOW's own concession valuation |
| Budget owner | Owner in SMEs; CFO in mid-market; sales ops owns CPQ budget in larger firms | *(inf.)* |
| Who benefits | Owner (sleeps), sales (a fast yes with a priced counter instead of a slow no), finance (no surprise draw) | |
| Who resists | Sales directors who see finance as a brake (Creditsafe: finance rejects deals; 44% would sell to late payers anyway); credit managers who own the policy table | Creditsafe |
| Replaces / complements | Replaces the ad-hoc call and the Excel; complements CPQ (as the missing financing line), insurer limits (as a ceiling), the bank RM | |

### 2.2 Multi-deal portfolio — "which deals should we take together"

| Question | Answer | Grounding |
|---|---|---|
| Who has the problem | Owner and finance manager at quarter end or tender season; sales director when several large orders land at once | Academic literature on order acceptance under capital constraints exists; no product found *(inf.)* |
| How often | Rare to monthly: tender seasons, 618/11.11 for consumer suppliers, year-end | *(inf.)* |
| Handled today | Taken one at a time, first come first served; the bank RM's informal view of headroom; a cash spreadsheet; concentration rules of thumb (e.g. no more than 20% of receivables from one buyer; bank borrowing-base concentration caps) | hyperbots glossary; JFQA on concentration |
| Cost of getting it wrong | Facility exhaustion before the best deal; covenant pressure; concentration on one buyer whose 2% of turnover late payment becomes a bad debt; margin given away on the wrong deal | Coface (late payment >2% of turnover); Hackett (receivables are the largest trapped pool) |
| Budget owner | Owner; CFO | *(inf.)* |
| Who benefits | Owner, finance; sales only if it gets a ranked answer rather than a veto | |
| Who resists | Sales (the ranking will say no to someone's deal); account managers paid on bookings | Creditsafe conflict data |
| Replaces / complements | Replaces nothing (nobody does it); complements the Envelope as its batch form | |

### 2.3 Collections prioritisation — "who should I chase first and why"

| Question | Answer | Grounding |
|---|---|---|
| Who has the problem | Credit controller or AR clerk daily; finance manager weekly; owner in micro firms (chases personally, 86 hours a year) | UK DBT; Xero (paid 6.6 days late on average, A$15k a year per small business) |
| How often | Daily worklist; weekly review | HighRadius, Esker, Chaser all ship daily worklists |
| Handled today | Aged-debtor report sorted by amount and days; email templates; WeChat nudges in China; collections software in mid-market (ranks by delinquency risk); accounting-app reminders (Xero, 金蝶精斗云) | Section 1.2 |
| Cost of getting it wrong | Bad debt (Atradius China 4%); overdue tying up 35% of credit sales; an unnecessary facility draw while a collectable receipt sits idle; time | Atradius; UK DBT |
| Budget owner | Finance manager / CFO for software; owner in SMEs | |
| Who benefits | Credit controller (shorter list with reasons), owner (cash), sales (fewer blunt chases of good accounts) | |
| Who resists | Sales, when a strategic account is top of the list; AR staff who distrust a black-box rank (FLOW's reason-giving is the answer) | *(inf.)* |
| Replaces / complements | Complements accounting and AR tools (reads their ledgers); competes with Chaser/Upflow at the SME end on the *reason* rather than the automation | |

### 2.4 Adjacent ideas

| Idea | Who, how often | Today | Cost of error | Evidence | Note |
|---|---|---|---|---|---|
| True customer profitability (margin after financing cost of terms, discounts, rebates, chasing time) | Owner/CFO, quarterly | Gross margin per customer in the ERP; cost-to-serve in large firms (71% apply it to specific customers in one consumer-goods study); SMEs lack a practical tool | Keeping customers that are unprofitable once terms are priced | consumergoods.com; UCT thesis on SME CPA | FLOW already has the financing cost per obligation; this is a presentation over existing engine values *(inf.)* |
| Trade-credit budget (total receivables exposure the firm can carry) | Owner/CFO, set yearly, breached monthly | Insurer limit totals; bank borrowing base; rule of thumb (20% per buyer) | Facility exhaustion, concentration | hyperbots; JFQA | Natural constraint for the portfolio idea |
| Liquidity tripwires | Owner/finance manager, continuous | Bank balance glance; covenant tools exist for *lenders* (CovenantPulse etc.), not SME borrowers; treasury tools alert at % of limit | Covenant breach discovered by the bank first | covenant-monitoring sources | FLOW's reserve, DSCR and covenant checks already compute this; the gap is a borrower-side alert with a cure |
| Stress-to-action | Owner, rarely (advisor-prompted) | Preset-scenario stress tools (Alaan, Pennylane, Finthesis): "top three customers pay slow", find the breaking month | Scramble when it happens | Alaan; hayot-expertise | Existing tools stop at the breaking month; FLOW's what-if sandbox can attach the cure |
| Cash value of a negotiation | Owner/sales, each negotiation | Calculators (cash freed = daily COGS × days; cost = amount × rate × days/360) on procurement blogs, from the *buyer's* side | Giving away 30 days for nothing | lapasar, economicsonline, eightx | The supplier-side version is what FLOW's concession valuation already does |

## 3. Before and after workflows

### 3.1 Safe Deal Envelope

**Before.** A buyer's procurement writes to the sales manager: 60 days instead of 45, a 1.2% early-payment discount on the current invoice, a 1% rebate next quarter. The sales manager forwards it to the owner on WeChat with "they're our second-largest account". The owner asks the finance manager "can we take 60 days?"; the finance manager opens the cash spreadsheet, which was last refreshed two weeks ago, adds the invoice, and says "tight in November". Nobody prices the rebate or notices the discount is ≈ 14.6% a year. The owner calls the bank RM about raising the line; the RM says "send me the accounts". Three days pass; the buyer chases. The owner accepts 60 days and the discount to protect the relationship (Intrum: 56% do), and tells finance afterwards. Finance books it, discovers in November that the reserve is breached, and draws the line at the worst rate. Handoffs: 4. Delay: 3 days. Manual calculations: 1, incomplete. Policy: the firm's credit policy, if any, was not consulted (Creditsafe: 42% do not understand theirs). Sales-versus-finance: the finance manager is the brake, the owner the override.

**After.** The same message lands in FLOW's inbox. FLOW types the three obligations, prices each against the current books and the committed facilities, projects cash, and verifies against the owner's mandate: the 12-month concession cost exceeds the ¥5k cap and the reserve breaks on day 47. It offers two counters the mandate allows (a smaller discount for a shorter horizon; the longer terms with a 0.30% price adjustment that nets to zero) and the funding plan if the buyer insists. The sales manager sends the counter the same afternoon with a reason the buyer can read; the owner approves only the piece above the mandate; the finance manager sees the commitment appear in the books with the funding leg scheduled. Handoffs: 1 (owner approval). Delay: hours. Manual calculations: 0. Policy: enforced by construction. Conflict: sales gets a priced yes, finance gets a decision it did not have to defend.

### 3.2 Multi-deal portfolio

**Before.** It is late October. Three orders arrive within a week: a ¥1.2m order from the anchor buyer on 90 days, a ¥400k order from a new buyer on 30 days with a 3% discount, a ¥700k tender win needing a performance bond. Each is handled by a different salesperson; each is accepted because each alone "fits". The finance manager learns of all three at month-end close, calculates that the line will be at 95% by December, and asks the owner to delay the tender's materials purchase. Sales learns the delay from the customer. Nobody compared the three; nobody asked which one the facilities could not carry. Handoffs: 3 parallel, uncoordinated. Duplicate work: three separate "can we afford it" judgments. Information gap: no shared view of commitments. Bottleneck: month-end. Conflict: finance appears to sabotage a signed deal.

**After.** Each order is a candidate action in FLOW with its typed terms and projected cash path. FLOW shows the three together against the same trajectory, mandate and trade-credit budget: all three breach the reserve in December; the anchor order alone is fine; the new buyer's discount is dearer than financing; the tender is fine if the anchor order's funding runs on the invoice. It proposes the set, the order of acceptance, and the funding legs, and flags the one that needs the owner. Sales gets the answer before promising dates. Handoffs: 1. Duplicate work: 0. The month-end surprise disappears because the commitments are in the books when accepted.

### 3.3 Collections prioritisation

**Before.** Monday. The AR clerk exports the aged-debtor report (sorted by amount), sends the standard reminder to everything over 7 days, and phones the three largest balances, one of which is the anchor buyer that always pays on day 75 anyway. The sales manager complains the anchor buyer was chased. The ¥180k invoice from a mid-sized buyer whose litigation record changed last week is on page two. Nobody connects the list to the fact that the line will be drawn on Thursday unless ¥200k lands. Thursday, the line is drawn. Handoffs: 2 (clerk → sales complaint → owner). Manual calculation: none; the sort order *is* the policy. Information gap: cash timing, buyer risk changes, and sales context are in three places.

**After.** FLOW ranks open receivables by what each receipt does to the projected cash floor and the planned draw, weighted by collectability from payment history (and a buyer-risk feed where available), and says why: "chase B first: ¥180k due in 4 days averts Thursday's ¥200k draw (¥841 saved); A pays on day 75 historically, do not chase before day 70; C's risk changed, confirm the invoice is accepted." The clerk works a list of five with reasons; the sales manager sees the anchor buyer is left alone and why. Handoffs: 0 until something needs an owner. The chase and the funding decision are the same decision.

## 4. Interview guides (actual behaviour, not "would you use")

**SME owner (China or elsewhere).** 1. Walk me through the last time a buyer asked for longer payment terms: who asked, how did you decide, how long did it take? 2. What did you check before saying yes, and where was that information? 3. Have you ever discovered after signing that a deal made cash tight? What happened next? 4. When did you last call your bank RM, and what did you ask? 5. How much of your receivables sits with your largest buyer, and do you know the number without looking? 6. Who in your company is allowed to give a discount without asking you? Has that been written down? 7. When cash was tightest in the last year, what did you do first, second, third? 8. How many hours a week do you personally spend on getting paid? 9. Which buyers have you kept despite poor payment, and why? 10. What would have to be true for you to let software send a counter-offer in your name?

**CFO (mid-market).** 1. Describe your deal-approval process: thresholds, who signs, average turnaround. 2. In the last quarter, how many deals did finance push back on, and how many were overridden? 3. How do you cost payment terms in a deal today — a rate, a rule, nothing? 4. How often is the cash forecast refreshed, by whom, in what tool, and when did it last miss badly? 5. What is your facility utilisation right now, and when did it last exceed your comfort? 6. Which covenants do you watch, and how would you know a month early that one is at risk? 7. Who decides when to draw a facility versus chase harder, and on what evidence? 8. What is your credit policy on new buyers, and when was it last updated? 9. What is the one number you wish sales saw before quoting? 10. What has stopped you buying AR or treasury software before?

**Finance manager.** 1. Show me the spreadsheet you use for cash; how many tabs, how often updated, who else edits it? 2. When sales agrees terms, how do you find out, and how late? 3. How do you compute the cost of an early-payment discount request? 4. What does month-end reveal that you wish you had known on day 5? 5. Describe the last unplanned draw on the line: cause, notice, cost. 6. How do you decide which supplier to pay late when cash is short? 7. What reports does the owner ask for, and which do you build by hand? 8. Which buyer's behaviour changed recently, and how did you learn of it? 9. How do you track rebates and contingent concessions you owe? 10. What breaks when you are on leave?

**Credit controller / AR clerk.** 1. Walk me through yesterday morning: what list did you open, in what order did you work it, why that order? 2. How many accounts did you touch, by which channel? 3. Which accounts are you told not to chase, by whom? 4. How do you know a buyer's risk has changed? 5. When a customer disputes an invoice, how long until someone resolves it, and who? 6. How do you record a promise to pay, and does anyone use it for the cash forecast? 7. Have you been asked to chase harder because a facility was about to be drawn? How did you know? 8. What do you do with the aged-debtor report that the system cannot do? 9. What would make you trust a ranked list you did not build? 10. When did a chase damage a relationship, and what happened?

**Sales manager / director.** 1. Tell me about a deal finance rejected or slowed in the last three months: what happened, what did the buyer do? 2. What discount or terms can you grant on your own authority, and how do you know? 3. When a buyer asks for 90 days, what do you say in the room, and what do you check afterwards? 4. How do you learn a customer pays late, and does it change how you sell to them? 5. Who told you about the last customer whose credit limit was cut, and when? 6. Have you ever offered a price concession instead of longer terms, or the reverse? How did you pick? 7. How are you paid: bookings, revenue, collected cash, margin? 8. How long do you wait for an approval, and what do you tell the buyer meanwhile? 9. What information would you want on your phone before a negotiation? 10. When did finance's "no" turn out right?

## 5. Is "commercial capital allocation" a category?

**Evidence from search.** The phrase "capital allocation software" resolves to **capex and investment portfolio planning**: IFS Copperleaf, Board Capital and Resource Planning, EY Capital Pro, Gartner's "capital investment management software". No vendor uses "commercial capital allocation", and no buyer-side listing (G2, Capterra, SourceForge) has such a category. The categories buyers do search and vendors do occupy are: *accounts receivable automation / invoice-to-cash* (Gartner Magic Quadrant, aimed at "corporate controllers"), *cash flow forecasting / cash management* (Agicap, Float, Trovata), *treasury management*, *working capital management* (G2 lists Kyriba, GTreasury, Trovata; Taulia and HighRadius both call themselves working-capital platforms for the CFO), *CPQ / pricing software*, *trade credit insurance*, *invoice finance*. Chinese buyers search 应收账款管理系统, 信用管理, 供应链金融, 微业贷-style product names; the English category words do not transfer.

**Reading.** "Commercial capital allocation" is an accurate *internal principle* (where should the next yuan of capacity go: a term, a discount, a chase, a draw, a deal) and a poor *category name*: no one searches for it, the words already mean capex, and SME owners do not think of a payment term as capital. It is compelling only as a one-sentence explanation to an investor or judge of why the three capabilities are one engine. In the market, FLOW should be found under the categories that exist (cash flow and working capital for SMEs; AR and collections; supply-chain finance in China) and should use the owner's words on the surface: "what can I offer", "which deals", "who to chase", "am I safe". Adjacent evidence for the pattern rather than the name: Ramp and Brex sold agentic enforcement of a signed spend policy to SMEs without naming a category; they sold "cards and expenses" and shipped the agent inside it *(inf.)*.

## 6. Not checked

The owner's strategy brief itself (sections 5, 6, 22) is not in the repository; I worked from the ticket's paraphrase. No interviews. Vendor claims (DSO reductions, forecast accuracy) are taken as claims. Enterprise vendors' scoring internals, and whether any prices payment days as cost of capital privately, are unverifiable from public material. Du Xiaoman's SME invoice products and Vic.ai's current scope were not confirmed. Chinese search was not exhaustive; no Chinese collections SaaS ranking by cash consequence was found, which is absence of evidence. The Creditsafe survey's date and sample were behind a form (a 2026 release cites 115+ sales and 100+ finance leaders).

## 7. Sources

Credit insurance and credit management
- Allianz Trade Online — https://www.allianz-trade.com/en_GB/trade-credit-insurance/tech-powered-trade-credit/allianz-trade-online.html — manage cover, request and track limits, see grades, exposures and top customers.
- Allianz Trade Grade Check — https://www.allianz-trade.com/en_global/our-solutions/information-product.html — real-time grade 1 (solid) to 10 (insolvency) for the next 12 months.
- Coface @Credit Opinion — https://business-information.coface.com/credit-opinion — rapid assessment in 5 value ranges for recurring small and mid transactions.
- Coface UK instant limits — https://biz.coface.com/icon-uk — instant decisions on credit limits up to £1m.
- Coface EasyLiner (Italy) — https://www.aziendabanca.it/notizie/imprese/coface-banca-di-asti-soluzioni-assicurative-gestione-credito — SME all-inclusive policy priced on turnover, portfolio size, sector.
- Creditsafe UK, how the limit is calculated — https://help.creditsafeuk.com/en/support/solutions/articles/7000051594-how-is-the-limit-calculated- — score, banding, turnover, stock, cash, working capital, total assets.
- Creditsafe, Sales vs Credit Control Battle — https://www.creditsafe.com/us/en/resources/research/the-sales-vs-credit-control-battle.html — 47% of sales have up to 10 deals a month rejected; 44% would pursue habitual late payers; 21% no formal credit policy.
- HighRadius credit management datasheet — https://pages.highradius.com/hubfs/highradius.com/datasheet/2025_Credit%20Management%20Software-1.pdf — credit limit suggestions from payment behaviour and score; automated low-risk approvals.
- Esker Credit Management — https://www.esker.com/solutions/order-cash/accounts-receivable/esker-credit-management — customisable scoring, approval workflows, blocked orders, periodic reviews.
- Serrala credit risk management (SAP) — https://www.serrala.com/ar-automation/credit-risk-management-sap — automated assessing, granting and modifying credit; insurer integration.
- 启信慧眼 SaaS — https://www.intsig.com/enterprise/qx-huiyan.shtml — credit admission, sets initial 账期 and 授信额度, warns on 账期客户.
- 用友 / 金蝶 credit modules — https://www.jiandaoyun.com/news/article/6842ae886544d8159cd614aa — U8 and K3 Cloud credit rating, limit control, reminders.
- 金蝶精斗云应收应付 — https://m.jdy.com/scene/fund/ — credit management, 核销, ageing for small firms.
- 中国信保 small-micro support — https://cs.com.cn/bx/202306/t20230616_6350650.html — small-micro export clients 2.1万 → 14.5万; domestic trade cover ¥204.2bn (+45.2%).
- Shenzhen 2025 SME export insurance bulk policy — https://www.szlhq.gov.cn/attachment/1/1580/1580673/12168694.pdf — exporters ≤ US$8m take policies directly.

Collections and AR
- HighRadius AI worklist prioritisation — https://www.highradius.com/software/order-to-cash/collections-management/ai-based-worklist-prioritization/ — 0–100 collections score, 100+ variables, 20+ customer factors, 30-day delinquency forecast.
- Sidetrade Aimie for SMEs (ezyCollect) — https://itbrief.com.au/story/ezycollect-launches-aimie-to-tackle-late-sme-payments — next-best action, late-payer spotting, credit-risk flags.
- Sidetrade data lake — https://www.sidetrade.com/sidetrade-demos — US$8.8tn of B2B payments across 42m buyers.
- Esker AR AI — https://www.esker.com/en-gb/solutions/accounts-receivable/ai — payment prediction per invoice, reprioritised call list.
- Billtrust Collections Agentic Procedures — https://www.cpapracticeadvisor.com/2025/11/06/billtrust-launches-ai-powered-collections-agentic-procedures/172521/ — network-wide behavioural segmentation, recommended outreach sequence.
- Quadient AR (YayPay) payer analysis — https://www.quadient.com/en-us/blog/yaypays-payer-analysis — on-time and overdue prediction models.
- Tesorio — https://erpresearch.com/erp-add-ons/treasury/tesorio — invoice-level inflow prediction, 13-week forecast, AR agents.
- Chaser AI features — https://www.chaserhq.com/blog/chaser-is-a-finalist-for-the-cicm-technology-development-award-2024 — payer rating, late-payment predictor, recommended chasing time.
- Chaser vs Upflow — https://www.g2.com/compare/chaser-vs-upflow-upflow — SME AR feature sets.
- 账款管家 — https://www.zhangkuanguanjia.com/insights/articles/article-352.html — contract-centred AR SaaS for Chinese SMEs, 回款计划, 对账核销.
- Gartner Magic Quadrant Invoice-to-Cash, Leaders definition — https://www.gartner.com/doc/5406263 — I2C aimed at corporate controllers' cash-flow and efficiency goals.

Pricing and CPQ
- Discount approval tiers — https://umbrex.com/resources/frameworks/pricing-frameworks/approval-threshold-frameworks/ — 0–15% rep, 16–25% deal desk, 26–35% VP + Finance, 35%+ CFO.
- Salesforce CPQ end-of-sale — https://www.rajeshkumar.xyz/blog/?p=1966 — legacy CPQ end-of-sale March 2025.
- PROS vs Vendavo — https://www.rfp.wiki/vendors/pros/vendavo — real-time price guidance, guardrails, approval routing.
- Vendavo pocket-price waterfall — https://usagepricing.com/blueprint/stack/vendavo — list to pocket price; no payment-terms line evidenced.
- Zilliant CPQ agreements — https://www.businesswire.com/news/home/20241105241347/en/Zilliant-Enables-Sellers-to-Close-Deals-Faster-with-Automated-Customer-Specific-Pricing-in-CPQ — negotiated pricing up to 80% of revenue in manufacturing and distribution.

Working capital, treasury, forecasting
- Kyriba Working Capital Solutions — https://www.kyriba.com/news/kyriba-launches-new-working-capital-solutions-to-close-trillions-trade-financing-gap/ — SCF, reverse factoring, dynamic discounting, receivables finance.
- Nomentia vs Trovata — https://www.rfp.wiki/financial-services-banking-fintech/treasury-management-systems/nomentia/trovata — mid-market treasury positioning.
- Agicap — https://www.softwareadvice.com/accounting/agicap-profile — Cashflow, CashCollect, Payment modules.
- Float vs Fathom — https://www.g2.com/compare/fathom-vs-float-cash-flow-forecasting — SME forecasting comparison.
- Futrli Flow — https://www.futrli.com/products/cashflow — daily cash forecasting, customer credit-score monitoring.
- Ramp AI agents — https://fintech.global/?p=222247 — 26m decisions in a month, US$5.5m idle cash moved to investments.
- Ramp agents for controllers — https://www.cpapracticeadvisor.com/2025/07/10/ramp-introduces-ai-agents-suited-for-controllers/164684/ — policy enforcement agents.
- Rho treasury sweep to zero — https://moreinfo.rho.co/task/blog/who-offers-sweep-to-zero-invest-excess-funds — automatic investment above a threshold; Mercury sweep comparison.
- Runway vs Pigment / Datarails / Mosaic — https://runway.com/blog/best-modern-fpa-software-runway-vs-pigment-vs-anaplan-vs-adaptive — FP&A positioning; Mosaic acquired by HiBob 2025.
- Zeni AI agents — https://www.zeni.ai/blog/ai-agents-for-accounting — AI Accountant and AI CFO agents.
- Digits vs Zeni — https://www.zeni.ai/blog/zeni-vs-digits — Ask Digits agent.
- Taulia working capital positioning — https://www.businesswire.com/news/home/20220126006121/de — "working capital management" for the CFO office; SAP stake.
- G2 working capital management — https://learn.g2.com/working-capital-management?hsLang=en — category listing Kyriba, GTreasury, Trovata.
- Hyperbots, working capital software — https://www.hyperbots.com/glossary/working-capital-software — category definition.

Invoice finance and lending
- C2FO vs Taulia — https://www.rfp.wiki/accounting-finance/supply-chain-finance-platforms/c2fo/taulia — Name Your Rate, Express Accept; buyer target rate.
- Taulia rate groups — https://customersupport.taulia.com/articles/en_US/Agent_Knowledge_Base/Payables-Financing-Rate-Groups-and-Supplier-Assignment — rates assigned per supplier group.
- Dynamic discounting guide for small suppliers — https://beancount.io/blog/2026/07/29/dynamic-discounting-c2fo-taulia-small-suppliers-guide — supplier chooses day and invoice.
- Previse InstantPay — https://supplychaindigital.com/technology/previse-immediate-supplier-payment-through-ai-technology — AI predicts approval, pays suppliers day one.
- Kabbage / American Express Business Blueprint — https://glenbrook.com/?p=30543 — lines US$1k–150k, 6/12/18-month terms.
- Fundbox vs Amex — https://www.nerdwallet.com/article/small-business/fundbox-vs-kabbage — online short-term lines.
- Kriya invoice finance — https://www.expertmarket.com/uk/invoice-factoring/top-10-invoice-financing-companies-in-the-uk — 90% advance within 24h, 1–3% fee, Allica Bank 2025.
- 微业贷 product page — https://sme.webank.com/esp-web/rls/asset/bd/index.html — online unsecured SME working-capital loan.
- 微业贷 terms (Zhihu summary) — https://zhuanlan.zhihu.com/p/660701209 — up to ¥10m, 2.88%–24% simple annualised, tax and invoice data.
- 网商银行大雁系统 — https://www.36kr.com/p/2191961116279169 — supply-chain graph from invoices, contracts, flows; 1,000+ brands; 中标贷, 采购贷, 分月付, 云资金.
- 京东供应链金融科技 京保贝 — https://finance.sina.com.cn/tech/roll/2025-01-09/doc-ineekqst6281096.shtml — reverse factoring, ¥200bn cumulative 2024, 100k+ suppliers.
- 京保贝无追索权 — https://finance.sina.com.cn/jjxw/2023-05-29/doc-imyvmrnz5292260.shtml — non-recourse factoring for JD suppliers.
- 度小满 — https://www.bjnews.com.cn/detail/165632662214691.html — licensed online microlender (Chongqing).

Market surveys and statistics
- Coface 2025 China Corporate Payment Survey — https://coface.com/content/download/77518/file/20250328%20-%20Payment%20survey%20-%20China%20Longer%20payment%20terms%20helped%20mitigate.pdf — terms 70 → 76 days, delays 65 days, 141 days delivery-to-cash, 65% grant terms.
- Atradius Payment Practices Barometer China 2025 — https://atradiuscollections.com/hk/出版物/報告/b2b-payment-practices-trends-china-2025 — 35% of B2B credit sales overdue, 4% bad debt, 51-day average terms.
- NBS industrial enterprises Jan–Feb 2026 — https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202603/t20260327_1962868.html — receivables ¥26.55tn (+7.1%), average collection period 76.4 days (+1.3).
- 保障中小企业款项支付条例 (2025 revision) — https://www.mee.gov.cn/zcwj/gwywj/202503/t20250325_1104643.shtml — large enterprises pay within 60 days; in force 1 June 2025.
- Intrum European Payment Report 2025 — https://intrum.com/epr2025 — 56% accepted unfavourable terms; about half accepted longer terms to avoid customer bankruptcies.
- UK DBT late payment response, July 2025 — https://www.gov.uk/government/consultations/late-payments-tackling-poor-payment-practices/outcome/late-payment-consultation-time-to-pay-up-government-response-web-version — £11bn a year, 38 closures a day, 86 hours a year chasing, 60-day cap, 8% over base.
- Xero Small Business Insights (Australia) — https://blog.xero.com/data-insights/small-business-insights-data-late-payment-results/ — 6.6 days late, A$15,257 a year per small business.
- Hackett 2025 US Working Capital Survey — https://www.businesswire.com/news/home/20250818205819/en/The-Hackett-Group%C2%AE-2025-Working-Capital-Survey-Payables-Rebound-but-Receivables-and-Inventory-Lag — DSO degraded a second year on customer bargaining power; US$600bn AR opportunity.
- Hackett 2025 Europe — https://www.thehackettgroup.com/insights/2025-working-capital-survey-europe-2510 — DSO 48.5, CCC 44.8 days.
- PwC working capital study — https://www.pwc.co.uk/services/value-creation/insights/working-capital-study.html — global DSO 47.3 → 50.0 days 2015–2024.
- AFP 2025 Treasury Benchmarking — https://www.financialprofessionals.org/training-resources/resources/survey-research-economic-data/details/treasury-benchmarking — over 60% call forecasting the hardest task; 96% of FP&A on spreadsheets weekly.
- NACM 2025 B2B Credit Insights — https://www.nacmnc.org/news/713219/White-Paper-Highlights-Credits-Digital-Era.htm — top priority more rigorous credit reviews (17%).
- 中小企业发展环境评估报告 2025 — https://www.news.cn/fortune/20260409/3a7596b8c56648c59469e75229f2ae93/c.html — financing supply-demand mismatch persists; order shortfall squeezes margins.
- OECD Financing SMEs Scoreboard 2025 — https://www.oecd.org/en/publications/oecd-financing-smes-and-entrepreneurs-scoreboard-2025-highlights_64c9063c-en.html — SME finance context.

Adjacent ideas and the category question
- Cost-to-serve adoption (consumer goods) — https://consumergoods.com/new-research-cost-serve-methodologies — 71% apply to specific customers; half plan terms and discount restructuring.
- SME customer profitability (UCT) — https://open.uct.ac.za/items/c6c174ba-dcda-4121-9bc3-db97f8b1f1ca — SMEs lack practical CPA tools.
- Concentration limits — https://www.hyperbots.com/glossary/credit-exposure-threshold — e.g. no more than 20% of receivables from one customer.
- Lenders and trade credit concentration (JFQA) — https://jfqa.org/wp-content/uploads/2024/08/24994_LendersLender-1.pdf — borrowing-base concentration limits shape trade credit.
- Covenant monitoring tools — https://www.cascadedebt.com/insights/covenant-monitoring-software-for-private-credit — lender-side monitoring and alerts.
- Cash stress test tool — https://www.alaan.com/tools/cash-flow-stress-test — preset scenarios, breaking month.
- Payment terms as prices — https://www.economicsonline.co.uk/managing_the_economy/payment-terms-are-prices-the-economics-of-supplier-credit.html/ — cost = amount × rate × days/360.
- Payment terms calculator — https://lapasar.com/payment-terms-calculator — cash freed = daily spend × days extended, at cost of capital.
- Order quantity under capital constraints — https://www.degruyterbrill.com/document/doi/10.1515/JSSI-2014-0358/html — trade credit versus external financing in ordering.
- Working capital with short-term debt (EPFL) — https://infoscience.epfl.ch/record/187592 — working-capital targets inflate when debt is dear or payment delays grow.
- IFS Copperleaf — https://www.copperleaf.com/?p=61314 — "capital allocation software" means investment portfolio planning.
- Hyperbots, capital allocation software — https://www.hyperbots.com/glossary/capital-allocation-software — category definition (capex).
- Gartner capital investment management — https://www.gartner.com/reviews/market/capital-investment-management-software — the category the phrase resolves to.
- Revenue leakage estimate (vendor) — https://chatfin.ai/guide/the-sales-finance-disconnect-preventing-revenue-leakage-with-ai/ — 4–20% of revenue; vendor estimate, cited as such.
