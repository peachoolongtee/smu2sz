# r5: what SME owners know and do (ticket #94 of map #88; mission section 42, part of deliverable L)

Researched 10 October 2026, on `dev` at 0cd60cb (read-only) and the web. Desk research only. **No interview, pilot week or comprehension reading has been done with a real owner** (grilling #59 is still open: on 9 October the owner recorded that no SME could be reached). So every statement below about owner behaviour comes from published surveys, academic papers, regulation, vendor documentation, one public filing, and the repository's agent-run walks and role-play. None of it comes from FLOW's own users. The six questions are partly answerable. Where they are not, this file says so.

Labels used: **[V]** I fetched the source and read the figure on 10 October 2026. **[S]** the figure comes from a search-engine summary or a secondary report that I could not open in full; treat it as unverified. **[R]** the figure is already cited in the repository (market map `02-market-map.md` on `origin/research/strategy`, ticket #41, 8 October 2026) and I did not re-verify it. **(inf.)** marks my own inference.

---

## 0. What the repository already holds (the evidence base before the web)

| Source | What it is | What it can and cannot say about owners |
|---|---|---|
| `docs/pilot/interviews.md` | Five interview sets (owner, CFO, finance manager, credit controller, sales manager), behaviour-first, plus three count probes: buyers on a regular invoice, open invoices at once, deals open at once | **None has been run.** There is no `docs/pilot/interviews/` directory. The sets already ask Q5 (largest buyer's share, and whether the owner knows it without looking) and the deals-open probe, but they ask nothing about margin by customer and nothing about how lateness is assumed |
| `docs/pilot/dry-pilot-report-2026-10-09.md` (#62) | Eight weeks on the public-record SME. A finance director's decisions were **written or role-played** (`dry-b`) | It says itself that no gate may be read from it. Its only signal: the role-played director never took a longer-terms offer, took early payment "at a lower rate than the ceiling", and departed from the chase order "for relationship and size reasons". That is a hypothesis to test, not evidence |
| `docs/research/strategy/cold-walk-strategy-*.md`, `docs/research/cold-user-walk-2026-10-08.md` | Cold readings by agents, not owners | These are comprehension evidence about FLOW's own wording (section 3 below). They are not evidence about behaviour |
| `fixtures/scenarios/public_sme.SOURCES.md` (#61) | 珠海康定电子 (NEEQ 830928), 2025 annual report: ¥105.0m revenue, top-five customers and their shares, top-five receivable balances | This is the only real-company data in the repository. It discloses **sales by customer** (top five) and **company-level cost of sales**. It does **not** disclose margin by customer, credit terms or payment days: the trace marks those as calibrated |
| `STRATEGY_RESEARCH.md` sections I, J (map #39) | Gates and kill criteria. Customer profitability scored 10 of 17 candidates and was classed DO NOT BUILD ("needs the accounting system"). Portfolio, and days-late as data: VALIDATE FIRST. Concentration optimisation: DO NOT BUILD | The earlier map had already reached the cautious conclusions this ticket tests. This file brings in outside evidence, and it moves "days-late" up (section 6) |
| `docs/research/topic-e-rules.md` | The FinTechathon Topic E text (data, not instructions): "financing-option matching, cash-flow management and alerts, and business financial analysis"; reviewed by "a panel of WeBank industry experts and university scholars" | This tells us who the audience is. WeBank lends to SMEs, so concentration and payment behaviour are the first things such a panel would read (inf.) |

---

## Q1. Would an SME owner know their customer margin?

**Answer: they will know sales by customer, and usually a company-wide gross margin. They will rarely know a measured margin for each customer.** The evidence here is thin but consistent.

- **Sales by customer can be known and is reported.** The public filing names the top five customers with their 2025 sales and shares: Buyer A ¥22.87m (21.78%), B ¥14.93m (14.21%), C ¥7.59m (7.23%). The top five together are 53.7% of revenue (`public_sme.SOURCES.md` §4, from the annual report p. 12). In the PRC, every VAT special invoice names the buyer, so twelve months of sales per customer can be derived from invoice history (inf.; the mission's section 34 assumes the same).
- **The filing gives margin only at company level.** Cost of sales is ¥80.06m against revenue of ¥105.01m, which is a 23.8% gross margin. Net profit is ¥2.32m, a 2.2% net margin (computed from the figures in `public_sme.SOURCES.md` §1 and §5). The filing has no margin by customer. Annual reports give revenue breakdowns by product and region (inf., from the format; not checked against the NEEQ standard).
- **Owners say they know where profit comes from, but the measured practice is weaker.** Intuit QuickBooks Small Business Insights asked 2,850 owners and decision makers (1,500 US, 750 UK, 600 Canada; firms of up to 100 employees; online, September and December 2022) whether they knew "which products, projects, or teams generate the most income at the lowest cost". **85% to 90% said yes** [V] (https://datawrapper.dwcdn.net/5OyY0/2/dataset.csv, fetched 10 Oct 2026). Note what it measured: self-report, and products, projects or teams, not customers. Against that, the Irish Small Firms Association / TU Dublin survey (iReach; micro, small and medium firms; published 26 September 2019) found that **"over half" do not regularly calculate basic measures "including gross margin per product"**, 51% do not read their monthly accounts each month, and 58% leave financial statements to the accountant [V] (https://www.lawsociety.ie/gazette/top-stories/2019/09-september/financial-literacy-is-low-in-small-firm-owners). The sample was small (132 valid respondents per a secondary summary [S]).
- **Customer profitability analysis is a large-firm practice.** No survey I found measures its adoption in SMEs. The literature is about large firms (for example, a survey of large Norwegian companies, NTNU), single case studies (a UCT dissertation on one South African SME, which says its findings "cannot be generalised"), and a 2024 PLOS ONE case study (Lueg and Ilieva) that ties CPA sophistication to uneven customer volume and customer-specific overhead [S] (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11111084/). The repository's market map cites a consumer-goods study in which 71% applied cost-to-serve to specific customers [R]. That population is large firms. **The evidence for SMEs is thin. I did not find a figure for the share of SMEs that track margin by customer, and I have not filled that gap.**
- **Industry level, PRC:** for January to August 2026, industrial enterprises above the size threshold carried ¥85.07 of cost per ¥100 of revenue, which implies roughly a 15% gross margin across industry [S] (NBS figure as reproduced by 格隆汇, 28 September 2026, https://m.gelonghui.com/live/2690970; not checked against the NBS original).

**What the repository's interviews and walks say:** nothing. No interview question asks about margin. The pilot books (`fixtures/pilot/*`, `templates/state.example.json`) carry no margin field. `Counterparty` has no sales or margin field (map #88's reconciliation).

**Design meaning**
- **Ask the owner for one number per customer, and offer a default.** The default is the company gross margin from the accounts, labelled `ESTIMATED (company average)`. The owner may overwrite it, and the label then becomes `OWNER_ENTERED`. Do not ask "what is your contribution margin for Foshan?" cold. Owners can answer "roughly what do you make on Foshan's orders, compared with your average?" (inf.; untested).
- **Derive annual sales from invoice history.** Label it `INVOICE_HISTORY` with the months covered. Ask the owner only when there is less than twelve months of history, and then label it `OWNER_ENTERED` or `ESTIMATED`.
- **Margin is the weakest input, so show what depends on it.** The concession's share of annual profit is inversely proportional to margin. ¥28.3k is 7.1% of ¥2.0m × 20%, 5.9% at 23.8%, and 3.0% at 47.5% (arithmetic). An expandable line such as "at a 15% margin this would be 9.4%" is one figure, and it is honest about the input. Do not make it a slider on level 1 (mission §41).
- **Do not build** cost-to-serve, activity-based customer costing, or the working-capital-adjusted profitability of mission §5 as a headline figure. No SME population is shown to have the inputs.

**Kill / defer (section 51) supported:** *defer sophisticated adjusted profitability*. The evidence says the input data is weak for this population, exactly as section 51 anticipates and as map #39 classed it (DO NOT BUILD). The simple version (sales × an owner-entered or estimated margin, with provenance) is supportable as **context only**.

---

## Q2. Would they think in gross profit or contribution?

**Answer: in gross profit (毛利 / 毛利率), because that is the line their accounts and their bank show. Contribution needs a split between variable and fixed cost that statutory accounts do not report.** The evidence is indirect.

- PRC statutory statements report 营业成本 (cost of sales) and therefore gross profit. Nothing in them reports variable cost. The public filing illustrates this: a contribution figure can only be **derived** by making assumptions about which costs are variable.
- **The two measures diverge sharply for a manufacturer.** On the public-record SME, gross margin is **23.8%**. If production wages and depreciation are treated as fixed and the rest of cost of sales as materials (the fixture's own derivation, `public_sme.SOURCES.md` §5, used there for the supplier flow), "contribution" over materials is about **47.5%**. Net margin is **2.2%**. The ratio "concession ÷ annual profit from this customer" therefore changes by a factor of two depending on which measure is used, and by a factor of twenty if someone reads it as net. This is the derivation in the fixture, not the company's own management accounts (illustrative).
- The Irish SFA survey (above) shows that even gross margin per product is not computed regularly by more than half of the sample [V]. Contribution is one step further from what these owners compute (inf.).
- The UK, Irish and US surveys I found test self-rated literacy, not whether owners can tell gross from contribution. **I found no survey that measures this distinction.**

**What the repository says:** the mission's own example calls ¥2.0m × 20% a "contribution". `FINANCIAL_SEMANTICS` and the strategy MVP have no margin term yet. No walk has tested either word.

**Design meaning**
- **Default term: "gross profit" (毛利), from the gross margin, labelled with its source.** Use it on the card as "about 7.1% of the ¥400k gross profit we estimate Foshan brings you each year". Gross profit is the **lower** of the two measures, so the concession's share comes out **larger**, which is the cautious direction for a figure that informs a decision outside the mandate (inf.; the reasoning is arithmetic).
- **Accept "contribution" only when the owner enters a variable-cost margin and calls it that.** Store which measure was entered (`margin_basis: GROSS | CONTRIBUTION`) and print the word that matches. Never relabel a gross margin as contribution.
- **Never print "profit from this customer" or "customer profitability".** Even the gross figure is not what the customer earns the firm. Mission §4: "do not pretend gross profit equals true customer profitability".
- **Add to the interview set (Set 1, after Q5):** "What did you make on [largest buyer]'s orders last year, and where would you look it up?" Write down the word they use (毛利, 利润, 净利) and the source (accountant, ERP, their head). This tests behaviour, not preference.

**Kill / defer supported:** none on its own. The finding narrows A (one measure, gross by default, with a recorded basis) rather than killing it.

---

## Q3. Would sales use "safe packages"?

**Answer: no field evidence exists either way. There is good experimental evidence that offering several whole packages beats single offers and per-lever maxima, and good market evidence that the price lever is the weakest one in China today.**

- **Packages, not maxima (experimental).** Leonardelli, Gu, McRuer, Medvec and Galinsky (2019, *Organizational Behavior and Human Decision Processes* 152: 64–83; six experiments) found that multiple equivalent simultaneous offers (MESOs) gave stronger anchors and better outcomes for the offerer, greater joint gains, and a more cooperative climate than a single package [S] (abstract via https://researchers.mq.edu.au/en/publications/multiple-equivalent-simultaneous-offers-mesos-reduce-the-negotiat/). The population is laboratory participants, not SME sales staff.
- **Why terms are given at all (PRC, 2024 data).** Coface's China Corporate Payment Survey (April 2025; 1,016 respondents [S for the count]; 13 sectors) gives these reasons for offering credit: market competition 26%, market practice 23%, customers requesting it 22% (up from 14%), confidence in the client 14%. Only **65%** offered payment terms at all, down from 79%, so **35% sold without credit terms** in 2024 [V] (https://coface.com/content/download/77518/file/20250328%20-%20Payment%20survey%20-%20China%20Longer%20payment%20terms%20helped%20mitigate.pdf, text extracted 10 Oct 2026). Upfront or cash terms are a common practice in China, not an exotic lever.
- **Who gets long terms.** Klapper, Laeven and Rajan (2012, *Review of Financial Studies* 25(3); about 30,000 trade-credit contracts) found that large, creditworthy buyers receive the longest terms from smaller suppliers, and that early-payment discounts are offered more often to **riskier** buyers [S] (abstract, https://www.nber.org/papers/w17146). Fabbri and Klapper (2016, *Journal of Corporate Finance* 41; firm-level data on Chinese firms) found that suppliers with weak bargaining power extend more credit and longer terms, and that "important customers" take payment beyond the agreed term [V, abstract] (https://openaccess.city.ac.uk/id/eprint/17179/).
- **Accepting rather than countering is common.** Intrum's European Payment Report 2025 (published April 2025; 9,150 executives, 25 countries [V for the sample]) reports that 56% accepted unfavourable payment terms to protect relationships, and almost half accepted longer terms to avoid customer bankruptcies [S] (press release, https://inderes.dk/releases/intrums-european-payment-report-2025-ai-can-play-a-critical-role-in-economic-recovery-urgently-needed-across-europe). Creditsafe's sales-versus-credit survey: 47% of sales staff have up to 10 deals a month rejected by finance; 21% of firms have no formal credit policy and 42% do not understand theirs [R; date and sample behind a form].
- **The price lever is weak in today's Chinese market.** PPI fell 1.1% in 2024 and price competition intensified, according to the same Coface report [V]. The automotive supply chain runs annual price-down rounds (年降), which suppliers describe as squeezing margins. In June 2025, 17 automakers publicly pledged supplier payment within 60 days [V for the 17] (Xinhua, 12 June 2025, https://www.news.cn/fortune/20250612/d908a333c6cb4ad58ea410d7cd167eec/c.html). Suppliers later reported that actual payment had not improved at some automakers, and that "paid" might mean a commercial acceptance bill [S] (cnstock, 14 August 2025, https://paper.cnstock.com/html/2025-08/14/content_2104694.htm). A package that asks the buyer for "+0.4% price" therefore asks for something the market currently pushes the other way (inf.).

**What the repository's walks say** (agent readers, comprehension only):
- The single-sentence package worked. "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥257,200 … at 0.85%" was understood in one reading (`cold-walk-strategy-2`).
- The composite "you can live with" sentence did not. One reader understood "up to 55-day terms if the price rises 0.30%, or early payment at up to 0.85% …; a rebate up to 1.25%; not 60 days without an early payment" only "half" (`cold-walk-strategy`, lines 13–27). Readers misread "not 60 days without an early payment" and were "lost" by "Lowest price that works: none works" beside "Price we would counter with 0.45%". Six near-identical percentages on one invoice (0.70 / 0.85 / 0.88 / 0.89 / 0.90 / 1.20) were the main source of confusion.
- "A rebate up to 1.25%" when the buyer asked for 1.00% invites "why would I give more than asked". Showing ceilings anchors against the owner.
- In the dry pilot's role-play, the director never took a longer-terms offer and took early payment below the ceiling. Written decisions only, with no gate read.

**Design meaning**
- **Show packages, not ceilings.** Two or three whole packages, each one sentence, each re-verified. That matches mission §11 and the envelope's grid, which already exists. Retire the multi-lever "you can live with" headline. Per-lever maxima stay in the evidence layer, never on level 1, and never phrased as something the owner may give.
- **Order the levers by how realistic they are in this market (inf.):** fewer days at current price, then part upfront or early payment, then a price step. Label the price step "needs the buyer to accept a price rise". Upfront is the most common real-world substitute in China (35% sell without terms), so the missing upfront dimension (#92) is worth adding.
- **One label per package for the mission's §13 split:** `Safe and within your limits` / `Safe, needs your approval`. Never a percentage of acceptance.
- **What to ask:** the interviews' Set 5 Q6 ("Have you offered price instead of terms, or the reverse; how did you pick?") is the right behavioural probe and should run before the price lever is promoted.
- **Do not build** a free-form multidimensional slider, a "maximum discount / maximum terms" table at level 1, or any negotiation-likelihood model.

**Kill / defer supported:** section 51's *"avoid multidimensional search if the UX becomes impossible to explain; return a few validated packages"*. The walks show the composite sentence is already at that limit. Keep the search engine (built, read-only) and present it only as packages. The existing gate stands (`STRATEGY_RESEARCH.md` I: kill if the owner's chosen response is outside the zone or packages on more than half of the first ten real offers).

---

## Q4. How often do simultaneous negotiations occur?

**Answer: unknown. No published source I found measures it for SME suppliers, and the repository has no count.** This is the thinnest of the six.

- The closest proxies only describe the shape of the customer base. In the public filing, the top five customers are 53.7% of sales and the rest (46.3%) is spread over unnamed buyers. A 2000 National Research Council survey of 98 small US manufacturers found the top three customers averaged 42.4% of sales (median 34.3%) [S] (https://www.nap.edu/read/6369/chapter/17; old and small). Neither says how many buyers negotiate in the same week.
- Annual cycles (年降 price rounds, year-end tenders, contract renewals) suggest negotiations **cluster** in a few weeks rather than spreading evenly (inf.). That would make "most weeks" a poor test, because a portfolio need could be real but seasonal.
- The Creditsafe figure (up to 10 deals a month rejected for 47% of sales staff [R]) shows deal flow in firms with sales teams. It does not show overlap at owner-run SMEs.

**What the repository says:** the deals-open probe ("At this moment, how many buyers are in the middle of asking you for different terms, a discount or a rebate?") exists and has never been asked. The portfolio gate is "two or more deals open at the same time in most pilot weeks".

**Design meaning**
- **Do not build** the portfolio optimiser (mission §30, §49). Keep the primitives batchable: one candidate in, one projected state out, as map #88 decision 2 already says.
- **Amend the probe** so that it also asks "and in your busiest month last year?". A seasonal pattern then counts, and the gate reads "most weeks *or* a recurring busy season".
- **For a single deal, the honest form of "other deals" is capacity:** "this uses 82% of remaining line capacity through 30 November" (mission §15). That needs no count of rival deals.

**Kill / defer supported:** *portfolio stays VALIDATE FIRST*; the evidence does not justify building it. Section 51's *"no 'future order lost' without defined future demand"* is reinforced, because nothing defines how often a competing deal exists.

---

## Q5. Does AR concentration change negotiation behaviour?

**Answer: yes. The evidence is reasonably strong and comes from several directions. Concentration weakens the supplier's hand, raises lateness from important buyers, and reduces financeable receivables.** Part of that effect can be computed, which matters for design.

- **Bargaining power.** Fabbri and Klapper (2016, Chinese firms) found that suppliers with weak bargaining power give more credit and longer terms, and that important customers stretch payment past the term [V, abstract].
- **Fear of the large customer, from surveys.** Intrum 2025: 56% accepted unfavourable terms to protect relationships [S]. UK FSB: an older finding that only about one in ten small firms charged statutory late-payment interest because they fear losing business [S; year and sample unconfirmed]. Money Advice Trust (2020, Business Debtline clients): four in ten feared losing future business if they chased [S].
- **Financing: concentration reduces what can be financed.**
  - UK invoice-finance practice caps a single debtor at "usually 25% to 35%" of the eligible ledger, and the excess is ineligible or advanced at a lower rate [S] (Spark Finance glossary, https://www.sparkfinance.co.uk/glossary/concentration-risk; lender glossaries, not loan agreements).
  - Asset-based lending gives a 20% worked example [S] (ABF Journal, https://www.abfjournal.com/understanding-the-concept-and-rationale-of-standard-accounts-receivable-ineligibles/).
  - Liu, Ju and Chan (2022, *International Journal of Production Economics* 243; 1,929 Chinese listed firms, 2010–2019, hand-collected factoring data) found that higher customer concentration **reduces** suppliers' use of factoring, that customer stability increases it, and that supplier market power softens the concentration effect [V, abstract] (https://ideas.repec.org/a/eee/proeco/v243y2022ics0925527321002978.html).
  - Campello and Gao (2017, *Journal of Financial Economics* 123(1)) found that more concentrated customer bases pay wider loan spreads, face more restrictive covenants and get shorter maturities [S] (https://ideas.repec.org/a/eee/jfinec/v123y2017i1p108-136.html; listed firms, population not checked).
- **The PRC counter-case.** Supply-chain finance is anchored on a creditworthy core buyer through electronic receivable certificates. 银发〔2025〕77号 (PBOC, NFRA, the Supreme People's Court, NDRC, MOFCOM, SAMR; signed 26 April 2025, effective 15 June 2025) says those certificates' payment term "原则上应在6个月以内，最长不超过1年", and forbids core firms from using their dominant position to delay SME payment [V] (https://www.gov.cn/gongbao/2025/issue_12086/202506/content_7026996.html). Concentration on a large, confirming buyer can therefore **open** a financing route in China that a UK debtor cap would close (inf.).
- **Policy evidence of the same mechanism.** A 2026 SSRN working paper on China's SME payment-protection reforms reports adverse effects concentrated among suppliers with high customer concentration [S; page returned 403, provisional] (https://papers.ssrn.com/abstract=6435458).
- **Real concentration levels.** The public-record SME has its largest customer at 21.8% of sales and its top five receivable balances at 47.9% of AR (filing p. 120). The demo fixture has Foshan at 100% of AR, which is extreme but not impossible for a small supplier (inf.).

**What the repository says:** interview Set 1 Q5 ("How much of your receivables sits with your largest buyer; do you know without looking?") and Q9 ("Which buyers have you kept despite poor payment, and why?") ask exactly this, and neither has been asked. The dry-pilot role-play departed from the chase order "for relationship and size reasons" (role-play only).

**Design meaning**
- **Show concentration as up to four separate shares, never as one score:** current AR, receipts due in the next 30 days, annual sales and annual gross profit (mission §17). On the deal card, show only the share that is material, for example "Foshan is 100% of what you are owed today".
- **Where concentration changes the numbers, compute it; do not merely mention it.** If an invoice-finance facility has a single-debtor cap or an eligibility rule, the eligible amount falls, and that is a capacity fact (D) and a stress fact (E). The data matrix (#90) should record whether `INVOICE_FINANCING` facilities carry a concentration cap. The fixture's platform terms (advance 80%) show none. Adding a cap is a facility-terms input, not a rule change.
- **Concentration informs; it never decides** (mission §18). No change to the mandate unless the owner writes a policy.
- **What to ask the owner:** the Q5 probe, and whether their bank or platform has ever refused or capped financing on one buyer's invoices. This is behavioural and checkable against facility letters.
- **Do not build** concentration optimisation or a diversification recommender. Map #39 already classed it DO NOT BUILD, and the evidence gives FLOW no lever to pull.

**Kill / defer supported:** none on the concentration *display*. The evidence supports E. It supports *"concentration affects context, not rules"*, with one qualification: where a facility's terms make concentration a funding constraint, it becomes a computed capacity input rather than only context.

---

## Q6. How are payment-delay assumptions used today?

**Answer: most small firms forecast on the due date and treat lateness as a fact of life. Better tools apply a per-customer average of days late from three or more months of history. Macro statistics show delays that are large, persistent and specific to sector.** The evidence is moderate to strong.

- **Tools.** Xero's native short-term cash flow projects from invoice due dates [S] (Chaser and Float summaries). Float's "Smart Expected Dates" "applies each customer's average days late from your own payment history to new invoices", starts "from three months of history and extending to twelve", is "applied at import and never recalculated", and can be overridden by hand [V] (https://floatapp.com/blog/xero-data-cash-flow-forecast; undated, ©2026; vendor material). Float also notes that "for a large minority of invoices the due date and the paid date are different days" [V].
- **Resignation.** The GoCardless and FSB report (UK, March 2025; more than 2,000 small-business owners) found:
  - 50% agree late payment is an "inevitable cost of doing business";
  - 45% had more late payments than a year earlier;
  - 52% write off late payments up to 10 times a year rather than chase;
  - 28% used short-term finance to cover them;
  - 32% feel little or no control.

  [S] (https://gocardless.com/blog/gocardless-fsb-late-payments-report-2025/)
- **PRC macro data (where delay expectations come from).**
  - Industrial enterprises' average receivable collection period was **76.4 days** at end-February 2026, 1.3 days more than a year earlier, on ¥26.55tn of receivables (+7.1%) [V] (NBS, 27 March 2026, https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202603/t20260327_1962868.html).
  - It was **72.2 days** at end-August 2026 (+0.9 days) [S] (NBS figure via 格隆汇, 28 September 2026).
  - Coface China (2024 data): average terms 76 days; 44% of respondents reported overdue payments (down from 62%); average delay 65 days; delivery to cash 141 days. Among firms with delays over 180 days, almost half had late payment above 2% of turnover. Coface says 80% of such debts are never collected [V].
  - Atradius China (Q3 2024 survey): late payment affects "just over one third" of B2B invoices; bad debt 3% of credit sales [S] (https://atradius.nl/rapport/payment-practices-barometer-china-cash-flow-strained-by-default-on-b2b-payments.html). **Correction to the repository:** the market map cites "Atradius China 2025 (35% overdue, 4% bad debt, 51-day terms)". I could find only the 2024 China report (about one third, 3%) and a pooled 2025 Asia report (44% overdue, 5% bad debt, eight markets) [S]. The "2025 China" figures are **unverified** and may be a mix of the two.
- **Regulation sets a contractual anchor, and practice lags it.** The 保障中小企业款项支付条例 (2025 revision, in force 1 June 2025) requires large enterprises to pay SMEs within 60 days [R]. Seventeen automakers pledged to do so [V]. Suppliers report that some still pay late or pay in commercial acceptance bills [S]. A "receipt" may therefore be a bill, not cash. The public-record fixture already flags this: its supplier payments are largely endorsed bank-acceptance bills (`public_sme.SOURCES.md` §5; dry-pilot report §6.1).
- **Comparators** [R, not re-verified]: UK DBT (July 2025): late payment costs £11bn a year, 86 hours a year spent chasing per affected business, and a 60-day cap announced. Xero Australia: 6.6 days late on average. PwC: global DSO rose from 47.3 to 50.0 days over 2015–2024.

**What the repository says:** the log holds each `RECEIVE_PAYMENT` with the reported day, and nothing aggregates it (map #88, E). The fixtures hold too little history for a P90. Interview Set 4 Q6 ("How do you record a promise to pay; does the forecast use it?") and Set 3 Q8 are the right probes and have never been asked. The dry pilot landed no receipts at all, so it says nothing about delays.

**Design meaning**
- **The contractual date stays the default projection** (the engine's existing semantics). FLOW adds two labelled alternatives.
  - **"Typical"**: this buyer's **median** days late, computed from receipts, with N and the date range shown ("median 11 days late over 9 payments since March").
    - Below a minimum history, show "not enough payment history yet" and give no typical figure. Float's three-month floor is one industry precedent. The receipt count is for the owner to set in #89, not invented here.
    - Use the median rather than the mean, because single very late payments are common (Coface's ultra-long delays) and would drag a mean (inf.).
    - Show P75 or P90 only once the count supports it.
  - **"Stressed"**: a fixed, named shift, for example "+30 days", the same for every buyer and labelled as a scenario. It needs no history, so it works on day one.
- **Never use a survey average as a buyer's assumption.** Coface's "65 days" is the average delay among firms that report delays, not anyone's expected lateness. NBS's 72–76 days is a collection period, not a delay. Macro figures may appear only as labelled context ("industry average collection period 72 days, NBS, August 2026"), never in the projection.
- **Settlement in bills is not cash.** If a buyer pays by acceptance bill, the "paid" day is not the cash day. Receipt statistics should record the instrument when the books do. If they do not, say so (data matrix #90).
- **Observed data outranks the owner's word** (mission §20). The owner's "they're usually two weeks late" is stored as `OWNER_ENTERED` and shown only while no history exists.
- **What to ask:** "When you last forecast cash, which date did you use for [buyer]'s invoice: the due date or when you expected it?" and "When did [buyer] last pay, and by what: transfer or 承兑汇票?"

**Kill / defer supported:** no kill. This is the best-supported capability. Defer percentile statistics (P90) until history exists. Keep the stressed scenario, which needs no history.

---

## Ranking the five capabilities for the owner's "lead with one"

The ranking is by strength of outside evidence that the problem is real and that owners face it, the data FLOW can get without asking the owner, and how directly the evidence supports the design. Build cost is the synthesis ticket's (#95) to weigh.

| Rank | Capability | Evidence for the problem | Data without owner input | Main evidential risk | Verdict |
|---|---|---|---|---|---|
| **1** | **E: late-payment stress and concentration** | Strong and PRC-specific: NBS 72–76-day collection periods; Coface 65-day delays and 141 days delivery to cash; regulation and pledges that lag practice; concentration lowers financeable receivables and raises lateness from important buyers. It matches the Topic E wording ("cash-flow management and alerts") and a lender panel's habits (inf.) | High. AR shares are derivable now. The stressed scenario needs nothing. The typical delay needs receipt history (the log holds it; the fixtures are short) | History is thin at first. Bills versus cash | **Lead.** Ship the stressed scenario and the AR share on the deal card first. Add the typical delay as history accrues |
| 2 | C: safe commercial packages | Experimental support for packages (MESO); the market shows terms are conceded under competition (Coface 26% / 23%) and relationships (Intrum 56%); agent walks show packages read well and composite maxima do not | High; already built, flagged | No field evidence that sales would use them. The price lever is unrealistic in a deflationary market | Keep, reshape to two or three sentence packages, add upfront. Gate by the existing ten-offer test |
| 3 | D: capacity consumption | Indirect: 28% of UK SMEs borrow to cover late payment (GoCardless/FSB); lenders cap concentration and ration financing (Liu et al., Campello and Gao) | High: facility limits and drawn amounts are in the books | No survey asks whether owners think in "capacity". The value lies in composing with E and C | Build as the "capacity before and after" line beside E, not as its own screen |
| 4 | A: customer economics | Owners know sales by customer; they rarely measure margin by customer (SFA, CPA literature); self-reports overstate it (QuickBooks 85–90%) | Sales: yes, from invoices. Margin: no, it needs owner input and is weak | The headline "7.1% of contribution" rests on an unmeasured margin | Build only the simple version (sales × gross margin, provenance, sensitivity line), as context. Defer adjusted profitability (§51) |
| 5 | B: accept / counter / customer-loss scenarios | The fear is real and documented (Intrum 56%, FSB, Money Advice Trust): owners concede to keep customers | Inherits A's weak margin; no churn data anywhere | A "loss" scenario multiplies the weakest input (margin) by an unmodelled event | Defer as a separate surface. Fold one line into the card ("if Foshan stopped buying, you would forgo about ¥X of gross profit a year; an assumption, not a forecast") only after A's input is owner-confirmed |

**One sentence for the owner:** the outside evidence most clearly supports leading with **E**: what this deal and this buyer do to cash if payment is late, and how much of what you are owed sits with this one buyer. The safe packages already built (C) and the capacity line (D) should be presented beside it. **A and B depend on a margin figure that SME owners demonstrably do not measure per customer.** They should enter as labelled owner estimates, giving context and never the headline, until the interviews show otherwise.

## The interview additions this file recommends (for #89 / #59; behaviour, not opinion)

1. Set 1, after Q5: "What did you make on [largest buyer]'s orders last year, and where would you look it up?" (Q1, Q2: record the word and the source.)
2. Set 1 or Set 3: "When you last forecast cash, which date did you use for [buyer]'s invoice: the due date or when you expected it? How late did it actually arrive, and in cash or in bills?" (Q6.)
3. The deals-open probe, extended: "...and in your busiest month last year?" (Q4.)
4. Set 1 or Set 2: "Has a bank or platform ever capped or refused financing on one buyer's invoices?" (Q5.)
5. Set 5 Q6 already exists and should be asked before the price lever is promoted (Q3).

## Gaps stated plainly

- No SME owner, finance manager or salesperson has been interviewed. Every behavioural claim comes from surveys in other markets (UK, Ireland, US, Europe) or from PRC macro data, apart from one PRC filing.
- I found no survey measuring: the share of SMEs that track margin by customer; whether owners distinguish gross from contribution; how often negotiations overlap; whether owners use per-customer delay assumptions (as opposed to what tools offer).
- I could not open the full texts of Fabbri and Klapper (2016), Klapper, Laeven and Rajan (2012), Campello and Gao (2017), the MESO paper or the SSRN working paper. Their findings above are from abstracts.
- The repository's "Atradius China 2025" figures could not be verified (see Q6). The 72.2-day NBS August figure is from a secondary reproduction.
