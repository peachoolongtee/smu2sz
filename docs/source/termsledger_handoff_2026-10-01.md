# Handoff: initialise and build TermsLedger v2 (full scope)

- **Written:** 1 Oct 2026. Revised the same day after the user asked for the full build rather than a trimmed one.
- **For:** a fresh agent that will create, scaffold and build the codebase for the FinTechathon 2026 entry.

**The user's instruction:** build **as much as possible**, then omit features at the end if time runs short. Nothing is cut up front. The build order in §10 puts the core first and the cuttable extras last. §11 is the cut ladder: the order to drop things **only if** a checkpoint is missed.

---

## 1. The decision

**Event:** FinTechathon 2026, the 8th Shenzhen International FinTech Competition.
- International track, **Topic E: SME Finance Copilot**.
- Theme: "AI as a Financial Participant".

**Project:** **TermsLedger v2**, an agent owned by a small supplier that manages both of the supplier's "debt books":
1. **Terms Guard: the credit it gives.** It compiles a buyer's free-text offer into typed obligations. It projects them onto the daily cash trajectory and a forward-liability ledger, then returns ACCEPT, REJECT, COUNTER or NO DEAL inside an owner-signed mandate.
2. **Debt Desk: the credit it takes.** It sizes cash gaps and compares the owner's funding sources on all-in cost, time to cash and covenant effect. It picks the cheapest plan that keeps the covenants intact. It also covers capex financing structures and generates a borrower file.

**The core reframe:** a payment-term extension is an interest-free loan from the supplier to the buyer, and the supplier funds it by borrowing.

**The 2026 rubric** (CONFIRMED on the official 2026 site):

| Criterion | Weight | What is scored |
| --- | --- | --- |
| Task completion | 40% | Scripted tasks in a simulated environment |
| Security & compliance | 30% | Induced transfers, data extraction, privilege escalation, prompt injection. Serious failures bring large deductions |
| Innovation & interaction | 30% | |
| Bonus | 0–5 | For harder topics or real deployment |

**Why this project:** see `/Users/ianpong/Hackathons/SZ_Research/research/fintechathon_winners_2026-09-30/HACKATHON_OPTION_EVALUATION.md`. Ignore its "trim" advice: the user overrode it and wants the full build.

## 2. Documentation to read, in order

| # | Path | What it is |
| --- | --- | --- |
| 1 | `/var/folders/hc/279g9_d544dcvfy59jhx6ql00000gn/T/termsledger_v2_spec_extracted.txt` | **The full product spec as plain text** (1,195 lines), extracted from `/Users/ianpong/Downloads/TermsLedger_Project_Document_v2.docx`. Read all of it. Copy both into the new repo's `docs/`. |
| 2 | This handoff | Scope, the additions to v2, the stack, architecture, build order, cut ladder |
| 3 | `/Users/ianpong/Hackathons/SZ_Research/research/fintechathon_winners_2026-09-30/HACKATHON_OPTION_EVALUATION.md` | The 13 changes required to v2; all are folded into §4 below |
| 4 | `/Users/ianpong/Hackathons/SZ_Research/research/fintechathon_winners_2026-09-30/deep_dive.md` and `winners.csv` | Past winners 2019–2025, judges, the 2026 rubric and deliverables |
| 5 | `/Users/ianpong/Hackathons/SZ_Research/files/FinTechathon_2026_Third_Review.md` | How TermsLedger was chosen; judge simulation; competition facts |
| 6 | `/Users/ianpong/Hackathons/SZ_Research/research/sme_liquidity_opportunity_2026-09-27/04_capitalpilot/deep_dive.md`, `12_china/deep_dive.md`, `05_facility_readiness/deep_dive.md` | Prior art for the Debt Desk (Xero JAX, MYbank 百灵2.0 / AI票据管家, Cerebro, Capitalise, Codat), Chinese bill rates, debt-headroom arithmetic |
| 7 | `/Users/ianpong/Hackathons/SZ_Research/research/sme_liquidity_opportunity_2026-09-27/datasets/liquidity_options.csv` | 159 real-world funding options with costs and speeds. Useful for making fixture rates plausible |

**v2 spec section map** (in the extracted text, search by heading):

