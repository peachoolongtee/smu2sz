# FLOW feature inventory, gaps and the video plan

Built from the code on `dev` at `3bd440a0` (17 Oct 2026), not from memory. Each claim was read in the code; the
own-books and buyer-channel claims were also run through the API in process (TestClient, `DEMO_MODE=1`,
`DATABASE_URL=memory`, `LLM_MODE=cache`, `TERMSLEDGER_NO_DOTENV=1`, the `pnpm demo` flags). Paths are relative to the
repository root; web paths are under `apps/web`, API paths under `services/api`.

**Status words.** *works*; *demo books only* (works on the golden demo books from `pnpm demo`, not on books opened with
the setup wizard); *flag off* (behind a flag that `pnpm demo` leaves off); *partial*; *known issue* (with the issue or
the code that shows it). **Tech doc** says whether `docs/deliverables/technical_document.md` mentions the feature.

**Books.** *Golden books*: `pnpm demo` (scenario `golden_sme`). *Own books*: `pnpm demo:blank`, then the setup wizard.

## 0. Flags: what `pnpm demo` turns on

`scripts/demo.mjs` (and `scripts/dev-api.sh`) start the API with `DEMO_MODE=1`, in-memory books, cached readings, and
the web app with `NEXT_PUBLIC_API_MODE=live`, `NEXT_PUBLIC_DEMO=1`.

| Flag (where read) | Default | Under `pnpm demo` | What it gates |
| --- | --- | --- | --- |
| `FEATURE_TERMS_GUARD`, `FEATURE_DEBT_DESK`, `FEATURE_BUYER_NEGOTIATION`, `FEATURE_ALERTS`, `FEATURE_EXPECTED_PLANS`, `FEATURE_CONTRACTS`, `FEATURE_SECURITY_SCENES`, `FEATURE_CAPEX`, `FEATURE_BORROWER_FILE` (`app/config.py`) | on | on | evaluate/negotiate, router, alerts and reconciliation, documents and deals, the security scene's fixtures, capex quick check, borrower file |
| `FEATURE_ENVELOPE`, `FEATURE_PRICE_CURVE`, `FEATURE_COLLECTIONS_WORTH` | off | **on (API)** | the strategy MVP routes; the web hides them anyway (next row) |
| `FEATURE_EXPOSURE` | off | **on** | buyer exposure, Business consequences, Cash `?stress=`, the customer inputs routes |
| `FEATURE_CAPEX_CONTRACTS` | off | **on** | the buy side: Capex hub, purchases, financial health, loan eligibility, long-term plans |
| `FEATURE_CONTRACT_TERMS` | off | **on** | "Set up in my books" from a confirmed customer contract (ADR-0014) |
| `FEATURE_CUSTOMER_ECONOMICS` | off | **off** | the six economics fields on `/customers/[id]/inputs` |
| `FEATURE_PILOT_JOURNAL` | off | **off** | `GET/POST /pilot/journal` |
| `NEXT_PUBLIC_STRATEGY_MVP` (web, `lib/config.ts`) | off | **off: `scripts/demo.mjs` does not set it** | hides, even though their API flags are on: the cash price sentence on Cash (`cash-price-sentence`), "Before they ask" (envelope) on the Deals Cash impact tab (`components/deals/before-they-ask.tsx`, `decision-pane.tsx:817`), the envelope packages panel (`components/deals/flow/investigate.tsx`), every `useStrategyAsync` read (`lib/use-async.ts:61`; the receivable worth cells of `components/business/strategy.tsx`), and the pilot journal on Activity (`app/activity/page.tsx:98`) |
| `DEMO_MODE` (`app/config.py`) | **off** (SEC-07) | on | demo credentials, seeded books, `POST /demo/reset`, `/demo/bank-receipt`, the setup wizard's open step, `/docs` |

Collections worth is visible in no live build even with `NEXT_PUBLIC_STRATEGY_MVP=1`: only `app/receivables/legacy.tsx`
reads it, and that page loads only when `GET /receivables` is missing (`app/receivables/page.tsx:65`).

## 0b. Own books against golden books: what the story needs (verified in process)

- **Buyer channel keys.** The setup wizard names customers `BUYER-1`, `BUYER-2`, … in the order entered
  (`app/setup/__init__.py:514`). The demo channel keys exist only for `BUYER-1` and `BUYER-2` (`app/api/auth.py:28`), so
  the **first two customers** of own books can send buyer messages; a third cannot.
- **Simulated buyer.** Profiles are keyed by id (`fixtures/counterparties/buyers.yaml`: `BUYER-1`, `BUYER-1-HARDLINE`,
  `BUYER-2`; `app/api/decide.py:simulated_profile`). On own books the first customer negotiates against the **golden
  Foshan profile** (its invoice ¥420,000 due day 32). **Defect:** in a NO DEAL run on own books the simulated buyer's
  counter text named "invoice RCV-A (¥420,000.00)", an invoice that does not exist there (own books call it `RCV-1-1`).
  A customer without a profile gets 409 `NO_SIMULATED_BUYER` ("Copy the message to the buyer instead").
- **Readings.** Recorded (cache) readings exist for the golden texts only; on own books the same message is read by the
  rules grammar. EX01 reads fine on books with one open Foshan invoice; with three Foshan invoices it asks the buyer
  which invoice (NO_VERDICT).
- **The verdict depends on the books' shape.** Same EX01 text through `POST /nl` with `demo-buyer-1-key`:
  - Golden books: REJECT with Option A (¥260,000 at 0.85%) and Option B (55 days + 0.30%); the cooperative buyer accepts A.
  - Own books shaped like golden (cash ¥400k, line ¥150k, invoice financing ¥350k, Foshan ¥420k due day 32, payroll
    ¥340k **once**, equipment loan ¥45k monthly): REJECT with Option A (¥180,000 at 0.85%) and Option B (60 days +
    0.45%); the cooperative buyer accepts A; ¥146,530 funded; `POST /demo/bank-receipt` posts the early payment and
    reconciliation reports it MATCHED; after the clock reaches day 34 the past-due alert, the reserve alert, the alerts
    turn ("What needs my attention?") and Ask FLOW all answer.
  - The same books with payroll **monthly**: REJECT with **no counters**, because no standing funding plan is admissible
    ("No price-adjustment counter: … no committed plan keeps cash at the reserve"); the buyer reads "We are not able to
    accept these terms."
  - With larger limits (line ¥300k, invoice financing ¥1m): only a terms counter; the simulated buyer refuses: NO DEAL.
- **The cure depends on timing.** On golden books day 34 offers the ¥200,000 invoice-financing cure (¥1,782.19, 32.5% a
  year, above the 15% ceiling, so "go ahead" queues it for approval). On the golden-shaped own books the breach starts on
  day 34 itself and financing lands three days later, so the alert says "No committed facility can cure it".
- **Receipts.** `POST /demo/bank-receipt` books only an **agreed early payment** that is still awaited (409
  `NO_PROMISED_RECEIPT` otherwise).
- **Demo chat labels.** The Demo shell's buyer picker labels `BUYER-1` "Foshan Home Retail" and `BUYER-2` "Dongguan
  Office Supplies" from the dictionary (`lib/dictionary.ts:959`), whatever the owner named them in setup.
- **Capex on own books** is partial: the quick check's financed structures name `FAC-ETL`/`FAC-LEASE`, which only the
  seeded scenarios have, so only "cash + credit line" can pass and Apply and the borrower file stay disabled (section 10).
- **The Demo story** runs on golden books only; on own books the page says so and offers Restore (section 11).

**Conclusion for the video.** Record the negotiation, funding, late-payment and cure story on the golden books. Show the
setup wizard as a short clip on blank books. Own books can carry the story only with figures prepared and rehearsed in
advance (the shape above).

