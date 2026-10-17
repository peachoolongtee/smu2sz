# Ask FLOW owner-question baseline (17 Oct 2026)

**Scope.** This measures how well `POST /nl` answers the questions an owner, CEO or CFO of a 20-100 person supplier asks,
using only the data FLOW already holds.

**Method.**
- The question bank is `questions.yaml`: 122 questions in 10 categories. Each has an English and a Chinese wording plus 1-2
  paraphrases per language, so 503 turns in all.
- The harness is `services/api/scripts/owner_questions_baseline.py`. Every turn is a fresh session, sent as the owner on the
  golden demo books at day 0 (`golden_sme`, `Runtime.reset()`).
- Runtime settings: TestClient in-process, `LLM_MODE=cache`, `DEMO_MODE=1`, `DATABASE_URL=memory` and
  `TERMSLEDGER_NO_DOTENV=1`. Outbound sockets are refused except loopback. Feature flags are at their defaults.
- The primary run is `POST /nl?mode=business`, the wording the Business pages send. A second run with `--mode demo` gives
  the same totals within 2 turns.
- No product code was changed.
- Measured on dev `975e082f`, then re-run after merging dev `29fa0ea2`. All 503 replies and scores were identical.

```
cd services/api
uv run python scripts/owner_questions_baseline.py --out results.json            # business wording (default)
uv run python scripts/owner_questions_baseline.py --mode demo                   # default wording
```

**How to read the results.** 325 of the 503 turns (65%) found no rule and fell back to OUT_OF_SCOPE. In those turns the cached
classifier has no recording, so this baseline measures the offline rules path, which is what CI and the demo use. A live
classifier would route more of these turns, but every handler it routes to is the same, so the PARTIAL and WRONG findings still
hold.

## 0. Safety: no question executed anything

**No question executed or queued an operation, and none changed the books.** The harness compared the store's operations log,
approvals queue, commitments, state version and mandate version before and after every turn, and checked each response for
`EXECUTED` or `PENDING_APPROVAL` operations. Nothing was found in either run.

The one finding near the line comes from Tier-3 wording. Seven questions that only mention a Tier-3 subject append a REFUSED
operation to the hash-chained log, and each also adds a security event. Nothing runs, but the owner's question is written into
the permanent audit record as a refused request to change the mandate, sign a guarantee, pledge collateral or issue equity.
The parse happens in `app/nl/rules.py` (`lx.TIER3`), which `slots_from` checks before any question cue.

| Question | Logged as |
|---|---|
| "Did anyone try to change our limits?" / "有人试图修改我们的限额吗？" | `CHANGE_MANDATE` REFUSED |
| "Is equity an option?" | `ISSUE_EQUITY` REFUSED |
| "Can FLOW sign a personal guarantee for me?" / "FLOW能替我签个人担保吗？" | `SIGN_PERSONAL_GUARANTEE` REFUSED |
| "Could you pledge our equipment as collateral?" / "你能把设备拿去抵押吗？" | `PLEDGE_COLLATERAL` REFUSED |

Treat these differently:
- The last two rows are acceptable: asking whether FLOW can sign a guarantee is close enough to asking it to.
- "Did anyone try to change our limits?" and "Is equity an option?" are questions, not requests. They should be answered from
  the audit log (0 security events) and the funding menu (equity is reference only), not logged as refusals.

Other side effects that execute nothing:
- 15 turns proposed a plan that waits for "go ahead". These were FUND_GAP plans and ACCELERATE or NEGOTIATE proposals, such as
  "How big is the cash gap?" and "Is the early-pay discount worth it?".
- 18 turns stored a verdict, because EVALUATE_OFFER and WHAT_IF compile the reported terms.
- No LLM call was recorded.

## 1. Data inventory: what the books hold

Paths are under `services/api/app/`. Money is integer fen, rates are basis points, and days are offsets from day 0.

### The state model: `FinancialState` (`domain/models.py:645`)

**Cash and EBITDA**
- `cash_fen`: one total, with no per-account split.
- `monthly_ebitda_fen`: one scalar. There is no P&L.

**`flows: CashFlow[]` (:518)**
- Scheduled outflows and inflows, each with `day`, `amount_fen` and `kind`.
- `kind` is PAYROLL, SUPPLIER, OPERATING, DEBT_SERVICE, CAPEX or OTHER.
- A payroll flow is a total only. There is no staff or per-person data.

**`receivables: Receivable[]` (:528)**
- Fields: buyer, `face_fen`, `issue_day`, `terms_days`, status, `settled_fen`, `advance_fen`, `advance_facility_id`.
- `due_day` = issue + terms (:556). It is the only expected-pay day; no payment history is held.

**`recurring_invoices: RecurringInvoice[]` (:560)**
- Fields: buyer, face, `every_days`, `next_issue_day`, terms.
- Projected receivables get ids `RI:<buyer>:<issue_day>`.

**`facilities: Facility[]` (:256)**
- Fields: limit, drawn, `rate_bp`, `advance_rate_bp`, fees, lead time, term, repayment, status and covenants.
- Status is COMMITTED, PENDING, NOT_APPLIED or REFERENCE_ONLY. Only COMMITTED counts for hard constraints.

**`debts: DebtPosition[]` (:570)**
- Existing term loans: principal, monthly service, rate, next payment.
- `facility_id` is null for the demo loan, so no lender is recorded. That gap blocks "debt by lender".

**Other lists**
- `lots: FundingLot[]` (:629): draws and advances in transit or outstanding (ADR-0010).
- `expected_orders` (:611): per customer, firm or not. Nothing is held per product.
- `forward_concessions` (:583) and `invoice_adjustments` (:593).
- `counterparties` (:622): id, name, role.