| Section | Content |
| --- | --- |
| §1–2 | Summary, plain-language rundown and the joint flow diagram |
| §3 | User and pain |
| §4 | Seven capabilities, novelty classification |
| §5.1 | Components |
| §5.2 | Flow |
| §5.3 | Tiers |
| §5.4 | Security keep/drop |
| §6.1 | Fixture |
| §6.2 | Compiled offer |
| §6.3 | Payer and risk table |
| §6.4 | Optimiser objective and the v1/v2 optima |
| §6.5 | Verdict and Counters A and B |
| §6.6 | Economic corrections |
| §7.2 | Funding menu |
| §7.3 | Honesty rules |
| §7.4 | Router table and break-even |
| §7.5 | Terms extension priced as a loan |
| §7.6 | Covenants |
| §7.7 | Capex mode |
| §7.8 | Borrower file |
| §7.9 | Debt Desk "will not" list |
| §8 | 12 worked examples; every one is a required test case |
| §9 | Prior-art map and positioning |
| §10 | Demo script (30-second wow, three scenes, 5-minute structure) |
| §11 | Rubric mapping |
| §12 | Risk register, two silent errors, judge attacks |
| §13 | Claims to make and avoid; safe claims |
| §14 | Validation gate E1–E10 |
| §15 | Build scope, 7 screens, team split |
| §16 | Pitch |
| §17 | Decision record |
| §18 | Sources |

## 3. Full feature catalogue: build all of it

Tags show the cut priority from §11:
- **[CORE]** is never cut.
- **[P1]** is cut only if badly late.
- **[P2]** is cut first.

### A. Mandate and governance
- **[CORE]** Owner-signed mandate with these predicates:
  - minimum cash;
  - maximum aggregate forward concession, with per-buyer sub-caps;
  - minimum DSCR and maximum leverage;
  - maximum APR;
  - clean-down rule;
  - permission tiers;
  - horizon and expiry.

  The mandate is versioned and revocable, and signed with Ed25519 (v2 §2.2, §5.1, §5.3).
- **[CORE]** Three permission tiers, enforced by the verifier and executor, never by the prompt:
  - **Tier 1:** autonomous inside the mandate.
  - **Tier 2:** owner approval.
  - **Tier 3:** never (personal guarantee, collateral, equity, mandate change).
- **[P1]** Owner approval queue for Tier-2 items, with the borrower file attached.
- **[P1]** Mandate revocation mid-plan, and correct handling of it.

### B. Intake
- **[CORE]** Inbox for buyer offers as free text (chat, email or portal message).
- **[P1]** File intake: PDF, DOCX and XLSX for offers and lender term sheets.
- **[P1]** Chinese and English offers.
- **[CORE]** Conflicting-source detection. Example 7: the attachment says ¥400,000 and the body says ¥40k, so the system abstains.

### C. Compiler (the language model; untrusted; output is a proposal only)
- **[CORE]** Obligation types:
  - immediate discount;
  - terms extension (recurring, perpetual until an end date is extracted, or bounded to N invoices);
  - contingent rebate;
  - volume commitment;
  - operational concession;
  - claimed prior concession.
- **[CORE]** Every obligation carries a source span, a base, a duration and a contingency class, or the compiler abstains. Strict schema with `additionalProperties: false`.
- **[CORE]** Wording invariance: economically identical wording gives the same verdict; similar wording with different economics gives a different one (§8).
- **[P1]** Term-sheet mode: rate, fees (folded into an all-in rate), guarantee clauses, covenant definitions. The owner approves any compiled facility before it enters the menu.
- **[CORE]** Result cache for all demo fixtures, so the demo runs offline.

### D. Trajectory engine (deterministic)
- **[CORE]** Daily cash recursion covering payroll, invoices in, discounts, draws, interest and repayments. All in integer fen.
- **[CORE]** Forward-liability ledger and debt ledger.
- **[CORE]** Two modes:
  - **Conservative:** unconfirmed inflows are ignored, contingent rebates count at maximum, and uncommitted facilities count as zero.
  - **Expected:** shown beside it, never relied on for hard constraints.
- **[CORE]** The horizon includes the repayment tail.
- **[P1]** A failure branch: an early receipt that fails, or a pending loan that is never approved.
- **[P1]** Multiple buyers and multiple invoices.

