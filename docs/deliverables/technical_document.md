# FLOW: Technical Document

2026 FINTECHATHON · SUBMISSION
International AI Track | Technical Document

| Team name | ISMOGGER |
| --- | --- |
| Competition track | International AI Track, Topic E: SME Finance Copilot |
| Submission date | 20 October 2026 |

**FLOW is an AI working-capital agent that works for a small supplier, not for its bank or its buyers.** When a large buyer
asks for better payment terms, FLOW reads the request, works out what it would cost the supplier in cash and borrowing, and
answers within limits the owner has signed. It counters, declines or accepts, arranges the funding the decision needs, and
then follows the deal through to payment. A language model reads text and nothing more. Deterministic code decides, and
only one component, the executor, can change the books. Every action is recorded in a tamper-evident log.

This is a working simulation. The engine, agent, security controls and web app are real code. The buyers, lenders and bank
feed are simulated, and no real money moves.

**Table 1. FLOW at a glance (offline. Engine, agent and test figures: `dev` at `975e082f`, 17 October 2026. Attack and
Ask FLOW figures: `int/batch-9` at `b4167053`, 18 October 2026. Table 14 gives each source).**

| What | Result |
| --- | --- |
| Decisions | Six verdicts (accept, counter, reject, no deal, needs the owner, no verdict), each with the failing rule, the figures and its formula |
| Engine correctness | Financial values exact to the fen against an independent oracle: 67/67. Covenant and capex values: 27/27 |
| Funding router | Optimal against an exhaustive brute force on 26/26 scenarios |
| Safety | 0 wrong autonomous accepts on two held-out sets (115 buyer messages) |
| Usefulness | Answers 57 of 115 held-out buyer messages with no owner involvement. Only 3 of the 14 genuinely acceptable offers are accepted on its own; the other 11 go to the owner for one review (section 03, Table 8) |
| Security | 261 stored attack cases (128 through the API, 133 through chat): 0 violations of the defined harm oracles in each specified run. Reviewed and certified by the team's Security Lead, an AI agent in a separate session (an internal review, not external accreditation) |
| Agent tasks | 49/49 scripted conversations completed, each with a verifiable evidence chain |
| Owner questions | Ask FLOW answers 303 of 503 owner, CEO and CFO questions (122 questions in English and Chinese, with rewordings) directly from the books, 46 partly, with 0 wrong answers. On 345 everyday wordings it reaches the right answer for 327 (held-out part: 127 of 142, 89.4%) and a wrong topic for 3 (0.9%). A question is answered, never acted on |
| Product | Setup, a daily view, documents, customers, deals, money over time, a chat, what-if and strategy views, capex and an evidence export: every screen in Table 3, and a supplier's journey through them in Appendix E |
| Tests | 9,085 API tests (9,040 passed, 1 known machine-specific hash failure, the rest skipped by design), 169 web unit tests, 445 mock and 139 live browser tests |
| Languages | Every Business screen and reply in English and Chinese. Chinese contracts are read with every term tied to its clause |

**How to read this document.** Section 01 explains the problem and what FLOW adds. Sections 02 and 03 explain how it works
and how well, including where it falls short. Section 04 covers security and section 05 covers running, testing and known
limits. Detailed inventories are in appendices at the end of section 05, and Appendix E is a tour of every feature in the
order a supplier meets them. Every number is synthetic, from the repository's
fixtures, and was measured on the build named in Table 1 unless a different date is given beside it.

## 01 Project Overview

### Problem, target users and selected topic

**Selected topic.** International AI Track, Topic E: SME Finance Copilot. The theme is "AI as a Financial Participant".