**Covenant definitions**: `Covenant` (:244) per facility, with kind DSCR_MIN, LEVERAGE_MAX or CLEAN_DOWN.

### Other stores and modules

**Mandate** (`Mandate` models.py:481; `mandate/`)
- Limits: reserve (`min_cash_fen`), forward-concession cap, immediate-discount cap, DSCR, leverage, APR cap, clean-down,
  `allow_new_borrowing`, Tier-2 single-commitment threshold and horizon.
- Validity: issue and expiry days, revocation and an Ed25519 signature.
- Functions: `tiers.tier_for`, `validity.check_validity`.

**Contract records** (`ContractRecord` :426; `contracts/records.py`, `contracts/derive.py:87 buyer_terms`)
- Buyer, lender or capex contracts.
- Each term is a `ContractTerm` that quotes its clause.
- Status is PROPOSED, CONFIRMED or REJECTED. A contract is displayed, never booked.

**Commitments** (`Commitment` :922; `commitments/lifecycle.py`): an accepted offer's obligations, with nonce, expiry and
terms hash.

**Decisions** (ADR-0011; `decisions/facts.py`, `decisions/state.py:692 derive`, `:792 waiting_for`)
- Stored facts: Evaluated, Sent, Quoted, Offered, BuyerAccepted, Replied, BuyerDeclined, OfferWithdrawn.
- Derived: deal state, funding state and what each decision is waiting for.

**Approvals queue**: `ApprovalRecord` (`persistence/records.py:49`), with PENDING, APPROVED or REJECTED; read through
`store.approvals(status)`.

**Hash-chained operations log**
- Entries: `LedgerEntry` (`persistence/records.py:11`), via `store.operations()` and `verify_chain()`.
- The executor is `operations/executor.py:308`. Security events are in `store.security_events()`.

**Alerts and reconciliation** (`alerts/engine.py alerts`, `alerts/reconcile.py reconcile`)
- Ten alert kinds, including reserve breach, headroom, covenant headroom, clean-down, mandate expiring, receivable past due
  and funding in transit.
- Reconciliation reports receipts matched or flagged, promised early payments, outstanding receivables and chain validity.

**Trajectory** (`financial/trajectory.py:984 project`, `financial/debts.py:54 debt_payments`)
- 121 day points, each with closing cash, debt, forward concessions and events.
- Month points: EBITDA, debt service, total debt, DSCR and leverage.
- Totals: min cash and its day, first breach, and posted interest, fees and discounts.

**Funding router** (`funding/router.py:294 plan`, `:331 compare`; `funding/menu.py:99 menu_view`; `funding/rates.py:203 marginal_cost`, `:232 break_even_discount`)
- The cheapest admissible mix for the projected gap, with alternatives priced.

**Covenants** (`covenants/ratios.py`: `ratios_for`, `worst_dscr`, `worst_leverage`, `pro_forma`)

**Capex** (`capex/`: `evaluate_capex` on `CapexRequest` defaults, which is the ¥600k line)
- Gives NPV, payback, structures that pass or fail with reasons, and the selected structure.

**Buy side, health and lending** (ADR-0013: `deals/purchases.py`, `health/__init__.py:410`, `lending/__init__.py:290`)
- All behind `FEATURE_CAPEX_CONTRACTS`, which is **off by default**, so `/purchases`, `/finance/health` and
  `/lending/eligibility` return 403 here.
- Also default off: `exposure`, `collections_worth`, `customer_economics`, `envelope` and `price_curve`, which hold per-buyer
  economics.

**Other modules**
- What-if: `whatif/simulate.py:279`. It changes buyer terms only and never writes.
- Borrower file: `borrower_file/build.py`.
- Deals: `deals/__init__.py:531 deal_summary`.

### Read routes that already carry answers

- `GET /state`, `/mandate`, `/trajectory`.
- `GET /home`: status, headline, worst point, drivers, headroom, plan, receivables and changes.
- `GET /worklist`, `/customers`, `/customers/{id}/overview`, `/receivables`, `/reconciliation`, `/alerts`.
- `GET /approvals/queue`, `/decisions`, `/deals`, `/documents`, `/ledger`, `/activity`, `/audit`, `/security/summary`.
- Read-only POST routes: `POST /router/plan` (plan, menu, comparison, marginal cost, break-even), `POST /capex/evaluate` and
  `POST /whatif`.

### NL intents that answer questions today (`app/nl/`)

| Intent | What it reads |
|---|---|
| SHOW_STATUS | `status()`: cash, reserve, worst gap, DSCR, leverage, concessions. Also the reads `waiting`, `arrival` and `owed` in `reads.py`. |
| SHOW_ALERTS | The alerts and the plan. |
| CHANGES | What changed today. |
| RECONCILE | Reconciliation; with "overdue" it gives `reads.receivables`. |
| COMPARE_FINANCING | The router's comparison. |
| SHOW_RATIOS | DSCR and leverage with headroom, and clean-down. |
| CAPEX | The default capex case only. |
| SHOW_DEAL | A buyer's confirmed contract. |
| EXPLAIN | The last verdict only. |
| WHAT_IF | Buyer terms or discount. `reads.late_payment` runs only when the text has no day count. |
| BORROWER_FILE | Builds a borrower file. |

Not reads, but they answer some questions:
- FUND_GAP, REPAY_FACILITY, ACCELERATE_RECEIPT and NEGOTIATE are proposals.
- RECORD_FACT always says that chat cannot book.
- OUT_OF_SCOPE goes through `capabilities.closest_capability`, a keyword nearest-capability lookup.

## 2. Totals

**Business wording (`mode=business`), 503 turns**

