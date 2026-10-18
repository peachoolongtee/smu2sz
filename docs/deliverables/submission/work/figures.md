# Figures for the submission

Figures and product screenshots for the technical document (Fintechathon 2026, International AI Track, Topic E). All files
are under `docs/deliverables/figures/`; the sources, alt text and design notes are in `figures/README.md`. Built on
18 Oct 2026 from `docs/techdoc-chat-fixes` at `571ea64f`, branch `docs/sub-figures`.

**Design system.** The existing figures' palette, fonts and sizes (`src/flowstyle.py`): FLOW brand blue, ink, purple, amber
and grey, Microsoft YaHei, smallest diagram text 13.5 pt at 8 in (about 10.8 pt at the 6.4 in embed). Every category is
also a word, shape or pattern, never colour alone. Each figure prints its build identifier in its bottom line. The
financial chart is not drawn here: `flowstyle.chart()`, `SERIES`, `yuan` / `yuan_k` and `stamp()` are ready for it.

**Embedding.** `<!-- figure: figures/<file> | Figure N. caption -->` in `docs/deliverables/technical_document.md`. The
diagrams are tall (8 × 11–11.7 in); embed them at 6.0–6.4 in wide, one per page. Screenshots: 6.4 in wide, except
`screen4-ask-answer.png`, which reads best at 4.5 in.

## Diagrams

| # | File | Caption | Where | Source |
| --- | --- | --- | --- | --- |
| A | `figures/fig8-system-architecture.png` | FLOW's architecture. A model assists in three places only (reading documents and buyer messages, classifying a chat request the rules miss, routing an owner's question to read-only tools) and sees redacted text only. Deterministic code computes every figure, and only the executor changes the books, recording every outcome in a hash-chained log. Buyer, lenders and bank feed are simulated. | 02, "Architecture diagram and component responsibilities": replaces Figure 2 (`fig1-architecture.png`, which names the compiler as the only model step) | `src/fig8_system_architecture.py` |
| B | `figures/fig9-request-to-settlement.png` | One buyer request from request to settlement. The terms stay proposed until the executor screens the buyer's acceptance; it then records the commitment, funds the plan through authorised operations, and the deal settles only when the (simulated) bank feed reports the cash and reconciliation marks the promise. | 02, after "One buyer request, end to end": replaces Figure 3 (`fig2-offer-lifecycle.png`) | `src/fig9_request_to_settlement.py` |
| C | `figures/fig10-authority-matrix.png` | Who may do what. Tier 1 runs inside the owner-signed mandate; Tier 2 waits for the owner; Tier 3 is refused for everyone, the owner included. The tier is computed from the typed operation alone, and the demo mandate's limits are shown below. | 04, "Tiered permissions and confirmation for sensitive actions": replaces Figure 7 (`fig3-permission-tiers.png`), or sits beside it if the gate order is kept | `src/fig10_authority_matrix.py` |

### Alt text

- **A.** Architecture diagram. A simulated buyer, the owner, the web app and a simulated bank feed call one FastAPI service.
  Three dashed trust zones sit below it. Model-assisted: question router, intent classifier and compiler, each sending
  redacted text to a model backend (recorded cache by default, live provider opt-in) and passing only typed output down.
  Deterministic core: read-only tools, financial engine, verifier, funding router. Action path: egress guard, signed
  mandate, executor, hash-chained log. The executor alone writes the books to storage (PostgreSQL, SQLite or in memory) and
  draws on simulated lenders; counter text leaves through the egress guard to the simulated buyer, or the owner copies it.
- **B.** Eleven steps top to bottom with a status bracket on the right. Steps 1–6 (request, reading, verdict and counters,
  owner gate, send by simulated channel or manual copy, reply from the simulated buyer or reported by the owner): proposed
  terms, nothing binds and no money moves. Step 7, the executor's acceptance screen: authorised operation. Step 8, commitment
  recorded: recorded commitment. Step 9, funding plan: authorised funding operations. Steps 10–11, bank-feed receipt and
  reconciliation: actual settlement. Badge shapes mark who acts (square code, diamond model, circle owner, hexagon simulated).
- **C.** A matrix with columns Tier 1, Tier 2 and Tier 3 and rows buyer offers, funding, cash received, purchases and
  contracts, and ownership and control. Tier 1: counter or reject, accept early payment on a named invoice, draw or advance on
  a committed facility, repay, book a bank-feed receipt, ask the owner. Tier 2: longer terms or concessions, a commitment
  above ¥100,000, an uncommitted facility, applying for or adding a facility, a payment reported by the agent or a buyer,
  buying equipment, setting up a contract's terms. Tier 3: a facility the owner did not request, a personal guarantee,
  collateral, equity, changing the mandate, any unknown operation. Footer: the signed demo mandate's limits.

## Product screenshots (one end-to-end walk)

Mock mode (the JSON mocks in `apps/web/mocks`, checked against the golden values; no API, no model, no money), Chromium 1440×900 at device scale 2, demo owner token, 18 Oct
2026, `571ea64f`. Annotated files have orange numbered callouts with a legend band and the scenario line; `-raw` files are
the same crops without annotations. Frames 6 and 7 are in Demo mode after story steps 5 and 8 (simulated bank receipt, owner
approval).

