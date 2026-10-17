# FLOW (TermsLedger): test cases

Deliverable 4 supporting document. A catalogue of the automated tests by area: what each proves, where it is, how many there are and how to run it. Counts were measured on 16 Oct 2026 at commit `0f92d433` (`dev`), by `pytest --collect-only -q` and `playwright test --list`. Repository: https://github.com/peachoolongtee/smu2sz

Everything runs offline: `LLM_MODE=cache` replays recorded model outputs, the books are synthetic fixtures, and no test needs an API key or the network. Run the API commands from `services/api`, the web commands from `apps/web`.

## 1. Last full gate (dev `0f92d433`, 16 Oct 2026)

| Suite | Result |
| --- | --- |
| API (`uv run pytest`) | **8,556 passed, 1 known failure** (#161, a machine-dependent hash). 8,598 tests are collected, so the other 41 are skips or deselected |
| Playwright, mock project | **435/435** |
| Playwright, live project | **141/141** |
| Web unit (`pnpm test:unit`) | **163 passed** |
| `tsc` (`pnpm typecheck`) and `eslint` (`pnpm lint`) | clean |

These are the figures recorded in the merge commit of `dev` at `0f92d433`. Re-checked in this session (Windows, 16 Oct): the collection counts below; web `lint`, `typecheck` and `test:unit` (163 pass); the API subsets named in section 4; and the Playwright specs named there. We did not repeat the 25-minute full API gate or the full e2e gate.

## 2. API tests (pytest, `services/api/tests/`)

8,598 tests collected in 333 files, in 12 areas. Every file belongs to exactly one row.

| Area | What it proves | Files (under `services/api/tests/`) | Tests |
| --- | --- | --- | --- |
| Engine: money, books, clock, commitments, covenants | Integer-fen money with the stated rounding; amortisation, charges, concessions and dated valuation against hand calculations and the independent golden oracle (`fixtures/golden/`); DSCR for bullet loans; the books that accepted commitments change; the simulated clock and partial settlement; the commitment lifecycle and terms hash; covenant ratios and clean-down | `financial/`, `books/`, `clock/`, `commitments/`, `covenants/`, `test_money.py`, `test_fixtures.py` | 427 |
| Verifier | The deterministic verdict (ACCEPT, COUNTER, REJECT, needs-owner) and its reason codes, formulas and counters, for the worked examples and for properties of the rules; the ADR-0005 autonomy proof | `verifier/` | 262 |
| Funding router and lending | The grid-search router over committed facilities matches an independent oracle (differential and cash-path tests), planner and executor agree, router rules, marginal cost of funds, break-even, lender eligibility | `funding/`, `lending/` | 1,161 |
| Executor and operations | Every operation is typed and checked against the signed mandate; Tier 1 / 2 / 3; approvals and the circuit breaker; idempotency, nonces and replay; the hash-chained log; bank effects and partial settlement; documents decided by the owner only | `operations/` (except the red-team files, in Security) | 273 |
| Mandate and permission tiers | The mandate's signature, revocation, expiry and version; each predicate; the tier of each operation kind; a tampered or foreign-signed mandate refuses everything | `mandate/` | 74 |
| Persistence, hash chain and concurrency | The in-memory and SQL stores obey one contract; the append-only log and its chain; compare-and-swap on the log head; migrations 0001 to 0008 on SQLite; two-process invariants | `persistence/` (except `test_tamper_and_sql.py`), `concurrency/` | 152 |
| Compiler and ingest | A buyer's text becomes typed obligations with exact source spans; paraphrases, Chinese and English, early-pay paths, term sheets; anything not fully read fails closed to the owner; text extraction from Word, PDF and text | `compiler/` (except contract and injection files), `ingest/` | 619 |
| Contracts | Reading a signed buyer contract or lender agreement: terms with their quoted clause, cross-checks, the golden-equality set, held-out scoring harness, the document routes (owner only, bound to the text hash), contract records on the store | `contracts/`, `compiler/test_contract*.py`, `compiler/test_eval_contracts.py`, `compiler/test_bond_and_price_lines.py`, `compiler/test_late_interest_party.py`, `api/test_documents.py`, `api/test_demo_documents.py`, `api/test_document_decision_atomicity.py`, `persistence/test_contract_records.py`, `operations/test_decide_document.py` | 203 |
| NL chat | `POST /nl`: the 22 intents, classification and abstention, plans proposed first and run only on "go ahead", consent (a closed affirmative command), correction, clarification, the agent speaking first, page context, the buyer channel, Chinese and English | `nl/` (except `test_security.py`) | 1,099 |
| Security and red team | The 259-attack catalogue (126 API, 133 chat) with zero harm; the five red-team rounds' fixes; authority boundaries; the egress guard against leaking protected figures (canaries, renderings, word numbers); injection and lexicon evasion; intake cap and the buyer's daily budget (R-10); demo credentials off by default (R-11, SEC-07); capex attacks; tamper and SQL | `security/`, `egress/`, `operations/test_redteam_*.py`, `operations/test_runtime_hardening.py`, `operations/test_sec02_one_agreement.py`, `operations/test_sec_authority_boundaries.py`, `nl/test_security.py`, `compiler/test_injection.py`, `compiler/test_lexicon_evasion.py`, `api/test_capex_attacks.py`, `api/test_capex_security.py`, `api/test_intake_cap.py`, `persistence/test_tamper_and_sql.py` | 1,526 |
| Certification and evaluation harness | The 231-item language-boundary certification (no wrong material outcome); the evaluation suites run on small inputs; the funding oracle and alternate held-out sets | `certification/`, `evals/` | 65 |
| Product modules on the engine | Alerts with executable cures and reconciliation; capex (NPV, payback, structures); the borrower file; what-if; the strategy surfaces (envelope, price curve, collections, stress, concentration); the buyer kernel and negotiation; the decision record; the shadow pilot; the buy side's financial health | `alerts/`, `capex/`, `borrower_file/`, `whatif/`, `strategy/`, `counterparties/`, `decisions/`, `pilot/`, `health/` | 1,159 |
| API routes | Every route end to end through the FastAPI client: owner and agent auth, Home, Deals and the decision queue, approvals, receivables and receipts, customer overview and inputs, the demo story and busy books, exposure and the picture caches, language and wording, the deal tracker | `api/`, `deals/` (except the files listed under Contracts and Security) | 1,578 |
| **Total** | | | **8,598** |

The per-file counts come from `uv run pytest --collect-only -q`, which prints `file: count` lines.

## 3. Web tests

| Suite | What it proves | Files | Tests |
| --- | --- | --- | --- |
| Web unit (`pnpm test:unit`, Node's test runner) | The UI never computes money: mocks match `fixtures/golden/golden_values.json`; adapters rename and copy server strings only; retry and timeout rules; presentation fallbacks; chat prompts; page-level rules for Home, Deals, tracker and collections | 23 files `apps/web/scripts/*.test.mjs` (listed in the `test:unit` script) | 163 |
| Playwright, mock project (`pnpm test:e2e:mock`) | The whole UI on recorded mocks, no backend: the guided Demo, Home, Deals, Receivables, Cash and funding, Approvals, Activity, customer overview, chat, language switch, tour, accessibility (axe), colour, responsive layouts and the phone project | 39 spec files `apps/web/e2e/*.spec.ts` | 496 listed (439 desktop, 57 phone) |
| Playwright, live project (`pnpm test:e2e:live`) | The same demo walk and the live-only checks against a real in-memory API: owner sign-in, chat, documents, adapters' contract tests, the slow-network states, trust and the security record | 18 spec files | 191 listed |

"Listed" is what `playwright test --list` shows. Some tests skip themselves at run time (the strategy specs run only with `E2E_STRATEGY=1`, and a few conditional skips), which is why the gate ran 435 of the 496 listed in mock and 141 of the 191 in live. `playwright test --list` counts with `E2E_TARGET=all` come to 687 (496 + 191).

## 4. How to run each

Set up once. `uv sync` in `services/api`, `pnpm install` and `pnpm exec playwright install chromium` in `apps/web`. The environment below keeps every run offline and in memory; `TERMSLEDGER_NO_DOTENV=1` stops the API reading a repository `.env`:

```bash
export TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory LLM_MODE=cache DEMO_MODE=1 SKIP_PERF_BENCH=1
```

| Area | Command (from `services/api` unless stated) |
| --- | --- |
| Everything in the API | `uv run pytest` (about 25 minutes) |
| Engine | `uv run pytest tests/financial tests/books tests/clock tests/commitments tests/covenants tests/test_money.py tests/test_fixtures.py` |
| Verifier | `uv run pytest tests/verifier` |
| Funding | `uv run pytest tests/funding tests/lending` |
| Executor and operations | `uv run pytest tests/operations` |
| Mandate | `uv run pytest tests/mandate` |
| Persistence and concurrency | `uv run pytest tests/persistence tests/concurrency` (the PostgreSQL cases of `tests/concurrency` run only when `TERMSLEDGER_TEST_DATABASE_URL` is set) |
| Compiler and ingest | `uv run pytest tests/compiler tests/ingest` |
| Contracts | `uv run pytest tests/contracts tests/compiler/test_contract.py tests/compiler/test_contract_checks.py tests/compiler/test_eval_contracts.py tests/api/test_documents.py` |
| NL chat | `uv run pytest tests/nl` |
| Security and red team | `uv run pytest tests/security tests/egress tests/operations/test_redteam_b.py`, then the attack catalogue: `uv run python -m app.security.attacks --report` (rewrites `evals/security/latest_report.*`) |
| Certification | `uv run pytest tests/certification`, then from the repository root `PYTHONUTF8=1 uv run --project services/api python scripts/certify_language_boundary.py --backend cache` (also `--backend fake`; `--backend live` needs an API key and is pending) |
| API routes | `uv run pytest tests/api tests/deals` |
| Scripted `/nl` tasks (49) | from the root: `PYTHONUTF8=1 uv run --project services/api python scripts/run_scenarios.py --inproc --out OUT_DIR`, then `python3 scripts/verify_evidence.py OUT_DIR/evidence/S01_scene1_counter_accept.jsonl` |
| Web lint, types, unit (from `apps/web`) | `pnpm lint && pnpm typecheck && pnpm test:unit` |
| Playwright mock (from `apps/web`) | `pnpm test:e2e:mock` (builds the app and serves it on :3100; `E2E_PORT` moves it) |
| Playwright live (from `apps/web`) | `pnpm test:e2e:live` (needs `uv`; starts its own in-memory API on :8000 and a web build on :3000; `E2E_API_PORT` and `E2E_LIVE_PORT` move them). With `E2E_STRATEGY=1` the strategy specs run too |
| One Playwright file | `E2E_TARGET=mock pnpm exec playwright test shell.spec.ts` |

Checked in this session (Windows, 16 Oct 2026): `uv run pytest tests/mandate tests/verifier tests/security/test_buyer_budget.py tests/compiler/test_eval_contracts.py tests/contracts tests/certification` gave 397 passed in 129 s (the collected count of those paths is 397); `pnpm lint`, `pnpm typecheck` and `pnpm test:unit` passed; `E2E_TARGET=mock pnpm exec playwright test shell.spec.ts demo.spec.ts` gave 25 passed, 2 skipped; `uv run python -m app.security.attacks --report` printed zero harm in every metric (126 API attacks plus 43 + 64 + 26 chat attacks per entry point, `attacks_with_harm` 0); the cache-backend language-boundary certification finished with `WRONG_MATERIAL=0` over 231 items; `scripts/run_scenarios.py --inproc` passed 49/49 and every chain verified.

## 5. Known failures and flakes

| Issue | What | Status |
| --- | --- | --- |
| #161 | `tests/books/test_modules_on_books.py::test_no_commitments_trajectory_and_router_plan_are_unchanged` compares a trajectory and router-plan hash that differs between machines (`24f1dc649f4363e3` against `252b9812e99b4aee` on Linux CI). It is the 1 failure in the 8,556-passed gate. The issue originally listed three more API failures (a red-team negotiate test and two Chinese-name tests); they were not failing in the gate | open |
| #157 | Playwright specs that are broken or flaky on the same tree. In `live.spec.ts`: "a write that lost a race is sent once more after the hint, and succeeds" and "a second conflict is not retried again" (both wait on a button the round-two Approvals card renamed; the second also flakes); "the EX01 verdict shows each early-pay discount as a yearly rate". In `demo.spec.ts`: a double-click test at 390 px that races the 400 ms arming window, and the engine-views rail count. `a11y.spec.ts` on /approvals is flaky (#156). In our run of `live.spec.ts` alone on 16 Oct (after the gate), 26 passed and the first two of these specs failed | open |

Per the issue, the #157 specs fail on a stale expectation (a renamed button, a longer list) or a timing window in the test. To see why a Playwright spec failed, run it alone and open its `trace.zip` with `pnpm exec playwright show-trace`.