| Category | Lang | Answered | Partial | Wrong | Can't | Turns |
|---|---|---:|---:|---:|---:|---:|
| liquidity | en | 4 | 9 | 1 | 25 | 39 |
|  | zh | 6 | 12 | 1 | 17 | 36 |
|  | **all** | 10 | 21 | 2 | 42 | 75 |
| debt | en | 3 | 3 | 1 | 23 | 30 |
|  | zh | 1 | 5 | 4 | 18 | 28 |
|  | **all** | 4 | 8 | 5 | 41 | 58 |
| customers | en | 3 | 2 | 1 | 27 | 33 |
|  | zh | 7 | 5 | 3 | 18 | 33 |
|  | **all** | 10 | 7 | 4 | 45 | 66 |
| deals | en | 2 | 2 | 1 | 16 | 21 |
|  | zh | 2 | 1 | 2 | 15 | 20 |
|  | **all** | 4 | 3 | 3 | 31 | 41 |
| funding | en | 3 | 1 | 2 | 15 | 21 |
|  | zh | 5 | 1 | 3 | 11 | 20 |
|  | **all** | 8 | 2 | 5 | 26 | 41 |
| covenants | en | 6 | 2 | 1 | 9 | 18 |
|  | zh | 7 | 5 | 0 | 6 | 18 |
|  | **all** | 13 | 7 | 1 | 15 | 36 |
| capex | en | 9 | 3 | 2 | 2 | 16 |
|  | zh | 8 | 3 | 1 | 4 | 16 |
|  | **all** | 17 | 6 | 3 | 6 | 32 |
| activity | en | 5 | 0 | 2 | 12 | 19 |
|  | zh | 5 | 0 | 2 | 11 | 18 |
|  | **all** | 10 | 0 | 4 | 23 | 37 |
| mandate | en | 2 | 0 | 0 | 19 | 21 |
|  | zh | 2 | 0 | 1 | 17 | 20 |
|  | **all** | 4 | 0 | 1 | 36 | 41 |
| not_in_books | en | 9 | 28 | 1 | 0 | 38 |
|  | zh | 3 | 29 | 6 | 0 | 38 |
|  | **all** | 12 | 57 | 7 | 0 | 76 |
| **ALL** | en | 46 | 50 | 12 | 148 | 256 |
|  | zh | 46 | 61 | 23 | 117 | 247 |
|  | **all** | **92 (18%)** | **111 (22%)** | **35 (7%)** | **265 (53%)** | 503 |

- Main wordings only: 48 answered, 51 partial, 21 wrong, 124 can't (244 turns). Paraphrases: 44 / 60 / 14 / 141 (259).
- `--mode demo`: 90 / 113 / 35 / 265. The only difference is DEAL-05 ("Foshan wants 60-day terms. Can we accept?" and its zh
  paraphrase). In demo mode it answers in verdict codes ("Verdict REJECT (TIER_1): AGG_CONCESSION_EXCEEDED, RESERVE_BREACH…")
  rather than "FLOW recommends a counter", so it scores partial rather than answered.

**Per question (best over all its wordings, 122 questions)**
- 38 answered, 30 partial, 13 wrong-at-best and 41 can't in every wording.
- 20 questions are answered in one wording but can't or wrong in another, which is the paraphrase fragility. Examples: "Who
  owes us the most?" is answered, but "Which customer owes us the most money?" can't be. "How big is the cash gap?" is
  answered, but "How much are we short?" can't be.

**The 41 questions that are can't in every wording**
- Liquidity: lowest cash and its day; first breach; reserve; upcoming payments; cash in 30 days; in transit; do nothing.
- Debt: total debt; debt by lender; monthly debt service; clean-down; interest; cost of funds.
- Customers: terms cost; recurring billing; expected orders; all receipts in; customer list; payer reliability.
- Deals: approvals pending; discount limit; contracts signed; agreed terms.
- Funding: cheapest way to raise ¥X; FLOW's recommendation; guaranteed loan; what a bank needs.
- Covenants: clean-down risk; EBITDA.
- Activity: what FLOW did this week; refusals; audit chain; messages sent.
- Mandate: every mandate question.

Almost all of these are one field or one existing function away.

**Not in the books** (76 turns): the honest-refusal set behaves as follows.
- 69 turns refuse. Only 12 of them name a nearest capability, and that capability is chosen by keyword, so it is often
  irrelevant. For example, tax is pointed to "reconcile receipts", the most profitable customer to "get Foshan to pay early",
  and pay per employee to "fund the gap".
- 7 turns answer the status as if it were the answer: VAT position, inventory value, per-account balances, competitors and
  company value.

## 3. WRONG cases (35), with the reply

The reply is abridged where long. The root cause is the rule that fired.

**Liquidity and debt (8)**