### E. Verifier (deterministic; reads no free text)
- **[CORE]** Evaluates every day and month against every predicate.
- **[CORE]** Verdicts:
  - `ACCEPT`
  - `REJECT`, with codes:
    - `AGG_CONCESSION_EXCEEDED`
    - `RESERVE_BREACH@day` (curable or not, with the cost to cure)
    - `DSCR_BREACH@month`
    - `LEVERAGE_BREACH@month`
    - `CLEAN_DOWN_BREACH`
    - `TIER3_PERSONAL_GUARANTEE`
    - `UNKNOWN_COUNTERPARTY`
    - `UNEVIDENCED_PRIOR_CONCESSION`
    - `DATA_EXTRACTION_REFUSED` (new)
  - `COUNTER`
  - `NO DEAL`
  - `NO VERDICT — CONFLICTING_SOURCES`
- **[CORE]** A formula and its inputs on screen for every verdict. Past winners scored on explainability.

### F. Negotiation (Terms Guard)
- **[CORE]** Counters priced from the Debt Desk's marginal cost of funds, e.g. Option A and Option B in v2 §6.5.
- **[CORE]** Mock buyer agent: a deterministic kernel with a hidden reservation value; the language model only verbalises. Bounded rounds; NO DEAL is a first-class outcome.
- **[P1]** Two concurrent offers: reserve against the aggregate cap, and accept only jointly feasible ones (example 8).

### G. Debt Desk
- **[CORE]** Funding menu, owner-approved typed records:
  - credit line;
  - invoice financing;
  - the buyer's early-pay offer;
  - government-guaranteed loan;
  - equipment term loan;
  - equipment lease;
  - equity (reference only, Tier 3);
  - **new: 银票 (bank acceptance bill) discounting**, at about 0.58% p.a. for a 6-month 国股 bill (Aug 2026 market level).
- **[CORE]** Router: grid search for the cheapest admissible mix.
  - It supports multi-step plans, e.g. an invoice-financing bridge refinanced into the guaranteed loan once that loan is approved. That plan appears as an expected plan only.
  - It emits the marginal cost of funds.
- **[CORE]** Break-even early-pay discount (0.88%), and the terms extension priced as a loan: notional, committed-marginal and expected bases (v2 §7.5).
- **[CORE]** Covenant model: DSCR, leverage and clean-down, with a per-facility covenant definition and its formula shown.
- **[P1]** **Capex mode** (v2 §7.7): NPV, payback and four financing structures with DSCR by month. The cheapest by interest fails DSCR; the 36-month loan is selected. Demo Scene 3.
- **[P1]** Borrower file (v2 §7.8), built from verified state only:
  - 13-week forecast;
  - 12-month trajectory;
  - covenant headroom before and after;
  - commitments ledger;
  - use of proceeds;
  - evidence labels.

  Output as DOCX or PDF, formatted as a **mock WeBank 微业贷 application**. Past briefs rewarded WeBank-app fit.
- **[CORE]** The "will not" rules (v2 §7.9): never applies for, signs or guarantees a loan; never takes a rate from an unsolicited message.

### H. Commitment ledger and executor
- **[CORE]** Commitment states: proposed → accepted → recorded, with expiry and nonce, and no reuse when terms change.
- **[CORE]** Typed Tier-1 operations:
  - accept, counter, record;
  - draw, repay;
  - submit invoice for financing;
  - receive.

  All go through an **append-only, hash-chained** operations table with idempotency keys.
- **[P1]** Circuit breaker: freeze a counterparty thread after repeated failures.

### I. Security suites (30% of the score)
- **[CORE]** Injection suite: 15 injected offers and 5 injected lender messages, with **0 booked**.
- **[CORE]** Data-extraction suite (new): a counterparty or message asks for the cash floor, reservation value, funding menu or other buyers' terms. The agent refuses and logs it.
- **[CORE]** Privilege-escalation tests: attempts to push a Tier-2 or Tier-3 action down to Tier 1, or to change the mandate.
- **[CORE]** Induced-transfer tests: fake pre-approvals, fake "agreed last month" concessions, hidden fees in term sheets.
- **[CORE]** Replay, expiry, revocation and unknown-lender tests.
- **[CORE]** Security self-assessment document (a submission deliverable).