**The problem.** Large buyers now negotiate payment terms with software. Procurement agents ask suppliers for longer terms,
early-payment discounts and rebates "within parameters you define" (Pactum's public material describes this). Lenders
approve small-business credit by model in seconds (MYbank, WeBank). The supplier in the middle usually has neither. An owner
reads a WeChat message at night and decides alone whether to accept 60-day terms, and separately whether to borrow to
survive them.

**The insight that drives FLOW: a longer payment term is a loan from the supplier to the buyer.** It moves no money today,
so every spending limit, approval rule and wallet control lets it through. But the supplier must fund the gap, usually by
borrowing. On the synthetic demo company, whose largest buyer takes a ¥420,000 invoice every month:

- moving that buyer from 45 to 60 days ties up **¥210,000** of extra receivables, permanently;
- funding that on the cheapest committed source able to carry a permanent need (invoice financing at 10.84% all-in) costs
  **¥1,871.30 per invoice**, or **¥24,326.92 a year**;
- the same request also asks for a 1.2% early-payment discount (¥5,040) and a rebate of up to ¥4,000.

The owner sees "60 days instead of 45". FLOW shows that the package costs more than five times the owner's own limit for
such promises, and that it would push cash below the safety reserve on day 47.

**Target users.** Supplier SMEs with roughly 20 to 100 staff, 10 to 40 business buyers, one bank credit line, at least one
term loan, a bookkeeper and no finance team. Typical sectors are light-manufacturing subcontracting, packaging, logistics,
maintenance supplies and facility services. This profile is a composite drawn from our specification. In two interviews with
real SME owners, one assumed pain point (that the owner phones the bank when cash looks low) was contradicted, so we do not
claim it.

### Core value and innovation

**What FLOW does for the owner.**

1. **Reads the request.** It turns a buyer's message or contract, in Chinese or English, into typed terms. Each term is tied
   to the exact words it came from.
2. **Prices it in cash.** It projects the supplier's daily cash, debt and future promises with and without the request, and
   prices every concession at the supplier's own cost of borrowing.
3. **Decides within the owner's limits.** It returns a verdict with the reason and the formula, and drafts priced
   counter-offers that keep the business safe.
4. **Arranges the money.** It finds the cheapest admissible way to cover any cash gap from the owner's own committed
   facilities, and checks loan covenants every month.
5. **Follows through.** It watches for late or partial payment, warns the owner first, proposes a fix inside the limits with
   its cost, and closes the loop when the money lands.

**One engine, two jobs.** *Terms Guard* controls the credit the supplier gives its buyers through payment terms, discounts and
rebates. *Debt Desk* controls the credit the supplier takes from lenders to survive those terms. They share one financial
model, so each makes the other better. A concession is priced at the supplier's real marginal cost of debt. And because Debt
Desk knows the funding alternative, FLOW can walk away from a bad deal and still cover the gap.

**The demo story, end to end** (golden books, `scripts/demo_run.py`, 17 steps, re-run 17 Oct 2026):

1. Foshan Home Retail asks for 60-day terms, a 1.2% early-payment discount and a rebate. FLOW rejects the package as asked
   and offers two counters.
2. The buyer accepts **Option A**: early payment on up to ¥260,000 of its invoice at 0.85%. It pays **¥257,790.00 on day 2**.
3. **Day 34:** ¥160,000 is still unpaid and cash is heading under the reserve. FLOW speaks first and proposes a ¥200,000
   advance on the next invoice, costing ¥1,782.19.
4. That cure costs 32.5% a year, above the owner's 15% ceiling. So "go ahead" **queues it for approval and nothing runs**.
   Only the owner's explicit approval runs it, and the cash lands on day 37.
5. The late money arrives on day 36. The financed invoice is paid on day 47 and its advance is repaid from that receipt.
6. FLOW proposes repaying the credit-line draw, reconciliation closes the deal, and the record holds 14 hash-chained entries
   that verify.

<!-- figure: screenshots/shot2-deal-decision.png | Figure 1. A buyer's request in FLOW. (1) The verdict and why the request cannot be accepted as asked. (2) The priced choices: Option A, early payment on ¥260,000 at 0.85%, costs ¥3,035.99; Option B is 55-day terms with a 0.30% price rise. (3) Nothing is sent or agreed without the owner. -->

**What is new.** Each building block exists somewhere: negotiation agents, cash-flow forecasts, loan marketplaces and covenant
monitoring. What FLOW adds is the combination, on the supplier's side:

- **An agent the supplier owns, bounded by its own signed limits across both debt books:** what it may promise buyers, and
  what it may borrow to keep those promises.
- **A promise is treated as a liability before it costs anything.** A contingent concession counts at its maximum exposure,
  and an unapproved loan counts as zero, on a dated daily cash forecast. That forecast is a hard boundary for every decision,
  together with a cap on total concessions and the bank's covenants.
- **Autonomy only with proof (ADR-0005).** FLOW may accept a buyer's offer on its own only when it can show it has accounted
  for every figure and request in the message. Otherwise the owner decides.
- **One deterministic pipeline.** Reading, forecasting, funding, covenants, signed mandate, commitments and an
  injection-resistant typed interface are a single pipeline, not a set of independent tools.

**Table 2. Products in the same space (vendor descriptions; "difference" is our reading of public material).**

| Product | What it does | How FLOW differs |
| --- | --- | --- |
| Pactum | Buyer-side agents that negotiate payment days, discounts and rebates | FLOW sits on the other side of the table |
| MYbank 百灵 / AI票据管家 | Lender agents that tailor the bank's own credit and bill products | FLOW is supplier-owned and compares several sources, starting from the trade terms that cause the need |
| Xero JAX Cash Flow Actions | Ledger-side cash-gap detection and suggested plans | FLOW reads incoming offers and decides them inside a signed mandate and covenants |
| Cerebro Capital, Capitalise, Codat, Lendio | Lender marketplaces and debt-capacity tools for banks or mid-market firms | FLOW starts before the owner decides to borrow, at the request that creates the need |

#### What the owner sees

FLOW is one web app with eight pages on its menu (Home, Deals, Attach deals, Cash & funding, Sandbox, Capex, Receivables,
Activity), a chat on every page, and an account menu. Table 3 lists every screen. Appendix E follows one supplier through
them in order.

**Table 3. Every screen, what the owner does there and what FLOW does (the web app writes no figure; the server does).**

| Screen | The owner | FLOW |
| --- | --- | --- |
| **Set up your books** (`/setup`, six steps) | Enters the company, cash, monthly sales and costs; credit lines and loans being repaid; customers with repeating contracts and unpaid invoices; bills coming up; the limits (minimum cash, the rate FLOW may borrow at alone, concessions a year, the approval threshold, covenants, validity). Can fill a lender or customer step from an uploaded agreement. Re-types the owner token to sign | Checks each step, shows a 90-day "First look" at what Home will say, signs mandate version 1 and opens the books with one entry that starts a new evidence chain. Bills and limits are fixed after setup; changing them means a new setup and a new signature |
| **Home** (`/`) | Sees whether cash is safe and what waits | The cash outlook (lowest cash ahead, the forecast with its events, *What we recommend*: the plan, its cost and whether it needs approval); *Your worklist* (needs you, waiting, customers); cash available today with a funding ring; upcoming movements, including what customers owe late; what is owed, by customer |
| **Attach deals** (`/documents`) | Drops a contract or lender agreement, then picks who it is with from the list of known companies, or adds a new customer from that list | Reads every term beside its clause; checks that the contract names the chosen company; offers to refile a misfiled reading; after *Confirm*, says what was saved, under which customer, and that the forecast is unchanged. Compares a lender agreement with the facility in the books. From a confirmed customer contract, *Set up in my books* adds its repeating invoice (Tier 2, undoable; ADR-0014) |
| **A customer** (`/customers/{id}`) | Opens any customer by name | What the customer is worth, what is outstanding, the financing linked to it and its share of what the business is owed; the receivable-to-cash flow; its deals and record; how it has paid; concentration and exposure, with a link that redraws Cash with that customer 30 days late; an inputs sheet for facts the books do not hold |
| **Deals** (`/deals`) | Reads buyer messages, checks a request, sends or copies the reply, records the buyer's answer, accepts as asked or declines | *Buyer messages*; *Your deals*, filed by who owes the next step (all, needs you, waiting, agreed); the verdict with Options A and B; *Cash impact* with business consequences and *Before they ask*; *Your agreements*, grouped by payment late, awaiting payment and closed, with a row for a contract on file with no deal yet and for a customer with invoices only; each deal's lifecycle strip and tracker |
| **Cash & funding** (`/cash`) | Runs or queues the plan | The plan, other plans considered, the 30/60/120-day forecast, the funding in use, the price of earlier cash, and the forecast with one customer paying late |
| **Sandbox** (`/whatif`) | Moves the terms, discount, rebate, price rise and early-settled amount of a real request | The verdict, lowest cash, concession cost and covenants. Nothing is written |
| **Capex** (`/capex`, with `/buy`, `/finance`, `/plans`) | Tests a machine, works through a vendor contract, commits a purchase | Health figures, the financing structures screened, *Apply* (Tier 2), the borrower file, financial health, loan eligibility and long-term plans |
| **Receivables** (`/receivables`) | Records a payment; copies a chase message | What each invoice nets after financing; a payment's effect: the rest stays open, a financed invoice repays its lender first, and the reconciliation's reading |
| **Activity** (`/activity`) | Reads what happened | Every operation and security event, newest first, with filters that hide but never remove, the chain check, the evidence per entry, and a *Reconciliation* tab |
| **Approvals** (`/approvals`) | Approves or declines | One card per request, with its terms, the stored quote and today's price if it moved. No "approve all" |
| **Ask FLOW** (header, side panel, `/ask`) | Asks in English or Chinese | Speaks first; answers from the books as cards with links to the page that shows the answer; proposes plans that run only on "go ahead" |
| **Your limits** (`/limits`); **Security and evidence** (`/trust`) | Reads the signed limits in plain words; downloads the record | What FLOW may do alone, what waits and what never happens; the evidence export, verifiable offline; the security events and the FastCapital scene |
| **Demo** (`/demo`, Demo mode) | Plays the six-scene story; moves the clock; loads other books | The story on the demo company, operator tools and the engine views (mandate, cash line, funding, verdict, ledger, alerts, reconciliation, security) |

Every Business screen is in English and Chinese (the Demo's engine views are in English), and a tour (*Show me around*)
explains twelve pages, opening by itself on a first visit.

**What we claim, and what we do not.** Claims:
- No model output alone can create a commitment, borrow or move money in FLOW.
- Every verdict carries its failing rule, the figures, the formula and the source words.
- In the cases we tested, no misread message was accepted without the owner after ADR-0005.

We do not claim that FLOW is a lender, broker or adviser, that it complies with any bank's covenants, or that it reads
contracts or messages perfectly. It does not. Section 03 says by how much.

## 02 System Architecture

### Architecture diagram and component responsibilities

FLOW is a modular monolith: one FastAPI service (`services/api`), one Next.js web app (`apps/web`) and one database. Modules
talk only through typed contracts in `app/domain/`, and import cycles are forbidden.

<!-- figure: figures/fig1-architecture.png | Figure 2. FLOW in one picture. Untrusted text enters on the left, where the compiler is the only model-backed step. The deterministic core decides on typed obligations and never reads free text. Only the executor writes, and it records every outcome in a hash-chained log. -->

**Table 4. The four roles in the pipeline.**

| Role | Code | May | May not |
| --- | --- | --- | --- |
| **Compiler** (the only model-backed role, untrusted) | `compiler/` | Turn text into typed obligations, each tied to the exact source words. Flag authority claims, data requests and unknown lenders. Prove whether it accounted for everything | See the books, the mandate, the funding options or a buyer's limits. Emit an operation, a tier or a reply |
| **Verifier** | `financial/`, `covenants/`, `verifier/` | Project the cash trajectory, test the mandate and covenants, return a verdict with formulas and priced counters | Read free text (enforced by a test on its imports) |
| **Negotiator** | `verifier/counters.py`, `counterparties/`, `egress/` | Price counters from the marginal cost of funds, run bounded rounds with the buyer, fill outbound templates | Reveal the reserve, caps, funding options or limits |
| **Treasurer** | `funding/`, `operations/` | Find the cheapest admissible funding plan and execute typed operations through the permission gates | Rely on an uncommitted facility for a hard constraint; execute a Tier-3 action |

**One buyer request, end to end.**

1. **Read.** The compiler proposes typed obligations, each with its source span, or abstains. A conflict between a message
   and its attachment, or a stated discount that does not equal rate × amount, gives NO_VERDICT. A coverage proof then
   checks that every figure and request in the text is accounted for.
2. **Screen.** Unknown senders, funding claims, unevidenced "we agreed last month" claims and data requests are logged as
   security events. None of them can book anything.
3. **Project.** The engine projects a conservative daily trajectory of cash, debt and future promises with the request's
   obligations.
4. **Fund.** The router prices any gap from committed facilities and returns the marginal cost of funds. Future concessions
   are valued at that rate.
5. **Decide.** The verifier tests every day and every month against the mandate and covenants, applies the break-even and
   autonomy rules, and returns a verdict. A rejection or counter comes with counters priced below the marginal cost.
6. **Negotiate.** The buyer answers within a bounded number of rounds. NO DEAL is a normal outcome.
7. **Execute.** Code, never the model, turns the verdict into typed operations. The executor runs Tier 1, queues Tier 2 for
   the owner, refuses Tier 3, and appends every outcome of an admitted operation to the hash-chained log. A request refused
   before it reaches the executor is recorded as a security event instead.

<!-- figure: figures/fig2-offer-lifecycle.png | Figure 3. One buyer request from message to money. The figure marks which steps run on their own, which wait for the owner, and which are simulated in this build: the buyer's replies, the bank feed, the facilities and the clock. -->

**How agreement happens, and what is simulated.** A counter can reach the buyer in two ways. Both pass through the same gates
afterwards: nonce, terms hash, re-verification on today's books, and the hash-chained log.

- **Through the simulated buyer.** The owner reviews the exact counter, then sends it with the verdict and books version it
  was built on. A changed counter is refused (409). The buyer in this build is a deterministic simulation with a hidden
  reservation price.
- **Outside FLOW.** The owner sends the counter themselves, for example by WeChat, and marks it as sent. FLOW then waits for
  the owner to record the buyer's answer, bound to the exact message hash. FLOW transmits nothing itself, and after a counter
  is marked as sent outside, no other path can answer that request.

**Design decisions that matter.**
- **Exact money.** Money is integer fen and rates are integer basis points, rounded half-up once per posting (ADR-0002).
- **Lead times are respected.** Funding is requested on the decision day and lands after its lead time, so a hard constraint
  never relies on money that has not arrived (ADR-0003).
- **Autonomy needs positive proof** (ADR-0005).
- **The browser computes no money and no dates.** Every figure and sentence is written by the server in English and Chinese
  (INVARIANT 13).

The full component list is Appendix B.

### Models, tools, data sources and external services

**Where the model is used.** In exactly three places:
- **Compiling** buyer offers, term sheets and contracts into a strict JSON schema.
- **Optionally classifying** a chat request into one intent from a closed list, when the deterministic parser finds nothing.
- **Optionally routing** an owner's question that the deterministic answers miss to at most three tools from a closed menu of
  40 read-only tools (ADR-0015, live mode only). Code runs the tools and writes every word and figure of the answer
  (section 03).

The model never decides, prices, negotiates, answers or executes.

**Table 5. Model backends.**

| Backend | Model | Used for |
| --- | --- | --- |
| Cache (default) | Recorded outputs keyed by a hash of the documents and the prompt version | Tests, the demo, the scenario runner and the offline evaluation. No network. A message not in the cache goes to the rules grammar |
| DeepSeek (live, opt-in) | `deepseek-flash` alias through the OpenAI-compatible API. The underlying model version is not recorded | A backend reachable from mainland China. Used for the live accuracy runs in section 03 |
| Claude (live, opt-in) | `claude-sonnet-5-5`, with `claude-opus-5-5` for hard compilations | Alternative live backend |
| Rules grammar | Deterministic regular expressions and lexicon, Chinese and English | Always available. The fallback when a backend fails, times out or returns invalid JSON |

**What the model sees.**
- **The document and the output schema, and nothing else.** The mandate, facility limits, buyers' limits and other buyers'
  terms are never attached to a model request, and a test on the compiler's imports keeps it that way. A person can still
  paste such figures into a message.
- **For the question router, only the redacted question and the tool menu.** The prompt is built without any access to the
  books; a test captures what the provider receives and checks that it holds no figure, name or limit, and that it is
  byte-identical whatever the books hold.
- **Identifying data is redacted first, by every provider backend (PRIV-1 to 3).** Bank and card numbers, phone numbers,
  email addresses, unified social credit codes, ID and passport numbers, and labelled street addresses are replaced with
  stable placeholders before the text leaves the process. Amounts, dates, rates, party names and clauses are kept, because
  FLOW reads them.
- **Quotes are mapped back to the original** before grounding, so every term still points at the real words.
- **Logging.** Only a document hash and timings are logged per call, never the text.

**Why a model at all.** The rules grammar is precise but narrow. On our held-out set of Chinese contracts, it found the party
names in **0 of 17** text-layer contracts. DeepSeek found them in **14 of 17**, and the other 3 had the right names with buyer
and seller swapped. For example, the rules returned nothing for "甲方（承包人）：中山市华岳城建集团有限公司", while the model read
both parties correctly. Both paths feed the same grounding and the same verifier: a term whose quote is not found word for word
in the document is dropped, whichever backend proposed it.

**Three ways to run FLOW. They are never mixed in our results.**
1. **Web on recorded mocks.** The web app alone, no API. Useful for the interface only.
2. **Real engine, recorded readings.** The full API with the model's past readings replayed from the cache. This is the demo,
   the tests and every evaluation figure unless stated otherwise.
3. **Real engine, live model.** The full API calling DeepSeek or Claude. Opt-in, and needs a key.

**The agent's tools.** Every tool is an HTTP route with a strict schema that rejects unknown fields; 105 routes on this
build (`scripts/security_route_inventory.py`). They cover:
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
- **The demo company ("golden books").**
  - Cash ¥400,000, payroll ¥340,000 on day 12 and a supplier payment of ¥120,000 on day 20.
  - An existing loan payment of ¥45,000 every 30 days, and Receivable A of ¥420,000 due on day 32.
  - An owner-signed mandate with a ¥300,000 cash reserve and a ¥5,000 cap on future concessions. DSCR must be at least 1.25×,
    leverage at most 2.5×, and APR at most 15%.
- **Fixtures.**
  - 12 worked offers and three held-out sets of buyer messages.
  - Three demo contracts in Markdown, Word and PDF.
  - 70 synthetic Chinese contracts in four formats for the contract-reading evaluation, kept outside the repository.
  - Alternative books: busy, short of facilities, blank, and a set calibrated from a public filing.
- **The owner's own books.** On blank books, the setup wizard turns what the owner types (and the agreements it reads)
  into books of the same shape.
- **Test suites.** The 261-case attack catalogue, the 49 scripted agent tasks, the 503-turn owner-question bank and the
  345 everyday owner wordings.

**Table 6. The demo company's funding options (synthetic; only the owner can add to them).**

| Facility | Status | Price | Time to cash |
| --- | --- | --- | --- |
| Bank credit line, ¥150,000 limit, 30-day clean-down | Committed | 6.4% simple | same day |
| Invoice financing, ¥350,000 limit | Committed | 7.8% + 0.25% per 30 days (10.84% all-in) | 3 days |
| Buyer early-payment offer | Committed | 1.2% discount | 2 days |
| Bank acceptance-bill discounting | Committed (no bill held at the start) | 0.58% a year | 1 day |
| Government-guaranteed working-capital loan | Not applied | 5.0% all-in | 21 days |
| Equipment loan, 36 months / equipment lease, 48 months | Not applied | 5.6% / 7.2% | 14 / 10 days |
| Equity | Reference only (Tier 3) | n/a | n/a |

**External services.**
- **No real finance APIs.** No bank, lender, payment or blockchain API is called.
- **Model provider.** In live mode only, the configured provider (DeepSeek or Anthropic) receives the redacted inbound
  documents and the schema, and, with the router switched on, an owner's redacted question with the tool menu.
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
- **A question is answered, never acted on.** A question gate runs before every action rule. "Can we pay off our loans?"
  is answered from the books; it never proposes a repayment, compiles an offer, queues anything or writes to the log.
  Answers come from a read-only module of about 40 figures computed by the engine's own functions, so every number is the
  one the screens show, and each answer leads with the yes, the no or the figure.
- **Everyday wording.** After the literal patterns, a scored matcher reads casual, misspelt or worried wording in both
  languages ("can my company survive this month?", 我们撑得过这个季度吗) and answers only when one question clearly wins. A
  horizon longer than the 120-day forecast is answered on the forecast and says so. A question about the business that no
  rule reads still goes to the books, never to a flat refusal.
- **The question router (ADR-0015).** When the deterministic answers and the topic reads both miss, a model may choose up to
  three of 40 read-only tools and fill their typed slots; code answers. It sees only the redacted question, fenced as data,
  and the tool menu, never the books. Its output is validated strictly: a canary check, exact JSON with no extra or duplicate
  keys, known tools, every slot checked against its schema twice. One bad call rejects the whole response, and a rejection,
  timeout, provider error or cache miss falls back to the honest "I cannot answer that yet" with the nearest read. It runs
  for the owner only, behind `FEATURE_ASK_ROUTER`, and only in live mode: the flag is on in `pnpm demo`, but no routes are
  recorded, so offline it changes nothing. Logs keep a hash of the question, never its text. The ADR is still *proposed*
  and the Security Lead's review is pending.
- **Every id is checked against the registry.**
- **An unmatched request gets the nearest capability**, not a flat refusal.
- **The model classifier is consulted only when the parser finds nothing.** It may choose only from a closed list of intents.
  Approve, reject and buyer messages are not in that list.
- **Who is asking comes from authentication, never from the text.** A buyer's message is never parsed for intents. It is
  compiled and verified as an inbound offer and can execute nothing.

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
- **Clarification.** "Fund it" with two open gaps asks which one.
- **Correction.** "Make it 0.8%" amends the plan. "1%" is refused, because it is above the 0.88% break-even.

**Acting first.** After time moves or money lands, FLOW names what needs the owner and proposes a cure found on the current
books, priced as the executor will charge it. It then waits; the executor decides the permission tier. FLOW proposes no cure
when the mandate forbids new borrowing, and no repayment while a reserve breach is open.

**Ask FLOW, as the owner uses it.**
- **Where.** A field in the page header, a side panel on every page, and a full page (`/ask`) for the same conversation.
  Each page suggests questions it can answer. *New conversation* clears it here and on the server, so a later "go ahead"
  runs nothing.
- **FLOW speaks first.** When the panel or page opens on an empty conversation, FLOW names what needs the owner and its
  priced cure, laid out like an answer, in the owner's words and with no internal ids (the opener).
- **Answer cards.** An answer from the books leads with its sentence, shows up to three key figures, the rest of the reply,
  how FLOW worked it out, and up to three links to the page that shows it: the cash forecast, FLOW's plan, the funding, the
  covenant readings, who owes what, one customer, approvals, Deals, Capex, Activity or the limits. Links only open pages; a
  card never approves, sends or runs anything, and only the owner's own turns carry one. Every word and link is written on
  the server, and a browser test clicks each one.
- **Language.** The reply follows the question: a Chinese question is answered in Chinese, an English one in English,
  whatever the page's language.
- **Doing, not only answering.** A plan shows its exact operations and cost with *Yes, run it* and *Cancel*. "Approve
  APR-000002" approves that request; a bare "approve it" binds only to the request the conversation just showed. Chat
  never records a fact ("add a ¥80,000 bill" is refused), and an unmatched request gets the nearest thing FLOW can do.

**Tool use.** Handlers call module functions (compile, evaluate, plan, negotiate) and send typed operations to the executor.
Each operation carries an idempotency key built from the session, turn and step. No handler can skip the verifier or build an
operation from model output.

**State.**
- **Sessions.** A chat session holds only typed references: the last offer and verdict, a pending plan, a pending
  clarification. Since SEC-21, it continues only for the caller that opened it.
- **Books.** The store holds today's position. Commitments hold agreed changes not yet realised, and every projection runs on
  the two combined (ADR-0006).
- **Time.** Time is a simulated day that moves only through the clock. Each move posts scheduled flows, issues recurring
  invoices and expires lapsed commitments.
- **Settlement.**
  - Partial payments leave the residual open.
  - A receipt on a financed invoice repays the lender first, from that receipt only.
  - Reconciliation reports each promised early payment as awaited, received, lapsed or settled otherwise.
- **Commitments are re-checked.** A verdict is not standing authority. At acceptance and at approval, the executor checks again
  on the books of that moment and refuses a commitment that no longer holds (STALE_VERDICT).
- **The decision record** derives each deal's state from stored facts (ADR-0011).
- **Contract records** hold a document's reading with each term's quoted clause and the owner's hash-bound decision
  (ADR-0012). From a confirmed customer contract, the owner can set up that customer's repeating invoice in the books, so
  the forecast counts it (ADR-0014).

**From setup to settlement: what FLOW keeps track of.**
- **Opening the books.** The setup wizard's six steps (section 01, Table 3) are checked by the server and previewed as a
  90-day forecast before anything is written. *Sign and open my books* signs mandate version 1 and writes one opening entry
  that heads a fresh evidence chain; it is refused once the books hold any activity.
- **Documents.** The file comes first; the owner then picks the company from the books' list or adds a new customer from it
  (Tier 2). The party check blocks *Confirm* when the contract does not name the chosen company and shows the companies it
  does name; *refile* moves the reading to the right customer without a new model call. The confirmation card links to the
  customer, the facility or the purchase. A lender agreement is compared with the facility already in the books and can be
  linked to it, which changes nothing in the facility.
- **Customers.** Each customer's overview is computed from the books: gross contribution, outstanding, the financing linked
  to its invoices, its share of what the business is owed, its payment history, and its exposure: concentration, cash with
  it paying 30 days late, the financing cost then and the capacity left.
- **Deals.** One queue files every request by who owes the next step. Once the owner has a reply, FLOW drafts it exactly;
  the owner sends it through the simulated buyer (Demo mode) or by their own channel, then records the buyer's yes, no or
  reply. When FLOW has no counter, *accept as asked* or *decline* is itself the owner's decision. A confirmed contract with
  no deal yet, and a customer with open invoices only, also appear under *Your agreements*. Each deal shows a lifecycle
  strip (received, analysed, reply ready, sent, agreed) and, once agreed, a tracker of promised against actual (terms
  negotiated, early payment in, collecting, fulfilled).
- **Money over time.** The simulated clock posts scheduled flows, lands funding, issues recurring invoices and expires
  lapsed commitments; it never records a receipt. The owner records a payment on Receivables (the whole outstanding or part
  of it, with an optional bank reference) as a Tier-1 receipt, and FLOW says what reached cash, what repaid a lender first
  and what is still open. Alerts are recomputed on each day's books: an overdue invoice (critical when it is financed), a
  reserve breach ahead with its funding cure, repaying a drawn credit line once cash allows, an agreement expiring within
  7 days, and the signed limits expiring within 14 days. Reconciliation matches each receipt and reports each promised early
  payment as awaited, received, lapsed or settled otherwise.

### Core algorithms and evaluation approach

**1. Daily cash trajectory.** For each day of the horizon:

`closing(t) = opening(t) + inflows(t) − scheduled outflows(t) − interest, fees and repayments(t)`

- **Order within a day.** Inflows come first, then outflows, then financing costs. Closing cash is tested against the
  reserve. This is a closing-cash test; it does not model liquidity within a day.
- **What "conservative" means.**
  - Unconfirmed inflows are ignored.
  - Only committed facilities can be drawn; others count as zero.
  - A contingent concession counts at its maximum.
- **What it does not cover.** Recurring invoices are assumed to be paid on their due day, so the forecast is not conservative
  about collections. The stress tests below cover that.
- **Interest** is Actual/365 simple. Invoice financing bills whole 30-day periods.

<!-- figure: figures/fig4-golden-cash.png | Figure 4. The demo company's cash over 60 days. Without new funding, cash falls below the ¥300,000 reserve on day 12 and reaches −¥105,000 on day 30. FLOW's plan (credit line ¥150,000 plus invoice financing ¥255,000, total cost ¥3,113.93) keeps cash at or above the reserve every day. -->

**2. Funding router.** It finds the cheapest admissible combination of funding actions:
- **Search.** Up to three actions, amounts on a ¥10,000 grid, each requested today and landing after its lead time.
- **Admissible** means cash stays at or above the reserve every day, no covenant is broken, and new borrowing is allowed.
- **Over the rate ceiling.** A leg above the mandate's rate ceiling flags the plan for the owner.
- **Future invoices.** A plan that relies on an invoice not yet issued is flagged "cannot run today".
- **Minimum size.** No action is smaller than ¥1,000.
- **On the demo company**, the ¥405,000 gap before day 32 is covered by the credit line (¥150,000, interest ¥841.64) plus
  invoice financing (¥255,000, ¥2,272.29): **¥3,113.93**. Taking the buyer's 1.2% discount instead would cost ¥5,040.00.
- **Optimality.** The router is within ¥1 of an exhaustive brute force on all 26 evaluation scenarios.

**3. Marginal cost and break-even.**
- **Marginal cost of funds.** The all-in rate of the cheapest committed source that can carry a permanent need: invoice
  financing at 10.84%. The credit line's clean-down rules it out.
- **Break-even.** An early-payment discount d is cheaper than borrowing only if d < c/(1+c), where c is that source's cost for
  the days paid early. For 30 days that is **0.8832%**.
- **The early-payment rule (ADR-0007).** An early payment is accepted only if it passes three tests:
  - it is below break-even for its actual days early;
  - the cash is needed;
  - it is cheaper than the router's plan without it.

  So 0.75% on the whole ¥420,000 invoice costs ¥3,150.00, more than the ¥3,113.93 plan, and is countered. 0.74% costs
  ¥3,108.00 and is accepted.

**4. Covenants.** Each projected month is tested exactly, per facility definition:
- **DSCR** = EBITDA ÷ debt service. A bullet loan is serviced on a level basis (ADR-0008).
- **Leverage** = month-end debt ÷ annualised EBITDA.
- **Clean-down** = the longest run of zero-balance days on a credit line.

For example, a ¥500,000 government-guaranteed loan would bring DSCR to 1.01×, below the 1.25× covenant, and is refused.

**5. Verdict.** The verifier checks, in this order:
- whether the offer was read completely;
- the security screen;
- mandate validity;
- the projection;
- every rule: daily reserve, the total and per-buyer concession caps, the discount cap, the APR ceiling, the covenants and the
  Tier-3 clauses;
- the three early-payment tests;
- the autonomy rule.

Every failed rule carries its code, the day or month, the observed value, the limit, a formula and its inputs. The autonomy
rule (ADR-0005) keeps an ACCEPT at Tier 1 only for a pure early-payment discount on a named whole invoice that passes all
three tests **and** whose message passed the coverage proof. Anything else that would be accepted becomes "needs the owner".

**The worked example, reconciled.** Table 7 traces the demo's central request (EX01) through every figure the document and the
screens use. It answers a common question: why does the forecast say ¥90,040 while the deal page says "breached by ¥135k for
15 days"? Both readings are correct. The first is the shortfall on the **first** day below the reserve (day 47). The second is
the **worst** shortfall (day 60), and the breach lasts 15 days.

**Table 7. The EX01 request, every figure in one place (golden books, day 0, books version 1, reserve ¥300,000).**

| Scenario | Funding | Lowest cash | Breach | Discount | Funding cost | Future concessions | Can run today? | Who decides |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Today's books, no request | none | −¥105,000 (day 30) | ¥405,000 short, days 12–31 | — | — | ¥0 | — | — |
| Today's books + FLOW's standing plan | line ¥150,000 + invoice financing ¥255,000 | ¥300,000 | none | — | **¥3,113.93** | ¥0 | yes | Tier 1 |
| **EX01 as asked** (1.2% early pay, 60-day terms, rebate), no new funding | none | ¥164,960 (day 60) | first day 47, ¥90,040 short; worst day 60, **¥135,040** short; 15 days | ¥5,040.00 | — | **¥28,326.92** (terms ¥24,326.92 + rebate ¥4,000), against a ¥5,000 cap | — | **Rejected**: concession cap, reserve, above break-even, dearer than the plan |
| EX01 + its cheapest cure | invoice financing ¥135,040 on an invoice issued on day 32 | ¥300,000 | none | ¥5,040.00 | ¥2,406.67 | ¥28,326.92 | **no**: the invoice does not exist yet | — |
| EX01 + the plan that can run | credit line ¥135,040, repaid day 62 | ¥300,000 | none | ¥5,040.00 | ¥1,468.05 | ¥28,326.92 | yes | — |
| Early-payment test inside the verdict | with the early payment: ¥6,508.05; without it (same terms): ¥3,873.58 | — | — | — | — | — | — | the early payment is dearer, so countered |
| **Option A** (FLOW's counter) | credit line ¥147,210 | ¥300,000 (day 30) | none | ¥2,210.00 on ¥260,000 at 0.85% | ¥825.99; total **¥3,035.99** | ¥0 | yes | **Accept, Tier 1** |
| Option B (FLOW's counter) | — | ¥300,000 (day 30) | none | — | — | 55 days + 0.30% price rise ≈ ¥0 net over 12 months | — | needs the owner (terms lengthen) |

**6. Counters.**
- **Option A, early payment.**
  - **Rate:** the largest whole-5-basis-point rate below break-even, here 0.85%.
  - **Amount:** the cash needed, grossed up and rounded **up** to a whole ¥10,000, here ¥260,000. Rounding stops a buyer
    reading FLOW's exact gap from the counter (R-10).
  - **Cost:** ¥3,035.99, below the ¥3,113.93 standing plan. Tests show that it passes its own re-evaluation, stays within
    every mandate limit and binds to a commitment with the same terms hash.
- **Option B, terms.** Longer terms with the smallest price rise that covers the funding cost.
  - Every counter is re-evaluated as an offer on the same books, so FLOW offers 55 days, not 60. At 60 days, a later invoice
    would land after a loan payment with no committed cure.
  - Outbound text is filled from an approved template, and the outbound guard checks it.
- **Option A's saving over the standing plan is modest** (¥77.94). Its real value is that the supplier gets the cash it needs
  without the ¥28,326.92 of future promises the buyer asked for.

**7. Simulated buyer.** The buyer kernel works out its own surplus from a package: the discount, rebate and extra days, less
its cost of paying early and any price rise.
- It accepts when the surplus reaches its hidden reservation.
- Otherwise it counters one step toward that reservation.
- In its last round it refuses.

With a hard-line reservation, the demo ends in NO DEAL within three rounds, and the router still covers the gap for
¥3,113.93.

**8. Capex screening.** For an owner's planned machine purchase, FLOW screens each financing structure for daily liquidity and
monthly covenants:
- cash with the line;
- an 18-month loan;
- a 36-month loan;
- a 48-month lease.

It ranks the feasible structures by total financing charges. On the synthetic ¥600,000 machine it selects the lease
(¥92,327.32 of charges). The 36-month loan is cheaper (¥53,206.14) but leaves cash ¥3,144.62 below the reserve for three days.

The search tests **one structure at a time**. A 36-month loan plus a three-day bridge on the credit line (interest ¥1.65)
would have no breach and cost about **¥39,000 less** than the lease, but FLOW does not try that combination today. So the
selection is the best *standalone* structure, and combined structures are on our roadmap. Applying for financing is a separate
owner step that queues one Tier-2 application. The owner's approval records a simulated pending facility, which counts as zero
until a lender commits.

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
  rate, rebate) can go on its own on today's books and what stops it, packages that pass every check, and the lowest price that works at each
  length of terms. Each package is re-checked before anything is sent.

Both are on in `pnpm demo`. The envelope repeats the funding search on its first read (about 17 s on the demo books), so
the demo computes it once in the background after each reset or setup and the owner's first visit reads the cached answer
(the cache is keyed by the books, mandate, day and commitments). Two further views are built behind flags that the demo
leaves off: customer economics (sales and margin as context for deals) and a pilot journal (what the owner did against what
FLOW said).

**Evaluation approach.** We evaluate on three levels:
- **The engine against an independent oracle and a brute force.**
- **The compiler on messages its authors had not seen.**
- **The whole agent through scripted tasks and attacks.**

One offline command regenerates the engine and agent figures in about 8 minutes:
`uv run --project services/api python scripts/evaluate.py`. Table 14 in section 05 lists every headline figure with its
build, date and command.

**Is FLOW safe, and is it useful? The autonomy funnel.** "Zero unsafe accepts" alone could mean that FLOW sends everything to
the owner. Table 8 shows both sides: how often FLOW was right to act alone, and how often it bothered the owner unnecessarily.

**Table 8. Autonomy on two held-out sets of buyer messages (115 messages, rules path, 17 Oct 2026).**

| Step | Held-out 3 | Held-out 2 | Both |
| --- | --- | --- | --- |
| Buyer messages | 66 | 49 | 115 |
| Genuinely acceptable as asked today (pure early payment, cheaper than the plan) | 10 | 4 | **14** |
| … handled by FLOW alone, correctly | 1 | 2 | **3** |
| … sent to the owner unnecessarily | 9 | 2 | **11** |
| Not acceptable, and FLOW answered alone (counter or reject at Tier 1) | 29 | 25 | 54 |
| Not acceptable, and FLOW asked the owner (correctly) | 27 | 20 | 47 |
| **Wrong autonomous accepts** | **0** | **0** | **0** |
| Owner interactions needed | 36 | 22 | 58 (50%) |

**What Table 8 shows.**
- **FLOW is safe.** It never accepted a message it had misread.
- **Most answers need no owner.** It answers more than half of all messages on its own, mostly by countering or declining
  within the mandate.
- **Coverage of good offers is low: 3 of 14.** Ten of the 11 unnecessary escalations have one cause. The buyer named a
  settlement date ("tmrw", "国庆后", "next Mon") that FLOW does not yet read into the terms, so the coverage proof cannot
  account for it and sends the offer to the owner. Reading settlement dates is the next improvement. Until then, each such
  offer costs the owner one review, with the verdict and the source words shown.

**Table 9. Compiler accuracy on the held-out sets.**

| Set and run | Independence | Path | Verdict agreement | Material errors | Silent material errors | Wrong autonomous accepts |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out 3, first run (1 Oct, before ADR-0005) | unseen | rules | 33/63 (52%) | 4/51 | 7 | 4 of 8 accepts |
| Held-out 3, today (17 Oct) | its failure classes guided later fixes | rules | 44/63 (70%) | 3/51 (5.9%) | 4 | 0 |
| Held-out 3, after round 3 (1 Oct) | prompt not tuned on it; shared gates were | live DeepSeek | 42/63 (67%) | 3/51 | 5 | 0 |
| Held-out 2, today (17 Oct) | guided round 2 | rules | 38/47 (81%) | 0/37 | 0 | 0 |
| Form baseline (labels typed in, today) | — | no compiler | 56/63 (89%) | — | — | — |

**Reading Table 9.**
- **Only the first held-out-3 row is an untuned accuracy figure.** Its four wrong autonomous accepts led directly to ADR-0005.
- **The form baseline is the verifier's policy compared with the labeller's.** It is below 100% because the labels (written
  on 1 Oct) predate the early-payment rule, which now counters some offers the labels expected to be accepted. This also
  explains why today's figures are lower than earlier versions of this document.
- **Targets not met.** The material-error target (≤ 5%) and the zero-silent-error target are not met on held-out 3.
- **Silent errors never cause an autonomous accept.** Every silent error ended with the owner or in a rejection.

Appendix A gives the exact definitions of each metric.

<!-- figure: figures/fig5-heldout-results.png | Figure 5. Compiler results on the held-out sets, labelled unseen or tuned on. After ADR-0005 no misread message was accepted without the owner, while verdict agreement and material errors still miss our targets on held-out 3. -->

**Reading Chinese contracts.** We generated 70 synthetic Chinese contracts:
- government procurement, goods, services, construction subcontracts, equipment installation, processing, leases, logistics
  and supplementary agreements;
- in four formats: digital PDF, Word, scanned PDF and phone photo.

We fixed the reader against batch 1 (40 contracts), then tested it on batch 2 (30 new contracts with six contract types it had
never seen).

<!-- figure: figures/fig6-contract-reading.png | Figure 6. Reading Chinese contracts, by format. 98% field accuracy on the tuned batch, 75% on the held-out batch, and 86% after fixes made by studying that batch (so no longer held out). Scans and phone photos are refused: FLOW has no OCR. -->

- **The honest figure is 75% field accuracy on unseen contracts with a text layer** (215 of 285 fields; recorded DeepSeek
  readings replayed, 17 Oct). After five fixes found by studying those failures, it rose to 86%, but that figure is no longer
  held out.
  - The fixes were slash and dot dates, a code check of who pays whom, repeated terms, the payer's late interest, and end
    dates.
  - Wrong values fell from 31 to 21.
- **The tuned batch scores 98%** (502 of 514) and stayed unchanged through every fix.
- **Scans and photos are refused,** because FLOW has no OCR.
- **Every term must quote its clause word for word,** and FLOW checks that the company the owner picked is one the contract
  actually names. A contract that names other companies cannot be confirmed.

**Table 10. Other evaluation results (offline, 17 Oct 2026 unless noted).**

| Question | Result |
| --- | --- |
| Is the engine exact? | Financial values 67/67 and covenant and capex values 27/27 exact against the independent oracle; mandate and covenant boundaries exact at ±1 fen, basis point or day (20/20) |
| Is the router optimal? | Within ¥1 of the brute force on 26/26 scenarios; no committed plan relies on an uncommitted facility |
| Is the router worth it, against a fair baseline? | Against "credit line first" restricted to actions FLOW can actually run, on the 18 scenarios where both can be compared: cheaper in 3 (¥169.78 in total) and equal in 15. In 1 more scenario it finds a runnable plan where the baseline finds none. The router's value is mainly that it finds a safe plan, explains it, and says plainly when that plan cannot run today, not large savings |
| Can every plan run today? | Of the 26 router plans, 19 can run now, 6 depend on an action no operation can perform yet (a buyer's early payment or a bill) and are labelled "cannot run today", and 1 scenario has no admissible plan, which the router says |
| Does it walk away honestly? | A hard-line buyer ends in NO DEAL within 3 rounds and the gap is still funded; 7/7 checks |
| Does the agent complete tasks? | 49/49 scripted chat tasks (87 turns); every evidence chain verifies, and a tampered copy is rejected |
| Does it answer an owner's questions? | A bank of 122 owner, CEO and CFO questions in English and Chinese, with rewordings (503 asks): 303 answered directly from the books (60%), 46 partly, 0 wrong, 154 declined honestly, naming the nearest thing FLOW can show (288, 38, 0 and 177 before the everyday-wording matcher). All 30 priority questions are answered in every wording. No question executes or queues anything (`b4167053`, 18 Oct) |
| Does it understand everyday wording? | 345 owner phrasings (219 English, 126 Chinese), casual, formal, misspelt and worried, each labelled with the answer it should reach and written before the matcher. Right: 327 of 345 (94.8%; 137 before). Held out from tuning: 127 of 142 (89.4%; 57 before). Wrong topic: 3 (0.9%). No turn executed, queued or changed anything (`b4167053`, 18 Oct, offline: the router does not run here) |
| Is the router safe? | Its own accuracy is not measured: it runs only in live mode, and no live run is recorded. Its contract is tested with a scripted model: 24 kinds of malformed output rejected, the canary, timeouts and provider errors with no second paid call, injection attempts, a prompt that holds nothing from the books, and the 231-item language-boundary set with a hostile routing model. With the answer cards: 433 passed, 1 skipped (`b4167053`, 18 Oct) |
| How fast is it? | Router p50 81 ms, p95 238 ms. Chat turn p50 9 ms, p95 567 ms. Full Scene 1 (read, decide, negotiate, execute) p50 1.08 s. All in process, cache mode |
| Does language stay safe at the boundary? | 231 adversarial inputs through the real chat route: 0 wrong-and-material (recorded and scripted models, 3 Oct; not yet run against a live model) |

**Table 11. Stress tests on the demo company (read-only copies of the books).**

| Stress | Effect on cash | What FLOW does |
| --- | --- | --- |
| Foshan pays 10 days late | Same lowest point (day 30); 30 days below the reserve instead of 20 | Keeps the same funding longer (¥5,649.25) and **asks the owner**, because the advance's cost (16.7% a year) is now above the 15% ceiling |
| Foshan pays only half | 35 days below the reserve | Its cheapest cover needs a buyer early payment on a future invoice, so it is labelled **cannot run today** |
| EBITDA 20% lower | Cash unchanged | Covenants weaken but hold (DSCR 1.50× at worst, leverage 2.15×); the plan is unchanged |

## 04 Security Design

### Tiered permissions and confirmation for sensitive actions

**Who can act.** Credentials are compared in constant time, and every refused credential is logged as a security event (up
to 300 an hour).

**Table 12. Credentials and what each confers.**

| Credential | Confers |
| --- | --- |
| Owner token | Owner authority: read views, Tier-2 decisions, answering a buyer's request, revocation, adding facilities, purchases, the clock; demo reset and books setup only in demo mode |
| Agent key | The agent's tool channel: Tier 1 inside the mandate; Tier 2 is queued; every chat reply passes an allow-list view that shows only the amounts of its own operations, with no cash, limit or reserve figure (R-11) |
| Bank-feed key | Recording a receipt as the bank (Tier 1) |
| Buyer channel key | That a message comes from that registered buyer; 5 messages a simulated day, then refused |
| None | A message is compiled and verified as a proposal only and can never execute |

- **A field in a request body confers nothing.** For example, "requested_by: OWNER" is downgraded before parsing.
- **Demo mode is off unless set.** Without it, the demo credentials are rejected, the owner and agent routes fail closed until
  real secrets are set, and no demo data is seeded.
- **The web app ships no credential.** The owner signs in, and the token is kept only for that browser tab.

<!-- figure: figures/fig3-permission-tiers.png | Figure 7. Who may do what. Tier 1 runs on its own inside the signed mandate; Tier 2 waits for the owner; Tier 3 is refused for everyone, the owner included. Every operation passes the executor's gates in the order shown. -->

**The three tiers. The executor computes the tier itself, and a caller-supplied tier is rejected.**

- **Tier 1, autonomous inside the mandate.**
  - Accept a pure early-payment discount that passes the three tests and the coverage proof.
  - Counter or reject within the mandate.
  - Draw on, repay or finance from a committed facility below the rate ceiling.
  - Record a receipt from the bank feed or the owner.
- **Tier 2, owner approval.** Every other acceptance (rebates, terms changes, price changes), and anything with future
  concessions above **¥100,000 per commitment**. That limit is measured on the commitment's *future-concession value*, not on
  the invoice amount, so an early-payment discount (future value ¥0) never reaches it. Also Tier 2:
  - a facility application or addition;
  - setting up a confirmed contract's repeating invoice in the books (ADR-0014);
  - adding a customer to the books;
  - an equipment purchase;
  - a draw above the rate ceiling;
  - a receipt reported by anyone other than the bank or the owner.
- **Tier 3, never.** A personal guarantee, collateral, equity, changing the mandate, or any unknown operation type. Refused for
  every caller, the owner included.

**Confirmation.** A Tier-2 operation is stored as its exact canonical JSON. When the owner approves, the executor re-runs every
gate against the mandate then in force. An approval after a revocation is refused, and an approval given twice is refused
even if the database row is reset (SEC-08).

**Verification gates, in order.**
1. Idempotency key.
2. Dating.
3. Mandate signature, pinned key, expiry and version.
4. Tier 3.
5. Circuit breaker on repeated refusals. Only the owner can reset it, and the agent cannot trip it to take a decision away from
   the owner.
6. For acceptances: an unexpired commitment with a single-use nonce, a matching terms hash, and a verdict re-verified on
   today's books.
7. The Tier-2 queue.
8. Admission for draws and advances on today's books.

The owner cannot waive a hard rule by approving.

**The record.**
- **Every outcome of an operation admitted to the executor is appended to a hash-chained log,** refusals and duplicates
  included: `entry_hash = sha256(prev_hash + payload + result)`. Requests refused earlier are kept as security events.
- **The database itself refuses to edit or delete history** (migrations 0003 and 0009):
  - the log, nonces and security events are append-only;
  - approvals can be decided only once;
  - no session setting can switch the guard off.
- **Verification needs nothing from FLOW.** `scripts/verify_evidence.py` recomputes the chain with Python's standard library.
- **The chain is internally checkable only.** Its head is not anchored outside the system.

**Rollback.** History is never edited. A mistake is corrected by a logged compensating operation: repay a draw, settle an
advance, revoke a commitment, decline a queued request or revoke the mandate. A refused or pending operation changes nothing. Each operation is atomic; a plan of
several steps is not, so a plan refused part-way keeps its earlier steps and the owner is told which step it stopped at
(SEC-28).

### Protection against prompt injection, privilege escalation and privacy leakage

**Prompt injection: architecture first, detection second.**
- **Buyer text can only become typed obligations whose quotes must match the source exactly.** The schema has no field for an
  operation, an approval, a tier, a reply or a new facility.
- **The deciding modules never read free text.** The verifier, funding router, covenants, mandate and financial engine are
  covered by a test on their imports.
- **Claims are not facts.**
  - A claimed prior concession with no matching commitment is never booked.
  - A lender named in a message becomes a logged funding claim, never a facility.
  - A condition on a future business event makes a gain contingent, whatever the model says.
- **Detection is logged, but refusal does not depend on it.** The rules grammar flags override attempts, fake system lines,
  role-play, encoded, full-width, zero-width and homoglyph text, and authority claims, in both languages.
- **Misreading is treated as a security problem.** A message the compiler cannot fully account for cannot be accepted without
  the owner (ADR-0005).
- **Contracts are read the same way.**
  - Every term quotes its clause, and its figures are parsed by code from the quoted words.
  - A sentence addressed to the agent blocks confirmation and logs a security event.
  - Documents are read only for counterparties on the owner's registry, and the contract must actually name the chosen
    company.
  - Confirming a document never changes the books. After confirming, FLOW says what was saved, under which customer, and that
    the forecast is unchanged.
  - Only a separate owner step, "Set up in my books", can add a confirmed customer contract's repeating invoice
    (ADR-0014). It uses only terms quoted word for word and re-read by code, is bound to the document and the exact terms
    shown, is re-checked on today's books, is logged, and can be undone. The agent, buyers and the bank feed are refused.
- **Chat is inside the boundary.**
  - Pasted or quoted text never becomes an instruction or an approval.
  - A session continues only for the caller that opened it.
  - Once the owner has sent a counter outside FLOW, no chat path can accept, decline or send on that request.

**Privilege escalation.**
- **Tiers are enforced by code, never by prompts.** The executor trusts no caller-supplied tier, actor or approval.
- **All of these are refused and logged:**
  - self-approval;
  - a circuit reset by the agent;
  - forged or edited mandates;
  - reused or guessed nonces;
  - backdated operations.
- **Unknown fields are rejected.**
- **Rate limits apply to every caller (SEC-20).** A burst is refused with 429 and a retry time.
- **Every route is tested** (105 on this build) by a route-policy test that calls every method and route as every kind of
  caller, with demo mode on, off and unset.

**Privacy leakage.**
- **Outbound text** is filled from an approved template, never free model prose. A request for data gets one fixed reply.
- **An outbound guard blocks the whole message** if it contains a protected value: the reserve, a cap, a limit, the marginal
  rate, a buyer's terms or a planted canary. It recognises the usual forms: ¥, k, 万, Chinese and 大写 numerals, English
  number words, percentages and per-mille.
- **Every read view requires the owner token.**
- **Contract terms are protected values of their counterparty.** Another buyer cannot read them.
- **The web app sends a strict Content-Security-Policy** with a fresh nonce on each request (SEC-12).
- **The model receives redacted text only** (section 02). The question router's prompt is built without the books, and an
  answer card, which carries the owner's figures, is attached only to the owner's own turns; the agent's allow-list and the
  buyer's reply view never include it.

**Compliance, in brief.**
- **Live-mode data.** Only in live mode do a buyer's documents go, redacted, to the configured provider, and only for
  extraction. With the router on, an owner question FLOW cannot answer itself also goes, redacted and without the books; a
  deployer would need a data-processing agreement covering it and should tell the owner. Cache mode sends nothing.
- **Cross-border transfer.** Sending real documents outside mainland China would be a cross-border transfer under the PIPL. A
  deployer would need a legal basis and, where required, a security assessment or a standard contract. We do not claim
  compliance.
- **Labelled AI output.** Model readings are labelled "AI-generated, for reference" until the owner confirms them.
- **Not advice.** FLOW is decision support inside an owner-signed mandate, not a licensed lender, broker or adviser, and it
  makes no real payment.

<!-- figure: figures/fig7-security-results.png | Figure 8. The attack catalogue on this build: 261 stored cases through the API and chat, by class (the Security Self-Assessment certified 260; DOC-05, adding a customer without the owner token, was added since). None violated the defined harm oracles. Every case reached the path it targets; of the 128 API cases, 120 were stopped by the control they name and 8 by another control. -->

**Table 13. Attack results (261 stored cases: 128 through the API, 133 through chat; each in a fresh in-memory runtime, offline, with recorded or scripted model answers; `b4167053`, 18 Oct 2026).**

| Measure | Result |
| --- | --- |
| Harm-oracle violations, in each specified run | 0 of 261 |
| Unauthorised operations executed / money moved by attacks | 0 / ¥0.00 |
| Facilities added by non-owners; concessions booked from unproven claims | 0; 0 |
| Integrity failures (partial write, double execution, erased log) | 0 |
| Protected values disclosed in outbound text or readable without the owner token | 0 |
| Cases that reached the path they target | 261 of 261. A case that never reaches its path no longer counts as defended |
| API cases stopped by the control they name | 120 of 128. The other 8 were stopped by another control, with no harm (known gaps, SEC-34, each pinned by a test) |

This is a test result within a scope, not proof that no exploitable path exists. The catalogue drives part of the 105 routes;
a separate route-policy test calls every route as every kind of caller. No running deployment has had a penetration test.

**Assurance.** Every review was AI-assisted; none was external professional assurance.
- **A separate audit and five red-team rounds by AI subagents (1 to 3 Oct)** found 39 issues. All are fixed, each with a
  regression test.
- **An external red-team run (16 Oct)** ran 17 tests, including 100 live model calls. Its results are its own; they were not
  re-run, and its five observations were re-checked on the code.
- **The Security Lead (14 to 17 Oct)** is an AI agent in a separate session and worktree. It reproduced every finding, wrote each
  fix on its own branch with a regression test, re-ran its checks on each merged commit and certified it. It also wrote the
  security fixes it certified. "Certified" here is an internal release decision, not accreditation.
- **Verdicts (Security Self-Assessment v3).**
  - Local simulation on loopback: GO.
  - A demo over a network: NO-GO until a tested deployment profile exists; we demonstrate the local configuration.
  - Production with real customers, documents or money: NO-GO, because of the items in section 05.

The full register is in the Security Self-Assessment (v3). It certified 260 cases on its assessed build; one case was added
afterwards (DOC-05: a non-owner trying to add a customer, with its positive control), giving the 261 above. Live mode and
the question router (ADR-0015) are outside its assessed scope; the router's review by the Security Lead is pending.

## 05 Deployment and Testing

### Environment, deployment instructions, test cases and known limitations

**Environment.**
- **API:** Python 3.12 with uv; SQLite or in-memory locally; PostgreSQL in production.
- **Web:** Node 22 or newer with pnpm.
- **No network or API key is needed** for the default mode, which replays recorded model readings.

**Run it (Windows, macOS or Linux, from the repository root).**

```
cd apps/web && pnpm install && cd ../..    # once
pnpm demo                                  # API on :8000 and web on :3000; open the address it prints
```

The launcher starts the API with in-memory books, recorded model readings and the demo credentials, then starts the web app
against it. It prints "Ready. Open http://localhost:3000" when both are up. The owner sign-in is prefilled with the published
demo token. It switches on everything the demo shows: contracts and their set-up in the books (ADR-0014), customer exposure,
the buy side, and the strategy views, whose envelope it computes in the background after each reset or setup. The question
router's flag is on too, but the router acts only in live mode.

- `pnpm demo:mock` runs the web app alone on recorded data.
- `pnpm demo:keep` keeps the books in a local file, so uploads, confirmations and the day survive a restart; `pnpm demo:keep --fresh` starts over.
- `pnpm demo:blank` starts with empty books, to set up your own company in six steps.
- If a port is taken, the launcher says so and suggests another.

In the app, open **Demo**, choose **Golden story** and follow the six scenes. Or use the Business pages directly: Home, Deals,
Attach deals, Cash & funding, Sandbox, Capex, Receivables and Activity, with Ask FLOW on every page and Approvals, Your limits
and Security and evidence from the header and the account menu.

**Check the evidence without the UI.**

```
uv run --project services/api python scripts/judge_eval.py     # 2 to 4 min: 49 tasks, 261 attack cases, the demo walk, the chain check
uv run --project services/api python scripts/evaluate.py       # about 8 min: the full offline evaluation
```

**Production deployment, and why it is not ready.** `infra/docker-compose.yml` runs PostgreSQL, the API and the web app with
demo mode off. It refuses to start without real secrets. **It does not yet produce a working API** (SEC-06). Three things are
missing:
- the owner's public signing key is not passed in;
- nothing provisions the books and the signed mandate;
- the web image is built against localhost.

These are open production blockers. The supported way to run FLOW is the local launcher above.

**Test cases.** The full catalogue, with what each suite proves, is `docs/deliverables/TEST_CASES.md`.

**Table 14. Evidence for every headline figure (dev `975e082f`, 17 Oct 2026, cache mode, offline, unless noted).**

| Claim | Command | Result |
| --- | --- | --- |
| API tests | `uv run pytest` (services/api) | 9,085 collected; 9,040 passed; 1 known failure (#161, a hash that differs by machine); the rest skipped by design |
| Web tests | `pnpm typecheck`, `pnpm lint`, `pnpm test:unit` (apps/web) | clean; 169 passed |
| Browser tests | `pnpm exec playwright test` (mock and live projects) | mock 445 passed, 0 failed; live 139 passed, with 2 known write-conflict retry failures (#157) |
| Attacks | `uv run python -m app.security.attacks --report` (services/api, with `DEMO_MODE=1 DATABASE_URL=memory LLM_MODE=cache`; it runs both catalogues), on `b4167053`, 18 Oct | 261 cases (128 API, 133 chat), 0 harm-oracle violations; 261 of 261 reached their path; 120 of 128 API cases stopped by the control they name |
| Agent tasks | `scripts/run_scenarios.py --inproc` | 49/49; all evidence chains verify |
| Owner questions | `uv run python scripts/owner_questions_baseline.py` (services/api), on `b4167053`, 18 Oct; the same as `BASELINE.md` section 8 | 303 answered, 46 partly, 0 wrong, 154 declined of 503 |
| Everyday wording | `uv run python scripts/owner_questions_general.py --part all` (services/api), on `b4167053`, 18 Oct | 327/345 right, 3 wrong topic (0.9%); held-out 127/142 (89.4%); 0 critical turns |
| Router and answer cards | `uv run pytest tests/nl/test_ask_router.py tests/nl/test_router_tools.py tests/certification/test_ask_router_boundary.py tests/nl/test_answer_card.py tests/security/test_nl_attacks.py`, on `b4167053` | 433 passed, 1 skipped |
| Offline evaluation | `scripts/evaluate.py` (7 min 41 s, including the funding brute force) | every target met; figures in Tables 9 and 6 |
| Autonomy funnel | `scripts/analysis/autonomy_funnel.py fixtures/heldout3 fixtures/heldout2` | Table 8 |
| Contract reading | `scripts/eval_contracts.py` on the 70 synthetic contracts, recorded DeepSeek readings | 75% held-out, 86% after fixes, 98% tuned; measured in session, 17 Oct |
| Routes / migrations | `python -I scripts/security_route_inventory.py . out.json`; Alembic head | 105 routes on `b4167053` (100 on `975e082f`); migration 0009 |

**Table 15. Representative test cases.**

| Case | Input | Expected result | Checked by |
| --- | --- | --- | --- |
| The golden request | EX01: 60-day terms, 1.2% early payment, contingent rebate | Rejected with four reasons; Options A and B; the buyer accepts A and pays ¥257,790.00 on day 2 | Scripted task S01, evidence chain verified |
| Honest no deal | A hard-line buyer refuses every counter | NO DEAL within 3 rounds; the gap funded for ¥3,113.93; the reserve holds | Evaluation gate E5 (7/7) |
| Early-payment boundary | Whole-invoice early payment at 0.75%, then 0.74% | 0.75% (¥3,150.00) countered as dearer than the plan; 0.74% (¥3,108.00) accepted at Tier 1 | Verifier hand-calculation tests |
| Cure above the ceiling | Day 34: "go ahead" on a ¥200,000 advance at 32.5% a year | Queued for approval, nothing runs; it runs only on the owner's approval, and the cash lands on day 37 | `scripts/demo_run.py` |
| Consent | Negated, conditional, future-dated, foreign-currency or quoted instructions, in both languages | Nothing executes | 41 consent attacks |
| Injection in a contract | A clause addressed to the agent | Never read as a term; cannot be confirmed; a security event is logged | Contract-ingestion attacks |
| Wrong company | A contract naming two other companies, uploaded "with Foshan" | Cannot be confirmed; the companies it names are shown | Contract party tests |
| Tier 3 by the owner | The owner asks to sign a personal guarantee | Refused for every caller | Permission tests |
| Tampered evidence | One log entry edited | The verifier rejects the copy; untouched chains verify | Judge report |
| Two writers at once | Two processes act on the same books | Eight invariants hold; a serial replay gives identical books | Concurrency tests, SQLite and PostgreSQL 17 |
| A question about acting | "Can we pay off all our loans?", 我们能还清所有贷款吗？ | "No. Repaying all ¥1,500,000 today…", in the question's language; nothing proposed, queued or logged | Owner-question bank (503 turns), `tests/nl/test_ask_books.py` |
| Recording a payment | The owner records a payment, or part of one, on Receivables, including on a financed invoice | Tier 1; a financed invoice repays its lender first, the rest stays open; the same press twice is one payment | `e2e/record-payment.spec.ts`, `tests/api/test_owner_receipt.py` |
| Contract set-up out of bounds | "Set up in my books" from a contract naming another buyer, even force-confirmed; or queued by the agent key | Nothing is set up; only the owner can queue it (Tier 2), bound to the document and the terms shown | `tests/api/test_contract_terms.py` |

<!-- figure: screenshots/shot3-approval.png | Figure 9. The owner stays in control. On day 34 FLOW proposes a ¥200,000 advance; because it costs 32.5% a year, above the owner's 15% ceiling, it waits on the Approvals page and nothing has run. -->

**Known limitations.** Grouped by what they affect.

*Limits of the demo (by design):*
- **Everything outside FLOW is simulated.** Lenders, buyers, rates and the bank feed are simulated, and no real money moves.
- **Recorded readings only.** The demo replays recorded model readings. A new document gets the rules reading unless live mode
  is on.
- **The plain demo forgets on restart.** `pnpm demo` keeps the books in memory, so restarting it starts fresh. `pnpm demo:keep` keeps them in a local SQLite file instead.
- **The buyer side on the owner's own books.** On books opened through setup, the buyer channel and the simulated buyer cover
  the first two customers, and the *Buyer messages* card holds the demo company's messages only. The full story is recorded
  on the demo company.

*Product gaps (known, with the next step):*
- **Settlement dates.** Good early-payment offers that state a settlement date go to the owner, because the date is not yet
  read into the terms (Table 8). Reading settlement dates is next.
- **Capex.** The search compares standalone structures only. It misses a loan plus a short bridge, which on the demo would save
  about ¥39,000.
- **Contracts.** Contract reading is 75% on unseen text-layer contracts. Scans and photos are refused, since there is no OCR.
  Setting up a contract's invoices covers one repeating invoice per contract; a contract that differs from a repeating
  invoice already in the books is refused rather than replacing it, and rebates and milestones are shown, not set up.
- **Funding router.** Six of the 26 router plans rely on actions FLOW cannot run yet (asking a buyer to pay early, discounting a bill).
  They are labelled "cannot run today".
- **Extra requests.** These are found by cue words and figures. A request with neither could pass the coverage proof, but only
  for a pure early-payment discount below break-even.
- **Live models.** Live-model runs are fewer than recorded ones. The live DeepSeek accuracy figure is from 1 Oct, the
  language-boundary set has not yet been run against a live model, and the question router has no live accuracy run.
- **Owner questions.** 154 of the 503 bank turns are still declined (each names the nearest read), and 15 of the 345 everyday
  wordings miss their answer.

*Open defect (minor):*
- In chat, the approval card does not print the approval's id. The reply's own sentence names it ("This needs your approval
  before it runs (APR-000001)"), and a bare "approve it" binds to the request just shown.

*Production blockers (from the Security Self-Assessment):*
- **No runnable production configuration** (SEC-06).
- **One worker process only** until PostgreSQL is proven in CI (SEC-11).
- **Single-operator key custody** (R-2).
- **The hash-chain head is not anchored outside the system.**
- **No tested network deployment profile** (TLS proxy, per-client limits, changed credentials and signing key), so a
  network demo is NO-GO.
- **No owner route to revoke or renew the mandate** (R-14), an anonymous offer that can name a registered buyer (SEC-19),
  and a multi-step plan that can stop part-way (SEC-28).
- **Open security risks:** the Tier-1 reach of a compromised agent (R-3), the trusted in-process actor (R-5), and a buyer
  with its key probing the counter cap within its daily budget (R-10, low). The agent key's chat replies pass an allow-list
  view with only its own amounts (R-11).

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
- **Eligible for autonomy (Table 8):** the label is a pure early-payment accept, and the discount is cheaper than the standing
  plan under today's rules.

#### Appendix B. Components (services/api/app unless noted)

| Component | Responsibility |
| --- | --- |
| `compiler/` | Offers, term sheets and contracts into typed obligations or terms, each grounded in an exact quote; redaction; the coverage proof |
| `financial/`, `covenants/` | The daily cash, debt and future-concession trajectory in integer fen; DSCR, leverage and clean-down |
| `funding/` | The router: the cheapest admissible mix, marginal cost of funds, break-even, admission |
| `mandate/` | Ed25519 signing and verification, validity, tiers and mandate rules |
| `verifier/` | The verdict, reason codes, formulas and priced counters; reads no free text |
| `operations/`, `commitments/` | The executor (the only writer) and the commitment lifecycle with nonce, expiry and terms hash |
| `books/`, `clock/` | Today's books plus agreed changes; the simulated clock |
| `persistence/` | Tables, migrations 0001–0009, the hash-chained log and the database guards |
| `nl/` | The chat harness: intents, slots, consent grammar, sessions, plans; `nl/answers` (the read-only answers and their figures), `nl/router` (the question router's 40 read-only tools and its validation, ADR-0015) and the answer card |
| `setup/` | The setup wizard: checking the six steps, the preview and opening the books |
| `contracts/`, `ingest/`, `deals/`, `decisions/`, `outbound/` | Contract records and reading, the party check and contract set-up, the deal summary, the decision record and tracker, the message to the buyer |
| `counterparties/` | The simulated buyer and its profile fitted to the books in use |
| `capex/`, `health/`, `lending/`, `borrower_file/` | Capex screening, purchases and long-term plans; financial health; loan eligibility; the borrower file |
| `alerts/`, `whatif/`, `strategy/`, `pilot/` | Cash alerts and reconciliation; the sandbox; read-only strategy answers (exposure, price curve, envelope); the pilot journal (off in the demo) |
| `api/` | Routes, authentication, rate limits and every sentence shown, in English and Chinese |
| `apps/web` | The Next.js app: the setup wizard, the Business pages, the Demo story, Ask FLOW (panel and page); displays server-written values only |

#### Appendix C. The agent's tools (HTTP routes, owner token unless noted)

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
| Mandate | The owner's signed limits: cash reserve, concession caps, covenant thresholds, rate ceiling, Tier-2 limit |
| Reserve (floor) | The lowest closing cash the mandate allows on any day: ¥300,000 on the demo company |
| Golden books | The synthetic demo company, with expected values from an independent oracle |
| Marginal cost of funds | The all-in rate of the cheapest committed source able to carry a permanent need: 10.84% |
| Break-even discount | The largest early-payment discount cheaper than that source: 0.8832% for 30 days |
| Future concession | A promise that costs money later (longer terms, a rebate, a price change), valued at the marginal cost of funds |
| Coverage proof | The compiler's check that every figure and request in a message is accounted for (ADR-0005) |
| ADR-nnnn | An architecture decision record (`docs/adr/`) |
| SEC-nn, R-nn, PRIV-n | A security finding, risk or privacy item in the Security Self-Assessment |

#### Appendix E. Feature tour: the life of a supplier using FLOW

The tour follows one owner through FLOW in the order a business meets it. Stage 1 runs on blank books (`pnpm demo:blank`);
every other stage runs on the demo company (`pnpm demo`), whose figures are those of sections 01 and 03. Each stage names the
screens, what the owner does and what FLOW does. Buttons and links are in italics.

**Video timestamps.** The lead fills these in after the final recording. They are kept together here, as one list.

1. Setting up the books: [VIDEO: mm:ss]
2. The daily view: [VIDEO: mm:ss]
3. Documents: [VIDEO: mm:ss]
4. Customers: [VIDEO: mm:ss]
5. Deals and negotiation: [VIDEO: mm:ss]
6. Money and approvals: [VIDEO: mm:ss]
7. Time passing: invoices, receipts, a late payment, the cure, reconciliation: [VIDEO: mm:ss]
8. Ask FLOW: [VIDEO: mm:ss]
9. What-if and strategy: [VIDEO: mm:ss]
10. Capex: [VIDEO: mm:ss]
11. Records, evidence and security: [VIDEO: mm:ss]

**1. Setting up the books.** *Screens:* the landing page, *Set up your books* (`/setup`), Home. *The owner* chooses *Join FLOW
now!* and works through six steps: the business and its cash; credit lines and loans (*Fill from an agreement* reads a lender
agreement); customers, their repeating contracts and unpaid invoices (*Fill from a contract*); bills coming up (quick-add
payroll, rent, supplier payments, tax); and the limits FLOW will work within. On the review step the owner sees the "First
look" at what Home will say and chooses *Sign and open my books*, re-typing the owner token. *FLOW* checks every step on the
server, signs the limits as mandate version 1 and opens the books with one logged entry that starts the evidence chain. Home
then answers from the owner's own figures.

<!-- figure: screenshots/shot1-home.png | Figure 10. Home on the demo company, day 0: without new funding cash falls to −¥105,000 within 30 days; FLOW recommends securing ¥405,000 before payroll in 12 days, for ¥3,113.93, with no approval needed. -->

**2. The daily view.** *Screens:* Home, the header, the account menu. *The owner* reads Home from the top: the cash outlook
says the reserve is breached in 12 days, and *What we recommend* covers it for ¥3,113.93 (the credit line ¥150,000 plus
invoice financing ¥255,000) inside the signed limits. Below are *Your worklist*, cash available today with the funding ring,
upcoming movements and what each customer owes. *FLOW* writes every figure and sentence on the server, in English or Chinese
(the account menu switches language), and counts what waits for the owner on the menu's badges. *Show me around* replays the
tour of any page, and the header switches between the Business app and the Demo shell.

**3. Documents.** *Screens:* Attach deals, the document review, Deals. *The owner* drops the Foshan supply agreement, then
picks Foshan Home Retail from the list of known companies (or *Add a new customer*). *FLOW* reads it into 18 terms, each beside
its quoted clause, and "This deal at a glance" shows the money terms against the forecast. After *Confirm*, the card says what
was saved, under which customer, and that the forecast has not changed. Filed under the wrong customer, the same contract
cannot be confirmed: FLOW lists the companies it names and offers *File it under Foshan Home Retail Co.* without a new
reading. Dongguan's contract reads as one invoice of ¥180,000 every 30 days on 45-day terms; *Set up in my books* shows each
figure beside its clause and the forecast before and after, and the owner's yes adds it as an owner-only Tier-2 operation that
can be undone. A lender agreement is compared with the credit line in the books and can be linked to it.

<!-- figure: screenshots/shot9-attach.png | Figure 11. Attach deals: the reading of supply agreement FHR-2026-07. (1) Each term with its clause number and the exact words quoted. (2) The clause lights up when its term is focused. (3) Markers show which terms each clause holds. -->

**4. Customers.** *Screens:* a customer's page (`/customers/BUYER-1`), Receivables, Cash & funding. *The owner* opens Foshan
Home Retail from its name on Home or Deals. *FLOW* shows what the customer is worth and what is outstanding, the financing
linked to its invoices, its share of what the business is owed, how it has paid, its deals and their records, and its
exposure: its concentration, and cash with Foshan paying 30 days late, which opens Cash & funding with that stress drawn.

**5. Deals and negotiation.** *Screens:* Deals (*Buyer messages*, *Your deals*, the deal page, *Your agreements*). *The owner*
opens Foshan's WeChat request (60-day terms, a 1.2% early-payment discount and a rebate) and chooses *Check against my
limits*. *FLOW* rejects it as asked, for four reasons: ¥28,326.92 of future concessions against a ¥5,000 cap, a reserve
breach from day 47, a discount above the 0.88% break-even, and a cost above its own plan. It offers Option A (early payment on
up to ¥260,000 at 0.85%, ¥3,035.99) and Option B (55 days with a 0.30% price rise). *Cash impact* shows the business
consequences and *Before they ask*. The owner chooses *Review and send the counter*. In the Demo shell the simulated buyer
answers at once: *Open to a counter* agrees to Option A in round 1, and *Holds firm* ends in no deal within three rounds with
the gap still funded. In Business mode the owner copies FLOW's exact message, sends it, marks it as sent and records the
buyer's answer. On the busy books, *Your deals* files six negotiations by who owes the next step, and a request FLOW has no
counter for is accepted as asked, or declined, by the owner's click. Once agreed, a deal moves to *Your agreements* with its
lifecycle strip and tracker.

**6. Money and approvals.** *Screens:* Cash & funding, Approvals, *Your limits*. *The owner* reviews the plan, the other
plans considered, the forecast at 30, 60 or 120 days and the funding in use, and runs the plan. *FLOW* runs the Tier-1 legs
at once and queues anything above the owner's 15% rate ceiling. On Approvals each card states what it does, why it needs the
owner and the stored quote; nothing runs until the owner approves, and there is no "approve all". *Your limits* says in plain
words what FLOW may do alone, what waits for the owner and what it will never do.

**7. Time passing.** *Screens:* Demo (operator tools: the clock), Home, Receivables, Approvals, Activity. *The owner* moves
the simulated clock. *FLOW* posts each day's scheduled flows, issues recurring invoices and lands funding. On day 2 Foshan pays
¥257,790.00 early, as agreed. On day 34 ¥160,000 is still unpaid and cash is heading under the reserve: Home and the worklist
flag the overdue invoice, Receivables offers a chase message to copy, and FLOW proposes a ¥200,000 advance costing ¥1,782.19.
At 32.5% a year it is above the ceiling, so *Queue it for my approval* puts it on Approvals; the owner approves and the cash
lands on day 37. The late money arrives on day 36. A payment the owner hears of directly is entered with *Record a payment*
on Receivables, and a financed invoice repays its lender first. Activity's *Reconciliation* tab matches each receipt and each
promised early payment. FLOW then proposes repaying the drawn credit line, and it warns 7 days before an agreement expires and
14 days before the signed limits do.

<!-- figure: screenshots/shot10-ask-answer.png | Figure 12. Ask FLOW, day 0: "Are we safe?" The card leads with the answer, shows three key figures (¥405,000 funding needed, −¥105,000 lowest cash, below the reserve from day 12), says what FLOW's plan costs, and links to the forecast and the plan. -->

**8. Ask FLOW.** *Screens:* the header's question field, the side panel, the full page (`/ask`). *The owner* opens the panel,
and FLOW speaks first, naming what needs attention and what fixing it costs. The owner asks "Are we safe?" and gets an answer
card (Figure 12); 我们安全吗？ is answered in Chinese, and each link opens the page that shows the answer. "Fund the cash gap"
proposes a plan with its operations and cost; *Yes, run it* runs exactly those, and a correction such as "make it 0.8%"
amends a pending counter. A queued request is approved by "approve APR-000001", or by "approve it" right after it was shown.
"Sign a personal guarantee" is refused for everyone, and "add a ¥80,000 bill to the forecast" is refused because chat never
records facts. *New conversation* starts over.

**9. What-if and strategy.** *Screens:* the Sandbox, Cash & funding, a deal's *Cash impact*. From Foshan's request the owner
chooses *Try other terms*: at 45 days instead of 60 the verdict becomes a counter, and Option A's preset is accepted. Nothing
is written. Cash & funding says what ¥10,000 arriving 30 days earlier is worth. *Before they ask* shows how far each lever can
go for Foshan, and which packages pass every check, before the buyer asks.

<!-- figure: screenshots/shot6-capex.png | Figure 13. The Capex hub: (1) the financial health figures; (2) the demo vendor contract FLOW has read; (3) the owner reviews the reading first; (4) the workbench to test a machine without a contract. -->

**10. Capex.** *Screens:* Capex, the purchase workbench, *Financial health and loans*, *Long-term plans*. *The owner* tests a
¥600,000 machine with *Test a machine without a contract*. *FLOW* screens cash with the line, 18- and 36-month loans and a
48-month lease, and selects the lease (¥92,327.32 of charges). *Apply* queues a Tier-2 application, and *Prepare the borrower
file* builds a lender-style file that is never sent. *Read the demo vendor contract* reads a supplier's contract; *Work out
the payments* lays out its schedule and prices its early-payment discount; *Commit, paying early* waits on Approvals.
*Financial health and loans* shows coverage, ratios, covenant room and four illustrative loans (*Add to my funding menu*
queues a Tier-2 addition), and *Long-term plans* ranks projects and structures over 60 months.

**11. Records, evidence and security.** *Screens:* Activity, *Security and evidence* (`/trust`), the Demo story. *The owner*
reads every operation and security event in order, each sealed to the one before it. On the evidence view, *Download JSONL*
exports the record, and `python scripts/verify_evidence.py <file>` recomputes the chain with Python's standard library and
rejects an edited copy. On the security view, *Run the FastCapital scene* sends a hostile "pre-approved lender" message: the
flagged words are shown, nothing is booked, the sender gets FLOW's fixed reply and the harm scoreboard stays at zero. The Demo
story replays the negotiation, the late payment and the cure in six scenes, and the owner's approval comes only from the
owner's click.