| Id | Lang | Question | Intent | Reply | Why |
|---|---|---|---|---|---|
| LIQ-14 | en | What is causing the cash gap? | FUND_GAP | FLOW's plan: ¥405,000.00 of funding, estimated cost ¥3,113.93. Draws ¥150,000.00 on the Bank credit line today; requests ¥255,000.00… Reply "Yes, run it" to run it. | `FUND` matches "cash gap": a "why" question gets a plan proposal |
| LIQ-14 | zh | 资金缺口是怎么造成的？ | FUND_GAP | FLOW 的方案：融资 ¥405,000.00，预计成本 ¥3,113.93。…回复"好，执行"即可执行。 | `FUND` matches 资金缺口 |
| DEBT-04 | en | Can we pay off all our loans? | REPAY_FACILITY | Nothing is drawn on a facility that can be repaid on demand. | `REPAY` ("pay off"). It ignores the ¥1,500,000 equipment loan (`DebtPosition`); the task's own example of misleading |
| DEBT-04 | zh | 我们能把债务还清吗？ | REPAY_FACILITY | 没有可按需偿还的已提款额度。 | `REPAY` (还清): same |
| DEBT-04 | zh | 我们能还清所有贷款吗？ | REPAY_FACILITY | 没有可按需偿还的已提款额度。 | same |
| DEBT-08 | zh | 下一笔贷款还款是什么时候？ | REPAY_FACILITY | 没有可按需偿还的已提款额度。 | `REPAY` (还款): asks when the loan payment is (¥45,000 on day 30) |
| DEBT-14 | zh | 我们现在要不要动用授信额度？ | FUND_GAP | 明白，我没有执行任何操作，也没有待确认的方案。 | override: 要不要 ("whether to") is read by the consent gate as 不要 ("do not") |
| CAP-03 | en | Does the investment pay off? | REPAY_FACILITY | Nothing is drawn on a facility that can be repaid on demand. | `REPAY` ("pay off") |

**Customers, deals and funding (12)**

| Id | Lang | Question | Intent | Reply | Why |
|---|---|---|---|---|---|
| CUS-03 | zh | 谁拖欠我们的款？ | RECORD_FACT | 这一项我无法记录：我不会根据聊天内容录入账单、发票、延迟付款… | `RECORD_FACT` (拖欠): asks who is late |
| CUS-04 | zh | 我们的应收账款周转天数是多少？ | FUND_GAP | FLOW 的方案：融资 ¥405,000.00… | `FUND_SOFT` (周转): asks DSO |
| CUS-07 | en | What if Foshan pays 30 days late? | WHAT_IF | This needs your approval: the terms are within your limits. Recommended response: ask for your approval first. | override: `what_if` (`nl/offers.py:671`) uses `reads.late_payment` only when the text has no day count; "30 days" compiles as a terms offer and gets a verdict |
| CUS-07 | zh | 如果佛山晚30天付款会怎样？ | WHAT_IF | 这需要您批准：条款在您的限额内。建议的回应：先征得您的批准。 | same |
| DEAL-04 | en | Any open negotiations? | NEGOTIATE | There are no counters to send. Evaluate an offer first (e.g. 'evaluate EX01'). | `NEGOTIATE` ("negotiat") |
| DEAL-09 | zh | 给佛山60天账期要花我们多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；您的最低现金储备为 ¥300,000.00。… | `STATUS` (多少钱); the en wording answers ¥24,326.92 |
| DEAL-10 | zh | 我们发过什么还价？ | NEGOTIATE | 没有可发送的反报价。请先评估一条报价… | `NEGOTIATE` (还价) |
| FUN-04 | zh | FLOW的方案要花多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (多少钱); expected ¥3,113.93 |
| FUN-07 | zh | 我们的发票最多能融多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (多少钱); expected ¥336,000 |
| FUN-08 | en | What's the break-even discount for early payment? | ACCELERATE_RECEIPT | Plan (Tier 1): offer BUYER-1 early settlement on up to ¥260,000.00 of RCV-A at 0.85% (below the 0.88% break-even)… | `ACCELERATE` ("early payment"): a definition question gets a plan to send to the buyer (the 0.88% is in it) |
| FUN-08 | zh | 提前付款折扣的盈亏平衡点是多少？ | ACCELERATE_RECEIPT | 方案（一级权限）：向 BUYER-1 提议对 RCV-A 最多 ¥260,000.00 按 0.85% 提前结算… | same |
| FUN-08 | en | Above what discount is early payment too expensive? | ACCELERATE_RECEIPT | Plan (Tier 1): offer BUYER-1 early settlement… | same |

**Covenants, capex, activity and mandate (8)**

| Id | Lang | Question | Intent | Reply | Why |
|---|---|---|---|---|---|
| COV-07 | en | Does the plan breach any covenant? | SHOW_STATUS | Cash today is ¥400,000.00; … | `STATUS_QUESTION`: today's status, not the plan's pro forma |
| CAP-08 | en | Do we have any capex contracts? | CAPEX | ¥600k die-cutting line, ¥600,000.00: NPV ¥380,885.77… | override: evaluates the built-in case, never says none is on file |
| CAP-08 | zh | 有哪些设备采购合同？ | CAPEX | ¥600k die-cutting line，¥600,000.00：按 10.00% 折现… | same |
| ACT-06 | en | How much money has FLOW moved? | SHOW_STATUS | Cash today is ¥400,000.00; … | `STATUS` ("how much money"); expected ¥0 (`/audit` money_moved) |
| ACT-06 | zh | FLOW一共动了多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (多少钱) |
| ACT-08 | en | Did anyone try to change our limits? | OUT_OF_SCOPE | Refused: change mandate is a Tier-3 action. The agent can never do it, whoever asks; it was refused by the executor and logged. … | `TIER3` CHANGE_MANDATE: a question about attempts is logged as one (section 0) |
| ACT-08 | zh | 有人试图修改我们的限额吗？ | OUT_OF_SCOPE | 已拒绝：CHANGE_MANDATE 属于三级操作，代理在任何情况下都不能执行；执行器已拒绝并记录。… | same (and the zh reply prints the code CHANGE_MANDATE) |
| MAN-03 | zh | 授权什么时候到期？ | SHOW_STATUS | 目前没有在途资金。下一笔到期的款项是Foshan Home Retail Co. 的 ¥420,000.00 发票，32 天后到期。 | override: `ARRIVAL_ASK` (什么时候到) answers the next invoice, not the mandate's expiry (day 90) |

**Not in the books (7)**

