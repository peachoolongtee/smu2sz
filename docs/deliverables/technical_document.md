# FLOW: Technical Document

2026 FINTECHATHON · SUBMISSION
International AI Track | Technical Document

| Team name | ISMOGGER |
| --- | --- |
| Competition track | International AI Track — Topic E: SME Finance Copilot |
| Submission date | 20 October 2026 |

**FLOW is a working-capital agent for a small supplier. When a large buyer asks for better payment terms, FLOW works out
what the request would cost the supplier in cash and borrowing, answers within limits the owner has signed, and arranges
and follows the funding the answer needs.**

- **Who it is for.** The owner of a supplier business with roughly 20 to 100 staff, 10 to 40 business buyers, one bank
  credit line and no finance team, who sells on credit to buyers larger than itself.
- **The decision it improves.** Whether to grant a buyer's request for longer payment terms, an early-payment discount or a
  rebate (trade credit the supplier gives), and how to fund what that costs (credit the supplier must then take). Today
  the owner usually decides the first alone, from a chat message, and discovers the second later.
- **Why it matters financially.** On the demo company's books, a buyer asks for 60-day terms instead of 45, 1.2% off for
  paying one invoice early and a 1% rebate. Priced at the supplier's own cost of borrowing, accepting as asked gives away
  **CNY 33,366.92**: a ¥5,040 discount now and ¥28,326.92 of future concessions over the next 365 days, 5.7 times the
  owner's limit for such promises. It also takes cash below the owner's safety reserve from day 47.
- **What FLOW does today.** It reads the request and the supplier's contracts; projects daily cash, debt and loan
  covenants; returns a verdict with its reason, formula and priced counter-offers; finds a funding plan among the owner's
  committed facilities; asks the owner for anything it may not do alone; follows the deal through receipts and
  reconciliation; and answers the owner's questions from the books, in English and Chinese.
- **Where AI contributes.** A language model assists in three places only: **reading** buyer messages, term sheets,
  contracts and lender agreements into typed terms, each tied to the words it came from; **classifying** an owner's chat
  request that the deterministic parser cannot read, into one intent from a closed list; and **routing** an owner's
  question to at most three of 40 read-only tools. Deterministic code computes every figure, verdict and reply. In the
  demo, the tests and every offline result, a deterministic rules grammar does the reading; a model is called only in
  live mode.
- **What limits its authority.** An owner-signed mandate (Ed25519) sets the reserve, the cap on future concessions, the
  covenants and the rate above which borrowing needs approval. The executor decides each operation's tier from the
  operation itself: **Tier 1** runs inside the mandate without an owner step, **Tier 2** waits for the owner's approval,
  **Tier 3** (personal guarantees, collateral, equity, changing the mandate) is refused for everyone, the owner included.
  No operation has a payee or account field.
- **The evidence.** Table 1, with each result's evidence class and denominator; section 03 explains them.
- **What is simulated, and what is incomplete.** Buyers, lenders, the bank feed and the clock are simulated. No real money
  moves and no bank, lender or payment API is called. FLOW runs as a local simulation; nothing in this document comes from
  a deployed system. FLOW accepts only 3 of 14 acceptable buyer offers on its own, does not read scanned or photographed
  contracts (no OCR), and its live-model results are single runs.

All amounts are Chinese yuan (CNY, written ¥) on synthetic books. "Day 0" is 1 October 2026, the demo books' opening date.

**Table 1. FLOW at a glance. Engine and agent figures: dev `975e082f` (17 Oct 2026), re-run offline on `571ea64f`
(18 Oct) with the same results. Owner-question and held-out figures: `571ea64f`, 18 Oct. Live figures: the dates given.
Table 18 gives each source.**

| What | Result | Evidence class |
| --- | --- | --- |
| Decisions | Six verdicts (accept, counter, reject, no deal, needs the owner, no verdict), each with the failing rule, the figures, its formula and the source words | Code |
| Engine correctness | 67 of 67 golden financial values exact to the fen against an independently written oracle (same specification, same team); covenant and capex values 27 of 27 | Tests |
| Funding router | Within ¥1 of a bounded brute-force search on 26 of 26 test scenarios; 19 plans run today, 6 are labelled "cannot run today", and in 1 scenario no admissible plan exists and the router says so | Tests |
| Safety of autonomy | On 115 held-out buyer messages FLOW accepted 3 on its own, all correctly. Before the coverage proof (ADR-0005), the first runs on the same sets accepted 6 misread messages; that is why autonomy now requires proof | Unseen first runs, then tuned |
| Usefulness | 57 of 115 messages handled with no owner step (54 counters or declines, 3 accepts). Only 3 of the 14 genuinely acceptable offers are accepted alone; the other 11 wait for one owner review (Table 9) | Tuned |
| Reading contracts | 75% of key fields right on 17 unseen Chinese contracts with a text layer (45% over all 30, because 13 scans and photos are refused) | Unseen, recorded model replay |
| Owner questions | Of 427 bank questions the books can answer, 228 answered from the books, 45 partly, 0 wrong (the bank the answers were built against). On 142 held-out everyday wordings, 127 reach the right answer (89%) and 3 a wrong topic (2%) | Tuned; held-out |
| Live model | One live DeepSeek run per component: buyer messages 42 of 63 verdicts, no wrong accept (1 Oct); the question router answered 33 of the 63 questions that reached it on 18 Oct, 22 fully right by one reviewer's reading | Live, single runs |
| Security | 279 stored attack cases (128 through the API, 151 through chat): none violated the defined harm oracles in the specified offline runs (rules path and a scripted hostile model; no real model read an attack). Internal review by the team's Security Lead, an AI agent; not external assurance (section 04) | Tests |
| Task completion | 49 of 49 scripted conversations, written by the team, pass their own checks (88 turns); the 17-step demo walk ends with a 14-entry hash chain that verifies, and a tampered copy is rejected | Scripted tasks, simulated environment |
| Product | Setup, a daily view, documents, customers, deals, money over time, approvals, a chat, what-if and strategy views, capex and an evidence export (Table 4), in English and Chinese | Code, browser tests |
| Tests | The API, web-unit and browser suites pass on the builds named in Table 18. A count measures the size of a suite, not correctness | Tests |

**How to read this document.** Section 01 follows one supplier through FLOW and states what is new. Section 02 explains how
FLOW is built and where a model is used. Section 03 explains how the agent understands, plans and acts, the algorithms, and
how well it works, including where it falls short. Section 04 covers security and section 05 running, testing and known
limits; the appendices follow section 05. Every number is synthetic and was measured on the build named beside it. The
submission build adds the Ask FLOW and error-handling changes described in sections 02 and 03 after the last measured
build.

## 01 Project Overview

### Problem, target users and selected topic

**Selected topic.** International AI Track, Topic E: SME Finance Copilot, under the theme "AI as a Financial Participant".
FLOW covers each part of the topic's scope: **financing-option matching** (the funding router compares the owner's
facilities), **cash-flow management and alerts** (a daily cash forecast and alerts that speak first), **business financial
analysis** (covenants, customer exposure, capex screening), **reconciliation** (each receipt matched against what was
promised) and **operational recommendations** (verdicts, priced counter-offers and funding plans).

Appendix 0 maps each judging criterion and template prompt to the section, table or figure that answers it and the
evidence file behind it.