| # | File | Caption | Where |
| --- | --- | --- | --- |
| S1 | `figures/screens/screen1-home.png` | Home on the opening books. Without new funding cash falls to −¥105,000 within 30 days; the red recommendation card asks the owner to secure ¥405,000 before payroll, for ¥3,113.93, with no approval needed. | 01, "What the owner sees" (or Appendix E, replacing `shot1-home.png`) |
| S2 | `figures/screens/screen2-deal-verdict.png` | A buyer's request after FLOW checked it. (1) The verdict: counter with Option A. (2) Why it cannot be accepted as asked. (3) Option A is within the mandate. (4) Nothing is sent until the owner sends it. (5) The priced choices. | 01, "Core value and innovation": replaces Figure 1 (`shot2-deal-decision.png`) |
| S3 | `figures/screens/screen3-cash-plan.png` | Cash & funding: the plan FLOW's funding router chose (¥150k credit line today, ¥255k invoice financing in 3 days) for ¥3,113.93, within the signed limits, and the cash line with and without it. | 03, "Core algorithms and evaluation approach", beside the funding router (next to Figure 4) |
| S4 | `figures/screens/screen4-ask-answer.png` | Ask FLOW: "Are we safe?" answered as a card from the books (lead sentence, three key figures, links). The answer reads; it never acts. | 03, the Ask FLOW part of "Intent understanding, planning, tool use and state management" (replaces Figure 12, `shot10-ask-answer.png`) |
| S5 | `figures/screens/screen5-documents.png` | Documents: the agent's reading of supply agreement FHR-2026-07. The focused term (Price, §3.1) lights its clause, and markers show which terms each clause holds. | 02, "Models, tools, data sources" (why a model reads contracts), or Appendix E (replaces Figure 11, `shot9-attach.png`) |
| S6 | `figures/screens/screen6-deal-tracker.png` | The deal tracker after the buyer's early payment arrived from the simulated bank feed: on plan, the stages done and to come, and the cost expected at agreement against the actual so far, each line with its evidence. | 03, "state management" (following a deal to payment), or Appendix E |
| S7 | `figures/screens/screen7-activity.png` | Activity after the owner approved a Tier 2 funding request: "Record chain checks passed", and the request's log entry with its hash, the previous entry's hash and the executor's audit sentence. | 04, beside the tamper-evident log (or 05 next to Figure 9, `shot3-approval.png`) |

### Alt text

- **S1.** FLOW's Home. Left: "Company cash outlook, −¥105,000 without new funding, ¥300,000 with plan" over a 36-day step
  chart. Right: a red-bordered card, "Action needed: without funding your cash falls to −¥105k in 30 days. Secure ¥405,000
  before payroll in 12 days": a ¥150,000 credit-line draw today and ¥255,000 of invoice financing in 3 days, cost ¥3,113.93,
  no approval needed, with a "Check funding plan" button.
- **S2.** The deal page for Foshan Home Retail Co.'s request for 60-day terms. "FLOW recommends Option A: terms stay at 45
  days, no rebate; early settlement on up to ¥260,000 at 0.85%, paid within 2 days." Tiles: cash held at the minimum, cost
  ¥3,035.99, within your mandate. "Why not accept as asked: breached by ¥135k for 15 days." Buttons to review and send
  Option A or decline; a table compares accepting as asked, Option A and Option B.
- **S3.** "Recommended next step: secure ¥405k of funding", ¥150k bank credit line today and ¥255k against the ¥420k Foshan
  invoice in 3 days, estimated cost ¥3,113.93, within the signed limits, "Run funding plan" button; a 60-day chart where doing
  nothing falls to −¥105k and the chosen plan stays at or above the ¥300k reserve.
- **S4.** Ask FLOW. The owner asks "Are we safe?"; FLOW answers "Not on today's books: without new funding, cash falls below
  your ¥300,000 reserve from day 12, lowest −¥105,000 on day 30", with ¥405,000 funding needed, −¥105,000 lowest cash, below
  reserve from day 12, the plan's cost ¥3,113.93 and links to the forecast and the plan.
- **S5.** Contract text on the left with clauses 2.1 and 3.1 highlighted and numbered markers; clause 3.1, "The Buyer shall
  pay the Supplier RMB 420,000 for each Batch", is outlined. On the right, the terms the agent read, each with its quoted
  clause; term 8, Price, ¥420,000.00 per delivery batch, §3.1, is focused.
- **S6.** "This deal is on the agreed terms so far. On plan: the buyer paid the early part it promised." Stages: contract read,
  terms negotiated, early payment in (done), collecting (now), fulfilled (to come). Expected ¥3,035.99, actual so far
  ¥3,035.99, and a table of cost lines with how sure each is and a link to its evidence.
- **S7.** Activity with a green "Record chain checks passed" badge. "You approved ¥200,000.00 of invoice financing" and
  "Approval requested: ¥200,000.00 of invoice financing at 32.5% a year, above the 15.00% limit you signed", with its evidence
  open: entry 9, hash, previous hash, and the audit sentence "Queued for owner approval (APR-000001): effective annual cost
  32.52% is above the mandate's 15.00% ceiling".

## Not done here, and caveats

- The financial chart (data on `docs/sub-financial-audit`) is left to its own agent; the style helper is in place.
- The screenshots are mock mode: the JSON mocks in `apps/web/mocks` (`pnpm test:unit` checks them against
  `fixtures/golden/golden_values.json`), not a live API run. The figures match the
  golden books the document quotes (¥405,000, ¥3,113.93, ¥3,035.99, −¥105,000). Say "web app on mocks" in the
  caption if the document distinguishes the three run modes.
- The Ask FLOW answer (S4) and the Activity audit sentence (S7) still show internal day numbers ("day 12", "day 37 to
  day 47"); that is the product's current text, not an annotation.
- `technical_document.md` is not edited here; the editor swaps the figure lines.
- Regenerate: render each diagram with `uv run --no-project --with matplotlib --with pillow python <script>` from
  `figures/src`; screenshots with `capture_screens.mjs` against a mock dev server on a spare port, then `crop_screens.py`.