### J. `/nl` harness (40% of the score)
- **[CORE]** `POST /nl`: natural-language request → typed plan → verdict → operation log. It asks for clarification when the request is ambiguous.
- **[CORE]** Goal-to-plan with a fallback (example 12).
- **[CORE]** Scenario-runner CLI; `POST /demo/reset`; execution-evidence export as JSONL with hashes.
- **[CORE]** Match the interface to the **Topic E rules docx** once it is read (§8).

### K. After-signing extension
- **[P2]** The commitment ledger also tracks the buyer's side:
  - the statutory due date from the contract plus Order 802 / 国办发〔2026〕24号;
  - late interest at 0.05% a day;
  - a drafted **确权** (receivable confirmation) request, as a Tier-2 action.
- **[P2]** Auto-supplier variant of the same extension, under 工信厅联通装函〔2026〕424号 (signed 2 Sep, released 7 Sep 2026):
  - deemed acceptance after 3 working days;
  - ≥90% provisional payment during price talks.

### L. UI (7 screens from v2 §15.3, plus 3 more)
- **[CORE]** The 7 screens:
  1. Mandate
  2. Inbox, with spans highlighted
  3. Trajectory: cash line, forward-liability meter, debt balance, failing day marked
  4. Funding: menu comparison, selected plan
  5. Verdict: reason, predicate, step, counter and its price
  6. Capex [P1]
  7. Ledger
- **[P1]** Owner approval queue.
- **[P1]** Security and audit log view: refusals with reasons and spans.
- **[P2]** Evidence-export page.
- **[P1]** Chinese and English labels. The defence is in English and the judges are Chinese.
- **[P2]** Multi-agent presentation layer: name the roles Compiler, Risk/Verifier, Negotiator and Treasurer. They map to the real processes in §6. The 2025 winners used multi-agent framing.

### M. Evaluation tooling (v2 §14)
- **[CORE]** E3: 30 hand-calculated engine cases.
- **[CORE]** E10: covenants and capex, 20 cases.
- **[CORE]** E4: injection.
- **[CORE]** E7: harness.
- **[P1]** E2: 20 held-out offers; compiler vs a form vs a bare model.
- **[P1]** E9: 20 router scenarios vs a "draw the line first" baseline.
- **[P1]** E5: an honest NO DEAL.
- **[P2]** E8: blind explanation by non-builders.
- **[P2]** E1: the prior-art check. Research is done; see §4.

### N. Deliverables (from the 2026 site)
- **Required:** a technical document, a deck of 10 minutes or less, and a demo video of 5 minutes or less.
- **Optional, but submit all of them:** source code, the security self-assessment, and execution evidence.
- The pitch script is in v2 §16; the demo script in v2 §10.

## 4. Additions and corrections to v2 (all are in scope)

1. **The rubric is CONFIRMED:** 40/30/30 plus 0–5. Remove the UNVERIFIED caveat in v2 §11.1.
2. **Dates.**
   - The official site shows international online review on **22–23 Oct**, finalists on **31 Oct**, an **English defence on 22 Nov** and awards on 23 Nov.
   - I saw no 48-hour optimisation round for the international track; confirm with the organisers.
   - The submission deadline is **20 Oct 2026**.
3. **Eligibility:** past editions were student-only. The user must confirm the team qualifies.
4. **Data-extraction defence and suite** (§3 I). This is new.
5. **Prior art to add** to v2 §4.1 and §9:
   - MYbank 百灵2.0: an agent building financing plans for about 42M merchants, using MYbank products only;
   - MYbank AI票据管家;
   - Xero JAX Cash Flow Actions (beta, Jul–Aug 2026);
   - Cerebro Capital;
   - Capitalise;
   - Codat Working Capital Insights.

   Novelty line: "none we found is owned by the supplier and bounded by its own mandate across both debt books."
6. **银票 on the funding menu** (§3 G).
7. **Policy facts:** 24号 and 424号 are both issued (dates in §3 K). Replace "the September 2026 supporting rule remains a draft" wherever it refers to these.
8. **Keep the v2 §3.2 pain rows labelled INFERENCE.** Two real SME interviews contradicted "the owner phones the bank when cash looks low".
9. **Past-winner ingredients:**
   - a formula on every verdict;
   - Risk/Verifier agent naming;
   - hallucination filtering through spans and abstention;
   - the 微业贷 mock borrower file;
   - execution evidence.