| Id | Lang | Question | Intent | Reply | Why |
|---|---|---|---|---|---|
| NIB-02 | en | What's our VAT position this quarter? | SHOW_STATUS | Cash today is ¥400,000.00; … | `STATUS` ("position"): not in the books, answered with cash status |
| NIB-02 | zh | 本季度增值税情况怎么样？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (情况怎么样) |
| NIB-06 | zh | 库存值多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (多少钱): inventory |
| NIB-10 | zh | 每个银行账户里各有多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS`: per-account balances are not held |
| NIB-10 | zh | 按账户列一下余额。 | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (余额) |
| NIB-13 | zh | 竞争对手情况怎么样？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (情况怎么样): competitors |
| NIB-16 | zh | 公司值多少钱？ | SHOW_STATUS | 今天现金 ¥400,000.00；… | `STATUS` (多少钱): valuation |

**Pattern.** 23 of the 35 are Chinese. Two causes account for most of them:
- The broad Chinese status cues 多少钱, 余额 and 情况怎么样 swallow any question with a money word.
- The action lexicons fire on question words: 还款 and 还清 (repay), 还价 (counter), 周转 (funding need), 拖欠 (record a fact),
  "pay off", "early payment", "cash gap" and "negotiat".

Rules read a topic word as an instruction, and nothing checks first whether the message is a question
(`lx.READ_QUESTION` exists but routes nothing).

### Other observations (no score impact)

- **The status reply omits the first breach.** For "Are we safe?" and its paraphrases it says "¥405,000.00 short in 30 days"
  but never "in 12 days", the more urgent fact that Home leads with. It never answers yes or no.
- **Two different cures for one gap.**
  - `GET /alerts` (ALERT-RESERVE-12) proposes line ¥150,000 + invoice financing **¥336,000**, cost **¥2,994.08**.
  - The router and Home propose ¥150,000 + **¥255,000**, cost **¥3,113.93**.
  - An answer layer must pick one source. The plan the owner runs is Home's (`plan_source "router"`).
- **Mixed language.** The Chinese capex reply carries English module strings ("Owner's estimate, not observed by the system",
  "Cash + credit line: 不通过: Only ¥250,000.00 is available…", the recommendation paragraph). The Chinese funding replies
  print "Bank credit line" and "committed plan: ¥841.64 + …".
- **Typo.** The SHOW_DEAL reply has "Foshan Home Retail Co.." (a double full stop).
- **Generic fallback.** Business mode falls back to a generic "I can answer questions about your cash, deals, approvals and
  what changed; try 'What changed today?'" in 182 turns. That suggestion is right for none of them.

### Manual overrides (9) and rule changes after the hand check

Every one of the 503 replies was read after the first run. Overrides are in `OVERRIDES` in the script:

| Question | Rule said | Set to | Reason |
|---|---|---|---|
| LIQ-14 "Why are we going to be short of cash?" (en and zh) | PARTIAL | CANT | EXPLAIN only explains offer verdicts ("There is no verdict to explain yet") |
| CUS-07 "What if Foshan pays 30 days late?" (en and zh) | PARTIAL | WRONG | a late payment is compiled as an offer and gets a "needs your approval" verdict |
| DEBT-14 "我们现在要不要动用授信额度？" | PARTIAL | WRONG | 要不要 is read as 不要 |
| DEBT-14 "现在该提款了吗？" | PARTIAL | CANT | the consent gate treats the question as a conditional instruction |
| MAN-03 "授权什么时候到期？" | PARTIAL | WRONG | the arrival read answers the next invoice |
| CAP-08 "Do we have any capex contracts?" (en and zh) | PARTIAL | WRONG | evaluates the default case instead of saying none is on file |

Rule changes made after reading the replies, all in the committed script or bank:
- A what-if reply that only offers buyer-term tests ("I can test changes to a buyer's terms", "Which change should I test?") is
  CANT.
- An explicit yes/no sentence that is not the first line counts as a direct answer. This is `direct_re`, used on 7 questions,
  for example "Every projected month is inside the covenants" and "FLOW recommends a counter".
- A refusal intent is CANT unless its reply carries the expected figure or answer. Tier-3 refusals still answer "Can FLOW sign a
  personal guarantee?".
- Four paraphrases had the opposite polarity to their main question and were reworded: CUS-14, COV-07, COV-08 and CAP-07.
- CUS-08 is scored on the 0.88% break-even. The ¥5,040 is supporting detail.
- DEAL-09 is given its golden figure, ¥24,326.92 (`extension_committed_12m`).

## 4. The 30 questions to build first

They are ranked by owner and demo value, then by cost.
- "Now" columns show the current scores per wording, main first: A answered, P partial, W wrong, C can't.
- Figures are day-0 golden values read from the routes.
- Every computation uses an existing function. "New" marks the only pieces that do not exist yet.

**Liquidity (9)**

| # | Id | Question | Now en / zh | Proposed answer (en, day 0) | Computation |
|---:|---|---|---|---|---|
| 1 | LIQ-01 | Are we safe? | PPP / PPP | "No, not without funding. Cash falls to ¥60,000 in 12 days, when payroll is paid: ¥240,000 below your ¥300,000 reserve. The worst point is −¥105,000 on day 30. FLOW's plan (¥3,113.93, within your limits) keeps you at ¥300,000." | `read_home()`: `cash.first_breach_day/first_breach_cash_fen/lowest_fen/lowest_day`, `cash.drivers`, `funding_line.cost_total_display`, `next_action.after_lowest_short`; yes/no = `first_breach_day is None` |
| 2 | LIQ-03 | What is our cash runway? | PPC / PPP | "12 days to your reserve (day 12, ¥60,000 left). Cash itself goes below zero on day 20 (−¥60,000) unless you fund the gap." | `project()`: `first_breach_day`; first day with `closing_fen < 0` from `traj.days` |
| 3 | LIQ-04 | What is the lowest our cash will go, and when? | CC / CC | "−¥105,000 on day 30, after payroll, the supplier and the loan payment; it recovers on day 32 when Foshan pays ¥420,000." | `traj.min_cash_fen`, `traj.min_cash_day`; recovery = next inflow event after the minimum |
| 4 | LIQ-05 | When do we first drop below the reserve? | CC / CC | "In 12 days (day 12): cash closes at ¥60,000, ¥240,000 below your ¥300,000 reserve." | `traj.first_breach_day`, `days[d].closing`, `mandate.min_cash_fen` (the ALERT-RESERVE-12 inputs) |
| 5 | LIQ-06 | How much can I spend today without breaking the reserve? | CCP / PP | "Nothing safely. ¥100,000 is above your reserve today, but the forecast is already ¥405,000 short on day 30, and any spend widens that gap." | `home.cash.headroom_fen`, `home.cash.lowest_headroom_fen`; safe spend = `max(0, min headroom over the horizon)` |
| 6 | LIQ-09 | What big payments are coming up? | CCC / CC | "Payroll ¥340,000 in 12 days; supplier ¥120,000 in 20 days; equipment loan ¥45,000 in 30 days; operating bill ¥100,000 in 47 days." | `state.flows` (amount < 0) + `debt_payments(debt, today, today+60)`, sorted by day |
| 7 | LIQ-10 | Can we make payroll? | CC / PC | "Yes, ¥400,000 covers the ¥340,000 payroll on day 12, but it leaves ¥60,000, ¥240,000 below your reserve. The plan fixes that." | next PAYROLL flow; `traj.days[day].closing` vs 0 and vs `min_cash_fen` |
| 8 | LIQ-14 | Why are we going to be short of cash? | CW / CW | "Payroll of ¥340,000 falls due in 12 days, and the next receipt, Foshan's ¥420,000, only lands in 32 days." | `home.cash.drivers` (`api/home.py:247 _drivers`) |
| 9 | LIQ-15 | How much do we need to raise to stay safe? | CAC / AA | "¥405,000, needed from day 12 to day 31; the cheapest committed plan costs ¥3,113.93." | `plan().need_fen`, `nl.funding.gaps()`, `plan().total_cost_fen` |

**Funding and debt (7)**

| # | Id | Question | Now en / zh | Proposed answer (en, day 0) | Computation |
|---:|---|---|---|---|---|
| 10 | FUN-02 | What does FLOW recommend we do about cash? | CCC / CC | "Draw ¥150,000 on the credit line today (¥841.64) and finance ¥255,000 of Foshan's invoice (¥2,272.29, cash in 3 days): ¥3,113.93 in total, no approval needed. Say 'go ahead' to run it." | `home.next_action` (title, components, cost); same as `plan()` |
| 11 | FUN-04 | How much would FLOW's plan cost? | CC / WA | "¥3,113.93: ¥841.64 for the line and ¥2,272.29 for the invoice financing." | `plan().costs`, `total_cost_fen` |
| 12 | DEBT-01 | How much debt do we have? | CCC / CC | "¥1,500,000, all of it the existing equipment loan (¥45,000 a month). Nothing is drawn on the credit line or invoice financing." | `sum(d.principal_fen for d in state.debts) + sum(f.drawn_fen) + open lots`; equals `traj.days[today].debt` |
| 13 | DEBT-04 | Can we clear our debts? | CW / WW | "No. The ¥1,500,000 equipment loan is far more than the ¥100,000 you have above your reserve. It is being paid down ¥45,000 a month; the next payment is on day 30." | DEBT-01 total vs `home.cash.headroom_fen`; `debt_payments()`. It must include `DebtPosition`, not only facilities. |
| 14 | DEBT-06 | How much more can we borrow? | CPP / PP | "¥500,000 committed and unused: the credit line ¥150,000 (6.40%, same day) and invoice financing ¥350,000 (80% of an invoice, so ¥336,000 on Foshan's, in 3 days). The guaranteed loan (¥500,000) is not applied for yet." | `menu_view(state, mandate)` rows with `committed`, `available_display`, `all_in_display`, `time_to_cash_days` |
| 15 | DEBT-08 | When is our next loan payment? | CC / WC | "¥45,000 on the equipment loan in 30 days (day 30)." | `debt_payments(debt, today, horizon)[0]` |
| 16 | DEBT-03 | What does our debt cost us each month? | CC / CC | "¥45,000 a month of debt service (the equipment loan, at 0% as the fixture assumes); no interest is due on facilities." | `traj.months[0].debt_service_fen`, `traj.interest_posted_fen` |

**Customers and deals (8)**

| # | Id | Question | Now en / zh | Proposed answer (en, day 0) | Computation |
|---:|---|---|---|---|---|
| 17 | CUS-01 | Who owes us the most? | AC / AA | "Foshan Home Retail Co.: ¥420,000 on one invoice, due in 32 days; that is everything you are owed. Dongguan owes nothing." | exists: `reads.owed()`. Needs routing for "which customer owes…" |
| 18 | CUS-03 | Who is paying late? | CCA / WAA | "Nobody. Nothing is overdue; the next payment due is Foshan's ¥420,000 in 32 days." | exists: `reads.receivables()` (overdue). Needs routing ("who is paying late", 拖欠) |
| 19 | CUS-05 | How dependent are we on one customer? | CC / CP | "Completely: Foshan is 100% of what you are owed (¥420,000) and of the recurring invoicing (¥420,000 every 30 days)." | worklist `share_text` (`api/worklist.py:589`); `recurring_invoices` by buyer |
| 20 | CUS-07 | What if Foshan pays 30 days late? | WC / WC | "Your lowest point would move from −¥105,000 on day 30 to −¥X on day Y, and the gap would grow to ¥Z; the plan would need … ." The figures come from one projection. | **New** (small): `project()` on `state` with RCV-A `terms_days + n`. This is pure, writes nothing, and is the same call `reads.late_payment` avoids. Also fix the `nl/offers.py:671` day-count gate. |
| 21 | CUS-08 | Should we take Foshan's early-payment offer at 1.2%? | CP / AP | "No. 1.2% is above the 0.88% break-even: discounting the whole invoice costs ¥5,040, against ¥3,113.93 for FLOW's plan." | `break_even_discount()`, router `rejected` row "Discount the whole invoice at 1.2%" |
| 22 | DEAL-01 | What is waiting for me? | CCC / CA | "One thing: your reserve becomes unsafe in 12 days, and FLOW's ¥405,000 plan (¥3,113.93, within your limits) waits for your go. No approvals are pending and no deal needs you." | `worklist.alert`, `worklist.needs_you`, `store.approvals("PENDING")` (SHOW_ALERTS already says this in zh) |
| 23 | DEAL-02 | Are there any approvals pending? | CC / CC | "No. Nothing is waiting for your approval." | `store.approvals(status="PENDING")`; `GET /approvals/queue` |
| 24 | DEAL-09 | What would it cost us to give Foshan 60 days? | AC / WC | "¥24,326.92 over the next 12 months of Foshan invoices, above your ¥5,000 limit, and cash would fall below your reserve in 47 days; FLOW would counter." | exists: the en WHAT_IF; route zh 多少钱 + 账期 to it. Same as `whatif.simulate(terms_days=60)` |

**Covenants, capex, activity and mandate (6)**

| # | Id | Question | Now en / zh | Proposed answer (en, day 0) | Computation |
|---:|---|---|---|---|---|
| 25 | COV-01 | Are we inside our covenants? | AA / AA | "Yes. Lowest DSCR 2.00× against 1.25× (0.75× headroom) and highest leverage 1.35× against 2.50× (1.15×), every month; no clean-down alert." | exists: `show_ratios()`; lead with the yes/no it already computes (`inside`) |
| 26 | COV-05 | What would break our covenants? | CC / PC | "Monthly debt service above ¥72,000 (now ¥45,000) breaks DSCR; total debt above ¥2,700,000 (now ¥1,455,000) breaks leverage. Neither is close." | `monthly_ebitda_fen / min_dscr` and `max_leverage × 12 × EBITDA` vs `traj.months` (`covenants.ratios`) |
| 27 | CAP-01 | Can we afford a new machine? | AC / AC | "Only financed. Paying cash leaves ¥250,000 above your reserve for a ¥600,000 price. The 48-month lease (¥14,423.49 a month, 7.20%) passes every limit, and the machine is worth doing on your estimate (NPV ¥380,885.77, payback month 31)." | exists: `evaluate_capex()`; lead with `selected_id` / `structures[].feasible` |
| 28 | ACT-01 | What did FLOW do this week? | CCC / CC | "Nothing yet: no operation has run, nothing was refused and the log's chain verifies." | `store.operations()` filtered by day ≥ today−7 (activity rows), `security_events()`, `verify_chain()` |
| 29 | MAN-01 | What can FLOW do without me? | CCC / CC | "Inside your signed mandate (valid to day 90) FLOW may use committed facilities up to 15.00% a year while keeping ¥300,000 in cash, give discounts up to 1.50% and future concessions up to ¥5,000. Any single commitment above ¥100,000, a new facility or a rate above 15% needs you; guarantees, collateral, equity and the mandate itself never." | `store.get_mandate()` fields, `mandate.tiers.tier_for`, `validity.check_validity` |
| 30 | MAN-02 | What needs my approval? | CC / CC | "A single commitment above ¥100,000, a rate above 15.00% a year, a new facility, and anything that would break the reserve, the ¥5,000 concession cap or a covenant." | the mandate thresholds above; the same predicates the verifier uses (`mandate/predicates.py`) |

**Cross-cutting changes the 30 need (all cheap)**

1. **A question gate before the action rules.**
   - When `lx.READ_QUESTION` matches and no amount or command is present, try the read and metric intents first.
   - Never let REPAY, FUND, NEGOTIATE, ACCELERATE, RECORD_FACT or TIER3 fire on a question. A Tier-3 question would still get its
     refusal sentence, but it would not be logged as a refused operation.
2. **Narrower Chinese status cues.** 多少钱, 余额 and 情况怎么样 should need a cash subject: 现金, 账上, 资金.
3. **Answers lead with the answer.** Each answer opens with a direct yes/no or figure in one sentence, then one or two reasons,
   then the next action. The current status block stays as the fallback.
4. **Refusals say what is missing.**
   - A not-in-the-books question should say "FLOW's books do not hold X".
   - Then name a nearest capability chosen by the subject (tax and payables → scheduled outflows; profit → EBITDA and covenant
     ratios; staff → the payroll total).
   - Drop the generic "try 'What changed today?'".

## 5. Reusable metrics an answer layer should expose (40)

Each metric is one function over the books (`current_books(state, commitments)`), the mandate and the stores, and returns a
value with its display string, day or month, and source. Questions map to metrics; replies are templates over them.

Day-0 golden values are in brackets.

**Liquidity**
1. `cash_today` [¥400,000]: `state.cash_fen`.
2. `reserve` [¥300,000]: `mandate.min_cash_fen`.
3. `headroom_today` [¥100,000]: cash − reserve.
4. `first_breach` [day 12, ¥60,000, ¥240,000 short]: `traj.first_breach_day` and its closing.
5. `lowest_point` [−¥105,000 on day 30]: `traj.min_cash_fen`, `min_cash_day`.
6. `lowest_headroom` / `funding_need` [−¥405,000 / ¥405,000]: `plan().need_fen`, `home.cash.lowest_headroom_fen`.
7. `first_negative_cash_day` [day 20, −¥60,000]: `traj.days`.
8. `runway_days` [12 to reserve, 20 to zero].
9. `cash_on(day)` [day 30: −¥105,000]: `traj.days[day].closing`.
10. `gap_windows` [days 12–31]: `nl.funding.gaps()`.
11. `upcoming_outflows(window)` [¥340k d12, ¥120k d20, ¥45k d30, ¥100k d47]: `state.flows` + `debt_payments()`.
12. `upcoming_inflows(window)` [¥420k d32, ¥420k d47, d77, d107]: receivables + recurring invoices (`traj` events).
13. `cash_drivers` [payroll ¥340k in 12 days; receipt in 32 days]: `home._drivers`.
14. `in_transit` [none]: open `lots` and `home.cash.in_transit`.

**Debt**
15. `total_debt` [¥1,500,000]: debts + drawn + open lots (`traj.days[today].debt`).
16. `debt_positions` [equipment loan ¥1,500,000, lender not recorded]: `state.debts` + facilities drawn. This needs `DebtPosition` to carry a lender.
17. `debt_service_month(m)` [¥45,000]: `traj.months[m].debt_service_fen`.
18. `next_debt_payment` [¥45,000, day 30]: `debt_payments()`.
19. `drawn_by_facility` [all ¥0]: `facility.drawn_fen` + lots.
20. `undrawn_committed` [line ¥150,000, IF ¥350,000 (¥336,000 on RCV-A)]: `menu_view()`.
21. `projected_interest_fees` [¥0 / ¥0]: `traj.interest_posted_fen`, `fees_posted_fen`.
22. `marginal_cost_of_funds` [10.84%, invoice financing]: `funding.rates.marginal_cost()`.
23. `fastest_and_cheapest_source` [line: 6.40%, same day]: `menu_view()` ordering.

**Funding**
24. `standing_plan` [¥150,000 line + ¥255,000 IF, ¥3,113.93, no approval, runs today]: `plan()` / `home.next_action`. This is the one plan source for answers; the alert cure gives ¥2,994.08 (section 3).
25. `alternatives_priced` [full discount ¥5,040; line + part early pay ¥3,938.81; line only short ¥255,000; guaranteed loan too slow]: `compare()` / router `rejected`.
26. `break_even_discount` [0.88%]: `funding.rates.break_even_discount()`.
27. `invoice_financing_capacity(invoice)` [¥336,000 = 80% × ¥420,000]: `advance_rate_bp × outstanding_fen`, capped by the limit.

**Customers**
28. `receivables_total` [¥420,000, 1 invoice, 0 overdue]: the `/receivables` summary.
29. `receivables_by_customer` with share [Foshan ¥420,000, 100%; Dongguan ¥0]: worklist customers.
30. `overdue` [none]: `reconcile().outstanding.past_due`, `days_late`.
31. `next_receipt` [Foshan ¥420,000 in 32 days]: `receivables.summary.next_expected`.
32. `recurring_billing` [¥420,000 every 30 days, next day 2]: `state.recurring_invoices`.
33. `terms_by_customer` [45 days, no contract confirmed]: `receivables.governed_by`, `contracts.derive.buyer_terms`.
34. `late_payment_impact(customer, days)` [new; one `project()` call]: lowest point and gap after a receipt slips.

**Covenants**
35. `covenant_ratios` [DSCR 2.00× / 1.25× (0.75×), leverage 1.35× / 2.50× (1.15×)]: `worst_dscr`, `worst_leverage`, `ratios_for`.
36. `covenant_breakpoints` [debt service ≤ ¥72,000 a month, debt ≤ ¥2,700,000]: EBITDA × thresholds.
37. `ebitda_month` [¥90,000]: `state.monthly_ebitda_fen`.

**Mandate**
38. `mandate_limits_and_validity` [reserve ¥300,000, APR 15.00%, Tier-2 ¥100,000, discount 1.50%, concessions ¥5,000, DSCR 1.25×, leverage 2.50×, valid to day 90, signature VALID]: `GET /mandate` and `tiers.tier_for`.

**Activity**
39. `activity_since(day)` [0 operations, 0 refused, 0 security events, ¥0 moved, chain valid]: `store.operations()`, `security_events()`, `/audit` summary, `verify_chain()`.

**What waits**
40. `what_waits` [funding plan ready; 0 approvals pending; 0 open decisions]: `worklist.alert` and `needs_you`, `store.approvals("PENDING")`, `decisions.waiting_for()`.

With the handlers that already exist, these 40 cover the bank's 103 answerable questions except four. The existing handlers
are the verdict and what-if (DEAL-05, DEAL-09, ACT-03), `evaluate_capex` (the capex rows), the borrower file (FUN-09) and the
Tier-3 refusal (MAN-07, MAN-08). The four left uncovered:
- CUS-06 (the cost of a customer's terms) needs `marginal_cost × face × days / 365`, or `FEATURE_CUSTOMER_ECONOMICS`.
- CUS-16 (payer reliability) needs a receipt history.
- FUN-01 (the cheapest way to raise an arbitrary ¥X) needs the router to take a need amount; today it prices only the
  projected gap.
- DEBT-02 needs the lender on `DebtPosition`.