## 1. Setup

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Landing page | "Access FLOW" for a known browser, else "Join FLOW now!" (to `/setup`) and "Preview"; links to the guided demo and Trust | `/welcome` (`components/landing/landing.tsx`); `lib/pre-hydration.ts` sends a first visit from `/` here once per tab | none | open `localhost:3000` in a fresh tab | **none** (specs bypass it with `tl-welcomed`) | works | **no** |
| Sign-in | The owner types the token; kept for the tab only; `pnpm demo` prefills `demo-owner-token` | `components/owner-auth.tsx`, `lib/auth.ts`; `app/api/auth.py require_owner` | none | header "Owner sign-in" | `tests/security/test_route_policy.py`; `e2e/approvals.spec.ts` | works | yes (§04) |
| Set up your books: welcome | Three ways in: "Type it in" (Start setup / Continue setup), "Upload the template" (**"Coming soon", not built**), "Upload your contracts" (step 3 with the picker open) | `/setup` (`components/setup/welcome.tsx`); also Home while the books are blank | DEMO_MODE | `pnpm demo:blank` → Join FLOW now! | **no e2e drives the wizard UI** | partial (spreadsheet route not built) | §05 one line |
| Step 1 · Business and cash | Company name (≤ 80), What you make or sell (**collected and dropped**: `build_books` ignores `what_you_sell`), Books start on (within 400 days of today), Cash in the bank, Sales a month, Costs a month (a monthly loss is an error) | `components/setup/steps.tsx`; draft in localStorage `tl-setup-draft`; `POST /setup/preview` on Next | DEMO_MODE | type and Next | `tests/api/test_setup_books.py` (≈45) | works | **no** |
| Step 2 · Credit lines and loans | Ways to borrow: Name, Kind (credit line, invoice financing, loan to apply for), Limit, Borrowed today, Cost a year, Fee per 30 days, Cash arrives in (days), Days a year at zero (clean-down), Agreed with lender; "Fill from an agreement". Loans you're already repaying: Lender, Still owed, Repayment, How often, Next payment, Interest. No input for share advanced (80%) or loan term (12 months) | `steps.tsx`, `doc-picker.tsx` | DEMO_MODE | "Fill from an agreement" with `fixtures/contracts/mb-cl-2026-031-credit-line-agreement.pdf` | `test_setup_books.py` | works; partial (two defaults not editable) | **no** |
| Step 3 · Customers and invoices | Customer name; Repeating contract (amount, every N days, pays within, next invoice); Invoices sent and not fully paid (sent on, amount, terms, paid so far, financed, financed by); "Fill from a contract" shows "Invoice n of N sent" | `components/setup/step-customers.tsx`; `GET/POST /setup/documents` (≤ 10 held in memory, lost on restart) | DEMO_MODE | "Fill from a contract" with `fixtures/contracts/fhr-2026-07-supply-agreement.md` | `test_setup_books.py` (incl. a contract confirmed under the new customer) | works | **no** |
| Step 4 · Bills coming up | Quick add Payroll, Rent, Supplier payment, Tax, Something else; What, Type, Amount, Next on, Repeats (once, month, quarter, year), Until; written out as dated flows for 3 years | `steps.tsx` | DEMO_MODE | Quick add → Payroll | `test_setup_books.py` | works; the footer "You can add more bills any time after setup" is **not implemented** (no operation adds a bill) | **no** |
| Step 5 · Your limits | Minimum cash; borrow alone up to N% a year (15); discounts and rebates a year (¥5,000); ask me above (¥100,000); valid days (90, 30–365); loan cover (1.25×) and debt (3×); the fixed "FLOW will never…" list | `steps.tsx` | DEMO_MODE | defaults | `test_setup_books.py` | works; the footer "Change them later under Account › Your limits (needs a new signature)" is **not implemented** (`/limits` is read-only; CHANGE_MANDATE is Tier 3) | **no** |
| Step 6 · Review and open | Errors with "Go to step n"; five tiles (cash, can borrow, owed to you, bills next 30 days, minimum cash); "First look · what Home will say" 90-day chart; warnings; "Sign and open my books" with the token re-typed; "Start again from blank books" | `components/setup/step-review.tsx`; `POST /setup/open` (one `OPEN_BOOKS` entry heads a fresh chain; mandate v1 signed; documents read in setup confirmed under the new ids) | DEMO_MODE | type `demo-owner-token` → Sign and open my books | `test_setup_books.py`; `e2e/live.spec.ts:729` posts `/setup/open` through the API only | works; refused once the books hold any activity (BOOKS_ALREADY_OPEN) | §05, Table 11 |
| Demo books against own books | Books are "blank", "own" or "demo" (`GET /setup/status`); own books hide the "Demo data" badge; the account menu shows "Your books" | `app/api/setup.py`, `components/app-shell.tsx` | — | — | `test_setup_books.py` | works; **known issue (code read, not run)**: after a `pnpm demo:keep` restart own books are taken for the golden ones on the Demo page and in the evidence header, because `Runtime.hydrate` (`app/api/runtime.py:134-139`) keeps `golden_sme` when the stored scenario is empty | partly |
| Demo scenarios | `golden_sme` (Golden story), `busy` (three customers, six negotiations, an approval, overdue invoices), `short_facilities` (no committed funding can restore the reserve), `blank` (live mode only), `public_sme` (calibrated from a public filing; **API only**, and it is given the golden mandate) | `app/api/read.py:286`, `fixtures/scenarios/*`, `components/demo/books-cards.tsx`; `POST /demo/reset?scenario=` | DEMO_MODE | Demo → Which books? → Load | `tests/api/test_demo_busy.py`, `test_demo_story.py`; `e2e/demo.spec.ts` (blank card not covered) | works | yes (§02 "Alternative books") |
| Launcher modes | `pnpm demo`, `demo:blank`, `demo:keep [--fresh]` (SQLite `.demo-data/flow-demo.db`), `demo:mock` (no setup possible) | `scripts/demo.mjs` | — | — | none | works | yes (§05) |
| Reset and restore | Load other books with a loss dialog; "Restore the main books"; "Reset the books"; own books reset to blank and open `/setup` | `POST /demo/reset`, `POST /demo/restore`; `lib/books-guard.ts`, `components/demo/books-dialog.tsx` | DEMO_MODE or in-memory store | Demo → Operator tools → The books → Reset the books | `e2e/demo.spec.ts`; `tests/api/test_demo_story.py` | works | reset only; `/demo/restore`: **no** |

## 2. Daily view

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Home | Am I safe, what should I do, what will it cost, what waits for me. Cards in order: Refresh; **Company cash outlook** (lowest cash ahead, forecast chart with events rail and plan line, **What we recommend**: plan amount, cost, legs, approval line, "Check funding plan" → Cash, "Compare funding options"); **Your worklist** (Needs you / Waiting / Customers, search, "All deals"); **Cash available today** (reserve bar, funding ring); **Upcoming cash movements** (incl. "Overdue from customers"); **What you are owed, by customer** (donut; a slice selects the customer and shows its panel) | `app/page.tsx`, `components/home/v2/*`; `GET /home` (`app/api/home.py`, `home_v2.py`, `home_hybrid.py`), `GET /worklist`, `GET /customers` | none (stress line: exposure) | `pnpm demo`: reserve breach on day 12 and the ¥3,113.93 plan; Busy books for a full worklist | `e2e/home-v2.spec.ts` (44, mock), `home-v2-states.spec.ts` (live); `tests/api/test_home*.py`, `test_worklist.py` | works on golden and own books; `FixResult` on Home is dead (`fix()` never called there) | routes and the word only; the cards: **no** |
| Cash forecast | The daily cash line against the reserve; 30/60/120 days on Cash | Home `OutlookChart`; Cash `components/business/cash-forecast.tsx`; `/trajectory` engine view (conservative/expected, the fix, covenants; `GET /trajectory`, no `lang`) | none | Home; Demo → Operator tools → Engine views → Cash line | `e2e/cash.spec.ts`; `tests/api/test_read.py`; `/trajectory` has no behaviour e2e | works | yes (§03 item 1) |
| Alerts page | Alerts on today's books with the cure and its cost, and the fix button | `/alerts` (engine view; `components/home/fix-alert.tsx`); `GET /alerts`, `POST /alerts/{id}/act` | alerts (on) | Demo → Operator tools → Engine views → Alerts | `e2e/alerts.spec.ts`; `tests/alerts/test_api.py` | works; English engine text even in Chinese (`title_when` unused) | yes |
| Worklist and rail counts | One list of what needs the owner and what waits; badges on Deals and Receivables; "n approvals waiting" | `GET /worklist`, `GET /nav/counts` | none | Home | `tests/api/test_worklist.py`, `test_nav_counts.py`; `e2e/shell.spec.ts` | works | routes only |
| Language switch | English or 中文 everywhere; the server writes both | account sheet "Language", landing toggle; `lib/i18n.ts` (`tl-lang`), `lib/dictionary.ts`; `t(lang, en, zh)`, `app/api/engine_zh.py` | none | Account → Language → 中文 | `e2e/shell.spec.ts`, `lang.spec.ts`; `tests/api/test_w7_language.py` | works on Business pages; engine views (`/alerts`, `/ledger`, `/trajectory`, Security events) stay English | yes (Table 1); the switch: no |
| Business and Demo modes | Business is the owner's app; Demo adds the synthetic-data strip, the story stepper on every page, the `/demo` story with Operator tools (clock, books, engine views: Signed mandate, Cash line, Debt Desk, Verdict, Ledger, Evidence export, Alerts, Reconciliation, Security), the buyer role in chat and the simulated send on Deals | header Mode switch (`lib/mode.ts`, `tl-mode`), `components/app-shell.tsx`, `components/demo-stepper.tsx` | none | header → Mode → Demo | `e2e/shell.spec.ts`, `demo.spec.ts` | works | partly; the two-shell design: **no** |
| Tours | "Show me around" on twelve pages; opens itself on a first visit | `components/business/tour.tsx` | none | Account → Show me around | `e2e/tour.spec.ts` | works; copy drift ("Three sets of books" shows four; "Run funding plan" is now "Check funding plan") | **no** |
| Navigation | Rail: Home, Deals, Attach deals, Cash & funding, Sandbox, Capex, Receivables, Activity; phone bar without Sandbox and Capex; locked (greyed) on blank books; account: Your limits, Security and evidence, Your books, Show me around, Language | `components/app-shell.tsx` | none | — | `e2e/shell.spec.ts`, `responsive.spec.ts` | works; `/inbox` is reachable only from `/verdict`; `DEMO_NAV` is dead code | **no** (§05 lists the pages without Sandbox) |