10. **Rounding (fix before freezing the golden vectors).** Some v2 totals don't equal the sum of their displayed parts:
    - ¥841.64 + ¥1,871.30 = ¥2,712.94, but v2 says ¥2,712.95;
    - ¥1,800.30 + ¥841.64 = ¥2,641.94, but v2 says ¥2,641.95.

    Write one rounding rule as an ADR: when interest rounds to the fen, and the rounding mode. Then regenerate every golden value. v2 §6.4 mentions a "fixture script" that is in neither folder; ask the user for it.

## 5. Tech stack (final)

| Layer | Choice | Notes |
| --- | --- | --- |
| Web | Next.js + TypeScript, Tailwind, shadcn/ui, Recharts, TanStack Query | Chinese and English. **The UI never computes money**; it only displays server-formatted values |
| API types | `openapi-typescript`, generated from FastAPI's OpenAPI schema | No drift between front and back end |
| Backend | Python 3.12, FastAPI | Tooling: `uv`, `ruff`, `mypy` |
| Validation | Pydantic v2 with `strict=True` and `extra='forbid'` | The model returns structured JSON; every obligation has a span, or the compiler abstains |
| Money | **Integer fen everywhere**; Decimal only at input and output, with the ADR rounding rule; never float | Postgres `BIGINT`; JSON as ints or strings; rates in basis points |
| Database | PostgreSQL (plain, **no** Supabase Auth or Storage), SQLAlchemy 2, Alembic | Operations table is append-only and hash-chained, with idempotency keys |
| Language model | Your own adapter with **two backends**: Claude (`claude-sonnet-5` default, `claude-opus-5-5` for hard compilations) and a China-reachable model (Qwen or DeepSeek) | Compiled results are cached for all fixtures. Log the model ID and prompt version on every call. The model is used **only** for compilation and verbalising |
| Optimiser | Plain Python grid search | Milliseconds; no solver; **no Redis, Dramatiq or RQ** |
| Signing | Ed25519 via PyNaCl | Owner-signed mandate |
| Files | pypdf or PyMuPDF (AGPL, fine for an open repo), python-docx, openpyxl | Intake and the borrower file |
| Tests | pytest, hypothesis, httpx, Playwright | hypothesis covers money invariants, cap and cap + 1 fen. httpx drives `/nl`. Playwright runs the full scripted demo. Recorded model responses mean CI never calls the API. Injection and extraction suites are driven from YAML |
| Logs | structlog JSON | A trace ID links offer → compile → verdict → operation. Exported as the execution-evidence submission |
| Deploy | **One Docker Compose stack** (web + api + postgres) on **one VM in Hong Kong or Singapore** | The venue or the judges' harness may sit in mainland China, where Vercel and foreign model APIs may be unreachable (UNVERIFIED; test early). Keep a recorded demo video as the fallback |

## 6. Architecture and security design

**Four roles, each with its own Postgres role and least privilege:**
- **Compiler** (the language model). It reads offers and term sheets and writes to `proposals` only. It holds **no secrets**: the mandate values, reservation values, funding menu and other buyers' terms never enter a prompt.
- **Engine and verifier** (deterministic). They read typed rows only and never free text. They project, evaluate and emit verdicts with reasons.
- **Executor.** It is the **only** writer to `commitments` and `operations`. It checks the tier, the mandate signature, the nonce, the expiry and the idempotency key.
- **Kernel.** The mock buyer agent and mock lenders. Outbound replies are template-filled, never free-generated with access to secrets.

**Invariants** (v2 §13 "safe claims" plus the additions):
- No model output alone can commit, borrow or move money.
- Only the owner adds funding sources.
- Contingent concessions count at their maximum; uncommitted facilities count as zero.
- Tier-3 actions are always refused.
- Data-extraction attempts are refused and logged.

**Tables:**
- `mandates`
- `facilities`
- `counterparties`
- `offers`
- `proposals`
- `obligations`
- `projections`
- `verdicts`
- `commitments`
- `operations` (append-only, hash chain)
- `approvals` (Tier-2 queue)
- `llm_calls` (audit)
- `evidence_exports`