**The problem.** Large buyers now negotiate payment terms with software. Procurement agents ask suppliers for longer terms,
early-payment discounts and rebates "within parameters you define" (Pactum's public material describes this). Lenders
approve small-business credit by model in seconds (MYbank, WeBank). The supplier in the middle usually has neither. An owner
reads a WeChat message at night and decides alone whether to accept 60-day terms, and separately, often later, whether to
borrow to survive them.

**The insight behind FLOW: a longer payment term is a loan from the supplier to the buyer.** It moves no money today, so
spending limits, approval rules and wallet controls let it through. But the supplier has to fund the gap, usually by
borrowing. On the demo company, whose largest buyer, Foshan Home Retail, receives a ¥420,000 invoice every 30 days on
45-day terms, the buyer's request (EX01) asks for three things:

- **Terms from 45 to 60 days on every future invoice.** That ties up ¥210,000 more in receivables on average for as long as
  the terms last (¥420,000 for 15 days in every 30). Priced at 10.84% a year, the all-in rate of invoice financing, the
  cheapest committed source that the credit line's 30-day clean-down rule allows, each invoice's 15 extra days cost
  ¥1,871.30, which is **¥24,326.92 over the 13 invoices issued in the next 365 days**. (10.84% is a tariff equivalent; an
  advance held for less than a whole 30-day period costs more.)
- **A 1.2% discount for paying the current ¥420,000 invoice early:** ¥5,040, given up now.
- **A 1% rebate on next quarter's expected ¥400,000 of orders,** counted at its maximum, ¥4,000.

The owner sees "60 days instead of 45". FLOW shows that the future concessions alone come to ¥28,326.92, 5.7 times the
¥5,000 cap the owner signed for such promises; that accepting as asked gives away CNY 33,366.92 in all; and that cash would
fall below the ¥300,000 reserve on day 47 and stay there until day 61.

**Target users.** Supplier SMEs with roughly 20 to 100 staff, 10 to 40 business buyers, one bank credit line, at least one
term loan, a bookkeeper and no finance team. Typical sectors are light-manufacturing subcontracting, packaging, logistics,
maintenance supplies and facility services. This profile is a composite drawn from our specification. In two interviews with
real SME owners, one assumed pain point (that the owner phones the bank when cash looks low) was contradicted, so we do not
claim it.

### Core value and innovation

**What FLOW does for the owner.**

1. **Reads the request.** It turns a buyer's message or contract, in Chinese or English, into typed terms, each tied to the
   exact words it came from.
2. **Prices it in cash.** It projects the supplier's daily cash, debt and future promises with and without the request, and
   prices every concession at the supplier's own cost of borrowing.
3. **Decides within the owner's limits.** It returns a verdict with the reason and the formula, and drafts priced
   counter-offers that keep the business safe.
4. **Arranges the money.** It searches the owner's committed facilities for the cheapest plan that keeps cash above the
   reserve and meets the covenants, and checks the covenants every month.
5. **Follows through.** It watches for late or partial payment, warns the owner first, proposes a fix inside the limits with
   its cost, and closes the loop when the money lands.

**One engine, two jobs.** *Terms Guard* controls the credit the supplier gives its buyers through payment terms, discounts
and rebates. *Debt Desk* controls the credit the supplier takes from lenders to survive those terms. They share one
financial model: a concession is priced at the supplier's real marginal cost of debt, and because Debt Desk knows the
funding alternative, FLOW can walk away from a bad deal and still cover the gap.

#### One supplier's journey, from documents to reconciliation

The demo company's story, tied out to the fen by an independent recomputation and by the engine replayed day by day
(`scripts/demo_run.py`, 17 steps). Each step says what state the money is in: **proposed** terms bind nobody; an
**authorised** operation has passed the executor's checks; a **recorded** commitment is in the hash-chained log; **settled**
means the (simulated) bank feed reported the cash.

1. **Documents.** The owner attaches the supply agreement with Foshan Home Retail. FLOW reads each term beside its clause
   (price ¥420,000 per batch, 45-day terms) and checks that Foshan is the contract's buyer. Nothing changes in the books
   until the owner confirms the reading, and a confirmed contract becomes forecast invoices only through a separate,
   undoable Tier-2 step.
2. **Today's books already need money.** Cash is ¥400,000. Payroll of ¥340,000 (day 12), a supplier payment of ¥120,000
   (day 20) and a loan payment of ¥45,000 (day 30) come before Foshan's ¥420,000 invoice is due on day 32. Untouched, cash is
   below the reserve on days 12 to 31 and reaches −¥105,000 on days 30–31: a need of ¥405,000. FLOW's standing plan draws
   the credit line (¥150,000 today, ¥841.64 of interest) and finances the Foshan invoice (¥255,000 landing on day 3,
   ¥2,272.29 for one 30-day period): **¥3,113.93**, with cash exactly at the reserve on day 30.
3. **The request and the verdict (proposed).** Foshan writes: "We'll settle the ¥420k early at 1.2% if you extend our
   standard terms to 60 days going forward and give us 1% off next quarter." FLOW rejects the package as asked, for four
   reasons: the concession cap (¥28,326.92 against ¥5,000); the reserve (¥90,040 short on day 47, ¥135,040 at worst on day 60);
   break-even (1.2% is above 0.8832%, beyond which paying for 30 days' early cash costs more than borrowing it); and price (with the early
   payment the funding costs ¥6,508.05, without it ¥3,873.58). It drafts two counters. **Option A**: terms stay at 45 days,
   no rebate, early payment on up to ¥260,000 at 0.85%. **Option B**: 55 days with a 0.30% price rise, a forward gain of
   ¥162.05 over 13 invoices, but its books still need **CNY 3,706.46** of funding. FLOW recommends Option A (Figure 1).
4. **Agreement (authorised, then recorded).** The owner sends Option A. When the buyer's acceptance arrives, the executor
   re-checks it on that day's books, binds it to the counter's terms hash and a single-use nonce, and records the
   commitment. Its funding runs as a Tier-1 operation: the credit line draws ¥147,210 (405,000 − 257,790). Quoted cost:
   ¥2,210.00 of discount plus ¥825.99 of interest, **¥3,035.99**, ¥77.94 below the standing plan, with no future concession.
5. **First receipt (settled).** On day 2 the bank feed posts ¥257,790.00 (¥260,000 at 0.85%); ¥160,000 of the invoice is
   still due on day 32. Reconciliation marks the promised early payment as received.
6. **Reality diverges.** On day 25 the bookkeeper schedules a second payroll of ¥200,000 for day 42. On day 32 the ¥160,000
   does not arrive. On day 34 FLOW speaks first: on the conservative forecast, which drops the overdue ¥160,000, cash would
   close day 42 at ¥100,000, ¥200,000 below the reserve. The new payroll causes the breach (with the ¥160,000 paid on time,
   day 42 would still close at ¥111,964.01); the late payment deepens it.
7. **Approval.** FLOW proposes an advance of ¥200,000 on the invoice due on day 47: ¥1,782.19, because a whole 30-day period
   is billed for a 10-day hold, which is 32.5% a year. That is above the 15% a year above which FLOW must ask, so "go ahead"
   **queues it for approval and nothing runs**. The owner's "approve APR-000001" runs it.
8. **Receipts and reconciliation (settled).** The ¥160,000 arrives on day 36 and the advance lands on day 37. After the
   payroll on day 42 cash is ¥460,000. On day 47 Foshan's next invoice is paid, the advance is repaid from it first, and the
   credit line is repaid with ¥1,213.17 of interest (47 days instead of the quoted 32). Reconciliation closes the deal, and
   the record holds 14 hash-chained entries that verify.

**Table 2. Option A's cost, quoted on day 0 and actually posted by day 47 (CNY).**

| Cost item | Quoted on day 0 | Actually posted |
| --- | --- | --- |
| Early-payment discount | ¥2,210.00 | ¥2,210.00 |
| Credit-line interest | ¥825.99 (32 days) | ¥1,213.17 (47 days, ¥160,000 paid late) |
| Advance to cover the new payroll | — | ¥1,782.19 |
| **Total** | **¥3,035.99** | **¥5,205.36** |

The supplier kept its 45-day terms and gave no rebate. It avoided ¥28,326.92 of future concessions, the ¥5,040 discount and
a day-47 breach, and the reserve held on every day (Figure 2). Assumptions: the buyer pays the ¥160,000 on day 36 and the
next invoice on its due day 47; the owner approves on day 34; no other cash flow is added.

<!-- figure: figures/screens/screen2-deal-verdict.png | Figure 1. Foshan's request after FLOW checked it (web app on recorded mocks, build 571ea64f). (1) The verdict: counter with Option A. (2) Why the request cannot be accepted as asked. (3) Option A is within the signed mandate. (4) Nothing is sent until the owner sends it. (5) The priced choices: Option A, early payment on up to ¥260,000 at 0.85%, costs ¥3,035.99; Option B is 55-day terms with a 0.30% price rise. | page -->

<!-- figure: figures/fig11-cash-scenarios.png | Figure 2. The demo company's closing cash, days 0 to 62, against the ¥300,000 reserve. Today's books fall to −¥105,000 on days 30–31; FLOW's standing plan (¥3,113.93) touches the reserve on day 30 and never goes below it; the request accepted as asked falls ¥90,040 short on day 47; Option A as the demo runs it holds the reserve every day, including the new ¥200,000 payroll on day 42. Numbered markers date the events. Data: the financial audit's independent recomputation, equal to the engine to the fen (synthetic golden books, mandate v1, build 571ea64f). | page -->

**What is new.** Each building block exists somewhere: negotiation agents, cash-flow forecasts, loan marketplaces and
covenant monitoring. What FLOW adds is the combination, on the supplier's side:

- **An agent the supplier owns, bounded by its own signed limits across both debt books:** what it may promise buyers, and
  what it may borrow to keep those promises.
- **A promise is treated as a liability before it costs anything.** A contingent concession counts at its maximum exposure
  and an unapproved loan counts as zero, on a dated daily cash forecast. That forecast is a hard boundary for every decision,
  together with a cap on total concessions and the bank's covenants.
- **Autonomy only with proof (ADR-0005).** FLOW may accept a buyer's offer on its own only when it can show it has accounted
  for every figure and request in the message. Otherwise the owner decides.
- **One deterministic pipeline.** Reading, forecasting, funding, covenants, the signed mandate, commitments and an
  injection-resistant typed interface form a single pipeline, not a set of independent tools.

**Table 3. Products in the same space (vendor descriptions; "difference" is our reading of public material).**

| Product | What it does | How FLOW differs |
| --- | --- | --- |
| Pactum | Buyer-side agents that negotiate payment days, discounts and rebates | FLOW sits on the other side of the table |
| MYbank 百灵 / AI票据管家 | Lender agents that tailor the bank's own credit and bill products | FLOW is supplier-owned and compares several sources, starting from the trade terms that cause the need |
| Xero JAX Cash Flow Actions | Ledger-side cash-gap detection and suggested plans | FLOW reads incoming offers and decides them inside a signed mandate and covenants |
| Cerebro Capital, Capitalise, Codat, Lendio | Lender marketplaces and debt-capacity tools for banks or mid-market firms | FLOW starts before the owner decides to borrow, at the request that creates the need |

#### Innovation & Interaction: what the owner sees

FLOW is one web app with eight pages on its menu (Home, Deals, Attach deals, Cash & funding, Sandbox, Capex, Receivables,
Activity), a chat on every page, and an account menu. Table 4 lists every screen. Appendix E follows one supplier through
them in order.

**Table 4. Every screen, what the owner does there and what FLOW does (the web app computes no figure; the server writes
every figure and sentence).**

| Screen | The owner | FLOW |
| --- | --- | --- |
| **Set up your books** (`/setup`, six steps) | Enters the company, cash, monthly sales and costs; credit lines and loans being repaid; customers with repeating contracts and unpaid invoices; bills coming up; the limits (minimum cash, the rate above which FLOW must ask before borrowing, concessions a year, the approval threshold, covenants, validity). Can fill a lender or customer step from an uploaded agreement. Re-types the owner token to sign | Checks each step, shows a 90-day "First look" at what Home will say, signs mandate version 1 and opens the books with one entry that starts a new evidence chain. Bills and limits are fixed after setup; changing them means a new setup and a new signature |
| **Home** (`/`) | Sees whether cash is safe and what waits | The cash outlook (lowest cash ahead, the forecast with its events, *What we recommend*: the plan, its cost and whether it needs approval); *Your worklist* (needs you, waiting, customers); cash available today with a funding ring; upcoming movements, including what customers owe late; what is owed, by customer |
| **Attach deals** (`/documents`) | Drops a contract or lender agreement, then picks who it is with from the list of known companies, or adds a new customer from that list | Reads every term beside its clause; checks that the chosen company is the contract's buyer, vendor or lender, as its kind needs; offers to refile a misfiled reading; after *Confirm*, says what was saved, under which customer, and that the forecast is unchanged. Compares a lender agreement with the facility in the books. From a confirmed customer contract, *Set up in my books* adds its repeating invoice (Tier 2, undoable; ADR-0014) |
| **A customer** (`/customers/{id}`) | Opens any customer by name | What the customer is worth, what is outstanding, the financing linked to it and its share of what the business is owed; the receivable-to-cash flow; its deals and record; how it has paid; concentration and exposure, with a link that redraws Cash with that customer 30 days late; an inputs sheet for facts the books do not hold |
| **Deals** (`/deals`) | Reads buyer messages, checks a request, sends or copies the reply, records the buyer's answer as the owner heard it, accepts as asked or declines | *Buyer messages*; *Your deals*, filed by who owes the next step (all, needs you, waiting, agreed); the verdict with Options A and B; *Cash impact* with business consequences and *Before they ask*; *Your agreements*, grouped by payment late, awaiting payment and closed, with a row for a contract on file with no deal yet and for a customer with invoices only; each deal's lifecycle strip and tracker |
| **Cash & funding** (`/cash`) | Runs or queues the plan | The plan, other plans considered, the 30/60/120-day forecast, the funding in use, the price of earlier cash, and the forecast with one customer paying late. On books with no committed source able to carry a permanent need, the plan and the menu still show, and the page says that no marginal source exists |
| **Sandbox** (`/whatif`) | Moves the terms, discount, rebate, price rise and early-settled amount of a real request | The verdict, lowest cash, concession cost and covenants. Nothing is written |
| **Capex** (`/capex`, with `/buy`, `/finance`, `/plans`) | Tests a machine, works through a vendor contract, commits a purchase | Health figures, the financing structures screened (a figure that does not apply shows a dash, with the reason), *Apply* (Tier 2), the borrower file, financial health, loan eligibility and long-term plans |
| **Receivables** (`/receivables`) | Records a payment; copies a chase message | What each invoice nets after financing; a payment's effect: the rest stays open, a financed invoice repays its lender first, and the reconciliation's reading |
| **Activity** (`/activity`) | Reads what happened | Every operation and security event, newest first, with filters that hide but never remove, the chain check, the evidence per entry, and a *Reconciliation* tab |
| **Approvals** (`/approvals`) | Approves or declines | One card per request, with its terms, the stored quote and today's price if it moved. No "approve all" |
| **Ask FLOW** (header, side panel, `/ask`) | Asks in English or Chinese, including small talk and "what will FLOW never do?" | Speaks first; answers from the books as cards with links to the page that shows the answer; proposes plans that run only on "go ahead"; the full page holds the conversation in one card |
| **Your limits** (`/limits`); **Security and evidence** (`/trust`) | Reads the signed limits in plain words; downloads the record | What FLOW may do alone, what waits and what never happens; the evidence export, verifiable offline; the security events and the FastCapital scene |
| **Demo** (`/demo`, Demo mode) | Plays the six-scene story; moves the clock; loads other books | The story on the demo company, operator tools and the engine views (mandate, cash line, funding, verdict, ledger, alerts, reconciliation, security) |

Every Business screen is in English and Chinese (the Demo's engine views are in English), and a tour (*Show me around*)
explains twelve pages, opening by itself on a first visit.

**What we claim, and what we do not.** Claims:
- No model output alone can create a commitment, borrow or move money in FLOW.
- Every verdict carries its failing rule, the figures, the formula and the source words.
- On the 115 held-out buyer messages tested since ADR-0005, FLOW accepted 3 on its own and none of them was misread.

We do not claim that FLOW is a lender, broker or adviser, that it complies with any bank's covenants, that it has been
deployed, or that it reads contracts or messages perfectly. It does not. Section 03 says by how much.

## 02 System Architecture

### Architecture diagram and component responsibilities

FLOW is a modular monolith: one FastAPI service (`services/api`), one Next.js web app (`apps/web`) and one database. Modules
talk only through typed contracts in `app/domain/`, and import cycles are forbidden. Figure 3 shows the whole system: who
calls it, the three places a model assists, the deterministic core that computes every figure, and the action path through
which every operation that commits the business or moves money must pass.

<!-- figure: figures/fig8-system-architecture.png | Figure 3. FLOW's architecture. A model assists in three places only (reading documents and buyer messages, classifying a chat request the rules miss, routing an owner's question to read-only tools); in live mode it gets text with identifying numbers redacted, and code validates its typed output. Deterministic code computes every figure; every typed operation passes the signed mandate and the executor, which records each outcome in a hash-chained log. Buyer, lenders and bank feed are simulated. Build 571ea64f. | page -->

**Table 5. The roles in the pipeline.**

| Role | Code | May | May not |
| --- | --- | --- | --- |
| **Compiler** (the main model-assisted role, untrusted) | `compiler/` | Turn text into typed obligations, each tied to the exact source words. Flag authority claims, data requests and unknown lenders. Prove whether it accounted for everything | See the books, the mandate, the funding options or a buyer's limits. Emit an operation, a tier or a reply |
| **Chat front** (rules first; model-assisted in live mode only) | `nl/`, `nl/router/` | Read an owner's request with the deterministic parser; in live mode, label a request the parser misses from a closed list of intents, or route a question to read-only tools. Answer from the books; store a plan for "go ahead" | Execute anything a model chose; approve or reject through the classifier; read a buyer's message as a request |
| **Verifier** | `financial/`, `covenants/`, `verifier/` | Project the cash trajectory, test the mandate and covenants, return a verdict with formulas and priced counters | Read free text (enforced by a test on its imports) |
| **Negotiator** | `verifier/counters.py`, `counterparties/`, `egress/` | Price counters from the marginal cost of funds, run bounded rounds with the buyer, fill outbound templates | Reveal the reserve, caps, funding options or limits |
| **Treasurer** | `funding/`, `operations/` | Find the cheapest plan in its search space and execute typed operations through the permission gates | Rely on an uncommitted facility for a hard constraint; execute a Tier-3 action |

**One buyer request, end to end (Figure 4).** The terms stay *proposed* until the executor has screened the buyer's
acceptance; they become an *authorised* operation and a *recorded* commitment; the deal is *settled* only when the bank feed
reports the cash and reconciliation marks the promise.

1. **Read.** The compiler proposes typed obligations, each with its source span, or abstains. A conflict between a message
   and its attachment, or a stated discount that does not equal rate × amount, gives NO_VERDICT. A coverage proof then
   checks that every figure and request in the text is accounted for.
2. **Screen.** Unknown senders, funding claims, unevidenced "we agreed last month" claims and data requests are logged as
   security events. None of them can book anything.
3. **Project.** The engine projects a conservative daily trajectory of cash, debt and future promises with the request's
   obligations.
4. **Fund.** The router prices any gap from committed facilities and returns the marginal cost of funds. Future
   concessions are valued at that rate.
5. **Decide.** The verifier tests every day and every month against the mandate and covenants, applies the break-even and
   autonomy rules, and returns a verdict. A rejection or counter comes with counters priced below the marginal cost.
6. **Negotiate.** The buyer answers within a bounded number of rounds. NO DEAL is a normal outcome.
7. **Execute.** Code, never a model, turns the verdict into typed operations. The executor runs Tier 1, queues Tier 2 for
   the owner, refuses Tier 3, and appends every outcome of an admitted operation to the hash-chained log. A request refused
   before it reaches the executor is recorded as a security event instead.
8. **Settle.** The bank feed (simulated) or the owner records each receipt; a receipt on a financed invoice repays the lender
   first; reconciliation reports each promised payment as awaited, received, lapsed or settled otherwise.

<!-- figure: figures/fig9-request-to-settlement.png | Figure 4. One buyer request from request to settlement. Steps 1 to 6 are proposed terms: nothing binds and no money moves. The executor's acceptance screen authorises the operation, the commitment is recorded in the hash-chained log, the funding plan runs as authorised operations, and the deal settles only when the simulated bank feed reports the cash and reconciliation marks the promise. Badge shapes show who acts: code, model, owner or a simulated party. Build 571ea64f. | page -->

**How agreement happens, and what is simulated.** A counter reaches the buyer in one of three ways. All three pass through
the same gates afterwards: the single-use nonce, the terms hash, re-verification on that day's books, and the hash-chained
log.

- **Through the simulated buyer (Demo mode).** The owner reviews the exact counter, then sends it with the verdict and books
  version it was built on. A changed counter is refused (409). The buyer in this build is a deterministic simulation with a
  hidden reservation price.
- **A registered buyer writing through its channel key.** FLOW answers at once within Tier 1, without an owner step: it
  counters, declines, or accepts a plain early-payment discount on a named invoice that passes every test and the coverage
  proof, inside the signed mandate. Anything else is queued for the owner (the authority matrix in section 04). A message without a
  channel key is a proposal only and executes nothing.
- **Outside FLOW.** The owner sends the counter themselves, for example by WeChat, and marks it as sent; the mark is bound to
  the exact message. FLOW transmits nothing itself. When the buyer answers, the owner records it: "accepted" and "declined"
  are bound to that message, and a pasted reply is read as a new request. FLOW does not authenticate the buyer's answer: an
  agreement recorded this way is **the owner's report**, checked against the terms and that day's books, not proof that the
  buyer agreed. After a counter is marked as sent outside, no other path can answer that request.

**Who changes the books.** Every typed operation that commits the business or moves money (accepting, countering or
rejecting an offer, a commitment, a draw, invoice financing, a repayment, a receipt, an approval decision, a document
decision, a capex step, a facility addition, a contract set-up) goes through one component, the executor, which checks it
and records it in the tamper-evident log. Outside the executor, three owner or demo actions also change the books, each
logged: moving the simulated clock (ADVANCE_CLOCK), opening books from setup (OPEN_BOOKS, demo mode) and adding a customer
(ADD_CUSTOMER). A demo reset erases the books and the log (demo mode only). Stored offers, verdicts, contract readings,
deal facts and chat sessions are records, not books.

**Design decisions that matter.**
- **Exact money.** Money is integer fen and rates are integer basis points, rounded half-up once per posting or valuation
  (ADR-0002).
- **Lead times are respected.** Funding is requested on the decision day and lands after its lead time, so a hard
  constraint never relies on money that has not arrived (ADR-0003).
- **Autonomy needs positive proof** (ADR-0005).
- **The browser computes no money and no dates.** Every figure and sentence is written by the server in English and Chinese
  (INVARIANT 13).
- **Errors say what they are.** An unexpected server error returns a JSON 500 with an error code and no exception text,
  with the CORS and security headers, so the web app reports a server error instead of "cannot reach the API".

The full component list is Appendix B.

### Models, tools, data sources and external services

**Where a model is used: three model-assisted uses, each with a closed output.**
1. **Reading documents and buyer messages (the compiler).** Buyer offers and messages (including a reply the owner pastes),
   term sheets, contracts, lender agreements, and setup's *Fill from an agreement*, become a strict JSON schema of typed
   terms. Setup is the one place a model-read number (a facility's limit, rate or fees) can reach the books, and only after
   the owner reviews the row and signs.
2. **Classifying an owner's chat request** that the deterministic parser cannot read, into one of 10 intents from a closed
   list that has no approve, reject or buyer-message intent. Its output never executes. In live mode with the question
   router on, a request it labels as a plain read (status, alerts, ratios, changes, comparing financing, a deal) is sent to
   the read-only answers and the router instead of a raw status view; action intents are never redirected.
3. **Routing an owner's question** that the deterministic answers miss to at most three tools from a closed menu of 40
   read-only tools (ADR-0015, live mode only). Code runs the tools and writes every word and figure of the answer
   (section 03).

A model never decides, prices, negotiates, writes an answer or executes.

**Table 6. Model backends.**

| Backend | Model | Used for |
| --- | --- | --- |
| Cache (default) | Recorded readings keyed by a hash of the documents and the prompt version. The 19 shipped recordings were made by the rules grammar; no model output ships in the repository | Tests, the demo, the scenario runner and the offline evaluation. No network. A message not in the cache goes to the rules grammar |
| DeepSeek (live, opt-in) | `deepseek-flash` alias through the OpenAI-compatible API. The underlying model version is not recorded | A backend reachable from mainland China. Used for the live runs in section 03 |
| Claude (live, opt-in) | `claude-sonnet-5-5`, with `claude-opus-5-5` for hard compilations | Alternative live backend |
| Rules grammar | Deterministic regular expressions and lexicon, Chinese and English | Always available. Every offline reading, and the fallback when a backend fails, times out or returns invalid JSON |

**What the model sees.**
- **The document and the output schema, and nothing else.** The mandate, facility limits, buyers' limits and other buyers'
  terms are never attached to a model request, and a test on the compiler's imports keeps it that way. A person can still
  paste such figures into a message.
- **For the question router, only the redacted question and the tool menu.** The prompt is built without any access to the
  books; a test captures what the provider receives and checks that it holds no figure, name or limit, and that it is
  byte-identical whatever the books hold.
- **Identifying numbers are redacted first, in live mode, by every model call** (compiler, intent classifier and question
  router): bank and card numbers, phone numbers, email addresses, unified social credit codes, ID and passport numbers, and
  addresses after a label become placeholders. Redaction is on by default, and `pnpm demo --live-llm` forces it on. It is
  pattern-based: party names, amounts, clauses, chat ids, IBANs and unlabelled addresses still reach the provider (PRIV-4,
  PRIV-5). It has been tested with scripted models only, and live mode is outside every security certification.
- **Quotes are mapped back to the original** before grounding, so every term still points at the real words.
- **Logging.** Only a document hash and timings are logged per call, never the text.

**Why a model at all.** The rules grammar is precise but narrow. On 17 unseen Chinese contracts with a text layer, the rules
grammar, which has no Chinese party pattern, found no party names. Recorded DeepSeek readings found both parties for 14 and
swapped buyer and seller in 3. For example, the rules returned nothing for "甲方（承包人）：中山市华岳城建集团有限公司",
while the model read both parties correctly. Both paths feed the same grounding and the same verifier: a term whose quote is
not found word for word in the document is dropped, whichever path proposed it.

**Three ways to run FLOW. They are never mixed in our results.**
1. **Web on recorded mocks.** The web app alone, no API. Useful for the interface only (the screenshots in this document).
2. **Real engine, offline.** The full API with the rules grammar and its recorded readings. This is the demo, the tests and
   every evaluation figure unless stated otherwise.
3. **Real engine, live model.** The full API calling DeepSeek or Claude (`pnpm demo --live-llm`). Opt-in, needs a key, and
   outside every security certification.

**The agent's tools.** Every tool is an HTTP route with a strict schema that rejects unknown fields: 105 routes under
`app/api` plus `/health` on `571ea64f` (`scripts/security_route_inventory.py`). They cover:
- setting up the books (demo mode only);
- the chat harness (`POST /nl`, and the opener in which the agent speaks first);
- offer intake, evaluation and negotiation, and the message to the buyer;
- the funding router, capex, financial health, loan eligibility and the borrower file;
- execution, receipts and approvals;
- the clock, alerts and reconciliation;
- contracts, customers and deals;
- the what-if sandbox and the strategy views;
- read views and the evidence export.

Appendix C lists them. Operations are typed:
- *offer:* accept, counter, reject, record a commitment;
- *funding:* draw, repay, finance an invoice, record a receipt;
- *owner:* apply for or add a facility, commit a purchase, confirm or reject a document;
- *Tier 3, always refused:* sign a personal guarantee, pledge collateral, issue equity, change the mandate.

No operation has a payee or account field, so FLOW cannot send money to a third party.

**Data (all synthetic).**
- **The demo company ("golden books"), day 0 = 1 October 2026.**
  - Cash ¥400,000; payroll ¥340,000 on day 12; a supplier payment of ¥120,000 on day 20; an operating bill of ¥100,000 on
    day 47.
  - An existing ¥1,500,000 loan at 0%, repaid ¥45,000 every 30 days; monthly EBITDA fixed at ¥90,000 (a fixture input).
  - Foshan's Receivable A of ¥420,000 due on day 32, and a ¥420,000 invoice issued on day 2 and every 30 days after, on
    45-day terms.
  - An owner-signed mandate: a ¥300,000 cash reserve; a ¥5,000 cap on future concessions; DSCR at least 1.25× and leverage
    at most 2.5× (the synthetic credit line's covenants, repeated in the mandate); funding that costs more than 15% a year
    needs the owner's approval when FLOW asks for it; a commitment worth more than ¥100,000 in future concessions needs the
    owner.
- **Fixtures.**
  - 12 worked offers and three held-out sets of buyer messages.
  - Three demo contracts in Markdown, Word and PDF.
  - 70 synthetic Chinese contracts in four formats for the contract-reading evaluation, kept outside the repository.
  - Alternative books: busy, short of facilities, blank, and a set calibrated from a public filing.
- **The owner's own books.** On blank books, the setup wizard turns what the owner types (and the agreements it reads)
  into books of the same shape.
- **Test suites.** The 279-case attack catalogue, the 49 scripted agent tasks, the 503-turn owner-question bank and the
  345 everyday owner wordings.

**Table 7. The demo company's funding options (synthetic; only the owner can add to them).**

| Facility | Status | Price | Time to cash |
| --- | --- | --- | --- |
| Bank credit line, ¥150,000 limit, 30-day clean-down | Committed | 6.4% simple, Actual/365 | same day |
| Invoice financing, up to 80% of an invoice's open face, ¥350,000 limit | Committed | 7.8% + 0.25% per whole 30-day period (10.84% all-in tariff equivalent) | 3 days |
| Buyer early-payment offer | Committed | 1.2% discount | 2 days |
| Bank acceptance-bill discounting | Committed (no bill held at the start) | 0.58% a year | 1 day |
| Government-guaranteed working-capital loan | Not applied | 5.0% all-in | 21 days |
| Equipment loan, 36 months / equipment lease, 48 months | Not applied | 5.6% / 7.2% | 14 / 10 days |
| Equity | Reference only (Tier 3) | n/a | n/a |

**External services.**
- **No real finance APIs.** No bank, lender, payment or blockchain API is called.
- **Model provider.** In live mode only, the configured provider (DeepSeek or Anthropic) receives the redacted inbound
  documents and the schema, the redacted owner requests the parser cannot read, and, with the router switched on, an
  owner's redacted question with the tool menu. With DeepSeek, text goes to a provider in mainland China.
- **Database.** PostgreSQL (Docker Compose, or Supabase in Singapore), with row-level security on every table and no access
  for Supabase's public roles. Locally, SQLite or memory.
- **Libraries.**
  - API: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 with Alembic (migrations 0001 to 0009) and PyNaCl (Ed25519).
  - Web: Next.js 16.3.8, React 19, Tailwind 4 and Recharts.
  - Tests: pytest, hypothesis and Playwright.

## 03 Agent Design

### Intent understanding, planning, tool use and state management

**Understanding a request.**
- **A deterministic parser (Chinese and English) maps each chat request to one of 23 intents** and fills typed slots.
  Examples: evaluate an offer, negotiate, speed up a receipt, fund a gap, show status, compare financing, explain, what-if,
  approve, reject, answer from the books (ASK_BOOKS), out of scope.
- **Who is asking comes from authentication, never from the text.** A buyer's message is never parsed for intents. It is
  compiled and verified as an inbound offer.
- **A question is answered, never executed.** A question gate runs before every action rule. "Can we pay off our loans?"
  is answered from the books; it never proposes a repayment, compiles an offer, queues anything or writes to the log.
  Answers come from a read-only module of about 40 figures computed by the engine's own functions, so every number is the
  one the screens show, and each answer leads with the yes, the no or the figure. (In live mode the intent classifier can
  still turn a question into a *proposed* plan; the live stress test below counts how often.)
- **A Tier-3 request put as a question is still a request.** "Sign a personal guarantee?", "should we pledge the
  equipment?" or 要不要签个人担保？ goes to the executor like the plain command: it is refused, logged and raises a Tier-3
  security event. Only a question that plainly asks for information and proposes nothing ("What is a personal
  guarantee?", "Is equity an option?") is answered, and only for the owner.
- **A question never cancels a waiting plan.** Asked about an action while a plan waits for "go ahead" ("should we draw
  ¥100,000 on the line?"), FLOW says that the earlier plan is still waiting, what it does and what it costs, and that "go
  ahead" runs that plan, not what was just asked about.
- **A terms question prices the terms asked for, with two-turn memory.** "From 45 to 60 days", "60 days instead of 45" or
  账期从45天改成60天 is read for the terms asked for apart from the ones they replace (to, instead of, 改成, 延长到). Day
  counts the words do not tell apart are asked back, never guessed, and the days of an early-payment window ("2% off if
  they pay in 10 days") are not terms. Terms no longer than the buyer's current ones are never priced and never called
  acceptable. When FLOW has to ask which customer, it keeps the terms already read, and the owner's next short reply
  naming one customer finishes the question. The answer, the router's tool and the what-if share one writer.
- **"Can I pay everyone?"** "Can I pay everyone?" or "Can I pay all my bills this month?" adds every outflow in the window
  (this month, or the next 30 days when none is named): payroll, suppliers, loan payments and the rest. It checks them
  against the reserve and against zero on the conservative forecast Home draws, and says yes or no, the first day below the
  reserve, the day below zero and the lowest point. When cash falls short, the answer offers FLOW's plan with its cost and
  saves it, so the owner's "go ahead" runs it, or queues it for approval, through the executor and the mandate checks. The
  answer itself runs nothing, and it never replaces a different kind of plan that waits.
- **Customers, borrowing and the record.** "If my biggest customer doesn't pay, how long can we last?" and "what happens
  if Dongguan stops ordering?" are answered on a model copy of the books without that customer's money (its open invoices
  and recurring invoicing, or only the invoicing still to come), against today's forecast; a customer with nothing open is
  said so plainly. "Can we borrow against the Foshan invoice?" gives what invoice financing would advance on it, the cost
  and the days to cash; nothing is submitted or drawn. Days sales outstanding is answered from the receivables, and "what
  did FLOW do?" names each operation in the audit log. Everyday ways of saying "show me my cash" open the cash answer.
- **Small talk and limits.** Greetings, thanks and "who are you?" get a short reply in the message's language, and "what
  will FLOW never do?" or "can FLOW borrow by itself?" is answered from the tier table: Tier 3 never, Tier 2 only after the
  owner. Recognition is whole-message only, so "hi, fund the gap" or a greeting followed by an instruction goes through the
  rules as before.
- **Claims are named for what they are.** A buyer who writes "as agreed with your team, we will now pay on 60-day terms"
  is told that no terms agreement is on record, in the chat reply and in the message to the buyer. Nothing is booked from a
  claim, and the claim is logged as a security event.
- **Everyday wording.** After the literal patterns, a scored matcher reads casual, misspelt or worried wording in both
  languages ("can my company survive this month?", 我们撑得过这个季度吗) and answers only when one question clearly wins. A
  horizon longer than the 120-day forecast is answered on the forecast and says so.
- **The intent classifier (live mode only)** is consulted only when the parser finds nothing, and may choose only from its
  closed list; approve, reject and buyer messages are not in it, and its choice never executes. With the question router
  on, a request it labels as a plain read goes to the answers and the router, not to a raw status view.
- **The question router (ADR-0015, live mode only).** When the deterministic answers and the topic reads both miss, a model
  may choose up to three of 40 read-only tools and fill their typed slots; code answers. It sees only the redacted
  question, fenced as data, and the tool menu, never the books. Its output is validated strictly: a canary check, exact JSON
  with no extra or duplicate keys, known tools, every slot checked against its schema twice. One bad call rejects the
  whole response, and a rejection, timeout, provider error or cache miss falls back to the honest "I cannot answer that
  yet" with the nearest read. For a terms question, code reads the day count from the owner's own words, whatever number
  the model copied into the slot. It runs for the owner only, behind `FEATURE_ASK_ROUTER`; no routes are recorded, so
  offline it changes nothing. Logs keep a hash of the question, never its text. The ADR is *proposed*; the Security Lead
  reviewed the router on `6d2b6941` and its four findings were fixed in `70f23ac5`. Live mode, where the router acts, is
  outside every security certification.
- **Every id is checked against the registry.**

#### Innovation & Interaction: dialogue efficiency, clarification, correction and fallback

- **Dialogue efficiency.** The 49 scripted tasks take 88 turns, 1.8 turns per task: most requests are answered or planned
  in one turn, and "go ahead" is the second. FLOW speaks first after time moves or money lands, so the owner does not have
  to ask what changed.
- **Clarification.** "Fund it" with two open gaps asks which one. A terms question with an ambiguous day count asks back. A
  question that needs a customer asks which, and finishes on the next turn.
- **Correction.** "Make it 0.8%" amends the plan. "1%" is refused, because it is above the 0.88% break-even.
- **Fallback.** An unmatched request gets the nearest thing FLOW can do, not a flat refusal; a question the books cannot
  answer gets "I cannot answer that yet" with the nearest read; a model that fails, times out or returns invalid output
  falls back to the rules grammar or the deterministic answers, never to a guess.

**Consent: instructions that move money execute only when they are unambiguous.**
- A financial instruction runs only when the whole message is one closed, affirmative command with exactly one RMB amount.
- These execute nothing, in English and Chinese: a negation, a question, a condition, a future time, a foreign currency, an
  unreadable amount, an extra request, or quoted or pasted text.
- An approval runs only on an exact decision sentence naming its id.

**Propose, then confirm.**
- A plan is stored with the exact typed operations shown, the quoted cost and the books it was built on.
- "Go ahead" runs exactly those operations. If the books have moved to a different or dearer plan, FLOW shows the new
  proposal instead.
- A new day or a changed mandate cancels the plan.

**Planning examples.**
- **A goal.** "Get paid early on the Foshan invoice without giving anything away next quarter" becomes an early-payment
  counter at 0.85% with no future concession, with invoice financing as the fallback if the buyer refuses.
- **Several steps.** Draw the line, finance an invoice, repay on receipt.

**Acting first.** After time moves or money lands, FLOW names what needs the owner and proposes a cure found on the current
books, priced as the executor will charge it. It then waits; the executor decides the permission tier. FLOW proposes no
cure when the mandate forbids new borrowing, and no repayment while a reserve breach is open. Day 34 of the journey in
section 01 is an example.

**Ask FLOW, as the owner uses it.**
- **Where.** A field in the page header, a side panel on every page, and a full page (`/ask`) for the same conversation.
  The full page holds the conversation in one card: the thread scrolls inside it and the composer is pinned at its foot.
  Each page suggests questions it can answer. *New conversation* clears it here and on the server, so a later "go ahead"
  runs nothing.
- **FLOW speaks first.** When the panel or page opens on an empty conversation, FLOW names what needs the owner and its
  priced cure, in the owner's words and with no internal ids.
- **Answer cards.** An answer from the books leads with its sentence, shows up to three key figures, the rest of the reply,
  how FLOW worked it out, and up to three links to the page that shows it. Links only open pages; a card never approves,
  sends or runs anything. Every word and link is written on the server, and a browser test clicks each one.
- **Language.** The reply follows the question: a Chinese question is answered in Chinese, an English one in English,
  whatever the page's language.
- **Doing, not only answering.** A plan shows its exact operations and cost with *Yes, run it* and *Cancel*. "Approve
  APR-000002" approves that request; a bare "approve it" binds only to the request the conversation just showed. Chat
  never records a fact ("add a ¥80,000 bill" is refused).

**Tool use.** Handlers call module functions (compile, evaluate, plan, negotiate) and send typed operations to the executor.
Each operation carries an idempotency key built from the session, turn and step. No handler can skip the verifier or build an
operation from model output.

**State.**
- **Sessions.** A chat session holds only typed references: the last offer and verdict, a pending plan, a pending
  clarification, and a pending question with the slots already read (`Session.pending_ask`). Since SEC-21, it continues only
  for the caller that opened it. A what-if clarification likewise resumes the words that raised it.
- **Books.** The store holds today's position. Commitments hold agreed changes not yet realised, and every projection runs on
  the two combined (ADR-0006).
- **Time.** Time is a simulated day that moves only through the clock. Each move posts scheduled flows, issues recurring
  invoices and expires lapsed commitments.
- **Settlement.** Partial payments leave the residual open. A receipt on a financed invoice repays the lender first, from
  that receipt only. Reconciliation reports each promised early payment as awaited, received, lapsed or settled otherwise.
- **Commitments are re-checked.** A verdict is not standing authority. At acceptance and at approval, the executor checks
  again on the books of that moment and refuses a commitment that no longer holds (STALE_VERDICT).
- **The decision record** derives each deal's state from stored facts (ADR-0011).
- **Contract records** hold a document's reading with each term's quoted clause and the owner's hash-bound decision
  (ADR-0012). From a confirmed customer contract, the owner can set up that customer's repeating invoice in the books; the
  conservative forecast counts it from the first invoice the clock issues (ADR-0014).

**From setup to settlement: what FLOW keeps track of.**
- **Opening the books.** The setup wizard's six steps (Table 4) are checked by the server and previewed as a 90-day
  forecast before anything is written. *Sign and open my books* signs mandate version 1 and writes one opening entry that
  heads a fresh evidence chain; it is refused once the books hold any activity.
- **Documents.** The file comes first; the owner then picks the company from the books' list or adds a new customer from it
  (Tier 2). The party check looks for the chosen company in the role the document's kind needs: the buyer of a customer
  contract, the vendor of a purchase contract, the lender of a lender agreement. It matches by company (case, punctuation
  and the legal-form suffix ignored), never by a first word or part of a name. It blocks *Confirm* when that party is
  another company or was not found in that role, and shows the companies the document does name. *Refile* moves the
  reading to the right customer without a new model call. A lender agreement is compared with the facility already in the
  books and can be linked to it, which changes nothing in the facility.
- **Customers.** Each customer's overview is computed from the books: gross contribution, outstanding, the financing linked
  to its invoices, its share of what the business is owed, its payment history, and its exposure. A new customer is refused
  when its name looks like a company already on the registry, reads as an id, is the business's own name, or takes a short
  name another customer already answers to.
- **Deals.** One queue files every request by who owes the next step. Once the owner has a reply, FLOW drafts it exactly;
  the owner sends it through the simulated buyer (Demo mode) or by their own channel, then records the buyer's yes, no or
  reply as the owner heard it. When FLOW has no counter, *accept as asked* or *decline* is itself the owner's decision. Each
  deal shows a lifecycle strip (received, analysed, reply ready, sent, agreed) and, once agreed, a tracker of promised
  against actual (terms negotiated, early payment in, collecting, fulfilled).
- **Money over time.** The simulated clock posts scheduled flows, lands funding, issues recurring invoices and expires
  lapsed commitments; it never records a receipt. The owner records a payment on Receivables as a Tier-1 receipt, and FLOW
  says what reached cash, what repaid a lender first and what is still open. Alerts are recomputed on each day's books: an
  overdue invoice (critical when it is financed), a reserve breach ahead with its funding cure, repaying a drawn credit
  line once cash allows, an agreement expiring within 7 days, and the signed limits expiring within 14 days.

### Core algorithms and evaluation approach

**1. Daily cash trajectory.** For each day of the horizon:

`closing(t) = opening(t) + inflows(t) − scheduled outflows(t) − interest, fees and repayments(t)`

- **Order within a day.** Inflows come first, then outflows, then financing costs. Closing cash is tested against the
  reserve. This is a closing-cash test; it does not model liquidity within a day.
- **What "conservative" means.** Unconfirmed inflows and overdue receivables are ignored; only committed facilities can be
  drawn, others count as zero; a contingent concession counts at its maximum; a repeating invoice set up from a contract
  counts only once the clock has issued its first invoice (ADR-0014).
- **What it does not cover.** Recurring invoices are assumed to be paid on their due day, so the forecast is not
  conservative about collections. The stress tests (Table 12) cover that.
- **Charges.** Credit-line interest is Actual/365 simple, posted at repayment. Invoice financing bills interest and its fee
  in whole 30-day periods, at least one, so an advance held for less than a period costs more than its 10.84% tariff.

Figure 2 (section 01) draws the trajectory of the demo books under four scenarios.

**2. Funding router.** It searches for the cheapest plan that keeps closing cash at or above the reserve on every day, breaks
no covenant and is allowed by the mandate:
- **Search space.** A discrete search: up to three actions, amounts on a ¥10,000 grid, no action below ¥1,000, every source
  requested on the decision day and landing after its lead time. It searches amounts, not dates.
- **Ranking.** A plan FLOW may run alone ranks before a cheaper plan with a leg that needs the owner (a leg above the 15%
  approval threshold); within each class, the cheapest wins.
- **Plans that cannot run.** A plan that relies on an action no operation can perform yet (a buyer's early payment, a bill
  FLOW does not hold, an invoice not yet issued) is labelled "cannot run today". When no plan in the search space is
  admissible, the router says so.
- **On the demo company**, the ¥405,000 gap before day 32 is covered by the credit line (¥150,000, interest ¥841.64) plus
  invoice financing (¥255,000, ¥2,272.29 for one 30-day period): **¥3,113.93**. Taking the buyer's 1.2% discount instead
  would cost ¥5,040.00.
- **How close to optimal.** Within ¥1 of a bounded brute-force search on all 26 evaluation scenarios (pairs on a ¥5,000
  grid, triples on a ¥10,000 grid; the time budget was reached in 2 priced cases, judged against the best plan the brute
  force found). The brute force is independent search code but uses the engine's own projection. This is optimality within
  the search space, not over every possible amount or date.

**3. Marginal cost and break-even.**
- **Marginal cost of funds.** The rate at which FLOW prices a concession: invoice financing's 10.84% all-in, the cheapest
  committed source that the credit line's clean-down rule allows to carry a permanent need. It is a pricing rate, not an
  executable quote: the platform advances at most 80% of an invoice and bills whole periods.
- **Break-even.** An early-payment discount d is cheaper than borrowing only if d < c/(1+c), where c is that source's cost
  for the days paid early. For 30 days c = 7.8% × 30/365 + 0.25% = 0.8911%, so the break-even is **0.8832%**.
- **The early-payment rule (ADR-0007).** An early payment is accepted only if it passes three tests: it is below break-even
  for its actual days early; the cash is needed; and it is cheaper than the router's plan without it. So 0.75% on the whole
  ¥420,000 invoice costs ¥3,150.00, more than the ¥3,113.93 plan, and is countered; 0.74% costs ¥3,108.00 and is accepted.

**4. Covenants.** Each projected 30-day month is tested against the synthetic credit line's definitions:
- **DSCR** = EBITDA ÷ debt service, with EBITDA fixed at ¥90,000 a month and a bullet loan serviced on a level basis
  (ADR-0008).
- **Leverage** = month-end drawn debt ÷ (12 × monthly EBITDA).
- **Clean-down** = the longest run of zero-balance days on a credit line.

DSCR here is a **forward-looking monthly screening proxy** for a synthetic covenant, not the trailing-twelve-month test on
reported accounts that a bank would normally apply. For example, a 12-month bullet ¥500,000 government-guaranteed loan,
levelised, would bring DSCR to 1.01×, below the 1.25× covenant, so FLOW refuses it.

**5. Verdict.** The verifier checks, in this order: whether the offer was read completely; the security screen; mandate
validity; the projection; every rule (daily reserve, the total and per-buyer concession caps, the discount cap, the implied
rate of an early-payment discount against the 15% threshold, the covenants and the Tier-3 clauses); the three early-payment
tests; and the autonomy rule. Every failed rule carries its code, the day or month, the observed value, the limit, a formula
and its inputs. The autonomy rule (ADR-0005) keeps an ACCEPT at Tier 1 only for a plain early-payment discount on a named
whole invoice that passes all three tests **and** whose message passed the coverage proof. Anything else that would be
accepted becomes "needs the owner".

**The worked example, reconciled.** Table 8 traces the demo's central request (EX01) through every figure the document and
the screens use, on the books of day 0. It answers a common question: why does the forecast say ¥90,040 while the deal page
says "breached by ¥135k for 15 days"? Both are right: ¥90,040 is the shortfall on the **first** day below the reserve (day
47), ¥135,040 the **worst** (day 60), and the breach lasts 15 days (47 to 61).

**Table 8. The EX01 request, every figure in one place (golden books, day 0, books version 1, reserve ¥300,000; CNY).**

| Scenario | Funding | Lowest cash | Breach | Discount | Funding cost | Future concessions | Can run today? | Who decides |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Today's books, no request | none | −¥105,000 (days 30–31) | days 12–31 (20 days), at worst ¥405,000 short | — | — | ¥0 | — | — |
| Today's books + FLOW's standing plan | line ¥150,000 + invoice financing ¥255,000 | ¥300,000 (day 30) | none | — | **¥3,113.93** | ¥0 | yes | Tier 1 |
| **EX01 as asked** (1.2% early pay, 60-day terms, rebate), no new funding | none | ¥164,960 (day 60) | first day 47, ¥90,040 short; worst day 60, **¥135,040** short; 15 days | ¥5,040.00 | — | **¥28,326.92** (terms ¥24,326.92 over 13 invoices + rebate ¥4,000), against a ¥5,000 cap | — | **Rejected**: concession cap, reserve, above break-even, dearer than the plan |
| EX01 + its cheapest cure | invoice financing ¥135,040 on an invoice issued on day 32 | ¥300,000 | none | ¥5,040.00 | ¥2,406.67 | ¥28,326.92 | **no**: the invoice does not exist yet | — |
| EX01 + the plan that can run | credit line ¥135,040, drawn today, repaid day 62 | ¥300,000 | none | ¥5,040.00 | ¥1,468.05 | ¥28,326.92 | yes | — |
| Early-payment test inside the verdict | with the early payment: ¥6,508.05; without it (same terms): ¥3,873.58 | — | — | — | — | — | — | the early payment is dearer, so countered |
| **Option A** (FLOW's counter) | credit line ¥147,210 | ¥300,000 (day 30) | none | ¥2,210.00 on ¥260,000 at 0.85% | ¥825.99; total **¥3,035.99** | ¥0 | yes | **Accept, Tier 1** |
| Option B (FLOW's counter) | line ¥90,000 + invoice financing ¥315,000 | ¥300,000 (day 30) | none | — | **¥3,706.46** (¥592.53 more than the standing plan) | 55 days + 0.30% price rise: a net forward gain of ¥162.05 over 13 invoices | the router's plan, yes | needs the owner (terms lengthen) |

*Funding cost and future concessions overlap: the EX01 cure pays for the cash effect of the first invoice's 15 extra days,
which ¥24,326.92 already prices. Do not add them. On FLOW's pricing, accepting as asked gives away ¥5,040 now and ¥28,326.92
of future concessions, CNY 33,366.92 in all, and still needs funding for days 47 to 61.*

**6. Counters.**
- **Option A, early payment.**
  - **Rate:** the largest whole-5-basis-point rate below break-even, here 0.85%.
  - **Amount:** the cash needed after the credit line, grossed up and rounded **up** to a whole ¥10,000:
    (405,000 − 150,000) ÷ (1 − 0.85%) = 257,186.08, so ¥260,000. Rounding stops a buyer reading FLOW's exact gap from the
    counter (R-10).
  - **Cost:** ¥3,035.99, ¥77.94 below the standing plan. It passes its own re-evaluation, stays within every mandate limit
    and binds to a commitment with the same terms hash. Its real value is that the supplier gets the cash it needs without
    the ¥28,326.92 of future promises the buyer asked for.
- **Option B, terms.** Longer terms with the smallest price rise that covers the funding cost of the extra days (0.30% of
  ¥420,000 = ¥1,260 against ¥1,247.53 per invoice). Every counter is re-evaluated as an offer on the same books, so FLOW
  offers 55 days, not 60: at 60 days a later invoice would land after a loan payment with no committed cure. Its books still
  need the ¥3,706.46 plan in Table 8, so FLOW recommends Option A.
- Outbound text is filled from an approved template, and the outbound guard checks it.

**7. Simulated buyer.** The buyer kernel works out its own surplus from a package: the discount, rebate and extra days, less
its cost of paying early and any price rise. It accepts when the surplus reaches its hidden reservation, otherwise counters
one step toward it, and refuses in its last round. In the one hard-line scenario tested, the demo ends in NO DEAL within
three rounds, and the router still covers the gap for ¥3,113.93.

**8. Capex screening.** For an owner's planned machine purchase, FLOW screens each financing structure for daily liquidity and
monthly covenants: cash with the line; an 18-month loan; a 36-month loan; a 48-month lease (modelled as a 7.2% amortising
loan with no residual). It ranks the feasible structures by total financing charges, undiscounted.

On the synthetic ¥600,000 machine (+¥22,000 a month from month 4 to month 60; no residual value, tax or maintenance; NPV
¥380,885.77 at a 10% hurdle; simple payback in month 31, discounted payback in month 35), run on today's unfunded books,
FLOW selects the lease (¥92,327.32 of charges). The 36-month loan is cheaper (¥53,206.14) but leaves cash ¥3,144.62 below
the reserve for three days. Once FLOW's ¥3,113.93 plan has been paid, every structure needs a few days' bridge on the line
(the lease ¥3.11, the 36-month loan ¥3.29).

The search tests **one structure at a time**. A 36-month loan plus a three-day bridge on the credit line (interest ¥1.65)
would have no breach and about ¥39,000 less interest than the lease, undiscounted across a 36- and a 48-month tenor; in
present value at the 10% hurdle the gap is **CNY 7,493.45**. FLOW does not try that combination today, so the selection is
the best *standalone* structure. Applying for financing is a separate owner step that queues one Tier-2 application; the
owner's approval records a simulated pending facility, which counts as zero until a lender commits. A figure that does not
apply, such as the payment of a structure the funding menu rules out, shows a dash, and the result says why.

Around the screening, the Capex hub holds the rest of the buy side:
- **Purchase contracts.** A vendor contract is read like any document. FLOW lays out its payment schedule against the
  owner's timeline and prices the vendor's early-payment discount. *Commit* is Tier 2 and books the payments only on
  approval; a committed purchase has no cancel path yet (CAPEX-NC in the Security Self-Assessment).
- **Financial health.** Cash coverage, the current and quick ratios (from the owner's estimates), covenant room and the
  capacity left on each facility.
- **Loan eligibility.** Four illustrative catalogue loans read against the books. *Add to my funding menu* queues a Tier-2
  facility addition that counts as zero until a lender commits.
- **Long-term plans.** Projects × financing structures × start months over 60 months, the top five by net present value.
- **The borrower file.** A lender-style file built from the verified books, as HTML or Word. It is prepared, never sent.

**9. Strategy views.** Two read-only views answer before a buyer asks:
- **The price of earlier cash**, on Cash & funding: what ¥10,000 arriving 30 days earlier is worth, by arrival day.
- **Before they ask** (the safe deal envelope), on a deal's *Cash impact*: how far each lever (terms, price, early-payment
  rate, rebate) can go on its own on today's books and what stops it, packages that pass every check, and the lowest price
  that works at each length of terms. Each package is re-checked before anything is sent.

Both are on in `pnpm demo`. The envelope repeats the funding search on its first read (about 17 s on the development
machine, a single observation), so the demo computes it once in the background after each reset or setup, keyed by the
books, mandate, day and commitments. Two further views are built behind flags that the demo leaves off: customer economics
and a pilot journal.

#### Evaluation approach: how to read our numbers

We evaluate on three levels: the engine against an independent oracle and a brute force; the readers (buyer messages,
contracts, owner questions) on items their authors had not seen; and the whole agent through scripted tasks and attacks.
One offline command regenerates the engine and agent figures (`uv run --project services/api python scripts/evaluate.py`,
12 minutes on 18 Oct); Table 18 in section 05 gives every headline figure's build, date and command.

Every result carries its **evidence class**: *unseen held-out* (labels written before the code saw the items, scored once,
and that first score is the one quoted); *tuned* (re-scored after fixes chosen by studying its failures, or a set that was
the development target); *recorded model replay* (a model's past reading replayed offline); *live* (a provider called that
day, one sample of a non-deterministic system); *rules* (no model); *scripted* (a fake model we wrote); and *tests*. **No
result comes from a deployed system.** A test count measures the size of a suite, not correctness. Labels for buyer
messages were written by AI agents in separate sessions, not by people. Figure 5 groups the accuracy results by class.

<!-- figure: figures/fig-eval-classes.png | Figure 5. FLOW's accuracy results grouped by evidence class: unseen held-out first runs, the same sets after tuning on their failures, recorded DeepSeek readings and live DeepSeek calls. Each bar is a share of its own row's denominator (shown beside it), and the right-hand column shows what that row's own oracle scores wrong. Rows with different oracles do not compare. Offline re-runs on 571ea64f, 18 Oct 2026; live rows on the dates shown. | page -->

#### Task Completion: scripted tasks in a simulated environment

- **49 of 49 scripted conversations pass their own checks** (88 turns, 18 Oct, `571ea64f`), each with a verifiable
  evidence chain; a tampered copy of the chain is rejected. The tasks and their pass conditions were written by the team
  that built the handlers, so they show that the paths written work, not how real owners would talk.
- **The demo walk** (17 steps, the journey in section 01) exits cleanly with 14 hash-chained operations that verify.
- **The engine** matches an independently written oracle on 67 of 67 golden financial values to the fen, and on 27 of 27
  covenant and capex values; mandate and covenant limits hold at the threshold and break one unit past it (20 of 20). The
  oracle shares the team and the specification, so a shared misreading of a rule would pass.

#### Reading buyer messages: safety beside usefulness

Two held-out sets of WeChat- and email-style buyer messages (66 and 49, Chinese, English and mixed) were labelled by separate
AI-agent sessions before the reader saw them. **Their first runs are our only unseen figures:** verdicts matched the label
on 33 of 63 and 28 of 47, and FLOW accepted **6 misread messages on its own** (4 of its 8 accepts on the first set, 2 on the
second). That result led to the coverage proof (ADR-0005): FLOW may now accept alone only when it can account for every
figure and request in the message. We then fixed the failure classes, so today's figures are tuned.

**Table 9. Autonomy on the two held-out sets of buyer messages today (115 messages, rules path, 18 Oct, `571ea64f`;
both sets have guided later fixes).**

| Step | Held-out 3 | Held-out 2 | Both |
| --- | --- | --- | --- |
| Buyer messages | 66 | 49 | 115 |
| Genuinely acceptable as asked today (plain early payment, cheaper than the plan) | 10 | 4 | **14** |
| … accepted by FLOW alone (autonomous acceptance coverage) | 1 | 2 | **3 (21%)** |
| … sent to the owner unnecessarily (unnecessary escalation) | 9 | 2 | **11 (79%)** |
| Not acceptable, and FLOW answered alone (counter or reject at Tier 1) | 29 | 25 | 54 |
| Not acceptable, and FLOW asked the owner (correctly) | 27 | 20 | 47 |
| Refusals to read (NO_VERDICT) | 16 | 14 | 30 (26%) |
| Owner reviews needed | 36 | 22 | 58 (50%) |
| **Wrong autonomous accepts** | **0 of 1** | **0 of 2** | **0 of 3** |
| *First run, 1 Oct, before ADR-0005* | *4 of 8 wrong* | *2 wrong* | *6 wrong* |

**What Table 9 shows.**
- **Safety comes from a rule, not from a large sample.** With 3 autonomous accepts, "no wrong accept" is weak evidence by
  itself; the evidence is that FLOW refuses to accept alone without proof, which the first runs showed is necessary.
- **Most messages need no owner.** FLOW answers 57 of 115 on its own, mostly by countering or declining within the mandate.
- **That caution has a cost: 11 of the 14 good offers wait for the owner.** Ten of the 11 have one cause: the buyer named a
  settlement date ("tmrw", "国庆后", "next Mon") that FLOW does not yet read into the terms, so the coverage proof cannot
  account for it. Reading settlement dates is the next improvement. Until then, each such offer costs the owner one review,
  with the verdict and the source words shown.

**Table 10. Reading buyer messages on the held-out sets.**

| Set and run | Class | Path | Verdict agreement | Material errors | Silent material errors | Wrong autonomous accepts |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out 3, first run (1 Oct, before ADR-0005) | **unseen** | rules | 33/63 (52%) | 4/51 | 7 | 4 of 8 accepts |
| Held-out 2, first run (1 Oct, before ADR-0005) | **unseen** | rules | 28/47 (60%) | 3/37 | 5 | 2 |
| Held-out 3, today (18 Oct) | tuned | rules | 44/63 (70%); 50/63 (79%) against today's policy | 3/51 (5.9%) | 4 | 0 of 1 |
| Held-out 2, today (18 Oct) | tuned | rules | 38/47 (81%); 44/47 (94%) against today's policy | 0/37 | 0 | 0 of 2 |
| Held-out 3, one live run (1 Oct, build `389cfd9`) | live; shared gates tuned, prompt not | DeepSeek | 42/63 (67%) | 3/51 | 5 | 0 |
| Form baseline (labels typed into today's verifier) | tests | no reader | 56/63 (89%) | — | — | — |

**Reading Table 10.**
- **Two agreement figures for today.** The 1 Oct labels predate the early-payment rule (ADR-0007), so 7 labels in each set
  disagree with today's policy applied to the true terms. "Against today's policy" compares the reader's verdict with the
  policy on the true terms, separating "the reader is wrong" from "the policy changed". The form baseline shows the same
  drift from the policy side.
- **Targets not met.** The material-error target (≤ 5%) and the zero-silent-error target are missed on held-out 3. No silent
  error caused an autonomous accept: each ended with the owner or in a rejection.
- **The live run is one sample** on an older build, with the provider's model version unrecorded; it was not repeated, so
  run-to-run variation is unmeasured.

Appendix A gives the exact definitions of each metric.

#### Reading Chinese contracts

We generated 70 synthetic Chinese contracts with their answer keys (government procurement, goods, services, construction
subcontracts, equipment installation, processing, leases, logistics and supplementary agreements; digital PDF, Word, scanned
PDF and phone photo) and built the reader on the first 40.

- **Unseen: 75% of key fields on 17 contracts with a text layer.** Of 30 new contracts (six new contract types), 13 are
  scans or phone photos and are refused before any reading, because FLOW has no OCR. On the 17 with a text layer, recorded
  DeepSeek readings got **215 of 285** key fields right (**75%**; **45%**, 215 of 474, over all 30).
- **The fields that decide money.** Of the 234 fields that move money or gate a decision (total amount, stage percentages,
  days, day units and triggers, late interest, retention, end date, buyer and seller), **178 were right (76%)**, 11 were
  stated wrongly (including buyer and seller swapped in 3 contracts), 45 were missed, and 18 stage items were stated that
  match nothing in the contract. Payment triggers were the weakest field (17 of 33). The record-only fields (contract
  number, signing and start dates) were right on 37 of 51.
- **Tuned figures.** After five fixes chosen by studying these failures (slash and dot dates, a code check of who pays whom,
  repeated terms, the payer's late interest, end dates), the same set scores 86%, no longer held out; on the 40 contracts
  the reader was built on, 98%.
- **What limits the damage.** Every term must quote its clause word for word; code checks that stage percentages sum to 100
  and stage amounts match the total; a reading changes nothing until the owner confirms it, and only a separate Tier-2 *Set
  up in my books* turns a contract into forecast invoices. Nothing here measures whether an owner would catch a plausible
  wrong stage or trigger. The contracts and readings are outside the repository, so these figures cannot be reproduced
  from it.

<!-- figure: figures/fig6-contract-reading.png | Figure 6. Reading Chinese contracts, by format. Unseen text-layer contracts: 75% of key fields (recorded DeepSeek readings). After fixes made by studying them: 86% (no longer unseen). The contracts the reader was built on: 98%. Scans and phone photos are refused: FLOW has no OCR. -->

#### Owner questions and the live-provider stress test

- **The owner-question bank** (122 owner, CEO and CFO questions in English and Chinese with rewordings, 503 turns) is the
  bank the answer module was built against, so it is a tuned set. Of the 427 turns the books can answer, FLOW answers 228
  (53%), 45 partly and declines 154 naming the nearest read, with 0 wrong by the bank's own scorer; 75 of the 76 questions
  the books cannot answer are declined honestly.
- **Everyday wording.** 345 phrasings (219 English, 126 Chinese; casual, formal, misspelt and worried) were labelled with
  the answer they should reach before the matcher was written, and split 60/40 by a hash. On the **142 held out** it reaches
  the right answer for **127 (89.4%)** and a wrong topic for **3 (2.1%)**; on the 203 it was tuned on, 199 and 1. It scores
  the topic of the answer, not its figures.
- **Offline, no question executed, queued or changed the books**; three proposed a plan that waits for "go ahead".
- These figures were measured on `571ea64f`, before the Ask FLOW additions described above (customers, borrowing against
  an invoice, DSO, small talk); one tuning item now reaches the new "pay everyone" answer instead of its label.

**The live-provider stress test (18 Oct 2026).** On build `28738f19`, with DeepSeek live, the question router on and the demo
books, a client sent 658 owner turns to a local API: 589 sweep questions (the bank's main wordings and the everyday set,
each in a fresh session), 20 hard questions, 8 attack prompts, 6 two-turn exchanges and bursts of 5, 10 and 20 concurrent
questions. It measured availability, latency, the path each turn took and the reply; it did not score correctness by
oracle or diff the books.
- **Availability.** All 589 sweep turns and all other turns returned HTTP 200.
- **Path.** Of the 589, the rules answered 546, the question gate 10, the intent classifier 12 and the fallback 21. 63
  reached the router: it answered 33, said "cannot answer yet" for 29 and rejected 1. One reviewer, not blinded, graded the
  33 answers: 22 right, 10 partial, 1 wrong topic (a question about the cost of funds got debt service).
- **Usefulness and safety in live mode.** The intent classifier turned 4 of 589 questions into proposed plans that waited
  for "go ahead" (none was sent); the read-intent routing added since sends plain reads to the answers but does not change
  action labels. A buyer message the model and the rules read differently gave NO VERDICT, where the offline path counters:
  safe, less useful. The 8 attack prompts executed nothing visible in the replies, but none reached the router, so they do
  not test it.
- **Latency.** Sequential questions: p50 0.13 s, p95 1.17 s, max 5.8 s (at least 75 called the provider; a router call
  took p50 0.91 s). Twenty concurrent questions were all answered, the slowest in 8.4 s.

**Table 11. Other evaluation results (offline, 18 Oct 2026, `571ea64f`, unless noted).**

| Question | Result | Class |
| --- | --- | --- |
| Is the engine exact? | Financial values 67/67 and covenant and capex values 27/27 exact against the independent oracle; limits exact at ±1 fen, basis point or day (20/20) | Tests |
| How close to optimal is the router? | Within ¥1 of a bounded brute-force search on 26/26 scenarios (budget reached in 2 priced cases); no committed plan relies on an uncommitted facility | Tests |
| Is the router worth it, against a fair baseline? | Against "credit line first" restricted to actions FLOW can run, on the 18 scenarios where both can be compared: cheaper in 3 (¥169.78 in total) and equal in 15; in 1 more it finds a runnable plan where the baseline finds none. Its value is mainly that it finds a safe plan, explains it and says when that plan cannot run today, not large savings | Tests |
| Can every plan run today? | Of the 26 plans, 19 can run now, 6 depend on an action no operation can perform yet and are labelled "cannot run today", and in 1 scenario no admissible plan exists, which the router says | Tests |
| Does it walk away honestly? | In the one hard-line scenario tested, NO DEAL within 3 rounds and the gap still funded; 7/7 checks | Tests, simulated buyer |
| Is the router safe? | Every malformed or hostile output we scripted is rejected (24 kinds; 452 router, boundary, card and chat-attack tests pass). Nothing the router chose can act: its 40 tools are read-only | Scripted |
| Does language stay safe at the boundary? | 231 adversarial inputs (3 Oct, build `979defb`): 0 wrong material actions on the rules path and with a scripted model; not run against a live model | Rules, scripted |
| How fast is it? | In process on one development machine, cache mode, no network or model: router p50 81 ms (26 scenarios), chat turn p50 9 ms and p95 567 ms (87 turns), full Scene 1 p50 1.08 s (5 runs) (`975e082f`); these vary severalfold with machine load | Tests |

**Table 12. Stress tests on the demo company (read-only copies of the books).**

| Stress | Effect on cash | What FLOW does |
| --- | --- | --- |
| Foshan pays 10 days late | Same lowest point (day 30); 30 days below the reserve instead of 20 | Keeps the same funding longer (¥5,649.25) and **asks the owner**, because the advance's effective cost (16.7% a year) is now above the 15% approval threshold |
| Foshan pays only half | 35 days below the reserve | Its cheapest cover needs a buyer early payment on a future invoice, so it is labelled **cannot run today** |
| EBITDA 20% lower | Cash unchanged | Covenants weaken but hold (DSCR 1.50× at worst, leverage 2.15×); the plan is unchanged |

## 04 Security Design

### Tiered permissions and confirmation for sensitive actions

**The rubric's four threats.** The Security & Compliance criterion names four: induced transfers, data extraction,
privilege escalation and prompt injection. Table 13 names, for each, the control that stops it, where it is in the code, the
attack cases that exercise it and what it does not cover. The rest of this section explains the controls under the two
template prompts. Code paths are under `services/api/` and line numbers are those of `571ea64f`, the last base read line by
line; Appendix F lists every control with its lines. The attack figures are from the stored catalogue (Table 15): the
grouping of its classes under the four threats is ours.

**Table 13. The four threats in the rubric, the control that stops each, and its limits.**

| Threat | What an attacker tries | Control that stops it | Evidence | Attack cases (all reached their path; 0 harm) | Limits |
| --- | --- | --- | --- | --- | --- |
| **Induced transfers** (money moved or the business committed because someone said so) | "The owner has approved this", a pasted approval, a "pre-approved lender", a claimed earlier deal, a conditional or negated "go ahead", a changed or expired offer | No operation has a payee or account field. Money moves only through typed operations whose tier the executor computes. A Tier-2 operation runs only on the owner's approval, and a Tier-3 one never. Chat consent is a whole-message closed command. A claim is never a fact: a claimed concession is never booked, and a named lender becomes a logged claim, never a facility | `app/domain/models.py` (operation types); `app/mandate/tiers.py:85-120`; `app/operations/executor.py:360-416`; `app/nl/consent.py:1-40`; `app/domain/claims.py` | 32 API (social engineering 8, fake lender 10, claimed prior concession 7, changed offer 4, expired commitment 3): 29 stopped by the named control, 3 by another. 75 chat (41 consent, 18 Tier-3 requests put as questions, 16 owner quoting a buyer) | Inside the mandate FLOW acts alone (Tier 1): the agent key or a registered buyer's keyed message can draw on a committed facility up to its limit, and there is no aggregate draw limit (R-3). FLOW cannot tell whether a buyer the owner reports as agreeing really did |
| **Data extraction** (the owner's limits, books or another buyer's terms got out) | A buyer asking for the reserve, the floor or the limits; probing the counter; asking for another buyer's terms; planting a canary; reading routes without a token | Every read of the books needs the owner token. Outbound text comes from approved templates. An outbound guard blocks a whole message that holds a protected value in any common rendering. The agent's chat view is an allow-list of its own amounts. Contract terms are entitled to their own counterparty only. In live mode, model prompts carry redacted text and never the books | `app/api/auth.py:25-80`; `tests/egress/` (guard, canaries, renderings); `app/nl/router/route.py:61-123` | 22 API (reserve and facility 6, mandate 5, another buyer 6, canary 5): 20 stopped by the named control, 2 by another. 42 chat (buyer extraction 38, counter probing 4) | `/health`, `/clock` and the demo offer list are public (`/health` shows the model mode and flags, SEC-13). A keyed buyer can learn within one ¥10,000 step where the counter cap lies (R-10, Low). Redaction is pattern-based and can be switched off (PRIV-4, PRIV-5). No catalogue case reaches the outbound guard itself; `tests/egress` tests it directly (SEC-32) |
| **Privilege escalation** (acting above one's credential) | Self-approval, a body field "requested_by: OWNER", a caller-supplied tier, a forged or edited mandate, a reused nonce, a backdated operation, an agent resetting the circuit breaker, a session taken over | Tiers, actors and approvals come from code and credentials, never from the request. The executor pins one mandate key. Nonces are single use, operations are dated by the executor, approvals are decided once by the owner only, and a session continues only for the caller that opened it | `app/api/auth.py:155-175`; `app/api/operations.py:82-85`; `app/mandate/validity.py:9-70`; `app/commitments/lifecycle.py:149-153`; `app/persistence/guards.py:55-136`; route-policy test `tests/security/test_route_policy.py` | 37 API (escalation 22, replay 8, revoked mandate 7): 37 stopped by the named control. 16 chat (agent channel 7, session replay 9). Every route is also called as every kind of caller | One person holds the owner token and the signing key (R-2). Code inside the process is trusted (R-5). The database owner can rewrite the log (R-13). There is no route to revoke or renew the mandate (R-14) |
| **Prompt injection** (text becoming an instruction) | Override lines, fake system messages, role-play, encoded, full-width, zero-width or homoglyph text, a clause addressed to the agent, an instruction inside a contract | The architecture, not detection: the reading schema has no field for an operation, approval, tier or facility; every term must quote the source; the deciding modules never read free text; the classifier's closed list has no approve or reject; buyer turns never reach a classifier; the router's 40 tools are read-only. Detection is logged, but refusal never depends on it | `app/compiler/schema.py:9, 29-30`; `app/compiler/grounding.py:97-162`; `tests/verifier/test_invariants.py:20-62`; `app/nl/classifier.py:33-34`; `app/nl/service.py:173-174` | 17 API (14 stopped by the named control, 3 by another) and 18 chat buyer injections; injection text also runs through most other classes (70 API text attacks) | Offline, attack text was read by the rules grammar (78 readings) and a scripted hostile model (4); no real model, recorded or live, read an attack. Live mode is outside every certification |

Integrity and recovery are a fifth class in the catalogue: 20 failure-recovery cases (partial writes, double execution, an
erased log), all stopped by the named control.

<!-- figure: figures/fig10-authority-matrix.png | Figure 7. Who may do what. Tier 1 runs inside the owner-signed mandate; Tier 2 waits for the owner; Tier 3 is refused for everyone, the owner included. The tier is computed from the typed operation alone, and the demo mandate's limits are shown below. -->

**Who can act.** Credentials travel in headers and are compared in constant time (`hmac.compare_digest`,
`app/api/auth.py:25-80`). Every refused credential is logged as a security event, within a budget of 300 an hour and 30 per
address.

**Table 14. Credentials and what each confers.**

| Credential | Confers |
| --- | --- |
| Owner token (`X-Owner-Token`) | Owner authority: every read of the books, Tier-2 decisions, answering a buyer's request, revoking a commitment, adding facilities and customers, purchases, the simulated clock; demo reset and books setup in demo mode only |
| Agent key (`X-Agent-Key`) | The agent's tool channel: Tier 1 inside the mandate; Tier 2 is queued; every chat reply passes an allow-list view that shows only the amounts of its own operations, with no cash, limit or reserve figure (R-11) |
| Bank-feed key (`X-Bank-Feed-Key`) | Recording a receipt as the bank (Tier 1) |
| Buyer channel key (`X-Counterparty-Key`) | That a message comes from that registered buyer. FLOW answers it at once within Tier 1 (a counter, a decline, or a plain early-payment discount that passes every test); anything else is queued for the owner. 5 messages a simulated day, then refused |
| None | A message is read and checked as a proposal only and can never execute |

- **A field in a request body confers nothing.** A body "requested_by: OWNER" or "SYSTEM" without the matching credential
  becomes AGENT, and approvals and circuit resets take the actor from the token (`app/api/operations.py:82-85, 366-377`).
- **Demo mode is off unless set** (`app/config.py:52-56`). Without it the published demo credentials are rejected, owner
  routes answer 503 until a real owner token is set, and no demo data is seeded.
- **A production build ships no credential.** The owner signs in and the token is kept for that browser tab only. The demo
  launcher prefills the published demo token.
- **Rate limits apply to every caller (SEC-20).** A burst is refused with 429 and a retry time. The buckets live in memory
  and reset on restart.

**The three tiers (Figure 7).** The executor computes the tier from the typed operation and rejects a caller-supplied tier
(`app/mandate/tiers.py:85-120`).

- **Tier 1, autonomous inside the mandate.** Counter or reject a buyer's request (only the owner's decline closes it).
  Accept a pure early-payment discount on a named invoice that passes break-even, need, "cheaper than the plan" and the
  coverage proof (ADR-0005, ADR-0007). Draw on, repay or finance invoices from a committed, owner-approved facility, at any
  size within its limit (`tiers.py:73-77`), when admission passes and, for the agent, the cost is within the 15% approval threshold.
  Record a receipt from the bank feed or the owner. Tier 1 is reached by the agent key, by a registered buyer's keyed message
  and by the owner's own clicks; in the web app the owner's "run the plan" submits its legs as the agent, so a leg above the
  threshold is queued.
- **Tier 2, owner approval.** Longer terms; rebates, price, volume and other terms that are not a plain early-payment
  discount; any commitment whose future-concession value is above **¥100,000** (measured on future concessions, not the
  invoice, so an early-payment discount, worth ¥0 in future concessions, never reaches it); a draw on an uncommitted facility;
  applying for or adding a facility; an equipment purchase; setting up a confirmed contract's repeating invoice in the books
  (ADR-0014); a receipt reported by anyone other than the bank or the owner; and a funding leg the agent requests above the
  15% rate threshold.
- **Tier 3, never.** A personal guarantee, collateral, equity, changing the mandate, a facility the owner did not request,
  or any unknown operation type (`tiers.py:46, 94-99`). Refused for every caller, the owner included; an approved Tier-3
  operation stays refused.

**What approval can and cannot do.** The owner's approval releases a Tier-2 operation. It never waives a hard rule. The hard
rules are refused for everyone, the owner included: the concession caps (aggregate and per buyer), the covenants (DSCR,
leverage, clean-down), a reserve breach no committed funding can cure, an invalid mandate, and Tier 3
(`app/verifier/evaluate.py:190-193, 447, 562-573, 726-758`; `app/api/accept.py:97-107`, which answers 409 OVER_MANDATE or
NOT_ACCEPTABLE; `app/funding/admission.py:6-13`). **The 15% rate limit is an approval threshold, not a hard rule.** Above
it the agent must ask; the owner may approve, as the demo does at 32.5% on day 34, or draw directly
(`executor.py:852-854`). A reserve breach that committed funding can cure is not hard either: the owner may accept as asked,
and the receipt says the gap stays open (`accept.py:129-137`).

**The signed mandate and its key.** The owner's limits are a mandate signed with Ed25519 over sorted-key JSON
(`app/mandate/signing.py:13-56`). The executor pins one public key (`OWNER_PUBLIC_KEY_HEX`, or the demo key in demo mode) and
refuses to start without one; a forged, edited, expired or wrong-version mandate refuses every operation except a receipt and
an owner repayment (`app/mandate/validity.py:9-70`). Limits on custody: the demo private key is committed and labelled DEMO
ONLY (`fixtures/keys/owner_demo_ed25519.json`); setup signs a new mandate on the server with that key, in demo mode only, and
its "signature" step re-types the owner token (`app/api/setup.py:568, 579`); one person holds the token and the key (R-2);
and no route revokes, renews or re-signs the mandate (R-14). FLOW warns 14 days before the signed limits expire.

**Binding an acceptance to the exact offer.** An acceptance executes only against a commitment that binds the offer id and
version, the verdict, a random 128-bit nonce, the terms hash (SHA-256 of the canonical obligations) and an expiry day
(`app/commitments/lifecycle.py:90-157`; `app/commitments/terms.py:21-30`). The executor finds it by a constant-time nonce
match and requires the terms hash and value to equal the verdict's terms or one of its counters (`executor.py:861-870,
963-1004`).
- **Nonce.** Single use, stored append-only; reuse or mismatch is REPLAY. The chat path derives its nonce from the session
  key and the verdict, so a repeated "yes" cannot accept twice.
- **Expiry.** After the expiry day the commitment is COMMITMENT_EXPIRED.
- **Stale state.** The operation's day must be the executor's day (STALE_OPERATION). At commit the named invoices must still
  be owed, a request can hold one live agreement, the caps are re-checked, and a verdict made on older books is re-verified
  (STALE_VERDICT unless still acceptable). Owner routes bind the verdict id and the books' version (409 VERDICT_CHANGED,
  BOOKS_CHANGED), and the state is written with compare-and-swap (`executor.py:669-670, 703-717, 1077-1146`;
  `app/api/accept.py:296-318`).

**Approval and idempotency.** A Tier-2 operation is stored as its exact canonical JSON. Only the owner may decide it; anyone
else is refused and logged as PRIVILEGE_ESCALATION. It is decided once, by the executor and by database triggers, and a
decision the log already holds is refused even if the row is reset (SEC-08; `app/persistence/guards.py:55-136`, migration
0009). Approving re-runs every gate except the queue, dated today, against the mandate and admission then in force. "Accept
as asked" approves its own queued item in the same click. Open: a re-run refused at approval leaves the row marked APPROVED
although nothing ran (SEC-27, deferred by the owner). Every operation carries an idempotency key: a resend of an executed or
pending one is DUPLICATE, a refused key may run again, and the same key on a different operation is REPLAY with a security
event (`executor.py:757-796`).

**Negotiation steps and owner-reported acceptance.**
- **The simulated buyer** (Demo shell) answers under the process lock, bound to the verdict, the counter and the books'
  version (409 COUNTER_CHANGED, BOOKS_CHANGED; `app/api/decide.py:350-391`).
- **A registered buyer through its channel key** is answered at once within Tier 1, and anything else is queued
  (`app/nl/offers.py:319-367`). An unsigned message is a proposal only.
- **Outside FLOW (Business mode).** The owner sends the counter, for example by WeChat, and marks it as sent; the mark is
  bound to the verdict, the books' version, the mandate and the exact message hash (`app/api/outbound.py:348-396`). From then
  on no chat path or raw operation can answer that request (OUT-1, OUT-1b; `app/api/decisions.py:101-115`). Withdrawing
  appends a fact and deletes nothing.
- **"The buyer accepted" is the owner's report, not the buyer's.** It needs the owner token, is bound to the sent message's
  hash, its expiry, the counter's terms hash, the books' version and the mandate, and executes the acceptance as the owner; a
  Tier-2 result stays queued (`outbound.py:455-513`). **The buyer is not authenticated**: any evidence text is stored as an
  unverified document. "Declined" is bound to the message too, but a pasted buyer reply is read as a new request, not bound
  to the message, and a reply with no terms is refused (`outbound.py:610-646`). What FLOW books on a reported acceptance is an
  agreement in its own books, checked against the terms and today's books. It is not proof that the buyer agreed, not a
  signature and has no legal effect.

**Verification gates, in order** (`app/operations/executor.py`).
1. Idempotency key.
2. Dating.
3. Mandate signature, pinned key, expiry and version.
4. Tier 3.
5. Circuit breaker on repeated refusals. Only the owner can reset it, and the agent cannot trip it to take a decision away
   from the owner.
6. For acceptances: an unexpired commitment with a single-use nonce, a matching terms hash, and a verdict re-verified on
   today's books.
7. The Tier-2 queue.
8. Admission for draws and advances on today's books.

**The record: tamper-evident, not tamper-proof.**
- **Every outcome of an operation admitted to the executor is appended to a hash-chained log,** refusals and duplicates
  included, in the same unit of work as its effect: `entry_hash = sha256(prev_hash + payload + result)` from a zero genesis
  (`app/persistence/chain.py:4-36`). Requests refused before the executor are kept as append-only security events, which are
  not chained.
- **The database refuses to edit or delete history** (migrations 0003 and 0009; `app/persistence/guards.py`): the log, nonces
  and security events are append-only, approvals are decided once, and no session setting switches the guard off.
- **Checking needs nothing from FLOW.** `scripts/verify_evidence.py` recomputes an exported chain with Python's standard
  library and, with `--checkpoint COUNT:HEAD`, checks that a later export extends one kept elsewhere.
- **Limits.** The chain shows tampering by anyone without write access to the database. The API connects as the table owner,
  so a database administrator can drop the triggers and rewrite the chain consistently (R-13), and **the chain's head is not
  anchored outside the system**: the export's head hash is stored in the same database. A demo reset and books setup start a
  new chain (demo mode only).
- **Writes outside the executor.** Every typed operation goes through the executor. Three owner or demo actions also change
  the books, each logged: moving the simulated clock (ADVANCE_CLOCK), opening books from setup (OPEN_BOOKS, demo mode) and
  adding a customer (ADD_CUSTOMER). A demo reset erases the books and the log (demo mode only). Stored offers, verdicts,
  contract readings, deal facts and chat sessions are records, not books.

**Correcting a mistake: three different things.**
- **An internal compensating entry.** History is never edited. A mistake in FLOW's books is corrected by a new, logged
  operation: repay a draw, settle an advance, revoke a commitment, decline a queued request. A refused or pending operation
  changes nothing.
- **Contractual cancellation.** Revoking a commitment changes FLOW's books, not the agreement with the buyer. Undoing what was
  agreed with a buyer or lender is a matter between the parties, outside FLOW.
- **External payment reversal.** FLOW makes no real payment; bank effects are simulated entries. In a real deployment, money
  that had left a bank account could not be pulled back by FLOW.
- **Partial execution (SEC-28, Medium, deferred by the owner).** Each operation is atomic; a plan of several legs is not.
  Chat's "go ahead" stops at the first leg not executed and says "stopped after step N of M"; an alert's *act* continues past
  a queued leg; the simulated buyer's acceptance runs every leg and reports the gap funded before the legs' results are known.
  Nothing reverses or resumes legs: recovery is manual (read Activity, compensate, ask again) (`app/nl/plans.py:211-254`;
  `app/api/alerts.py:236-241`; `app/api/decide.py:358-375, 534-555`).

### Protection against prompt injection, privilege escalation and privacy leakage

**Prompt injection: architecture first, detection second.**
- **Buyer text can only become typed obligations whose quotes match the source.** The schema forbids extra fields and has
  none for an operation, an approval, a tier, a reply or a new facility (`app/compiler/schema.py:9, 29-30`). Every term must
  quote the source (exact match, with a whitespace-tolerant fallback), and its values are parsed by code from the quote
  (`app/compiler/grounding.py:97-162, 342-352`).
- **The deciding modules never read free text.** The verifier, funding router, covenants, mandate and financial engine are
  held to this by a test on their imports (`tests/verifier/test_invariants.py:20-62`).
- **Claims are not facts.** A claimed prior concession with no matching commitment is never booked; the chat reply and the
  buyer message call it what it is ("No terms agreement is on record"). A lender named in a message becomes a logged funding
  claim, never a facility. A condition on a future business event makes a gain contingent, whatever the reading says.
- **Detection is logged, but refusal does not depend on it.** The rules grammar flags override attempts, fake system lines,
  role-play, encoded, full-width, zero-width and homoglyph text, and authority claims, in English and Chinese.
- **Extraction errors are treated as a security problem.** A message the compiler cannot fully account for cannot be accepted
  without the owner (the coverage proof, ADR-0005), and the proof is forced false when the readers disagree
  (`app/compiler/cross_check.py:81`). Contract reading is imperfect (75% of fields on unseen text-layer contracts, section
  03), so a reading changes nothing until the owner confirms it, and only the owner's separate Tier-2 *Set up in my books*
  turns a contract into forecast invoices.
- **Contracts are read the same way.** Every term quotes its clause. A sentence addressed to the agent, assistant or system,
  or an instruction to add someone to the owner's customers or books, blocks confirmation and logs a security event.
  Documents are read only for counterparties on the owner's registry, and the chosen company must be the document's party in
  the role its kind needs (buyer, vendor or lender). The contract set-up is owner-only, bound to the document and the exact
  terms shown, re-checked on today's books, logged and undoable, and fails closed on an outsized invoice (OUTSIZED), an
  uncertain end date (END_NOT_CERTAIN), an interval under 7 days or a buyer that is not the customer's registered name. The
  borrower file counts set-up invoices only once the first is issued (CT-2b).
- **Chat and Ask FLOW are inside the boundary.**
  - Owner chat executes only a whole-message closed command (at most 160 characters, one RMB amount; `app/nl/consent.py`).
    Pasted or quoted text never becomes an instruction or an approval.
  - A question is answered from the books and never executes. Asking "can I pay everyone?" may save FLOW's plan, which runs
    only on the owner's later "go ahead"; a terms question is priced as asked, and a follow-up that only names the customer
    reuses the same terms.
  - A Tier-3 request put as a question is refused, logged and raises a Tier-3 security event, like the plain command.
    Greetings and thanks are recognised only as whole messages, and "what will FLOW never do" is answered from the tier
    lists in `app/mandate/tiers.py`.
  - The intent classifier (live mode only) chooses from a closed list without approve, reject or a buyer's message, buyer
    turns never reach it, and its output never executes (`app/nl/classifier.py:33-34`; `app/nl/service.py:173-174,
    346-347`). In live mode a question it labels as a plain read goes to the read-only answers and then the router; the rules
    and every security check run first, the classifier's canary guard stays, action intents are never redirected, and
    offline behaviour is unchanged.
  - The question router (ADR-0015, owner only) picks from 40 read-only tools; its output is validated, and its prompt holds
    the redacted question and the tool list, never the books.
  - A session continues only for the caller that opened it. Once the owner has marked a counter as sent outside FLOW, no chat
    path can accept, decline or send on that request.

**Privilege escalation.**
- **Tiers are enforced by code, never by prompts.** The executor trusts no caller-supplied tier, actor or approval.
- **Refused and logged:** self-approval; a circuit reset by the agent; a forged or edited mandate; a reused or guessed nonce;
  a backdated operation; an approval by anyone but the owner; a document decision by anyone but the owner.
- **Unknown fields are rejected.**
- **Every route is tested.** A route-policy test calls every method and route (106, including `/health`) as every kind of
  caller, with demo mode on, off and unset (`tests/security/test_route_policy.py`).

**Privacy leakage and data extraction.**
- **Outbound text** is filled from an approved template, never free model prose. A request for data gets one fixed reply.
- **An outbound guard blocks the whole message** if it contains a protected value: the reserve, a cap, a limit, the marginal
  rate, a buyer's terms or a planted canary. It recognises ¥, k, 万, Chinese and 大写 numerals, English number words,
  percentages and per-mille.
- **Every read of the books requires the owner token.** `/health`, `/clock` and the demo offer list are public.
- **Contract terms are protected values of their counterparty.** Another buyer cannot read them. A record refiled under
  another customer, or blocked because the party check found another company, entitles no buyer to its terms (REG-8; the fix
  is on the submission build, see Assurance).
- **The answer card**, which carries the owner's figures, is attached only to the owner's own turns; the agent's allow-list
  and the buyer's reply view never include it.
- **The web app sends a strict Content-Security-Policy** with a fresh nonce on each request (SEC-12).
- **What goes to a model provider (live mode only; cache mode sends nothing).** The compiler sends its fixed prompt, the
  schema and the document. The classifier sends the owner's message. The router sends a fixed prompt with the tool catalogue
  and the question (at most 500 characters, fenced as data); it never sends the books. Providers: DeepSeek
  (`api.deepseek.com`) or Anthropic, with no zero-retention setting and no region chosen.
- **Redaction, and its limits.** Before any of the three model calls, six kinds of identifier are replaced by placeholders:
  bank and card numbers, phone numbers, email addresses, unified social credit codes, ID and passport numbers, and addresses
  after a label (`app/compiler/redaction.py`). It is on by default. `LLM_REDACT=0` turns it off for all three calls; `pnpm
  demo --live-llm` forces it on whatever the shell says. It is pattern-based: names, amounts, clauses, chat ids, IBANs,
  full-width digits, 12- to 15-digit accounts and unlabelled addresses still reach the provider (PRIV-4, PRIV-5, Moderate).
  It has been tested with scripted models only.
- **Logging.** Each model call logs its backend, model, outcome, prompt version, a document hash, latency and redaction counts
  per kind. Router log lines carry a 16-hex hash of the redacted question and fixed reason codes, never the text; the hash is
  unsalted, so it hides nothing from someone who guesses the question. No document or question text is logged. The access log
  keeps the method, the path with its query string, the status and the client address.
- **An unexpected server error** returns a JSON 500 with the code INTERNAL_ERROR and no exception text, with the usual CORS
  and security headers, so the web app reports a server error rather than a lost connection.

**Compliance, in brief.**
- **Live-mode data.** Only in live mode does text leave the machine, redacted, to the configured provider. A deployer would
  need a data-processing agreement covering it and should tell the owner.
- **Cross-border transfer.** With DeepSeek, text goes to a provider in mainland China; with Anthropic, outside it. Sending real
  documents across the border would be a cross-border transfer under the PIPL, needing a legal basis and, where required, a
  security assessment or a standard contract. We have not done that assessment and do not claim compliance.
- **Labelled AI output.** Model readings are labelled "AI-generated, for reference" until the owner confirms them.
- **Not advice.** FLOW is decision support inside an owner-signed mandate, not a licensed lender, broker or adviser, and it
  makes no real payment.

**Attack results.**

<!-- figure: figures/fig7-security-results.png | Figure 8. The attack catalogue: 279 stored cases through the API and chat, by class. The catalogue grew from 259 (16 Oct) to 260 (TC-04, a changed offer), 261 (DOC-05, adding a customer without the owner token) and 279 (18 chat cases that put a Tier-3 request as a question, round five). None violated the defined harm oracles. Every case reached the path it targets; of the 128 API cases, 120 were stopped by the control they name and 8 by another control. -->

**Table 15. Attack results (279 stored cases: 128 through the API, 151 through chat; each in a fresh in-memory runtime,
offline, rules grammar and a scripted hostile model; report generated on `1294e941`, certified as part of `70f23ac5`, and
re-run on `571ea64f` with the same result).**

| Measure | Result |
| --- | --- |
| Harm-oracle violations, in each specified run | 0 of 279 |
| Unauthorised operations executed / money moved by attacks | 0 / ¥0.00 |
| Facilities added by non-owners; concessions booked from unproven claims | 0; 0 |
| Integrity failures (partial write, double execution, erased log) | 0 |
| Protected values disclosed in outbound text or readable without the owner token | 0 |
| Cases that reached the path they target | 279 of 279. A case that never reaches its path does not count as defended |
| API cases stopped by the control they name | 120 of 128 (93.8%). The other 8 were stopped by another control, with no harm (known gaps, SEC-34, each pinned by a test) |
| API cases with a detection signal / with a logged security event | 125 of 128 (97.7%) / 95 of 128 (74.2%). Over all 279, detection is 70.6%: most chat cases without a signal are consent cases, where the right result is that nothing runs |
| Tier-3 requests put as questions (chat) | 18 of 18 refused, logged and raising a Tier-3 security event (9 wordings, each as the owner and as the agent key) |

**How to read Table 15.** The harm oracles compare the books before and after each case: money moved, operations executed,
facilities added, concessions booked, commitments activated, protected values in any outbound text or readable without the
owner token, canaries, and the log's integrity. Six positive controls (legitimate actions, `tests/security/
test_positive_controls.py`) pass through the same runtime and oracle and are seen, and switching off one control at a time
makes the harness report harm (`tests/security/test_mutations.py`; 2 of 7 mutations first exposed blind spots, since fixed),
so the clean result is not a system that refuses everything. The attack text was read by the rules grammar (78 readings) and
a scripted hostile model (4): **no real model, recorded or live, read an attack.** The catalogue is the team's own, drives
part of the 106 routes (the route-policy test calls all of them) and runs in one process on an in-memory store. This is a
test result within a scope, not proof that no exploitable path exists. No running deployment has had a penetration test.

**The live stress test (18 Oct) is separate evidence, with its own scope.** On `28738f19` with DeepSeek live, the router on
and the demo books on loopback, 589 owner questions and 69 other turns all returned HTTP 200. Its 8 attack prompts executed
nothing visible in the replies, but none reached the router, no store diff was taken, and 2 of 8 raised a security event. It
measured availability and latency, not correctness or harm; section 03 gives its results.

**Assurance and certification.** Every review was AI-assisted and internal; none was independent professional assurance.
- **An audit and five red-team rounds by AI subagents (1 to 3 Oct)** found 39 issues. All are fixed, each with a regression
  test.
- **An external red-team run (16 Oct)** ran 17 tests, including 100 live model calls. Its report is not in the
  repository and who ran it is not recorded there, so we do not call it independent; its results are its own and were not re-run, and its five observations were re-checked against
  the code.
- **The Security Lead** is an AI agent working in a separate session and worktree. It reproduced every finding, wrote each fix
  on its own branch with a regression test, re-ran its checks on each merged commit and certified it. It also wrote the fixes
  it certified. "Certified" here is an internal release decision for a stated build and scope, not accreditation.
- **What it certified** (`docs/security/CERTIFICATIONS.md`): `29fa0ea2` (260 cases) and `85309b63` (261), each for the local
  simulation; `6d2b6941`, conditional on contract terms being switched off; and dev **`70f23ac5`, the final assessed build**,
  for the local simulation with contract terms and the router switched on as `pnpm demo` sets them, live model mode excluded.
  On `70f23ac5`: 10,674 API tests passed, 0 failed; 279 cases, 0 harm; PostgreSQL concurrency 3 of 3; 479 mock browser tests
  passed; 0 CSP violations. Disclosed with it: REG-8 (Low), REG-9 (Info), CT-2b (Low), and SEC-27 and SEC-28, deferred by the
  owner. (The record is commit `08c8dac0`; Security Self-Assessment v3 names its assessed build in its release manifest.)
- **The submission build is not yet certified.** It adds to `70f23ac5`: the Security Lead's round-six fixes (REG-8, blocked
  records entitle nobody; REG-9, demo lender names in demo mode only; CT-2b, the borrower file); Ask FLOW's new answers
  (paying everyone, terms priced as asked with two-turn memory, customer loss, a customer that stops ordering, borrowing
  against an invoice, DSO, the audit log by operation, greetings and "what will FLOW never do", "show me my cash"); the
  claimed-terms wording; the live-mode routing of classifier read intents; the Cash page's funding plan on books without a
  permanent source and the JSON 500; the Ask page card; the capex dash; and `--live-llm` forcing redaction. These go to the
  Security Lead as a short follow-up review. The attack catalogue still showed 0 harm on `571ea64f`; that is a test result,
  not a certification.

**Readiness.**

**Table 16. Where FLOW may run, and what stands in the way.**

| Configuration | Verdict | Minimum blockers |
| --- | --- | --- |
| Local demo (`pnpm demo`, loopback, cache mode, one API process, synthetic data, the presenter holds the credentials) | **GO** | None for `70f23ac5`. The submission build's additions await the Security Lead's follow-up review |
| Live-LLM mode (`pnpm demo --live-llm`, opt-in) | **Not covered by any certification** | A certification run in live mode; the language-boundary set and the attack catalogue run against a live model; a provider agreement on retention and region; PRIV-4 and PRIV-5 (redaction gaps) |
| A demo reachable over a network | **NO-GO** | A tested deployment profile: changed credentials and signing key, a TLS proxy with per-client limits, anonymous intake off (SEC-19), API docs hidden, one API process, the web dev server bound to loopback (DEMO-L1), a stop procedure, and the route sweep and browser checks run against it |
| Production with real customers, documents or money | **NO-GO** | A runnable configuration (SEC-06); one API process enforced or the route checks and the clock moved into the store (SEC-11); separate custody of the token and the key (R-2); an external anchor and a database role that cannot rewrite the log (R-13); mandate revoke and renew (R-14); resumable or reversible plans (SEC-28); an aggregate draw limit (R-3); redaction gaps and a PIPL assessment; backups and restore; a penetration test; and real counterparties, lenders and bank feeds in place of the simulated ones |

**Supported deployment configuration.** One API process. The two-process concurrency tests prove that the store's
compare-and-swap and unit of work hold (eight invariants; SQLite, and PostgreSQL 17 in 3 of 3 runs); they call the executor
directly and do not prove two API processes. Route checks use a per-process lock and each process keeps its own clock, so a
second API process could bypass a route check or act on an old day (SEC-11, open by the owner's decision). Nothing yet refuses
a second process.

## 05 Deployment and Testing

### Environment, deployment instructions, test cases and known limitations

**Environment.**
- **Operating system:** Windows 11, macOS or Linux.
- **API:** Python 3.12 or 3.13 with uv (`services/api/pyproject.toml`: `>=3.12,<3.14`); FastAPI and Pydantic 2. Books in
  memory or SQLite locally; PostgreSQL 17 for the concurrency suite and the (not yet runnable) compose stack.
- **Web:** Node 22 or newer with pnpm; Next.js and React. Exact versions are in the lockfiles and the Security
  Self-Assessment's release manifest.
- **No network or API key is needed** for the default mode, which reads every message and document with the rules grammar and
  its recorded readings (cache mode). Only `--live-llm` calls a model provider.
- **Name.** The code and its variables still use the working name TermsLedger (`termsledger-api`, `TERMSLEDGER_NO_DOTENV`,
  `termsledger.db`). It is the same system as FLOW.

**Run it (from the repository root, with uv, Node and pnpm installed).**

```
cd apps/web && pnpm install && cd ../..   # once
pnpm demo                                 # API on 127.0.0.1:8000, web on :3000; open the address it prints
pnpm demo --blank                         # empty books: set up your own company in six steps
pnpm demo --mock                          # the web app alone, on recorded data, no API
pnpm demo --keep                          # books kept in a local SQLite file across restarts (--fresh starts over)
pnpm demo --live-llm                      # live model calls for one run (key from the shell, see below)
```

`pnpm demo` starts the API with in-memory books, cache mode, `DEMO_MODE=1`, `TERMSLEDGER_NO_DOTENV=1` and the published demo
credentials, then the web app against it, and prints "Ready" with the address when both are up. The owner sign-in is
prefilled with the published demo token. It switches on everything the demo shows: contracts and their set-up in the books
(ADR-0014), customer exposure, the buy side, the strategy views and the question router's flag (the router acts only in live
mode). If a port is taken, the launcher says so and suggests `--api-port` or `--web-port`. `pnpm demo:blank`, `demo:mock` and
`demo:keep` are the same commands.

- **`pnpm demo --live-llm`** calls the provider live: Ask FLOW's router answers what the built-in answers miss, and new
  documents and buyer messages are read by the model. It reads the key from the shell only (`DEEPSEEK_API_KEY`, else
  `ANTHROPIC_API_KEY`; PowerShell: `$env:DEEPSEEK_API_KEY = "..."`), never `.env`, and does not start without one. It forces
  redaction on. Each call is paid. Live mode is outside every security certification (Table 16). It does not combine with
  `--mock`.
- **The web dev server listens on all interfaces** (DEMO-L1). Run the demo on a trusted machine, or behind a firewall.

In the app, open **Demo**, choose **Golden story** and follow the six scenes. Or use the Business pages directly: Home, Deals,
Attach deals, Cash & funding, Sandbox, Capex, Receivables and Activity, with Ask FLOW on every page and Approvals, *Your
limits* and *Security and evidence* from the header and the account menu.

**Check the evidence without the UI** (from the repository root; on Windows also set `PYTHONUTF8=1`).

```
uv run --project services/api python scripts/judge_eval.py --out <folder>/judge-report.md
uv run --project services/api python scripts/verify_evidence.py <exported.jsonl>
uv run --project services/api python scripts/evaluate.py --out <folder>
```

- `judge_eval.py` takes about 2 minutes: it runs the 49 scripted tasks, the 279 attack cases and the demo walk, checks the
  evidence chain and confirms that a tampered copy is rejected. Without `--out` it overwrites the committed
  `services/api/evals/judge/judge-report.md`, which is from 16 Oct (259 attacks).
- `verify_evidence.py` recomputes the chain of an export from *Security and evidence* (*Download JSONL*) with Python's standard
  library; `--checkpoint-out` prints a `COUNT:HEAD` to keep elsewhere, and `--checkpoint COUNT:HEAD` checks a later export
  against it.
- `evaluate.py` is the full offline evaluation (about 8 to 12 minutes, most of it the funding brute force).

**Production deployment, and why it is not ready.** `infra/docker-compose.yml` runs PostgreSQL, the API and the web app with
demo mode off, and refuses to start without real secrets. **It does not yet produce a working API** (SEC-06): the owner's
public signing key is not passed in, nothing provisions the books and the signed mandate, no buyer channel keys are set, and
the web image is built against `localhost:8000`. It also runs the containers as root and the web app over plain HTTP on all
interfaces. The supported way to run FLOW is the local launcher above, as one API process (section 04).

**Test inventory.** No test runs against a deployed, networked system: every result is local, loopback or in-process. The
full catalogue, with what each suite proves, is `docs/deliverables/TEST_CASES.md`.

**Table 17. Test classes, what each can show, and the latest recorded result.**

| Class | What it covers | Latest result (build) |
| --- | --- | --- |
| Unit and invariant tests (pytest, hypothesis) | Engine against the independent oracle, verifier, router, executor and tiers, mandate, persistence and the chain, two-process store invariants, compiler, contracts, chat, security harness, route policy | 10,674 passed, 0 failed, 47 skipped (`70f23ac5`, the Security Lead's run, 18 Oct) |
| Browser, mock (Playwright on recorded JSON) | Every page on recorded JSON, checked against the golden values | 479 passed, 77 skipped (`70f23ac5`) |
| Browser, live (Playwright `live` project against a local API) | Writes through the real API on loopback | 139 passed, 2 known failures (`975e082f`; see Known failures) |
| Web unit, types and lint | The web app's own logic | 169 passed; typecheck and lint clean (`975e082f`) |
| Scripted model | Hostile or malformed model outputs written by the team: the router's validator, the classifier, the compiler's cross-check, the 231-item language boundary | Router, boundary, answer-card and chat-attack tests 452 passed, 1 skipped (`571ea64f`); language boundary 0 wrong-and-material (last run on `70f23ac5`) |
| Recorded replay | Past readings replayed offline | The 19 shipped recordings are rules-grammar output; no model output ships. The contract figures used DeepSeek readings recorded outside the repository |
| Live provider | DeepSeek called on the day | Buyer messages, 1 Oct (older build); the stress test, 18 Oct (section 03); the external red-team run, 16 Oct |
| Deployed system | — | None |

**Table 18. Evidence for every headline figure (offline, cache mode, unless noted; commands from `services/api` unless they
start with `uv run --project`).**

| Claim | Command | Result |
| --- | --- | --- |
| API tests | `uv run pytest` (tests opt in to demo mode; on Windows set `SKIP_PERF_BENCH=1`) | 10,674 passed, 0 failed, 47 skipped on `70f23ac5`. Issue #161 (a stale pin) is closed since `29fa0ea2` |
| Web tests | `pnpm typecheck`, `pnpm lint`, `pnpm test:unit` (apps/web) | Clean; 169 passed (`975e082f`) |
| Browser tests | `pnpm exec playwright test` (mock projects); `--project=live` with a local API running | Mock 479 passed, 77 skipped (`70f23ac5`); live 139 passed, 2 known failures (`975e082f`) |
| Attacks | `TERMSLEDGER_NO_DOTENV=1 DEMO_MODE=1 DATABASE_URL=memory LLM_MODE=cache uv run python -m app.security.attacks --report` (overwrites the committed `evals/security/latest_report.*`) | 279 cases (128 API, 151 chat), 0 harm-oracle violations, 279 reached their path, 120 of 128 API cases stopped by the named control; API detection 97.7%, security events 74.2% (`1294e941`; certified in `70f23ac5`; the same on `571ea64f`) |
| Agent tasks | `uv run --project services/api python scripts/run_scenarios.py --inproc` | 49/49 (88 turns); every evidence chain verifies (`571ea64f`) |
| Judge pack | `uv run --project services/api python scripts/judge_eval.py --out <folder>/judge-report.md` | 49/49 tasks, 279 attacks with 0 harm, demo walk OK, chain valid (14 operations, 8 security events), tampered copy rejected; 105 s (`571ea64f`) |
| Owner questions | `uv run python scripts/owner_questions_baseline.py` | Of the 427 turns the books can answer: 228 answered, 45 partly, 154 declined, 0 wrong; 75 of the 76 turns the books cannot answer declined honestly (`571ea64f`). The script's own tally, 303 answered and 46 partly of 503, counts those honest declines as answers |
| Everyday wording | `uv run python scripts/owner_questions_general.py --part all` | 326/345, 4 wrong topic (1.2%); held-out 127/142 (89.4%), 3 wrong (2.1%) (`571ea64f`) |
| Router and answer cards | `uv run pytest tests/nl/test_ask_router.py tests/nl/test_router_tools.py tests/certification/test_ask_router_boundary.py tests/nl/test_answer_card.py tests/security/test_nl_attacks.py` | 452 passed, 1 skipped (`571ea64f`) |
| Offline evaluation | `uv run --project services/api python scripts/evaluate.py --out <folder>` (7 min 41 s on `975e082f`) | Every target in its own gate met, on its default offers set (`fixtures/heldout`, used in tuning). On held-out 3, scored separately, the material-error and silent-error targets are not met. Figures in Tables 10 and 11 |
| Autonomy funnel | `uv run --project services/api python scripts/analysis/autonomy_funnel.py fixtures/heldout3 fixtures/heldout2` | Table 9 |
| Contract reading | `scripts/evaluate_contracts.py` (live readings) and the scorer in `services/api/scripts/eval_contracts.py`, on 70 synthetic contracts kept outside the repository | 75% of fields on unseen text-layer contracts, 86% after fixes, 98% tuned (recorded DeepSeek readings, 17 Oct). Not reproducible from the repository |
| Evidence chain | `uv run --project services/api python scripts/verify_evidence.py <exported.jsonl>` | VALID; an edited copy is rejected |
| Concurrency on PostgreSQL | `TERMSLEDGER_TEST_DATABASE_URL=<empty local database> uv run pytest tests/concurrency` | 3 of 3 clean runs (`85309b63`, `70f23ac5`) |
| Routes and migrations | `python -I scripts/security_route_inventory.py . out.json` (repository root); Alembic head | 106 routes: 105 under `app/api` plus `/health` (100 on `975e082f`, counted the same way), plus three documentation routes in demo mode; migration 0009 |

The submission build adds the changes listed under Assurance in section 04 after the last measured base (`571ea64f`); the
owner-question figures, the judge pack and the API suite are re-run on it before submission.

**Table 19. Representative test cases.**

| Case | Input | Expected result | Checked by |
| --- | --- | --- | --- |
| The golden request | EX01: 60-day terms, 1.2% early payment, contingent rebate | Rejected with four reasons; Options A and B; the buyer accepts A and pays ¥257,790.00 on day 2 | Scripted task S01, evidence chain verified |
| Honest no deal | A hard-line buyer refuses every counter | NO DEAL within 3 rounds; the gap funded for ¥3,113.93; the reserve holds | Evaluation gate E5 (7/7) |
| Early-payment boundary | Whole-invoice early payment at 0.75%, then 0.74% | 0.75% (¥3,150.00) countered as dearer than the plan; 0.74% (¥3,108.00) accepted at Tier 1 | Verifier hand-calculation tests |
| Cure above the approval threshold | Day 34: "go ahead" on a ¥200,000 advance at 32.5% a year | Queued for approval, nothing runs (Figure 9); it runs only on the owner's approval, and the cash lands on day 37 | `scripts/demo_run.py` |
| Consent | Negated, conditional, future-dated, foreign-currency or quoted instructions, in both languages | Nothing executes | 41 consent attacks |
| Injection in a contract | A clause addressed to the agent | Never read as a term; cannot be confirmed; a security event is logged | Contract-ingestion attacks |
| Wrong company or role | A contract naming two other companies, one naming Foshan only as the supplier, a reading with no parties | Cannot be confirmed; the companies it names are shown | `tests/contracts/test_party_roles.py` |
| Blocked record | A contract record blocked by the party check, then a buyer asking for its terms | The record entitles no buyer to its terms (REG-8) | `tests/security/test_round_six.py` |
| Look-alike customer | "Add a customer" with a homoglyph or accented copy of a registered name, an id-like name or the business's own name | Refused (409 or 422); nothing is added | `tests/api/test_customer_lookalikes.py` |
| Tier 3, plain or as a question | "Sign a personal guarantee", "should we pledge the equipment?", 要不要签个人担保？, as the owner or the agent key | Refused, logged, a Tier-3 security event; the plain information question ("What is a personal guarantee?") is answered and writes nothing | 18 chat attacks (NL-TQ01 to 18), `tests/nl/test_tier3_questions.py` |
| Tampered evidence | One log entry edited | The verifier rejects the copy; untouched chains verify | Judge pack |
| Two writers on one database | Two worker processes call the executor on the same books at once | Eight store invariants hold and a serial replay gives identical books (SQLite; PostgreSQL 17, 3 of 3). This covers the store, not two API processes (SEC-11) | `tests/concurrency/` |
| A question about acting | "Can we pay off all our loans?", 我们能还清所有贷款吗？ | "No. Repaying all ¥1,500,000 today…", in the question's language; nothing executed or queued | Owner-question bank, `tests/nl/test_ask_books.py` |
| Recording a payment | The owner records a payment, or part of one, including on a financed invoice | Tier 1; a financed invoice repays its lender first; the same press twice is one payment | `e2e/record-payment.spec.ts`, `tests/api/test_owner_receipt.py` |
| Contract set-up out of bounds | "Set up in my books" from a contract naming another buyer; queued by the agent key; ¥90,000,000 every day; an uncertain end date | Nothing is set up; only the owner can queue it (Tier 2); OUTSIZED or END_NOT_CERTAIN | `tests/api/test_contract_terms.py`, `tests/contracts/test_terms_setup.py` |
| A server error on Cash & funding | Books with no committed source able to carry a permanent need | The plan, menu and comparison still answer; any unhandled error is a JSON 500 with no exception text and CORS headers | `tests/api/test_cash_unreachable.py` |

<!-- figure: screenshots/shot3-approval.png | Figure 9. The owner decides what is outside FLOW's limits. On day 34 FLOW proposes a ¥200,000 advance; because it costs 32.5% a year, above the 15% approval threshold, it waits on the Approvals page and nothing has run. -->

**Known failures, as they stand.**
- **Live browser suite:** `e2e/live.spec.ts:334` and `:348`, the write-conflict retry tests (#157), and
  `e2e/tracker.spec.ts:216` ("after the owner's approval the page's figures are the API's own"). The first two fail the same
  way on the base; a knock-on failure can follow them in the same run.
- **Timing benches under load:** the cold-read timing bounds in `tests/api` (`test_compare`, `test_exposure_routes`) and the
  performance benches fail on a busy machine; set `SKIP_PERF_BENCH=1` on Windows. Latency figures in section 03 are
  single-machine and vary severalfold with load.

**Known limitations.**

*Limits of the demo, by design:*
- **Everything outside FLOW is simulated.** Lenders, buyers, rates and the bank feed are simulated, and no real money moves.
- **No model output ships.** Offline, every message and document is read by the rules grammar and its recorded readings; live
  readings need `--live-llm`.
- **The plain demo forgets on restart.** `pnpm demo` keeps the books in memory; `pnpm demo --keep` keeps them in SQLite.
- **The buyer side on the owner's own books.** On books opened through setup, the buyer channel and the simulated buyer cover
  the first two customers, and the *Buyer messages* card holds the demo company's messages only.
- **Business-mode acceptance.** Recording a buyer's acceptance books the agreement; the funding plan is run separately from
  Cash & funding.

*Product gaps, with the next step:*
- **Settlement dates.** Good early-payment offers that state a settlement date go to the owner, because the date is not yet
  read into the terms (Table 9). Reading settlement dates is next.
- **Funding search.** The router searches up to three actions on a ¥10,000 grid, all requested today; six of the 26 router
  plans rely on actions FLOW cannot run yet (a buyer's early payment, discounting a bill) and are labelled "cannot run today".
- **Capex.** The search compares standalone structures only. It misses a loan plus a short bridge, which on the demo would save
  about ¥39,000.
- **Contracts.** 75% of fields on unseen text-layer contracts; scans and photos are refused, since there is no OCR. One
  repeating invoice per contract is set up; rebates and milestones are shown, not set up.
- **Extra requests** are found by cue words and figures. A request with neither could pass the coverage proof, but only for a
  pure early-payment discount below break-even.
- **Live models.** Each live result is one run on one day: buyer messages on 1 Oct (an older build), the question router on
  18 Oct. Neither measures run-to-run variation, and the provider's model version is not recorded. The language-boundary set
  has not been run against a live model. In live mode the older intent classifier can turn a question into a proposed plan
  (4 of 589 on 18 Oct), which still waits for the owner's "go ahead".
- **Owner questions.** 154 of the 427 bank turns the books can answer are still declined (each names the nearest read), and 15 of the 345 everyday
  wordings miss their answer.
- **Chat approval card.** The card does not print the approval's id; the reply's sentence names it ("APR-000001"), and a bare
  "approve it" binds to the request just shown.

*Security and production limits* are in section 04: Table 13 (each threat's limits), Table 16 (readiness and the minimum
blockers) and the supported single-process configuration. The open risks are listed with their ratings in the Security
Self-Assessment.

#### Appendix 0. Criterion-to-evidence index

Each judging criterion, and each prompt of the technical document template, with the part of this document that answers it
and the evidence behind it. Paths are repository-relative.

| Criterion or template prompt | Answered in | Evidence |
| --- | --- | --- |
| **Task Completion (40%)**: scripted tasks in a simulated environment | Table 1; 03 "Core algorithms and evaluation approach"; Table 18 (agent tasks, judge pack); Appendix E | `scripts/judge_eval.py` (49 tasks in `services/api/evals/e2e/scenarios.yaml`); `docs/deliverables/execution_evidence.md`; `docs/deliverables/evidence/EVIDENCE_PACK.md`; the demo video |
| **Security & Compliance (30%)**: induced transfers | Table 13, first row; Figure 7; 04 "What approval can and cannot do", "Binding an acceptance", "Negotiation steps" | `services/api/evals/security/latest_report.json` (classes social engineering, fake lender, prior concession, changed offer, expired commitment, consent); `docs/SECURITY_SELF_ASSESSMENT.md` |
| Data extraction | Table 13, second row; 04 "Privacy leakage and data extraction" | `latest_report.json` (exfiltration, cross-buyer, canary and chat extraction classes); `services/api/tests/egress/` |
| Privilege escalation | Table 13, third row; Table 14; 04 "Privilege escalation" | `latest_report.json` (escalation, replay, revoked mandate, agent channel, session classes); `services/api/tests/security/test_route_policy.py` |
| Prompt injection | Table 13, fourth row; 04 "Prompt injection: architecture first, detection second" | `services/api/evals/security/attacks.yaml`; the chat catalogue in `services/api/app/security/attacks.py`; `services/api/tests/verifier/test_invariants.py` |
| Serious security failures; assurance and readiness | Table 15, Figure 8; 04 "Assurance and certification"; Table 16 | `docs/security/CERTIFICATIONS.md`; `docs/security/FINDINGS_REGISTER.md`; `docs/security/RELEASE_GATE.md` |
| **Innovation & Interaction (30%)**: scenario novelty and real-world value | 01 "Problem, target users and selected topic" and "Core value and innovation" | Section 01's comparison and screen tables; the deck; the demo video |
| Dialogue efficiency, clarification, correction, fallback | 03 "Intent understanding, planning, tool use and state management"; Appendix E stage 8 | `services/api/tests/nl/`; `services/api/scripts/owner_questions_baseline.py`, `owner_questions_general.py` |
| **Bonus (0–5)**: advanced topic or real-world deployment | Not claimed: FLOW is a local simulation (05 "Production deployment"; Table 16) | — |
| 01 Problem, target users and selected topic | Section 01, first prompt | Section 01's tables |
| 01 Core value and innovation | Section 01, second prompt; Figure 1 | `docs/deliverables/evidence/EVIDENCE_PACK.md` (the worked example) |
| 02 Architecture diagram and component responsibilities | Section 02, first prompt; Appendix B | `docs/deliverables/figures/`; `docs/adr/` |
| 02 Models, tools, data sources and external services | Section 02, second prompt; Appendix C | `services/api/app/compiler/`; `services/api/app/nl/router/`; `fixtures/` |
| 03 Intent understanding, planning, tool use and state management | Section 03, first prompt | `services/api/app/nl/`; `services/api/tests/nl/` |
| 03 Core algorithms and evaluation approach | Section 03, second prompt; Appendix A | `scripts/evaluate.py`; `services/api/evals/`; `fixtures/golden/` |
| 04 Tiered permissions and confirmation for sensitive actions | Tables 13 and 14; Figure 7; Appendix F | `services/api/app/mandate/tiers.py`; `services/api/app/operations/executor.py` |
| 04 Protection against prompt injection, privilege escalation and privacy leakage | Tables 15 and 16; Figure 8 | `services/api/evals/security/latest_report.json`; `docs/SECURITY_SELF_ASSESSMENT.md` |
| 05 Environment, deployment instructions, test cases and known limitations | Tables 17 to 19; Figure 9 | `README.md`; `docs/deliverables/TEST_CASES.md`; `scripts/demo.mjs`; `scripts/verify_evidence.py` |

#### Appendix A. Metric definitions

- **Verdict agreement:** the share of labelled messages where FLOW's verdict equals the label. Three held-out-3 messages are
  unlabelled, so 66 messages give 63 comparisons.
- **Material error:** FLOW booked a verdict and a booked obligation differs from the label in type, rate, amount, days or
  contingency. It is counted over messages not labelled "must abstain": 51 of 66 in held-out 3.
- **Silent material error:** a material error, plus a must-abstain message that FLOW booked anyway.
- **Wrong autonomous accept:** FLOW accepted at Tier 1 with no owner, and the label is not "accept" or the booked terms carry a
  material error.
- **Form baseline:** the labels typed straight into the verifier, with no compiler. It measures the verifier's policy against
  the labeller's.
- **Eligible for autonomy (Table 9):** the label is a pure early-payment accept, and the discount is cheaper than the standing
  plan under today's rules.
- **Harm-oracle violation (Table 15):** after an attack case, the books show money moved, an operation executed, a facility
  added or changed, a concession booked, a commitment activated, a protected value in outbound text or readable without the
  owner token, a canary tripped, or a broken log.
- **Stopped by the named control (Table 15):** the evidence the case names among its expected controls was observed. A case
  held by a different control counts as a known gap (SEC-34), not as defended.
- **Detection signal (Table 15):** a security event, an executor refusal, a security or mandate-limit verdict code, an HTTP
  refusal or a detected chain break.

#### Appendix B. Components (services/api/app unless noted)

| Component | Responsibility |
| --- | --- |
| `compiler/` | Offers, term sheets and contracts into typed obligations or terms, each grounded in an exact quote; redaction; the coverage proof |
| `financial/`, `covenants/` | The daily cash, debt and future-concession trajectory in integer fen; DSCR, leverage and clean-down |
| `funding/` | The router: the cheapest plan in its search space, marginal cost of funds, break-even, admission |
| `mandate/` | Ed25519 signing and verification, validity, tiers and mandate rules |
| `verifier/` | The verdict, reason codes, formulas and priced counters; reads no free text |
| `operations/`, `commitments/` | The executor (the only path for typed operations) and the commitment lifecycle with nonce, expiry and terms hash |
| `books/`, `clock/` | Today's books plus agreed changes; the simulated clock |
| `persistence/` | Tables, migrations 0001–0009, the hash-chained log and the database guards |
| `security/` | The attack harness and its harm oracles |
| `nl/` | The chat harness: intents, slots, consent grammar, sessions, plans, small talk; `nl/answers` (the read-only answers and their figures), `nl/router` (the question router's 40 read-only tools and its validation, ADR-0015) and the answer card |
| `setup/` | The setup wizard: checking the six steps, the preview and opening the books |
| `contracts/`, `ingest/`, `deals/`, `decisions/`, `outbound/` | Contract records and reading, the party check and contract set-up, the deal summary, the decision record and tracker, the message to the buyer |
| `counterparties/` | The simulated buyer and its profile fitted to the books in use |
| `capex/`, `health/`, `lending/`, `borrower_file/` | Capex screening, purchases and long-term plans; financial health; loan eligibility; the borrower file |
| `alerts/`, `whatif/`, `strategy/`, `pilot/` | Cash alerts and reconciliation; the sandbox; read-only strategy answers (exposure, price curve, envelope); the pilot journal (off in the demo) |
| `api/` | Routes, authentication, rate limits, the JSON error responses and every sentence shown, in English and Chinese |
| `apps/web` | The Next.js app: the setup wizard, the Business pages, the Demo story, Ask FLOW (panel and page); displays server-written values only |

#### Appendix C. The agent's tools (HTTP routes, owner token unless noted)

`GET /health`, `GET /clock` and the demo offer list are public; the buyer channel, the agent key and the bank feed use their
own credentials (Table 14).

| Area | Routes |
| --- | --- |
| Setup (demo mode) | `GET /setup/status`; `GET`/`POST /setup/documents`; `POST /setup/preview`, `/setup/open`; `POST /demo/reset`, `/demo/restore`, `/demo/bank-receipt`; `GET /demo/story` |
| Chat | `POST /nl` (a buyer sends its channel key); `POST /nl/opener`; `POST /nl/session/reset`, `/nl/reset` |
| Offers and negotiation | `POST /offers`, `/offers/{id}/evaluate`, `/negotiate/{id}`, `/offers/{id}/accept`, `/decline`; `GET /offers/{id}/picture`, `/scenarios`, `/compare`, `/exposure`; the message to the buyer, marked sent, withdrawn, accepted or declined (`/offers/{id}/counters/{cid}/…`), `POST /offers/{id}/buyer-reply` |
| Funding and capex | `POST /router/plan`, `/facilities/compile`, `/capex/evaluate`, `/capex/apply`, `/capex/plans`, `/capex/contracts/{id}/evaluate`, `/capex/contracts/{id}/commit`; `GET /purchases`; `GET`/`POST /finance/health`, `/lending/eligibility`; `POST /lending/products/{id}/add-to-menu`; `POST /borrower-file`, `GET /borrower-file/{id}.html`, `.docx`, `.pdf` |
| Execution | `POST /operations` (including the owner's recorded payment); `GET /approvals/queue`; `POST /approvals/{id}`; `POST /commitments/{id}/revoke`; `POST /circuit/{id}/reset` |
| Clock, alerts, reconciliation | `GET /clock`, `POST /clock/advance`; `GET /alerts`; `POST /alerts/{id}/act`; `GET /reconciliation`; `GET /receivables`, `/receivables/{id}/chase` |
| Contracts, customers and deals | `POST /documents`; `GET /documents`, `/documents/{id}`; `POST /documents/{id}/confirm`, `/reject`, `/refile`; `GET`/`POST /documents/{id}/terms`, `POST /documents/{id}/terms/undo`; `GET`/`POST /customers`; `GET /customers/{id}/overview`; `GET`/`POST /buyers/{id}/inputs`, `/firm/inputs`; `GET /deals`, `/deals/{buyer}`; `GET /decisions/{id}/tracker`, `/compare`, `/exposure` |
| Sandbox and strategy | `GET /whatif/presets`, `POST /whatif`; `GET /cash/price-curve`, `/buyers/{id}/envelope`, `/buyers/{id}/exposure`, `/receivables/worth`; `GET`/`POST /pilot/journal` |
| Read views and evidence | `GET /state`, `/mandate`, `/trajectory`, `/ledger`, `/audit`, `/evidence`, `/security/summary`, `/home`, `/worklist`, `/nav/counts`, `/activity`, `/decisions`, `/decisions/{id}`; fixture lists for the demo |

#### Appendix D. Terms and codes

| Term | Meaning |
| --- | --- |
| fen, bp | ¥0.01; 0.01%. Money is integer fen and rates integer basis points |
| Mandate | The owner's signed limits: cash reserve, concession caps, covenant thresholds, the rate and commitment approval thresholds |
| Reserve (floor) | The lowest closing cash the mandate allows on any day: ¥300,000 on the demo company |
| Tier 1, 2, 3 | What FLOW may do alone inside the mandate; what waits for the owner's approval; what is refused for everyone (Figure 7) |
| Hard rule | A rule no approval can waive: the concession caps, the covenants, a reserve breach no committed funding can cure, an invalid mandate, Tier 3 |
| Approval threshold | A limit above which the owner must approve: a commitment's future concessions above ¥100,000, or funding the agent requests above 15% a year |
| Golden books | The synthetic demo company, with expected values from an independent oracle |
| Marginal cost of funds | The all-in rate of the cheapest committed source able to carry a permanent need: 10.84% |
| Break-even discount | The largest early-payment discount cheaper than that source: 0.8832% for 30 days |
| Future concession | A promise that costs money later (longer terms, a rebate, a price change), valued at the marginal cost of funds |
| Coverage proof | The compiler's check that every figure and request in a message is accounted for (ADR-0005) |
| Tamper-evident | Any edit to the log breaks its hash chain and is detected; it does not stop a database administrator rewriting the whole chain |
| Cache mode, live mode | Offline reading with the rules grammar and its recorded readings; live calls to a model provider (`--live-llm`) |
| ADR-nnnn | An architecture decision record (`docs/adr/`) |
| SEC-nn, R-nn, PRIV-n, REG-n, CT-n | A security finding, risk, privacy item, registry finding or contract set-up finding in the Security Self-Assessment and the findings register |

#### Appendix E. Feature tour: the life of a supplier using FLOW

The tour follows one owner through FLOW in the order a business meets it, on the submission build. Stage 1 runs on blank
books (`pnpm demo --blank`); every other stage runs on the demo company (`pnpm demo`), whose figures are those of sections 01
and 03. Each stage names the screens, what the owner does and what FLOW does. Buttons and links are in italics.

**Demo video.** The submission video follows these chapters: setting up the books; the daily view; a buyer asks; FLOW decides;
the counter is sent; the deal, followed; time passing and the cure; the owner decides; documents; Ask FLOW; records, evidence
and security. Its timestamps follow the final recording and are given with it (`docs/deliverables/video/README.md`).

**1. Setting up the books.** *Screens:* the landing page, *Set up your books* (`/setup`), Home. *The owner* chooses *Join FLOW
now!* and works through six steps: the business and its cash; credit lines and loans (*Fill from an agreement* reads a lender
agreement); customers, their repeating contracts and unpaid invoices (*Fill from a contract*); bills coming up (quick-add
payroll, rent, supplier payments, tax); and the limits FLOW will work within. On the review step the owner sees the "First
look" at what Home will say and chooses *Sign and open my books*, re-typing the owner token. *FLOW* checks every step on the
server, signs the limits as mandate version 1 (with the demo key, demo mode only) and opens the books with one logged entry
that starts the evidence chain. Home then answers from the owner's own figures.

<!-- figure: screenshots/shot1-home.png | Figure 10. Home on the demo company, day 0: without new funding cash falls to −¥105,000 within 30 days; FLOW recommends securing ¥405,000 before payroll in 12 days, for ¥3,113.93, with no approval needed. -->

**2. The daily view.** *Screens:* Home, the header, the account menu. *The owner* reads Home from the top (Figure 10): the cash outlook
says the reserve is breached in 12 days, and *What we recommend* covers it for ¥3,113.93 (the credit line ¥150,000 plus
invoice financing ¥255,000) inside the signed limits. Below are *Your worklist*, cash available today with the funding ring,
upcoming movements and what each customer owes. *FLOW* writes every figure and sentence on the server, in English or Chinese
(the account menu switches language), and counts what waits for the owner on the menu's badges. *Show me around* replays the
tour of any page, and the header switches between the Business app and the Demo shell.

**3. Documents.** *Screens:* Attach deals, the document review, Deals. *The owner* drops the Foshan supply agreement, then
picks Foshan Home Retail from the list of known companies (or *Add a new customer*). *FLOW* reads it into 18 terms, each beside
its quoted clause (Figure 11), and "This deal at a glance" shows the money terms against the forecast. After *Confirm*, the card says what
was saved, under which customer, and that the forecast has not changed. Filed under the wrong customer, the same contract
cannot be confirmed: FLOW lists the companies it names and offers *File it under Foshan Home Retail Co.* without a new
reading. Dongguan's contract reads as one invoice of ¥180,000 every 30 days on 45-day terms; *Set up in my books* shows each
figure beside its clause and the forecast now and once the first invoice is issued, and the owner's yes adds it as an
owner-only Tier-2 operation that can be undone. A lender agreement is compared with the credit line in the books and can be
linked to it.

<!-- figure: screenshots/shot9-attach.png | Figure 11. Attach deals: the reading of supply agreement FHR-2026-07. (1) Each term with its clause number and the exact words quoted. (2) The clause lights up when its term is focused. (3) Markers show which terms each clause holds. -->

**4. Customers.** *Screens:* a customer's page (`/customers/BUYER-1`), Receivables, Cash & funding. *The owner* opens Foshan
Home Retail from its name on Home or Deals. *FLOW* shows what the customer is worth and what is outstanding, the financing
linked to its invoices, its share of what the business is owed, how it has paid, its deals and their records, and its
exposure: its concentration, and cash with Foshan paying 30 days late, which opens Cash & funding with that stress drawn.

**5. Deals and negotiation.** *Screens:* Deals (*Buyer messages*, *Your deals*, the deal page, *Your agreements*). *The owner*
opens Foshan's WeChat request (60-day terms, a 1.2% early-payment discount and a rebate) and chooses *Check against my
limits*. *FLOW* rejects it as asked, for four reasons: ¥28,326.92 of future concessions against a ¥5,000 cap, a reserve
breach from day 47, a discount above the 0.88% break-even, and a cost above its own plan. It offers Option A (early payment on
up to ¥260,000 at 0.85%, ¥3,035.99) and Option B (55 days with a 0.30% price rise). A buyer's claim of an earlier terms
agreement is answered as what it is ("No terms agreement is on record") and nothing is booked from it. *Cash impact* shows the
business consequences and *Before they ask*. The owner chooses *Review and send the counter*. In the Demo shell the simulated
buyer answers at once: *Open to a counter* agrees to Option A in round 1, and *Holds firm* ends in no deal within three rounds
with the gap still funded. In Business mode the owner copies FLOW's exact message, sends it, marks it as sent and records the
buyer's answer as the owner heard it; recording an acceptance books the agreement, and the funding plan is run separately
from Cash & funding. On the busy books, *Your deals* files six negotiations by who owes the next step, and a request FLOW has
no counter for is accepted as asked, or declined, by the owner's click. Once agreed, a deal moves to *Your agreements* with
its lifecycle strip and tracker.

**6. Money and approvals.** *Screens:* Cash & funding, Approvals, *Your limits*. *The owner* reviews the plan, the other
plans considered, the forecast at 30, 60 or 120 days and the funding in use, and runs the plan. *FLOW* runs the Tier-1 legs
at once and queues anything above the 15% approval threshold. On books with no committed source able to carry a permanent
need, Cash & funding still shows the plan and the menu and says there is no marginal source. On Approvals each card states
what it does, why it needs the owner and the stored quote; nothing runs until the owner approves, and there is no "approve
all". *Your limits* says in plain words what FLOW may do alone, what waits for the owner and what it will never do.

**7. Time passing.** *Screens:* Demo (operator tools: the clock), Home, Receivables, Approvals, Activity. *The owner* moves
the simulated clock. *FLOW* posts each day's scheduled flows, issues recurring invoices and lands funding. On day 2 Foshan pays
¥257,790.00 early, as agreed. On day 34 ¥160,000 is still unpaid and cash is heading under the reserve: Home and the worklist
flag the overdue invoice, Receivables offers a chase message to copy, and FLOW proposes a ¥200,000 advance costing ¥1,782.19.
At 32.5% a year it is above the threshold, so *Queue it for my approval* puts it on Approvals; the owner approves and the cash
lands on day 37. The late money arrives on day 36. A payment the owner hears of directly is entered with *Record a payment*
on Receivables, and a financed invoice repays its lender first. Activity's *Reconciliation* tab matches each receipt and each
promised early payment. FLOW then proposes repaying the drawn credit line, and it warns 7 days before an agreement expires and
14 days before the signed limits do.

<!-- figure: figures/screens/screen4-ask-answer.png | Figure 12. Ask FLOW, day 0 (web app on recorded mocks): "Are we safe?" The card leads with the answer, shows three key figures (¥405,000 funding needed, −¥105,000 lowest cash, below the reserve from day 12), says what FLOW's plan costs, and links to the forecast and the plan. The answer reads; it never acts. -->

**8. Ask FLOW.** *Screens:* the header's question field, the side panel, the full page (`/ask`), which holds the conversation
in one card. *The owner* opens the panel, and FLOW speaks first, naming what needs attention and what fixing it costs. "Are we
safe?" gets an answer card (Figure 12); 我们安全吗？ is answered in Chinese, "show me my cash" is answered from the books, and each
link opens the page that shows the answer. "Fund the cash gap" proposes a plan with its operations and cost; *Yes, run it*
runs exactly those, and a correction such as "make it 0.8%" amends a pending counter. "Can I pay everyone?" adds the ¥505,000
due in the next 30 days and answers no: cash falls below the reserve from day 12 and below zero from day 20. It offers FLOW's
¥3,113.93 plan and saves it, and "go ahead" runs it like the fund-the-gap plan. 账期从45天改成60天，我该接受吗？ prices the 60
days asked for, not the 45 they replace: ¥24,326.92 of forward concessions for Foshan, above the ¥5,000 limit, so FLOW would
counter. When the books do not point at one customer, FLOW asks which one, and the reply "Foshan" answers with the same terms.
FLOW also answers what happens if the biggest customer does not pay or a customer stops ordering, whether it can borrow
against the Foshan invoice, DSO, and what the audit log holds, naming each operation. A greeting or a thanks gets a short
reply, and "what will FLOW never do?" is answered from the tier rules: what FLOW does alone, what
waits for the owner and what it never does. A queued request is approved by
"approve APR-000001", or by "approve it" right after it was shown. "Sign a personal guarantee" is refused for everyone, asked
as a question too, and "add a ¥80,000 bill to the forecast" is refused because chat never records facts. *New conversation*
starts over.

**9. What-if and strategy.** *Screens:* the Sandbox, Cash & funding, a deal's *Cash impact*. From Foshan's request the owner
chooses *Try other terms*: at 45 days instead of 60 the verdict becomes a counter, and Option A's preset is accepted. Nothing
is written. Cash & funding says what ¥10,000 arriving 30 days earlier is worth. *Before they ask* shows how far each lever can
go for Foshan, and which packages pass every check, before the buyer asks.

<!-- figure: screenshots/shot6-capex.png | Figure 13. The Capex hub: (1) the financial health figures; (2) the demo vendor contract FLOW has read; (3) the owner reviews the reading first; (4) the workbench to test a machine without a contract. -->

**10. Capex.** *Screens:* Capex (Figure 13), the purchase workbench, *Financial health and loans*, *Long-term plans*. *The owner* tests a
¥600,000 machine with *Test a machine without a contract*. *FLOW* screens cash with the line, 18- and 36-month loans and a
48-month lease, and selects the lease (¥92,327.32 of charges). A figure that does not apply shows a dash. *Apply* queues a
Tier-2 application, and *Prepare the borrower file* builds a lender-style file that is never sent. *Read the demo vendor
contract* reads a supplier's contract; *Work out the payments* lays out its schedule and prices its early-payment discount;
*Commit, paying early* waits on Approvals. *Financial health and loans* shows coverage, ratios, covenant room and four
illustrative loans (*Add to my funding menu* queues a Tier-2 addition; the demo lender names appear in demo mode only), and
*Long-term plans* ranks projects and structures over 60 months.

**11. Records, evidence and security.** *Screens:* Activity, *Security and evidence* (`/trust`), the Demo story. *The owner*
reads every operation and security event in order, each operation sealed to the one before it. On the evidence view,
*Download JSONL* exports the record, and `python scripts/verify_evidence.py <file>` recomputes the chain with Python's
standard library and rejects an edited copy. On the security view, *Run the FastCapital scene* sends a hostile "pre-approved
lender" message: the flagged words are shown, nothing is booked, the sender gets FLOW's fixed reply and the harm scoreboard
stays at zero. The Demo story replays the negotiation, the late payment and the cure in six scenes, and the owner's approval
comes only from the owner's click.

#### Appendix F. Security controls and their evidence

Code under `services/api/`, lines at `571ea64f`; tests under `services/api/tests/`. Section 04 explains each control and its
limits.

| Control | Code | Tests |
| --- | --- | --- |
| Credentials, constant-time compare, body actor downgraded, demo mode off by default | `app/api/auth.py:25-80, 155-175`; `app/config.py:52-56`; `app/api/operations.py:82-85, 366-377` | `security/test_route_policy.py`, `security/test_demo_mode_default.py` |
| Rate limits and refusal budget (SEC-20, SEC-26) | `app/api/ratelimit.py` | `security/test_rate_limits.py`, `security/test_sec26_refusal_budget.py` |
| Tier computed from the operation; Tier 3 for everyone | `app/mandate/tiers.py:46, 73-77, 85-120` | `mandate/`, `nl/test_tier3_questions.py` |
| Hard rules and the approval threshold | `app/verifier/evaluate.py:190-193, 447, 562-573, 726-758`; `app/api/accept.py:97-107, 129-137`; `app/funding/admission.py:6-13`; `app/operations/executor.py:852-854` | `verifier/`, `funding/` |
| Signed mandate and pinned key | `app/mandate/signing.py:13-56`; `app/mandate/validity.py:9-70`; `app/api/runtime.py:284-293` | `mandate/`; catalogue class revoked mandate (7) |
| Exact-offer binding, nonce, expiry | `app/commitments/lifecycle.py:90-157`; `app/commitments/terms.py:21-30`; `executor.py:861-870, 963-1004` | catalogue classes replay (8), changed offer (4), expired commitment (3) |
| Stale-state checks | `executor.py:669-670, 703-717, 1077-1146`; `app/api/accept.py:296-318` | `operations/`, `security/test_mutations.py` |
| Approval, decide once, idempotency | `executor.py:360-416, 689, 757-796`; `app/persistence/guards.py:55-136`; migration 0009 | `operations/`, `persistence/` |
| Sent outside FLOW; owner-reported acceptance | `app/api/outbound.py:348-396, 455-513, 554-646`; `app/api/decisions.py:101-115` | `security/test_out1b_raw_operations.py` |
| Reading schema, quotes, no free text in the deciding modules | `app/compiler/schema.py:9, 29-30`; `app/compiler/grounding.py:97-162, 342-352`; `app/compiler/cross_check.py:81` | `verifier/test_invariants.py:20-62`, `compiler/test_injection.py`, `compiler/test_lexicon_evasion.py` |
| Chat consent, classifier closed list, buyer turns | `app/nl/consent.py:1-40, 159`; `app/nl/classifier.py:33-34`; `app/nl/service.py:173-174, 346-347` | `nl/`, `security/test_nl_attacks.py` |
| Question router (read-only tools, validation, no books in the prompt) | `app/nl/router/route.py:61-123, 425-434`; `app/nl/router/catalogue.py` | `nl/test_ask_router.py`, `certification/test_ask_router_boundary.py` |
| Outbound guard and counterparty entitlement | `app/outbound/message.py`; the egress guard | `egress/`, `security/test_round_six.py` |
| Redaction and provider calls | `app/compiler/redaction.py:4-12, 42, 73-80`; `app/compiler/backends.py:64-82`; `app/config.py:97-99` | `compiler/test_redaction_mandatory.py` |
| Hash-chained log and guards | `app/persistence/chain.py:4-36`; `app/persistence/guards.py:19-23, 55-188`; `scripts/verify_evidence.py` | `persistence/`, `security/test_evidence_verifier.py`, `concurrency/` |
| Partial plans (SEC-28) | `app/nl/plans.py:211-254`; `app/api/alerts.py:236-241`; `app/api/decide.py:358-375, 534-555` | `nl/`, `alerts/` |
| Attack harness and harm oracles | `app/security/attacks.py`; `evals/security/attacks.yaml` | `security/test_attacks.py`, `security/test_positive_controls.py`, `security/test_mutations.py` |