## 3. Documents: Attach deals

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Upload and read | Drop a signed contract or lender agreement; FLOW reads it into a proposed record, every term tied to its clause | `/documents` (nav "Attach deals"; `app/documents/page.tsx`), the "Attach a deal" tile on Deals (`components/deals/tools.tsx`); `POST /documents`, `GET /documents`, `GET /documents/{id}` (`app/api/documents.py`), `app/ingest/text.py` | contracts (on) | Golden: Attach deals → "Contract with a buyer", "Foshan Home Retail Co." → `fixtures/contracts/fhr-2026-07-supply-agreement.md` (recorded reading, 18 terms) | `e2e/documents.spec.ts` (readings live only); `tests/api/test_documents.py`, `tests/ingest/test_text.py`; no e2e for the tile | works. Formats: .md/.txt (.markdown on the server only: the browser refuses it), .docx, PDF with a text layer; refused: .doc, scans, photos (no OCR), encrypted PDF; 5 MB, 60 PDF pages, 40 chunks. `DESIGN.md:884` says the tile was left out; the code renders it | formats and the no-OCR limit: yes; the page: named only |
| Counterparty field | "Who it is with": only known companies of the right role (buyer for a contract, lender for an agreement); an unknown name is refused and logged | `app/documents/page.tsx` `UploadForm`; `documents.py:170-187` | contracts | type a partial name | `tests/api/test_documents.py` | works | yes (§04: "Documents are read only for counterparties on the owner's registry") |
| Party check | A contract that does not name the chosen company cannot be confirmed; the companies it names are shown | `app/contracts/parties.py` `with_party_check`; `components/document-review.tsx` (`doc-cannot-confirm`) | contracts | Golden: upload the Foshan contract under "Dongguan Office Supplies Ltd." | `tests/api/test_document_parties.py`, `tests/contracts/test_parties.py`; `e2e/new-customer.spec.ts` (mock) | works; caveats: the set-up step ignores the owner's short names (`terms_setup.py:124`), PARTY_UNCHECKED (no names found, typical of Chinese contracts on the rules path) allows Confirm but blocks "Set up in my books" (`terms_setup.py:274`), documents carried in by the setup wizard skip the check | yes (§03, §04, Table 14) |
| New customer from a document | Add a buyer by name from Attach deals or from the mismatch flag; Tier 2, one ADD_CUSTOMER entry | `NewCustomerPanel` (`app/documents/page.tsx`); `POST /customers` (`app/api/customers.py`) | none | "Shunde Kitchen Supply Co." → "Add … as a new customer" | `e2e/new-customer.spec.ts` (mock only); `tests/api/test_new_customer.py` | works; **trap**: on `pnpm demo:blank`, adding a customer before the setup wizard blocks `/setup/open` (BOOKS_ALREADY_OPEN) until a reset | yes (Tier 2 list, Appendix C) |
| Refile | Move a misfiled reading to the right customer without a new model call | `POST /documents/{id}/refile`; `doc-party-actions` in `document-review.tsx` (buyer contracts only) | contracts | after the party-check block: "File it under Foshan Home Retail Co." | `tests/api/test_new_customer.py` (refile), `e2e/new-customer.spec.ts` | works; a lender agreement can be refiled through the API only | route only (Appendix C) |
| Review screen with clause links | Text with every term highlighted and numbered, each term beside its quote and clause, blanks and flags; clause links from the deal summary | `components/document-review.tsx`, `annotated-text.tsx`, `components/deals/deal-summary.tsx` (`ClauseLink`, `/documents?id=…&at=…&clause=4.2`); `app/contracts/views.py` | contracts | Golden: open `/documents?id=DOC-000001`, or after an agreed deal click "§4.2" in the deal summary | `e2e/documents.spec.ts` ("each term … beside its clause") | works | indirectly ("every term quotes its clause"); the screen: **no** |
| This deal at a glance | Money-moving terms, the forecast with this company's receipts marked, facilities in use | `components/deal-picture.tsx` | none | any document review | `e2e/documents.spec.ts` | works; #103 notes a browser-side fen comparison | **no** |
| Confirm / reject and the outcome card | The owner's hash-bound decision; the card says what was saved, under which customer, and that the forecast is unchanged, with links to the customer, the facility or the purchase | `POST /documents/{id}/confirm`, `/reject`; `app/api/document_outcome.py`; `OutcomeCard` | contracts | Confirm on any reading | `tests/api/test_document_outcome.py`, `test_document_decision_atomicity.py`; `e2e/documents.spec.ts`, `contract.spec.ts` | works; the lender card links "See your funding" to `/funding`, the Demo engine view | yes (§04) |
| Set up in my books / Undo (ADR-0014) | From a confirmed customer contract, add its one repeating invoice to the books, with each figure beside its clause and the forecast before and after; Tier 2; undoable | `components/contract-terms-step.tsx`; `GET/POST /documents/{id}/terms`, `POST /documents/{id}/terms/undo` (`app/api/contract_terms.py`), `app/contracts/terms_setup.py` | contract_terms (**on** in `pnpm demo`, off by default) | Golden: Attach deals → "Dongguan Office Supplies Ltd." → `fixtures/contract_terms/dgos-2026-09-supply-agreement.md` → Confirm → READY (¥180,000 every 30 days, 45 days) → Set up in my books → Yes → Undo. Foshan's contract shows ALREADY | `tests/api/test_contract_terms.py`, `tests/operations/test_contract_terms.py`; `e2e/contract-terms.spec.ts` | works on golden books; own books use the same code but are **untested** there; ADR-0014 notes the Security Lead's review is pending; refused when the contract ends inside the forecast or the customer already has a different repeating invoice | yes (§03, §04, limitations) |
| Lender agreement linked to a facility | The agreement against the facility in the books (same or differs), Tier-3 clauses, an opt-in link; the facility itself is unchanged | `app/contracts/records.py suggest_facility`, `document-review.tsx` (`doc-compare`, `doc-link`) | contracts | Golden: "Main bank" → `fixtures/contracts/mb-cl-2026-031-credit-line-agreement.pdf` → tick link → Confirm (links FAC-LINE); or "Invoice financing platform" → `gbr-if-2026-118-invoice-financing-agreement.docx` (FAC-IF) | `e2e/documents.spec.ts` (live); `tests/api/test_documents.py` | works | **no** (comparison and linking) |
| Capex contract on the documents path | A vendor contract read and confirmed, then committed as a purchase | upload on `/buy` (not on Attach deals); review on `/documents?id=` | capex_contracts (on) | `/buy` → "Read the sample" | `tests/api/test_capex_documents.py`; `e2e/buyside.spec.ts` | works | routes only |

**Recorded readings.** In `pnpm demo` (cache) only four document readings are recorded, keyed by text and sender:
the Foshan contract under `BUYER-1`, the credit-line agreement under `BANK-1`, the invoice-financing agreement under
`PLATFORM-1`, and the offers. Everything else (including every document read inside the setup wizard and the Dongguan
contract) is read by the rules grammar. On own books the Foshan contract replays its recording only when uploaded under
the first setup customer (`BUYER-1`).