**Endpoints:**
- `POST /nl`
- `POST /offers`, `POST /offers/{id}/compile`, `POST /evaluate`
- `POST /facilities/compile` (term sheet)
- `POST /router/plan`
- `POST /capex/evaluate`
- `POST /borrower-file`
- `POST /operations` (executor only)
- `GET /approvals`, `POST /approvals/{id}`
- `GET /trajectory`, `GET /ledger`, `GET /audit`
- `POST /mandate` (signed)
- `POST /demo/reset`
- `GET /evidence`

Reshape all of these to the Topic E rules docx.

**Repo:** a new standalone git repo, **not** inside `/Users/ianpong/Hackathons/SZ_Research/`, which is research only.

```
termsledger/
  apps/web/                    # Next.js, 7 screens + approvals + audit + evidence
  services/api/termsledger/
    money.py                   # fen arithmetic, ADR rounding rule
    engine/                    # trajectory, forward-liability, debt ledger, conservative/expected modes
    covenants/                 # DSCR, leverage, clean-down per facility definition
    router/                    # Debt Desk grid search, marginal cost, break-even
    capex/                     # NPV, payback, structures
    compiler/                  # LLM adapter (claude + qwen/deepseek), prompts, schemas, cache, term-sheet mode
    verifier/                  # predicates, verdict codes, formulas
    negotiation/               # counter generation, bounded rounds
    executor/                  # tiers, nonces, idempotency, append-only hash-chained ops, circuit breaker
    kernel/                    # buyer agent + mock lenders
    aftersign/                 # statutory due dates, late interest, 确权 draft (P2)
    borrowerfile/              # 微业贷-style mock file
    harness/                   # /nl, scenario runner CLI, evidence export
    migrations/                # Alembic
  fixtures/                    # v2 fixture JSON, golden vectors, 12 worked examples, held-out offers, router scenarios, injection + extraction YAML
  tests/
  infra/docker-compose.yml
  docs/                        # v2 docx + extracted text, CONTEXT.md, ADRs, security self-assessment, tech doc, deck
```

## 7. Golden values (synthetic; from v2 §6–7)

**Regenerate these under the rounding ADR first** (§4 item 10).

| Quantity | v2 value |
| --- | --- |
| Full early-pay discount, 1.2% on ¥420,000 | ¥5,040.00 |
| v1.0 optimum: line ¥150k + partial early pay on ¥212,550.61 face | ¥3,392.25 |
| v2.0 optimum: line ¥150k + invoice financing ¥210k for 30 days | ¥2,712.95 (parts ¥841.64 + ¥1,871.30) |
| Break-even early-pay discount | 0.88% |
| Terms 45→60 days on ¥420k/month: extra receivables | ¥207,123.29 |
| 12-month funding cost of the extension, committed marginal source | ¥22,455.62. Notional line basis ¥13,255.89; expected plan ¥11,052.30 |
| Forward ledger vs cap | ¥26,455.62 vs ¥5,000 → REJECT; RESERVE_BREACH@day 47 (curable at ¥1,871.30 a month) |
| Covenants after the extension is funded | DSCR 1.92×, leverage 1.72× (base 2.00× and 1.53×) |
| Counter A | ≤¥211,800 at 0.85%: ¥2,641.95 total |
| Counter B | 60 days with a 0.45% price adjustment: ¥1,890 per invoice vs ¥1,871.30 funding cost |
| Capex: ¥600k machine, +¥22k/month from month 4, 5 years, 10% hurdle | NPV ≈ ¥380,886; payback month 31 |
| Capex: 18-month loan at 5.6% | ¥34,830.60/month; DSCR 1.13× → REJECT month 1 |
| Capex: 36-month loan at 5.6% | ¥18,144.62/month; DSCR 1.43× / 1.77×; interest ¥53,206.17 → SELECTED |
| Capex: 48-month lease at 7.2% | ¥14,423.49/month; interest ¥92,327.34; ¥39,121.17 dearer |
| Capex leverage | 2.08× (2.28× if the 60-day terms are also funded) |

**All 12 worked examples in v2 §8 are mandatory test cases.**

## 8. Blockers: ask the user

1. **The Topic E rules docx** (`international-topics-rules-en.docx`, on the official 2026 site; see `research/fintechathon_winners_2026-09-30/sources.csv`). It has **not been read**, because downloads need the user's permission. It likely defines the scripted tasks and the harness interface, which is 40% of the score.
2. **Team:** eligibility (student-only?), team size and roles. v2 §15.4 suggests 4 roles.
3. **Repo location and name.**
4. **API keys** for Anthropic and for Qwen or DeepSeek, supplied as environment variables. Never commit them.
5. **VM provider** in Hong Kong or Singapore, and a reachability test from mainland China.
6. **The v2 fixture script** (for the rounding reconciliation).