## 4. Customers

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Customer overview | What one buyer is worth, what it puts at risk, what is outstanding: four figures (gross contribution, outstanding, financing linked, share of what you are owed), the action block, other open work, the receivable-to-cash flow, deals with the buyer, economics, exposure, history | `/customers/[id]` (`components/customer/overview.tsx`, `receivable-flow.tsx`, `exposure-table.tsx`, `outstanding.tsx`); `GET /customers/{id}/overview` (`app/api/customer_overview.py`) | none (exposure block: exposure, on) | Golden: click "Foshan Home Retail Co." anywhere, or `/customers/BUYER-1`; own books: `/customers/BUYER-1` | `e2e/customer-overview.spec.ts` (mock only); `tests/api/test_customer_overview.py` | works; there is **no customer list page** (`GET /customers` feeds search only); with economics off the margin is the Demo's assumption ("assumed for the Demo") on any books | **no** (route in Appendix C only) |
| Terms in force, contract on file | The terms the books use, and the contract they came from | one "In force" history row on the overview (links to `/documents`, not the document); the contract reference on receivable rows (`app/api/receivables.py _contract_refs`); the outcome card | contracts | overview → History | `tests/api/test_customer_overview.py` | partial (no section of its own; generic link) | **no** |
| Receivables and invoices per customer | Outstanding and the flow card; "View the invoices" | overview → `/receivables?customer=…` | none | overview → View the invoices | `e2e/receivables-layers.spec.ts` | works | see §11 |
| Inputs sheet | Facts the books do not hold, each with its source: annual sales, margin, margin basis, classification, typical days late; firm margin and VAT | `/customers/[id]/inputs` (`components/customer/inputs-sheet.tsx`); `GET/POST /buyers/{id}/inputs`, `/firm/inputs` (`app/api/customer_inputs.py`, `inputs_sheet.py`) | routes: exposure (on); the fields: customer_economics (**off**) | in `pnpm demo` the page shows only "Customer economics is not switched on yet"; the "Edit these facts" link is hidden | `e2e/inputs-sheet.spec.ts` (mock); `tests/api/test_customer_inputs.py` | flag off (#97) | **no** |
| Payment behaviour | How the buyer has paid, or "not enough history yet" | exposure block (`app/strategy/payments.py`) | exposure (on) | overview → Exposure | `tests/strategy/test_payments.py` | partial: no reliability grade exists (#153 open) | **no** |
| Decision record (ADR-0011) | One page per decision with its state from stored facts: what was sent, authorised, ran, landed, and what remains | `/decisions/[id]`; `GET /decisions`, `GET /decisions/{id}` (`app/api/decisions.py`, `app/decisions/*`) | none | after an agreed deal: overview → History → "The record", or Activity | `e2e/record.spec.ts`, `tracker.spec.ts`; `tests/decisions/*`, `tests/api/test_decisions_flow.py` | works (needs a deal) | yes (§03, Appendix C) |
| Concentration and exposure | The buyer's share of what is owed, the 30-day-late stress, the financing cost then, spare capacity | overview Exposure panel, Receivables aside, "Stress-test payment"; `GET /buyers|offers|decisions/{id}/exposure` | exposure (on) | `/customers/BUYER-1` → Exposure → Stress-test payment | `tests/api/test_buyer_exposure.py`; `e2e/customer-overview.spec.ts` | works | **no** |

## 5. Deals: requests, verdicts, counters, negotiation, agreements

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Buyer messages (inbox) | The buyer's messages, one thread per buyer; a click reads one into a negotiation | `/deals` "Buyer messages" card (`components/deals/flow/deals-page.tsx:150-279`, `components/deals/inbox-list.tsx`, fixed list `lib/inbox.ts`: EX01, EX01B, ACC from BUYER-1, SEC from FastCapital); `/inbox` (Demo engine page); `POST /offers`, `GET /fixtures/offers` | none | Golden: Deals → Buyer messages → Foshan's WeChat (EX01) | `e2e/deals.spec.ts`, `deals-queue.spec.ts` | **demo books only**: on own or blank books the card is empty by design (`books === "demo"`, commit `0ebdb6e2`; untested) | **no** |
| Other ways a request arrives | A buyer's message by its channel key; an offer the owner pastes or reports in chat; the buyer's pasted reply | `POST /nl` (buyer key, Demo shell's buyer role), `POST /offers`; chat: quoted text, "X sent this: …", or a reported offer with a question ("Foshan says they'll pay early at 1.2% if we go to 60 days. Good deal or not?"; `rules.py reported`); `POST /offers/{id}/buyer-reply` | buyer_negotiation | Demo shell → Ask FLOW → Role: Buyer → BUYER-1 | `tests/nl/test_counterparty_channel.py`, `tests/api/test_buyer_message.py` | works; a bare "Foshan wants 60-day terms" (no quote, no question) matches no rule; a chat-filed request has no RECEIVED fact, so (from the code, untested) its message to the buyer is blocked `UNVERIFIED_SENDER`; no web form files an offer for an arbitrary customer | yes (buyer channel); the paths: partly |
| Verdicts | "Check against my limits": the verdict with its rule, figures and formula. Six outcomes: ACCEPT, COUNTER, REJECT, NO_DEAL, NEEDS_OWNER_APPROVAL, NO_VERDICT (`app/domain/models.py:872`); Deals headlines "Accept their request", "Counter instead of accepting their request", "No deal", "Accept, with your approval", "Not safe to act on", "Clarify before deciding" (`app/api/deal_offers.py:62`) | `POST /offers/{id}/evaluate` (`app/api/decide.py:196`), `GET /offers/{id}/picture`; `components/deals/flow/decision-pane.tsx`, `deal-overview.tsx` | terms_guard (on) | Golden: EX01 → Check against my limits → REJECT, four reasons | `e2e/deals.spec.ts`, `deals-queue.spec.ts`; `tests/api/test_deals_workspace.py`, `tests/verifier/*` | works on any books given a request (#164: a request needing clarification still shows a recommendation and a ready counter) | yes (Table 1, §03 item 5) |
| Counters: Option A and B | Priced replies: A early payment at the largest 5 bp step below break-even on the face that closes the gap; B the asked terms (or 5-day shorter) with the smallest price rise covering the funding cost; each passes its own re-check | `app/verifier/counters.py` (`early_pay_counter`, `price_adjustment_counter`); `components/deals/flow/terms-table.tsx`, `cost-table.tsx` | terms_guard, debt_desk | Golden EX01: A ¥260,000 at 0.85% (¥3,035.99); B 55 days + 0.30% | `tests/verifier/test_counter_a_floor.py`, `test_counter_property.py`; `e2e/deals-queue.spec.ts` | works; **no counters when the books have no admissible standing plan** (section 0b) | yes (§03 item 6, Table 6) |
| Negotiation with the simulated buyer | A Demo-only send that a deterministic buyer with a hidden reservation answers at once: accept, counter one step, refuse in its last round; NO DEAL is an outcome and the gap is still funded | `POST /negotiate/{offer_id}` (`app/api/decide.py:405`), `app/counterparties/buyer.py`, `negotiation.py`, `profiles.py`; `components/deals/flow/send-block.tsx` (Demo mode only: lean "Open to a counter" / "Holds firm"); `/verdict` engine page | buyer_negotiation (on); web Demo mode | Golden, Demo shell: EX01 → Check → "Review and send the counter" → "Open to a counter" (Option A agreed in round 1) or "Holds firm" (NO DEAL within 3 rounds) | `tests/counterparties/*`, `tests/api/test_negotiate_binding.py`; `e2e/deals.spec.ts`, `buyer-message.spec.ts:327` | works on golden BUYER-1 (both leans) and BUYER-2 (cooperative); own books: section 0b; `NegotiateIn.max_rounds` is never read; the buyer's counter-counter is ignored | yes (§02, §03 item 7, Table 14) |
| Message to the buyer: copy, mark sent, record the answer | FLOW drafts the exact reply; the owner sends it by their own channel, marks it sent, then records yes, no or the buyer's reply (bound to the message hash) | `GET /offers/{id}/counters/{cid}/message`, `POST …/offered`, `…/offered/withdraw`, `…/buyer-accepted`, `…/buyer-declined`, `POST /offers/{id}/buyer-reply` (`app/api/outbound.py`, `outbound_record.py`, `app/outbound/message.py`); `components/deals/flow/buyer-message.tsx` | buyer_negotiation | Golden, Business mode: EX01 → Check → "Review and send the counter" → Copy response → Mark as sent → "The buyer accepted" | `tests/api/test_buyer_message.py` (≈40); `e2e/buyer-message.spec.ts` (mock only) | works for requests from a buyer key, the owner or the agent; blocked for anonymous and (inferred) chat-filed requests | yes (§02 "Outside FLOW", Appendix C) |
| Accept as asked / decline | Agree to the buyer's terms exactly, or close the request, when FLOW has no counter; the click is the approval | `POST /offers/{id}/accept`, `/decline` (`app/api/accept.py`); `components/deals/flow/accept-block.tsx` | terms_guard | Busy books (`/demo` → Busy): Zhuhai EX09 → Review the request → accept; Dongguan EX08B → decline | `tests/api/test_accept_as_asked.py`; `e2e/accept-as-asked.spec.ts` | works; **#158** (one click logs two operations, the decline reason is not stored, a refused accept leaves a PROPOSED commitment), **#159** | Appendix C only |
| Lifecycle strip and deal tracker | The deal's stages (Received, Analysed, Reply ready, Sent, Agreed; then Terms negotiated, Early payment in, Collecting, Fulfilled) and, once agreed, promised against actual | `GET /decisions/{id}/tracker` (`app/api/deal_tracker.py`), `app/api/lifecycle.py`; `/decisions/[id]/tracker`, `components/deals/lifecycle-strip.tsx`, `stage-track.tsx` | none | agree Option A on golden EX01 → the deal's Overview → advance the clock | `tests/api/test_deal_tracker.py`; `e2e/tracker.spec.ts` | works; `e2e/slice-b-round-three.spec.ts` is empty (#163); #155 owner decisions | **no** |
| Your deals queue | One row per task, filed by who owes the next step: tabs All, Needs you, Waiting, Agreed; counts from the server; table layout from 20 rows | `GET /deals` (`app/api/deals.py`), `GET /worklist`; `components/deals/flow/queue-table.tsx`, `queue-model.ts` | contracts | busy books for the tabs (one negotiation shows no tabs) | `e2e/deals-queue.spec.ts` (19); `tests/api/test_deals_queue.py` | works (own books: buyer-channel requests appear, verified in process) | **no** |
| Your agreements | Agreements grouped Payment late / Awaiting payment / Closed; buyers with invoices and no contract | `components/deals/commitments.tsx`, `deal-summary.tsx`; `app/api/lifecycle.py after_group` | contracts | golden after the agreement; own books with an open invoice | `e2e/live.spec.ts:730` (own books via `/setup/open`), `deals.spec.ts`; `tests/api/test_deals_no_contract.py` | works on both | **no** |
| Deal page with previous / next | A deal as its own page: "All deals (N)", "Deal i of N", previous/next; Overview, Compare, Cash impact, Terms, Messages | `deals-page.tsx:363-391`, `deal-model.ts` | none | busy books | `scripts/slice-b-r2.test.mjs`; no e2e clicks previous/next | works | **no** |
| Business consequences (scenarios) | Continue as is / buyer pays 30 days late / buyer stops ordering | `GET /offers/{id}/scenarios` (`app/api/offer_picture.py:1165`, `picture_scenarios.py`); `components/deals/flow/cash-tab.tsx` | exposure (on) | EX01 → Check → Cash impact | `tests/api/test_slice_b_round_three.py`; `e2e/deals-queue.spec.ts` | works | **no** |
| Before they ask (envelope) | see §9 | — | web off | — | — | flag off | **no** |
| Approvals from deals | A Tier-2 agreement (Option B lengthens terms) or a funding leg above the ceiling waits for the owner | `POST /negotiate`, `…/buyer-accepted`; "Approve and send {label} to {buyer}" | none | golden Option B send in Demo mode | `e2e/approvals.spec.ts`; `tests/api/test_negotiate_binding.py` | works | yes |

## 6. Money: Cash & funding, permissions, approvals

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cash & funding page | How bad cash is, the plan to run, other plans, the forecast, your funding, doors to the sandbox and Capex | `/cash` (`app/cash/page.tsx`, `components/business/cash-forecast.tsx`, `next-action.tsx`, `funding-options.tsx`, `current-funding.tsx`); `GET /home`, `POST /router/plan`, `GET /trajectory` | debt_desk (on); price sentence hidden (STRATEGY_MVP) | Golden: Cash & funding at day 0 (plan: line ¥150,000 + invoice financing ¥255,000, ¥3,113.93) | `e2e/cash.spec.ts`, `live.spec.ts`; `tests/api/test_home.py`, `tests/funding/*` | works | named in §05; the router in §03 |
| Router plan and compare financing | The cheapest admissible mix and every option with its cost, time to cash and covenant effect | Cash "Ways to cover the gap" / "Other plans considered"; `/funding` (the Demo engine view "Debt Desk"); `POST /router/plan`; chat COMPARE_FINANCING | debt_desk, expected_plans | Cash → open the options | `cash.spec.ts`; `tests/funding/test_router_rules.py`, `test_golden.py` | works; 6 of 26 router plans are "cannot run today" | yes (§03, Appendix C) |
| Run a funding plan (draw, invoice financing, repay) | One button runs the cure's legs (Tier 1) or queues it (Tier 2); bound to the books shown (409 if they moved) | `components/business/next-action.tsx` ("Run funding plan" / "Queue it for my approval"); `POST /alerts/{id}/act` (`app/api/alerts.py`) | alerts (on) | Golden: Demo → Operator tools → clock to day 34 → Home or Cash → Queue it for my approval → Approvals → Approve → clock to day 38 | `e2e/live.spec.ts`, `catchup.spec.ts`; `tests/alerts/test_act.py`, `test_cure_cost.py` | works | yes (§04 Tier 1, §03) |
| Repay a drawn line (C5) | FLOW proposes repaying a drawn credit line once cash allows | `alerts/engine.py _repay_alerts`; Home and Cash next action | alerts | after the draw, once cash stays above the reserve | `tests/alerts/test_repay_alert.py` | works | indirect (§01 step 6) |
| Funding ring | Own money against each lender's and a buyer's agreed early payment | `components/home/v2/cash-mix.tsx`, `lib/funding-mix.ts` | none | Home, Cash | `e2e/home-v2.spec.ts`, `cash.spec.ts` | works (hidden on a phone's Home) | **no** |
| Tiers as the owner sees them | Plain sentences of what FLOW may do alone, what waits and what never happens | `/limits` (account menu; `app/limits/page.tsx`), `/mandate` (Demo engine view with tier cards), the approval card's tier line, `components/autonomy-panel.tsx`; `GET /mandate` | none | account menu → Limits | `e2e/pages-a2.spec.ts`, `trust.spec.ts`; `tests/mandate/test_tiers.py` | works | yes (§04) |
| Approvals page | Each card is a question with its terms, the stored quote (and today's price if different), a picture, Approve / Decline; no "approve all" | `/approvals` (`components/approval-card.tsx`, `approval-lifecycle.tsx`); `GET /approvals/queue`, `POST /approvals/{id}` | none | Golden day 34: the ¥200,000 cure at 32.5% a year waits here | `e2e/approvals.spec.ts`; `tests/api/test_approval_quote.py`, `tests/operations/test_approvals_and_circuit.py` | works; the card does not show the approval id; #157 (live retry flakes) | yes (§04, Figure 9) |

## 7. Lifecycle over time

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Simulated clock | Move the day: scheduled flows post, funding lands, instalments are paid, recurring invoices issue, lapsed commitments expire; it never records a receipt | **UI only on `/demo`** → Operator tools → The clock (`components/home/today-card.tsx`: +1, +7, +30, days); the story stepper; `GET /clock`, `POST /clock/advance` (owner only, forward only, ≤ 366 days a step) | none | Demo → Operator tools → +30 | `tests/api/test_clock.py`, `tests/clock/*`; `e2e/demo.spec.ts` | works on any books; golden books also apply `fixtures/scenarios/golden_sme.events.json` (DEMO_MODE only) | yes (§03 "Time", Table 11, Appendix C) |
| Recurring invoices issued | Each contract's repeating invoice becomes a receivable on its day, with agreed terms written on | `app/clock/__init__.py`; sources: setup step "customers" contract row, or "Set up in my books" | contracts, contract_terms | advance the clock past the next invoice date | `tests/clock/test_clock.py`, `tests/books/test_invoice_terms.py` | works; the forecast assumes they are paid on the due day | yes |
| Receipts | Money in, partial payments leave the rest open, a financed invoice repays its advance first | bank feed: `POST /operations` `RECEIVE_PAYMENT` with `X-Bank-Feed-Key`; owner: the same route with the owner token; Demo: `POST /demo/bank-receipt` (one awaited early payment only) | none / DEMO_MODE | golden story scene 4 ("bank") | `tests/api/test_demo_bank_receipt.py`, `tests/operations/test_partial_settlement.py`; `e2e/receipt-basis.spec.ts` | **partial: no button records a receipt in the web app** (the owner path is API only; Receivables offers Chase only), although the setup wizard says a late invoice is not counted "until a payment is recorded" | yes (Tier 1 receipt); the missing UI: **no** |
| Late-payment alerts and cures | An overdue invoice is flagged (WARNING, CRITICAL when financed) with "chase the buyer"; when that pushes cash under the reserve, a reserve alert carries a funding cure | `alerts/engine.py _past_due`, `RESERVE_BREACH_AHEAD`; Home changes, worklist, Receivables, Deals; `/alerts` (Demo engine view); `GET /alerts`, `GET /receivables/{id}/chase` | alerts | golden day 34 | `tests/alerts/test_alerts.py`; `e2e/live.spec.ts`, `alerts.spec.ts` | works; the late invoice itself has no runnable cure (409 `NO_EXECUTABLE_CURE`); own books verified in process (section 0b), no automated test | yes (§01 "Follows through"); alert kinds not named |
| Reconciliation | Each receipt matched (MATCHED, SHORT_PAYMENT, …) and each promise AWAITED, RECEIVED, LAPSED or SETTLED_OTHERWISE, with the chain check | Activity → Reconciliation tab (`components/business/reconciliation-section.tsx`), `/reconciliation` (Demo engine view); `GET /reconciliation` (`app/alerts/reconcile.py`) | alerts | Activity → Reconciliation after the bank event | `e2e/alerts.spec.ts`, `catchup.spec.ts`; `tests/alerts/test_reconcile*.py` | works; reuses SHORT_PAYMENT for partial payments | yes |
| Commitments expiring | A warning 7 days before an agreement expires; the clock expires lapsed ones | `alerts/engine.py _expiring`, `clock _end_lapsed` | alerts | needs an agreement on the books | `tests/alerts/test_alerts.py`, `tests/api/test_lapsed_offers.py` | works | partly |
| Mandate expiry | WARNING 14 days before the signed limits expire, CRITICAL after; information only | `MANDATE_EXPIRING`; golden expiry day 90, own books `limits.valid_days` | alerts | advance to day 76+ | `e2e/catchup.spec.ts`; `tests/alerts/test_alerts.py` | works | the alert: **no** |
| FLOW speaks first after a clock event | see section 8 "The opener" | `POST /nl/opener` | alerts | — | API tests only | API only, no UI caller | yes, route |

## 8. Ask FLOW chat

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Chat surfaces | Ask in words on any page | `app/chat/page.tsx`, `components/chat/chat-view.tsx`, `chat-panel.tsx` (the "Ask FLOW" slide-over), `components/ask-header.tsx` (header input, typewriter examples, scope chip); `POST /nl` (`app/api/nl.py`) | none | Header "Ask FLOW anything…", Enter | `e2e/chat.spec.ts`, `ask-header.spec.ts`, `ask-header-live.spec.ts` | works | partly (Appendix B "Ask FLOW chat"); the header input, slide-over and scope chip: **no** |
| 23 intents | One closed list of things chat can do | `app/nl/models.py` `Intent`; `rules.py` first, `classifier.py` only when no rule matches (10 intents, never approve/reject/buyer) | none | see the intent table below | `tests/nl/test_rules.py`, `test_intents.py`, `test_intent_coverage.py`, scenarios S01–S49 (`evals/e2e/scenarios.yaml`) | works | yes (§03, "23 intents") |
| ASK_BOOKS (question bank) | Questions answered from the books, never acted on | `app/nl/ask.py`, `app/nl/answers/answers.py` (30 `QUESTIONS`), `answers/metrics.py` | none | "Are we safe?", "How much do we need to raise to stay safe?", "What does FLOW recommend we do about cash?", "Can we make payroll?", "How much more can we borrow?", "What if Foshan pays 30 days late?", "Should we take Foshan's early-payment offer at 1.2%?", "Are we inside our covenants?"; zh: 我们安全吗？, 下次发工资的钱够吗？ | `tests/nl/test_ask_books.py`, `test_answers.py`; `evals/owner_questions/` (122 questions, 503 turns: 288 answered, 38 partial, 0 wrong, 177 can't) | works | yes (§03, Table 1, Table 9); the 30 ids: no |
| Plans and "go ahead" | A plan shows its exact operations and cost; "go ahead" runs exactly those | `app/nl/sessions.py` `PendingPlan`, `plans.py`, `service._confirm`; web Go ahead / Cancel buttons (`components/chat/assistant-turn.tsx`) | none | Demo shell: "Fund the cash gap", then Go ahead | `tests/nl/test_plan_binding.py`, `test_plan_flags.py`, `test_goal_and_corrections.py`; `e2e/chat.spec.ts` | works | yes (§03 "Propose, then confirm") |
| Consent rules | Money moves only on an unambiguous command | `app/nl/consent.py` (money command: one line, ≤ **160** characters, one RMB amount); `service._direct_command` (approve, reject, go ahead, cancel: ≤ **80** characters, no counterparty name, no paste or forward marks) | none | "Draw ¥50,000 on the credit line" executes; "Don't draw ¥50,000" does not | `tests/nl/test_consent.py` (41 consent attacks) | works | yes (§03 "Consent"); the 80/160 limits: **no** |
| Approvals by sentence | "approve APR-000002"; a bare "approve it" binds only to the approval this session just showed | `consent.approval_verdict`, `bare_verdict`, `session.shown_approvals` | none | after a queued cure: "approve it" | `test_consent.py`, S10, S13 | works; **known issue**: the approval card hides its id (`assistant-turn.tsx` `showId={false}`), which the exact sentence needs | yes (exact sentence); the bare "approve it": **no** |
| Corrections and goals | "actually make it 0.8%"; "Get paid early on the Foshan invoice without giving anything away next quarter" | `service._correct`, ACCELERATE_RECEIPT | none | Demo prompts "goal", "amend" | `test_goal_and_corrections.py`, S17, S19 | works | yes (§03 "Planning examples") |
| The opener (FLOW speaks first) | After time moves, FLOW names what needs the owner and proposes a priced cure | `POST /nl/opener` (`app/api/nl.py`), `nl/alerts.py` `alerts_turn` | alerts | **No UI caller since 8 Oct** (commit `218a3be1` removed `needs-card.tsx`; `nlOpener`, `appendOwnerOpener` and `mocks/home_opener_*.json` are unused). In the UI use Home's prompt "What needs my attention?" (same `alerts_turn`). `scripts/demo_run.py` still calls the route | `tests/nl/test_alerts_opener.py`, `test_queued_cure_opener.py`, `test_repay_opener.py`; no e2e | partial (API only) | yes (§01, §03 "Acting first", Appendix C); that the UI no longer calls it: **no** |
| New conversation | Starts over here and on the server; a later "go ahead" runs nothing | "New conversation" (`data-testid=chat-new`), `lib/chat.ts newConversation`; `POST /nl/session/reset`, `POST /nl/reset` | none | Ask FLOW → New conversation | `tests/api/test_nl_session_reset.py` (11); `e2e/chat.spec.ts` | works | route only (Appendix C); behaviour: **no** |
| Buyer channel through chat | A buyer's message is compiled and verified, never parsed for intents; the buyer sees only the reply | `POST /nl` with `actor=COUNTERPARTY` + `X-Counterparty-Key`; `_counterparty_view` (session, turn, reply, intent, lang, trace id only); `enforce_buyer_budget` (5 a simulated day, R-10); Demo shell role switch (`chat-view.tsx`) | buyer_negotiation | Demo shell → Ask FLOW → Role: Buyer, BUYER-1 → "We can pay this one early at 1.5%. Nothing else changes." | `tests/nl/test_counterparty_channel.py`, `tests/security/test_buyer_budget.py`; S06, S07, S30–S33 | works (golden; own books: first two customers, section 0b) | yes (§03, Table 11) |
| RECORD_FACT refusal | "add a ¥80,000 bill" is refused: chat never records facts | `app/nl/capabilities.py record_fact` | none | "We have a supplier bill of ¥80,000 due on day 30, add it to the forecast" | `tests/nl/test_record_fact.py`, S47, S48 | works | **no** |
| Nearest capability | An unmatched request gets the closest thing FLOW can do | `capabilities.nearest_reply` (16 capabilities) | none | "Email the loan officer about our rates" | `test_capabilities.py`, S24, S45 | works | yes |
| Quoted text is never an instruction | A pasted "approve APR-…" approves nothing and logs an injection event | `rules.split_provenance`, `quoted_approval` | none | paste `"approve APR-000001"` inside quotes | `tests/nl/test_security.py`, `test_boundary.py`, S30, S31, S35 | works | yes (§04) |
| Tier-3 refusals | A personal guarantee, collateral, equity or a mandate change is refused for everyone and logged; asked as a question it is answered as information | `lexicon.TIER3`, `service._out_of_scope`, `ask.tier3_info` | none | "Sign a personal guarantee for the bank loan" | `test_rules.py`, S28, S29 | works | yes |
| Chinese | Every intent, the consent grammar and the answers in Chinese | `lexicon.detect_lang`; `t(ctx, en, zh)` | none | 我们安全吗？ | S05, S19, S29, …; `e2e/chat.spec.ts` | works | yes |
| Suggested prompts | Chips per page; only questions the page can answer | `lib/chat-prompts.ts`, `lib/use-chat-facts.ts` | none | Home: "What changed today?", "What needs my attention?"; Deals: "Why are we countering this?"; Cash: "Why did FLOW choose this plan?" | `scripts/chat-prompts.test.mjs`, `tests/nl/test_business_page_prompts.py` | works | **no** |

**The 23 intents.** EVALUATE_OFFER ("Evaluate EX01"), NEGOTIATE ("Send the counters"), ACCELERATE_RECEIPT (the goal
sentence), FUND_GAP ("Fund the cash gap"; executes only the closed draw command), REPAY_FACILITY ("Repay the credit
line"), SHOW_STATUS ("How's our cash position?"), SHOW_ALERTS ("What needs my attention?"), COMPARE_FINANCING ("Which
financing option is cheapest?", owner only), RECONCILE ("Reconcile this month", owner only), SHOW_RATIOS ("What is our
DSCR?", owner only), CAPEX ("Evaluate the ¥600k machine", owner only), BORROWER_FILE ("prepare the borrower file for the
term loan, ¥600,000", owner only), SHOW_DEAL ("where are we with Foshan?", owner only), EXPLAIN ("Why was it
rejected?"), WHAT_IF ("What if we give Foshan 60-day terms?"), RECORD_FACT (refused), CHANGES ("What changed today?",
owner only), ASK_BOOKS (owner only), APPROVE, REJECT, COUNTERPARTY_MESSAGE (buyer channel only), OUT_OF_SCOPE,
AMBIGUOUS ("help me sort out our cash"). With the agent key alone every reply passes the `agent_view` allow-list
(`app/api/agent_view.py`, R-11): no cash, limits or reserve figures.

## 9. What-if sandbox and strategy

| Feature | For the owner | Where | Flag (`pnpm demo`) | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| What-if sandbox | Move terms, discount, rebate, price rise and early-settled amount on a real buyer invoice; see the verdict, lowest cash, concession cost and covenants; nothing is written | `/whatif` (nav "Sandbox"; phone bar omits it), `app/whatif/page.tsx`, `components/whatif-controls.tsx`, `whatif-results.tsx`; `GET /whatif/presets`, `POST /whatif` (`app/api/whatif.py`) | none (visible) | Golden: Deals → EX01 → "Check against my limits" → "Try other terms"; terms 60 → 45 days gives COUNTER; preset Option A gives ACCEPT | `e2e/whatif.spec.ts`, `slice-b.spec.ts`; `tests/whatif/test_api.py`, `test_simulate.py` | works; **known issue**: presets are hard-coded to EX01 (60 days / 1.2% / 1%, Option A ¥260,000, `app/whatif/params.py`), so on other offers they mislead or give 422; rates off the 5 bp grid give 422 | the chat intent and Appendix B only |
| Late-payment stress on Cash | Cash redrawn with a buyer 30 days late: lowest cash, days under the reserve, what no facility covers | `/cash?stress=BUYER-1:30` (`app/cash/page.tsx`, `lib/cash-stress.ts`); link from the customer page "Stress-test payment"; `GET /buyers/{id}/exposure` | exposure (on) | Customers → Foshan → "Stress-test payment" | `e2e/cash-stress.spec.ts` (mock only); `tests/api/test_buyer_exposure.py`, `tests/strategy/test_stress.py` | works, golden and own books | **no** (Table 10 is the offline stress) |
| Buyer exposure and Business consequences | Concentration, how the buyer pays, the 30-day-late stress, capacity before and after, three consequence cards | Deals decision pane, Cash impact tab (`components/deals/flow/cash-tab.tsx` BusinessConsequences), Receivables aside, customer "Financial exposure"; `GET /offers|decisions|buyers/{id}/exposure`, `GET /offers/{id}/scenarios` | exposure (on) | Deals → EX01 → check → Cash impact → Business consequences | `deals-queue.spec.ts`, `customer-overview.spec.ts`; `tests/api/test_exposure_routes.py`, `tests/strategy/test_concentration.py` | works | **no** |
| Cash price curve | What ¥10,000 arriving 30 days earlier is worth | Cash header `cash-price-sentence`; `GET /cash/price-curve` | API on, **web off** (STRATEGY_MVP) | needs a `NEXT_PUBLIC_STRATEGY_MVP=1` build | `e2e/strategy.spec.ts` (`E2E_STRATEGY=1`); `tests/strategy/test_price_curve.py` | flag off | **no** |
| Collections worth | Rank invoices by what collecting each saves | `app/receivables/legacy.tsx` only; `GET /receivables/worth` | API on, web unreachable | API only, or a mock build with the fallback forced | `e2e/strategy.spec.ts`; `tests/strategy/test_collections.py` | **dead in live builds** | **no** |
| Safe Deal Envelope ("Before they ask") | What the owner can live with for a buyer before it asks | `components/deals/before-they-ask.tsx`, `deals/flow/investigate.tsx`; `GET /buyers/{id}/envelope` | API on, **web off** | STRATEGY_MVP build → Deals → EX01 → Cash impact | `e2e/strategy.spec.ts`; `tests/strategy/test_envelope*.py` | flag off | **no** |
| Customer economics | Sales, margin and classification as context for deals | `/customers/[id]/inputs` (`components/customer/inputs-sheet.tsx`); `POST /buyers/{id}/inputs`, `/firm/inputs` | **off** | — | `e2e/inputs-sheet.spec.ts`; `tests/api/test_customer_inputs.py` | flag off | **no** |
| Pilot journal | What the owner did against what FLOW said | Activity (`components/business/pilot-journal.tsx`); `GET/POST /pilot/journal` | **off** (API and web) | — | `tests/pilot/*` | flag off | **no** |

## 10. Capex & purchases

Nav label "Capex" (Demo: "Capex & purchases"); the phone bar omits it. Cash's "Need more funding?" card links to it.

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Capex hub | Health figures, every vendor contract with its stage, the chosen contract worked through, a quick check | `/capex` (`app/capex/page.tsx`, `components/capex/health-figures.tsx`); `GET /finance/health`, `GET /purchases` | capex + capex_contracts (on) | Capex → "Read the demo vendor contract" → confirm on Documents → row READY | `e2e/buyside.spec.ts` (mock only); `tests/api/test_purchases.py` | works | page named in §05; the hub: no |
| Evaluate a machine, financing structures, apply | ¥600k machine: NPV, payback; cash + line, 18/36-month loan, 48-month lease screened daily and monthly; Apply queues one Tier-2 application | `components/capex/quick-check.tsx` (fixed ¥600k request); `POST /capex/evaluate`, `POST /capex/apply` | capex (on) | Capex → "Test a machine without a contract" → Evaluate → lease selected (¥92,327.32) → Apply → approve | `e2e/capex.spec.ts` (mock only); `tests/capex/test_evaluate.py`, `test_api.py` | **demo books only** (needs `FAC-ETL`/`FAC-LEASE`) | yes (§03 item 8, Appendix C, limitations) |
| Purchase contracts and commit | A vendor contract's payment schedule from its reading and the owner's timeline; the vendor's early-payment discount priced; Commit is Tier 2 and books the payments on approval | `/buy`, `/buy/contract?id=`, `components/capex/contract-workbench.tsx`; `POST /capex/contracts/{id}/evaluate`, `/commit`, `GET /purchases/{id}`; fixture `fixtures/capex/gzpm-2026-114-equipment-purchase.md` | capex + capex_contracts (on) | Capex → the GZPM row → "Work out the payments" → "Commit, paying early" → Approvals → "Authorize the purchase" | `e2e/buyside.spec.ts`; `tests/capex/test_schedule.py`, `tests/api/test_capex_commit.py` | works (own books: fewer financed structures); a committed purchase cannot be cancelled | yes (§02, Appendix C) |
| Financial health | Cash coverage, current and quick ratios (owner estimates), covenant room, capacity per facility | `/finance`; `GET/POST /finance/health` (`app/api/buyside.py`) | capex_contracts (on) | Capex → "Financial health and loans" | `e2e/buyside.spec.ts`; `tests/health/test_health.py` | works | **no** |
| Loan eligibility | Four illustrative catalogue loans read against the books; "Add to my funding menu" queues a Tier-2 AddFacility (counts as zero until committed) | `/finance`; `GET/POST /lending/eligibility`, `POST /lending/products/{id}/add-to-menu`; `fixtures/lending/catalogue.json` | capex_contracts (on) | `/finance` → months trading 36 → Read eligibility → Add | `e2e/buyside.spec.ts`; `tests/lending/test_eligibility.py` | works (indicative) | **no** |
| Long-term plans | Projects × structures × start months over 60 months, top five by NPV | `/plans`; `POST /capex/plans` | capex_contracts (on) | Capex → "Long-term plans" → Run | `e2e/buyside.spec.ts`; `tests/capex/test_plans.py` | works | **no** |
| Borrower file | A lender-style file from the verified books, prepared and never sent; HTML, DOCX (PDF only with WeasyPrint) | quick check `#file`, `components/business/borrower-file.tsx`; `POST /borrower-file`, `GET /borrower-file/{id}.html|.docx|.pdf` | borrower_file (on) | after the quick check: "Prepare the borrower file" | `e2e/capex.spec.ts`; `tests/borrower_file/*` | **demo books only** | one bullet in §02; routes: no |

## 11. Records, evidence and the Demo story

| Feature | For the owner | Where | Flag | How to demo | Test | Status | Tech doc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Receivables | Customer list, then one customer's invoices: what each nets after financing, what it rests on, a late stress aside, "Chase payment" (a request to copy; nothing is sent) | `/receivables` (`?customer=`), `components/receivables/*`, `components/business/chase-payment.tsx`; `GET /receivables`, `GET /receivables/{id}/chase` | none (stress aside: exposure) | Receivables → Foshan; after day 34 → Chase payment → Copy | `e2e/receivables-layers.spec.ts`, `receipt-basis.spec.ts`; `tests/api/test_receivables_net.py`, `test_collections.py` | works; drops `from` (#163) | page named only; chase and net view: **no** |
| Activity log | Every operation and security event newest first, filters that hide but never remove, chain badge, evidence fold per row; Reconciliation tab | `/activity` (`components/activity/activity-read.tsx`, `components/business/reconciliation-section.tsx`, `#reconciliation`); `GET /activity`, `GET /reconciliation` | alerts for the tab | Activity → Reconciliation | `e2e/activity.spec.ts` (no test clicks the Reconciliation tab); `tests/api/test_activity_read.py` | works | page named only |
| Hash-chained evidence and export | Every executor outcome chained `sha256(prev + payload + result)`; Download JSONL; offline verification | `/trust?view=evidence` (`components/trust/evidence-view.tsx`), `/evidence`, `/ledger`; `GET /evidence`, `GET /ledger`; `scripts/verify_evidence.py` | none | Demo → Proof → "The full record" → Download JSONL; `python scripts/verify_evidence.py e.jsonl` | `e2e/trust.spec.ts`; `tests/security/test_evidence_verifier.py`, `tests/api/test_read.py` | works (no verify route: offline only) | yes (§04 "The record"); `/trust`: **no** |
| Security events and the FastCapital scene | The hostile message with flagged spans, a zero-harm scoreboard, the buyer's fixed reply, circuit resets | `/trust?view=security`, `/security` (`components/trust/security-view.tsx`); `GET /audit`, `GET /security/summary`, `POST /circuit/{id}/reset` | security_scenes (hides fixtures only; the button works with it off) | Account menu → Security and evidence → Security → "Run the FastCapital scene" | `e2e/trust.spec.ts`; `tests/security/test_scoreboard.py` | works; **known issue**: `GET /audit` called without `lang`, so event words stay English in zh | events yes; the page: **no** |
| Demo story | Six scenes, one next control, the owner's approval only by the owner's click; Proof block; operator tools (clock, books, four more scenes) | `/demo` (`app/demo/page.tsx`, `components/demo/books-cards.tsx`, `lib/demo.ts`); `GET /demo/story`, `POST /demo/restore`, `POST /demo/reset?scenario=` (golden_sme, short_facilities, public_sme, busy, blank), `POST /demo/bank-receipt` | DEMO_MODE | Demo → Golden story → the filled button through six scenes | `e2e/demo.spec.ts`, `tour.spec.ts`; `tests/api/test_demo_story.py` | **demo books only** | yes (§05) |
| Judge tools | One offline command for 49 tasks, the attack catalogue, the demo walk and the chain check | `scripts/judge_eval.py` (writes `services/api/evals/judge/judge-report.md`), `scripts/verify_evidence.py`, `scripts/demo_run.py`, `scripts/export_demo_evidence.py`, `scripts/run_scenarios.py`; `docs/deliverables/JUDGING_QUESTIONS.md` | — | `uv run --project services/api python scripts/judge_eval.py` | `tests/nl/test_runner.py`, `tests/security/test_evidence_verifier.py`; nothing tests `judge_eval.py` itself | works | judge_eval, verify_evidence, demo_run, run_scenarios: yes; export_demo_evidence and JUDGING_QUESTIONS.md: **no** |

## 12. Security a user can see

| Feature | What the user sees | Where | Test | Tech doc |
| --- | --- | --- | --- | --- |
| Sign-in and the landing page | "Access FLOW" / "Join FLOW now!" on `/welcome`; the owner token is kept for the tab only (sessionStorage), the account flag never holds it; `pnpm demo` prefills the demo token | `app/welcome/page.tsx`, `components/landing/landing.tsx`, `lib/auth.ts`, `lib/account-flag.ts`, `components/owner-auth.tsx`; `app/api/auth.py` (constant-time, refusals logged, 300 an hour) | `tests/security/test_route_policy.py`, `test_sec26_refusal_budget.py`; no e2e for `/welcome` | sign-in yes; `/welcome`: **no** |
| Demo credentials off by default | Without `DEMO_MODE` the published keys are refused, nothing is seeded, `/docs` is not served | `app/config.py`, `app/main.py:50` | `tests/security/test_demo_mode_default.py` | yes |
| Rate limits | 429 with a retry time: owner 3000, agent 1200, bank feed 600, buyer 120, anonymous 300 a minute; anonymous intake 200 and a keyed buyer 5 a simulated day | `app/api/ratelimit.py`, `app/api/offers.py` | `tests/security/test_rate_limits.py`, `test_buyer_budget.py`, `test_intake_cap.py` | yes |
| Tier 3 never | Refused for everyone, logged | `app/operations/executor.py` | `tests/operations/test_tiers.py` | yes |
| CSP and headers | A nonce per request; no framing | `apps/web/proxy.ts`, `lib/csp.ts`, `app/main.py` | `scripts/csp.test.mjs`, `tests/security/test_headers_and_docs.py` | yes |
| Outbound guard with canaries | A message that would leak a protected value is replaced by a fixed reply and logged | `app/egress/guard.py`, `canaries.py`, `app/outbound/message.py` | `tests/egress/*` | yes |
| Buyer channel boundary | A buyer sees its reply only; a key decides who it is | `app/api/nl.py _counterparty_view` | `tests/nl/test_counterparty_channel.py` | partly |
| Redaction before a live model | Accounts, phones, IDs and addresses replaced before text leaves | `app/compiler/redaction.py` | `tests/compiler/test_redaction.py` | yes |

## 13. Counts by status

One row per feature in sections 1 to 12 (112 rows; the section 7 row that points to the opener is not counted twice).

| Section | Rows | Works | Works, known issue | Partial | Demo books only | Flag off | Unreachable |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 Setup | 13 | 7 | 1 | 5 | 0 | 0 | 0 |
| 2 Daily view | 8 | 5 | 3 | 0 | 0 | 0 | 0 |
| 3 Documents | 11 | 8 | 3 | 0 | 0 | 0 | 0 |
| 4 Customers | 7 | 4 | 0 | 2 | 0 | 1 | 0 |
| 5 Deals | 14 | 8 | 2 | 1 | 2 | 1 | 0 |
| 6 Money | 7 | 6 | 1 | 0 | 0 | 0 | 0 |
| 7 Lifecycle | 7 | 6 | 0 | 1 | 0 | 0 | 0 |
| 8 Ask FLOW | 16 | 14 | 1 | 1 | 0 | 0 | 0 |
| 9 What-if and strategy | 8 | 2 | 1 | 0 | 0 | 4 | 1 |
| 10 Capex | 7 | 5 | 0 | 0 | 2 | 0 | 0 |
| 11 Records | 6 | 3 | 2 | 0 | 1 | 0 | 0 |
| 12 Security | 8 | 8 | 0 | 0 | 0 | 0 | 0 |
| **All** | **112** | **76** | **14** | **10** | **5** | **6** | **1** |

"Flag off" counts what `pnpm demo` does not show: customer economics and the pilot journal (API flags off), the price
curve and the envelope (web flag `NEXT_PUBLIC_STRATEGY_MVP` off). "Unreachable" is collections worth.

## 14. Not yet built, or discussed but not done

From the code above, the project's internal tracker and handover notes, the ADRs, the open GitHub issues (17 Oct) and
`services/api/evals/owner_questions/BASELINE.md` section 7.

**Promised on screen but not built (fix the words or build the feature before the video):**
1. **Recording a receipt.** No button in the web app records money in. The owner path is `POST /operations` only; the Demo
   has `POST /demo/bank-receipt` for one agreed early payment. The setup wizard says a late invoice is not counted "until a
   payment is recorded".
2. **Adding a bill after setup.** Step 4 says "You can add more bills any time after setup"; no operation or route does it.
3. **Changing the signed limits.** Step 5 says "Change them later under Account › Your limits (needs a new signature)";
   `/limits` is read-only and changing the mandate is Tier 3.
4. **The spreadsheet template** on the setup welcome ("Coming soon").
5. **"What you make or sell"** is asked in step 1 and dropped; share advanced and loan term cannot be entered.

**Own books (the owner's own company) cannot yet carry the whole story:**
6. Buyer channel keys exist only for `BUYER-1`/`BUYER-2`; no route or screen issues a key for any other customer.
7. The simulated buyer is the golden Foshan/Dongguan profile; on own books it names the golden invoice `RCV-A` (defect);
   customers after the second get `NO_SIMULATED_BUYER`.
8. The Deals inbox is empty on own books, and no web form files a buyer's request for an arbitrary customer (chat can, but
   its request then has no copyable message to the buyer, from the code).
9. Counters and cures depend on the books' shape (section 0b); nothing tells the owner why there is no counter.
10. The capex quick check and the borrower file need the golden `FAC-ETL`/`FAC-LEASE`; the request is fixed at ¥600,000.
11. "Set up in my books" is untested on own books; the set-up party check ignores short names, and PARTY_UNCHECKED blocks
    it (typical of Chinese contracts on the rules path).
12. After a `pnpm demo:keep` restart own books are taken for golden ones on the Demo page and in the evidence header
    (`app/api/runtime.py:134-139`; read in code, not run).
13. Adding a customer on blank books before the wizard locks the wizard out until a reset.

**Wired in the API but not in the UI:**
14. The opener (`POST /nl/opener`): no UI caller since 8 Oct; the client code and mocks are dead.
15. Collections worth: reachable only through the legacy Receivables page, which live builds never load.
16. The strategy MVP (price curve, envelope, receivable worth cells, pilot journal): `pnpm demo` never sets
    `NEXT_PUBLIC_STRATEGY_MVP`.
17. Customer economics (`FEATURE_CUSTOMER_ECONOMICS`, #97; #89 owner decisions).
18. `/inbox` is reachable only from `/verdict`; a lender agreement can be refiled through the API only.

**Product gaps already listed in the technical document:** settlement dates are not read (Table 7), capex combinations
(loan plus bridge), contract reading 75% on unseen contracts and no OCR, 6 of 26 router plans "cannot run today", one
repeating invoice per contract, live-model runs fewer than recorded ones.

**Open issues (17 Oct):** #164 (a deal needing clarification shows a recommendation and a ready counter), #163 (dangling
`#cash-options` links, empty `e2e/slice-b-round-three.spec.ts`, Receivables drops `from`), #161 (four API tests, one known
hash), #158 (accept as asked: one click logs two operations; decline reason not stored; a refused accept leaves a
PROPOSED commitment), #159, #157 (live retry flakes), #156 (a11y phone timeout), #155 (tracker owner decisions), #153
(reliability grade), #119 and #106 (mock flakes, order dependence), #144 Slice C, #146 Slice E, #113 the Financial
Timeline, #117, #118, #104, #103 (contract-ingestion debt: a later confirmed contract silently replaces the earlier one on
the deal card; missing oversize and zip-bomb route tests), #97 to #101 (customer economics phases), #58/#59 (shadow
pilot), #5, #7, #9, #10 (team, region, organiser, registration).

**From the handover and tracker:** NR1 (should the agent propose drawing the line and asking the buyer or owner when no
runnable plan exists: owner decision), LC1 (language-boundary certification against a live model, needs keys), the
LICENSE file, the deck (outline only) and the video, the `[TEAM:]` placeholders, round four (multi-deal comparison, the
proposing sandbox), the chain head not anchored, one worker process, no production configuration (SEC-06), a network demo
NO-GO. Loose ends still true in code: `NegotiateIn.max_rounds` is never read; the buyer's counter-counter is ignored; the
alert cure search is greedy; reconciliation reuses SHORT_PAYMENT for partial payments; the approval card hides the
approval id; `public_sme` is given the golden mandate.

**Owner questions not answered in every wording (BASELINE section 7, 46 questions, none in the top 30):** the minimum
cash reserve as a figure (LIQ-07), headroom above it (LIQ-08), cash in 30 days (LIQ-11), the 13-week forecast (LIQ-12),
money in transit (LIQ-16), cash if we do nothing (LIQ-17), who we owe (DEBT-02), what is drawn on the line (DEBT-07),
the cheapest facility (DEBT-09), the clean-down date (DEBT-10), interest over four months (DEBT-11), cost of funds
(DEBT-13), DSO (CUS-04), what one customer owes (CUS-11), next month's invoicing (CUS-12), "who are our customers"
(CUS-15), reliability (CUS-16), signed contracts and agreed terms (DEAL-07, DEAL-08), what we last offered (DEAL-10), the
cheapest way to raise ¥200,000 (FUN-01), borrowing against an invoice (FUN-07), what a bank needs (FUN-09), EBITDA
(COV-09), clean-down risk (COV-08), committed purchases (CAP-08), refusals and log integrity (ACT-04, ACT-05), money moved
(ACT-06), mandate expiry, validity and limits (MAN-03 to MAN-10), and the others in that table. Most are one metric away:
`answers/metrics.py` already computes `in_transit`, `cash_on`, `drawn_by_facility`, `mandate_limits_and_validity`,
`activity_since` and `invoice_financing_capacity`.

**Tests missing for what the video shows:** no e2e drives the setup wizard, the landing page, the blank-books card, the
Activity Reconciliation tab, the deal page's previous/next or the opener; `capex.spec.ts`, `buyside.spec.ts` and
`cash-stress.spec.ts` run on mocks only; nothing tests `scripts/judge_eval.py` itself; own books plus clock plus a late
invoice has no automated test (verified in process for this document).

**Stale documents found on the way:**
`docs/deliverables/JUDGING_QUESTIONS.md` Q8 (export on Activity; it is on `/trust?view=evidence`),
`services/api/evals/e2e/latest/summary.md` (S16 as CAPEX; now ASK_BOOKS), `services/api/evals/judge/judge-report.md`
(259 attacks, 16 Oct; the technical document's 260 is the round-four figure), `apps/web/DESIGN.md:884` (the Attach a deal
tile "left out"; it is rendered), two ADRs numbered 0013, ADR-0013 (setup) still "proposed".

## 15. Missing from the technical document

Features in the code that `docs/deliverables/technical_document.md` does not mention, or names only as a page or a route.

- **Setup:** the six steps and their fields, the "First look" forecast, signing with the re-typed token, the setup routes
  (`/setup/*` are not in Appendix C), the landing page `/welcome`, `POST /demo/restore`.
- **Daily view:** Home's cards (cash outlook, What we recommend, worklist, cash available today and the funding ring,
  upcoming movements, owed by customer), the Business and Demo shells, the Demo's Operator tools and engine views, the
  tours, the navigation (the §05 list omits Sandbox), the language switch.
- **Documents:** the review screen with clause links, "This deal at a glance", the lender-agreement comparison and
  facility link, refile (route only), the outcome card's links.
- **Customers:** the customer overview page, the inputs sheet, payment behaviour, buyer exposure and concentration,
  Business consequences, the late-payment stress on Cash.
- **Deals:** the buyer messages inbox, the Your deals queue, Your agreements grouped by money owed, the lifecycle strip
  and the deal tracker, the deal page with previous/next, accept as asked as a feature (Appendix C only).
- **Money and time:** the funding ring, the repay-the-line alert (C5) by name, the mandate-expiry and commitment-expiry
  alerts, the missing owner receipt screen (a limitation worth stating).
- **Ask FLOW:** the header input, slide-over, scope chip and suggested prompts; New conversation (route only);
  RECORD_FACT (chat never records a fact); the bare "approve it" bound to the approval just shown; the 80- and
  160-character limits; that the opener has no UI caller.
- **Strategy and capex:** the What-if routes, the cash price curve, collections worth, the Safe Deal Envelope, customer
  economics, the pilot journal, financial health (`/finance/health`), loan eligibility (`/lending/*`), long-term plans
  (`/capex/plans`), the borrower file's routes and downloads, the `NEXT_PUBLIC_STRATEGY_MVP` gate.
- **Records and judging:** the `/trust` page (evidence and security views), the Activity log's filters and evidence fold,
  the Receivables chase handoff and net-per-invoice view, `scripts/export_demo_evidence.py`,
  `docs/deliverables/JUDGING_QUESTIONS.md`, the `security_scenes` flag (it hides fixtures only).

**Lines that may be stale:**
- Line 851 lists "the agent key reading status and alerts through chat (S9)" as open; since R-11 (16 Oct) every agent-key
  chat reply passes an allow-list (`app/api/agent_view.py`). Ask the Security Lead whether S9 is closed.
- Line 770: "260 attack cases" is the round-four figure; the committed judge report says 259 (16 Oct): regenerate it.
- Line 764 lists the Business pages without Sandbox.
- Line 841 (the approval card hides the approval id) is still true.

## 16. Video plan

### 16a. The submission video (≤ 5:00 rule; target 4:50)

Record the story on the **golden books** (`pnpm demo`), with one short clip of the setup wizard on **blank books**
(`pnpm demo:blank`, a second run). Section 0b explains why the own-books path is not used for the money story: the
counters, the simulated buyer and the day-34 cure depend on the golden figures. 1920×1080, English subtitles, Business
mode unless marked Demo.

| # | Time | Seconds | Books | Scene and clicks | What it proves |
| --- | --- | --- | --- | --- | --- |
| 0 | 0:00–0:15 | 15 | — | Title card; "everything outside FLOW is simulated" | framing |
| 1 | 0:15–0:40 | 25 | blank → own | `/welcome` → Join FLOW now! → Start setup; flash steps 1–5 (step 3 "Fill from a contract" with `fixtures/contracts/fhr-2026-07-supply-agreement.md`); step 6 "First look" chart → Sign and open my books → Home answers from own figures | own books in six steps, limits signed |
| 2 | 0:40–0:55 | 15 | golden | Cut to the golden company's Home: "Your cash reserve becomes unsafe in 12 days", What we recommend ¥3,113.93 | am I safe, what to do, what it costs |
| 3 | 0:55–1:10 | 15 | golden (Demo) | Demo shell → Ask FLOW → Role: Buyer, BUYER-1 → paste EX01 (or Deals → Buyer messages → Foshan's WeChat) | the buyer channel: the buyer sees only a reply |
| 4 | 1:10–1:40 | 30 | golden | Deals → the request → Check against my limits: REJECT, ¥28,326.92 against the ¥5,000 cap, reserve breach; Options A and B; Cash impact → Business consequences | the verdict with its rule, figures and counters |
| 5 | 1:40–2:05 | 25 | golden (Demo) | Review and send the counter → "Open to a counter" → Option A agreed in round 1, funding landed (say that "Holds firm" ends in NO DEAL with the gap still funded) | bounded negotiation, bound to what the owner saw |
| 6 | 2:05–2:15 | 10 | golden | Your agreements → the deal's tracker | the deal followed after agreement |
| 7 | 2:15–2:30 | 15 | golden (Demo) | Story step "bank": the agreed early payment arrives (synthetic), then the clock to day 34 | time passes; receipts come from the bank only |
| 8 | 2:30–2:50 | 20 | golden | Home alarm; Receivables: ¥160,000 two days late, Chase payment; Ask FLOW "What needs my attention?" | late-payment alert; FLOW names a priced cure |
| 9 | 2:50–3:15 | 25 | golden | Queue it for my approval → Approvals: ¥200,000 at 32.5% a year, above the 15% ceiling → the owner clicks Approve | Tier 2: the agent cannot press this button |
| 10 | 3:15–3:30 | 15 | golden (Demo) | Clock to day 38 → Cash: landed; Activity → Reconciliation: MATCHED | the loop closes |
| 11 | 3:30–3:55 | 25 | golden | Attach deals: `fixtures/contract_terms/dgos-2026-09-supply-agreement.md` under Dongguan → clauses → Confirm (outcome card) → Set up in my books → forecast before/after (**separate take** on fresh golden books: it changes the figures of scenes 2–10) | contracts read, confirmed, then set up by the owner |
| 12 | 3:55–4:15 | 20 | golden | Ask FLOW: "Are we safe?", 我们安全吗？, then "Sign a personal guarantee for the bank loan" (refused, Tier 3) | answers from the books in two languages; refusals |
| 13 | 4:15–4:35 | 20 | golden | Account → Security and evidence → Download JSONL; terminal `python scripts/verify_evidence.py e.jsonl` → VALID | a tamper-evident record checkable without FLOW |
| 14 | 4:35–4:50 | 15 | — | Closing card: 260 attacks with 0 harm, 49/49 tasks, 0 wrong answers on 503 owner questions, 0 wrong autonomous accepts | results |

Recording notes. Scenes 3 to 10 can be recorded with the Demo story stepper (`docs/DEMO_FLOW.md`, rehearsed by
`e2e/demo.spec.ts`); its first step resets the books, so do not mix the hand-made path and the stepper in one take
(whether the story page picks up a deal agreed by hand was not checked). The bank event has no button outside the
stepper. Scene 11 changes the golden books, so record it last or on its own reset. If the owner prefers own books for
scenes 3 to 10, prepare the setup figures in advance (one open Foshan invoice, payroll once, committed line and invoice
financing; section 0b) and rehearse: the counters and the simulated buyer then work for the first customer, but the
day-34 cure may not exist.

### 16b. The full feature tour (15–20 minutes), in chapters

| Chapter | Minutes | Books | Contents |
| --- | --- | --- | --- |
| 1 Setup | 2:30 | blank → own | landing, sign-in, the six steps field by field, Fill from a contract and from an agreement, First look, Sign and open, Home on own books; launcher modes; Which books? (golden, busy, short facilities), reset and restore |
| 2 Daily view | 1:30 | golden | Home card by card, the worklist, the forecast, Business and Demo modes, Operator tools and engine views, the tour, 中文 |
| 3 Documents | 2:00 | golden | upload FHR (recorded reading), the review with clauses, deal at a glance, Confirm and the outcome card; party check (FHR under Dongguan), refile, new customer; DGOS → Set up in my books → Undo; the credit-line agreement linked to FAC-LINE |
| 4 Customers | 1:00 | golden | the customer overview, exposure and Stress-test payment, the decision record; the inputs sheet's off notice |
| 5 Deals | 2:30 | golden, then busy | inbox, verdict, Options A and B, Business consequences, send to the simulated buyer (open and hard-line), copy and mark sent, the buyer's answer, the queue with tabs (busy), accept as asked and decline (busy), agreements, tracker, previous/next |
| 6 Money | 1:30 | golden | Cash & funding, the router and its options, run a plan, the funding ring, Limits in plain words, the Approvals card |
| 7 Lifecycle | 1:30 | golden | the clock, recurring invoices, the synthetic bank receipt, late alerts and chase, the cure and its approval, reconciliation, repay-the-line, mandate expiry at day 76+ |
| 8 Ask FLOW | 2:00 | golden | page prompts, ASK_BOOKS in two languages, plans and "go ahead", a correction, approve by sentence, the RECORD_FACT refusal, nearest capability, a pasted approval ignored, New conversation, the buyer role |
| 9 Sandbox and strategy | 1:00 | golden | the sandbox from a deal (60 → 45 days, the Option A preset), stress on Cash; the strategy MVP only in a `NEXT_PUBLIC_STRATEGY_MVP=1` build (say so) |
| 10 Capex & purchases | 1:30 | golden | the quick check (lease selected), Apply, the borrower file and its downloads; the GZPM vendor contract, its schedule, Commit and the approval; financial health, loan eligibility, long-term plans |
| 11 Records and judging | 1:30 | golden | Receivables and chase, Activity with filters and the evidence fold, `/trust` evidence and security (the FastCapital scene), Download JSONL and `verify_evidence.py`; `scripts/judge_eval.py` in a terminal; the Demo story end to end in fast motion |
| 12 Security | 0:45 | golden | demo credentials off by default, rate limits (a 429), Tier 3 refused, the buyer's reply only |
| **Total** | **19:15** | | |