## 9. Context only: the startup track (not this agent's job)

TermsLedger is judged a strong hackathon project but a weak startup. The user's startup direction is a **missing-claim detection engine** for project billers, validated by hand, with a decision on 17 Oct 2026. It may later reuse TermsLedger's compiler.

The research is in `/Users/ianpong/Hackathons/SZ_Research/`, starting with `CURRENT_IDEA_BRIEF.md`. The two Claude Docs still say "hackathon = detection demo"; that is outdated. **Keep the codebases separate.**

## 10. Build order: everything, core first

Build a **thin vertical slice first** (Scene 1 end to end), then widen. That way any cut in §11 removes a finished extra, never a half-built core.

| Dates | Build | Checkpoint |
| --- | --- | --- |
| 1–3 Oct | Repo and Docker Compose; `docs/` (v2 + extracted text, CONTEXT.md, ADRs including rounding); fixture JSON; golden vectors; read the Topic E rules | Golden-vector tests exist and fail |
| 4–7 Oct | money, engine (both modes), debt ledger, covenants, verifier with all verdict codes; thin compiler for offers; executor; a thin `/nl`; the Inbox, Trajectory and Verdict screens | **Scene 1 end to end.** E3 green |
| 8–11 Oct | Router (all menu sources incl. 银票; multi-step expected plans), negotiation with Counters A and B, buyer kernel, NO DEAL, commitment ledger, Funding and Ledger screens, injection and extraction suites | **Scene 2 end to end.** E4, E9 and E10 (non-capex) green |
| 12 Oct | **Checkpoint:** if Scenes 1–2 are not solid, start the cut ladder | |
| 12–15 Oct | Capex mode and screen (Scene 3); term-sheet compiler; borrower file (微业贷 mock); approvals queue; concurrency; failure branches; circuit breaker; Chinese and English; audit view; E2 held-out evaluation; E5 | **Scene 3 end to end.** Playwright demo green |
| 15–16 Oct | After-signing extension (确权, late interest, 424号 variant); multi-agent presentation; evidence page; E8 | |
| 17–18 Oct | Demo video (≤5 min), deck (≤10 min), technical document, security self-assessment, execution-evidence export | **Checkpoint:** feature freeze |
| 19–20 Oct | Buffer; submit | No new features |

## 11. Cut ladder (only if a checkpoint is missed; drop from the top)

1. After-signing extension and the 424号 variant (K)
2. Multi-agent presentation layer and the evidence page
3. E8 blind explanation
4. Chinese and English UI (English only)
5. Circuit breaker, concurrency and failure branches
6. Approvals-queue UI (keep Tier-2 as a refusal plus a message)
7. Borrower file as DOCX or PDF (keep JSON)
8. Term-sheet compiler (enter facilities as typed records)
9. Capex mode and Scene 3
10. Multi-step expected plans in the router

**Never cut:**
- the mandate and tiers;
- the offer compiler with spans and abstention;
- the engine, verifier, router (committed sources), counters and executor ledger;
- the injection, extraction and escalation suites;
- `/nl`;
- the golden vectors;
- the required deliverables.

## 12. Suggested skills for the next agent

- **`init`:** CLAUDE.md for the new repo.
- **`writing-for-agents`:** keep CLAUDE.md and AGENTS.md tight.
- **`claude-api`:** **before** writing the model adapter: model IDs, structured outputs and tool use, prompt caching.
- **`domain-modeling`:** CONTEXT.md and ADRs (fen, rounding, conservative mode, the role split, verdict codes).
- **`codebase-design`:** module seams between engine, compiler, verifier, executor and kernel.
- **`impeccable`:** the screens and the demo flow.
- **`dataviz`:** trajectory, forward-liability, debt and covenant charts.
- **`security-review`:** after the executor, harness and security suites.
- **`code-review`** and **`simplify`:** at each checkpoint.
- **`diagnosing-bugs`:** golden-vector mismatches.
- **`run`:** launch, screenshot and verify the demo.
