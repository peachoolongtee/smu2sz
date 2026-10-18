# Figures for the submission

Figures and product screenshots for the technical document (Fintechathon 2026, International AI Track, Topic E). All files
are under `docs/deliverables/figures/`; the sources, alt text and design notes are in `figures/README.md`. Built on
18 Oct 2026 from `docs/techdoc-chat-fixes` at `571ea64f`, branch `docs/sub-figures`; refreshed the same day on branch
`docs/sub-figures2` against the build candidate `int/final3` at `2ce5265c` (fig9 revised; D–H and S8–S12 added).

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
| B | `figures/fig9-request-to-settlement.png` | One buyer request from request to settlement. A registered buyer writing on its own channel key is answered by FLOW alone inside the signed mandate (counter, decline, or acceptance of a plain early-payment discount; no owner step); any other request waits for the owner. The terms stay proposed until the executor screens the acceptance; it then records the commitment and funds the plan through authorised operations. If a funding leg is queued for approval or refused, the agreement stays recorded with its funding incomplete. The deal settles only when the (simulated) bank feed reports the cash and reconciliation marks the promise. (Revised 18 Oct on `int/final3` `2ce5265c`.) | 02, after "One buyer request, end to end": replaces Figure 3 (`fig2-offer-lifecycle.png`) | `src/fig9_request_to_settlement.py` |
| D | `figures/fig11a-cash-alternatives.png` | The financing alternatives for Foshan's request, like for like: five series under the same events, differing only by the day-0 choice. No action falls to −¥105,000; accepting as asked with no funding falls below the ¥300,000 reserve on days 47–61; the standing plan, Option A and Option B touch the reserve exactly on days 30–31. Day-62 cash = ¥590,000 − each choice's net cost (¥3,113.93, ¥5,040.00, ¥3,035.99, ¥2,446.46). | 03, the funding router and the counter pricing (replaces Figure 4 / `fig11-cash-scenarios.png`, first half) | `src/fig11a_cash_alternatives.py`; `work/fin/daily_cash.csv`, `events.csv` |
| E | `figures/fig11b-cash-disruption.png` | What happened after Option A was agreed, as the demo runs it: a ¥200,000 payroll added on day 25 and ¥160,000 paid late; the ¥200,000 cure, queued for the owner on day 34 (32.5% a year) and landing on day 37, keeps cash at or above the reserve every day, for ¥5,205.36 against ¥3,035.99 quoted. Without the cure the payroll alone would leave ¥111,964.01 on days 42–46. | 03 or 05, "reality diverges" in the story (replaces `fig11-cash-scenarios.png`, second half) | `src/fig11b_cash_disruption.py`; `work/fin/daily_cash.csv`, `events.csv` |
| F | `figures/fig-eval-buyer.png` | Buyer messages: share of verdicts that match the label, on the unseen first runs (33/63, 28/47), after tuning (44/63, 38/47), against today's policy (50/63, 44/47) and live on 1 Oct (42/63), each with its wrong autonomous accepts (4 of 8 and 2 in the first runs; 0 since). | 03, "Core algorithms and evaluation approach" (replaces `fig-eval-classes.png`, buyer rows) | `src/fig_eval_panels.py` |
| G | `figures/fig-eval-contracts.png` | Contract fields: the unseen batch 2's first reading got 215 of 285 fields right on the 17 text-layer contracts (75%), 45% over all 30 with the 13 scans refused; decision-critical fields 178 right, 45 missing, 11 wrong of 234. The tuned sets (hatched) reach 85% and 97%. | 03, contract reading (replaces the contract rows of `fig-eval-classes.png`; `fig6-contract-reading.png` keeps the per-format view) | `src/fig_eval_panels.py` |
| H | `figures/fig-eval-questions.png` | Owner questions: the bank answers 228 of 427 in-books turns (0 wrong); everyday wording 326/345, held-out part 127/142; the live router was fully right on 22 of the 63 questions that reached it, 22 of the 33 it answered. | 03, Ask FLOW evaluation (replaces the question rows of `fig-eval-classes.png`) | `src/fig_eval_panels.py` |
| C | `figures/fig10-authority-matrix.png` | Who may do what. Tier 1 runs inside the owner-signed mandate; Tier 2 waits for the owner; Tier 3 is refused for everyone, the owner included. The tier is computed from the typed operation alone, and the demo mandate's limits are shown below. | 04, "Tiered permissions and confirmation for sensitive actions": replaces Figure 7 (`fig3-permission-tiers.png`), or sits beside it if the gate order is kept | `src/fig10_authority_matrix.py` |

### Alt text

- **A.** Architecture diagram. A simulated buyer, the owner, the web app and a simulated bank feed call one FastAPI service.
  Three dashed trust zones sit below it. Model-assisted: question router, intent classifier and compiler, each sending
  redacted text to a model backend (recorded cache by default, live provider opt-in) and passing only typed output down.
  Deterministic core: read-only tools, financial engine, verifier, funding router. Action path: egress guard, signed
  mandate, executor, hash-chained log. The executor alone writes the books to storage (PostgreSQL, SQLite or in memory) and
  draws on simulated lenders; counter text leaves through the egress guard to the simulated buyer, or the owner copies it.
- **B.** Eleven steps top to bottom with a status bracket on the right. Steps 1–3: request, reading, verdict and counters.
  Then two lanes: 4a "Tier 1, alone" for a registered buyer on its own channel key (FLOW counters, declines, or accepts a
  plain early-payment discount inside the signed mandate, no owner step; counters and declines go back on the channel,
  egress-checked, binding nothing; an acceptance goes to step 7), and for any other sender 4b the owner gate, 5a/5b send by
  simulated channel or the owner's copy, 6a/6b reply from the simulated buyer or reported by the owner. Steps 1–6: proposed
  terms, nothing binds and no money moves. Step 7, the executor's acceptance screen (a refusal records nothing): authorised
  operation. Step 8, commitment recorded: recorded commitment. Step 9, funding plan, with a dashed end-state box 9b,
  "agreement recorded; funding incomplete: a leg queued or refused after step 8": authorised funding operations, or queued /
  refused. Steps 10–11, bank-feed receipt and reconciliation: actual settlement. Badge shapes mark who acts (square code,
  diamond model, circle owner, hexagon simulated).
  *Text equivalent:* request → reading → verdict → [own channel key: FLOW alone, Tier 1 → acceptance] or [owner gate → send →
  reply] → executor screen → commitment recorded → funding plan → funded, or agreement recorded with funding incomplete →
  bank-feed receipt → reconciliation.
- **D.** Step chart of closing cash (CNY) over days 0–62 with the dashed ¥300,000 reserve and the shaded area below it;
  five series, each with its own colour, dash and marker: A0 no action, A1 standing plan, A2 EX01 as asked with no funding,
  A3 Option A, A4 Option B. Eleven numbered event markers with a key, then a table.
  *Text equivalent (lowest; day 62; net cost):* A0 −¥105,000.00 (days 30–31); ¥590,000.00; ¥0.00. A1 ¥300,000.00;
  ¥586,886.07; ¥3,113.93. A2 ¥164,960.00 (below the reserve days 47–61); ¥584,960.00; ¥5,040.00. A3 ¥300,000.00;
  ¥586,964.01; ¥3,035.99. A4 ¥300,000.00; ¥587,553.54; ¥2,446.46 (¥3,706.46 funding − ¥1,260.00 premium). Shared events:
  payroll −¥340,000 day 12, supplier −¥120,000 day 20, loan −¥45,000 days 30 and 60, bill −¥100,000 day 47.
- **E.** Step chart, same axes and reserve, three Option A series: B0 as quoted (reference), B1 with the month-2 payroll only,
  B2 as the demo ran; eleven dated markers with a key, then a table.
  *Text equivalent:* day 25 a ¥200,000 payroll is scheduled for day 42; day 32 ¥160,000 of the invoice is not paid (B2 holds
  at ¥300,000); day 34 FLOW proposes ¥200,000 of invoice financing at 32.5% a year, queued as APR-000001, approved by the
  owner; day 36 the ¥160,000 arrives; day 37 the advance lands (¥660,000); day 42 payroll (¥460,000); day 47 invoice in,
  advance and line repaid (¥429,794.64); day 60 loan (¥384,794.64). Lowest; day 62; cost: B0 ¥300,000.00; ¥586,964.01;
  ¥3,035.99. B1 ¥111,964.01; ¥386,964.01; ¥3,035.99. B2 ¥300,000.00; ¥384,794.64; ¥5,205.36.
- **F.** Horizontal bars in four groups, each a share of its own row; right share solid (hatched and tagged TUNED when the
  set was tuned on), with the counts under each bar and the wrong autonomous accepts beside it.
  *Text equivalent:* first runs (1 Oct): held-out 3 33/63, 4 of 8 accepts wrong; held-out 2 28/47, 2 wrong. After tuning
  (18 Oct): 44/63, 0 of 1; 38/47, 0 of 2. Today's policy, reading only: 50/63; 44/47. Live DeepSeek 1 Oct: 42/63, 0 wrong.
- **G.** Stacked bars (right, missing, wrong, refused) with counts under each bar, the share right and the number stated
  wrongly beside it; tuned rows hatched.
  *Text equivalent:* batch 2 first reading, 17 text-layer contracts: 215 right, 58 missing, 12 wrong of 285 (75%); over all
  30: + 189 refused, 215/474 (45%); decision fields 178 / 45 / 11 of 234 (76%) + 18 stage items matching no key item. Tuned:
  batch 2 after fixes 198 / 34 / 2 of 234 (85%); batch 1 412 / 12 / 0 of 424 (97%).
- **H.** Stacked bars (right, partly, declined, wrong, rejected) with counts, share right and wrong count; tuned rows hatched.
  *Text equivalent:* bank (tuned) 228 / 45 / 154 / 0 of 427 (53%); everyday wording all (mostly tuned) 326 right, 15
  missed, 4 wrong of 345 (94%); held-out part 127 / 12 / 3 of 142 (89%). Live router 18 Oct: of 63 reached, 22 right, 10
  partly, 1 wrong, 29 "cannot answer yet", 1 rejected (35%); of 33 answered, 22 / 10 / 1 (67%).
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

## Product screenshots from the build candidate (18 Oct 2026)

Retaken from `int/final3` at `2ce5265c` in mock mode (same browser settings and annotation style; scenario line
"Mock mode, golden books (synthetic), int/final3 @ 2ce5265c"). They replace the `docs/deliverables/screenshots` frames of the
same names; full alt text in `figures/README.md`.

| # | File | Caption | Where |
| --- | --- | --- | --- |
| S8 | `figures/screens/shot1-home.png` | Home on the opening books: −¥105,000 within 30 days without new funding; the red card recommends securing ¥405,000 before payroll in 12 days (credit line ¥150,000 today, invoice financing ¥255,000 in 3 days) for ¥3,113.93, with no approval needed. | 01 or Appendix E (replaces `shot1-home.png`; use instead of S1) |
| S9 | `figures/screens/shot3-approval.png` | An approval waiting: FLOW queued ¥200,000 of invoice financing because 32.5% a year is above the 15% ceiling the owner signed; it costs ¥1,782.19, and nothing runs until the owner authorizes or declines. | 04/05, tiered permissions (replaces `shot3-approval.png`) |
| S10 | `figures/screens/shot6-capex.png` | Capex quick check of the ¥600,000 machine: worth doing (NPV ¥380,885.77, payback month 31); the 36-month loan is selected, the 18-month loan fails DSCR in months 1–3, and figures that do not apply read "—", not "None". | 03, capex (replaces `shot6-capex.png`) |
| S11 | `figures/screens/shot9-attach.png` | Documents, attaching a contract: what it is, who it is with, a drop zone and "Upload and read" (PDF with text, Word or plain text, up to 5 MB); the documents already read, each confirmed by the owner. | 02 or Appendix E (replaces `shot9-attach.png`) |
| S12 | `figures/screens/shot10-ask-answer.png` | Ask FLOW, full page in its card: "Are we safe?" answered from the books (lead, three figures, the plan's cost, links). The mocks hold no recording of "Can I pay everyone?", so this recorded question is shown. | 03, Ask FLOW (replaces `shot10-ask-answer.png`; use instead of S4) |

Alt text, short form (full text in `figures/README.md`):

- **S8.** Home: cash outlook −¥105,000 without new funding and ¥300,000 with plan over a 36-day chart; a red card "Secure
  ¥405,000 before payroll in 12 days", cost ¥3,113.93, split ¥150,000 credit line today and ¥255,000 invoice financing in 3
  days, "No approval needed". Six numbered callouts with a legend.
- **S9.** Approvals card "Request ¥200,000 of invoice financing", waiting for approval; 32.5% a year above the 15.00% limit;
  cost ¥1,782.19; lands in 3 days if approved; a decline leaves ¥200,000 below the reserve in 8 days; Authorize and Decline
  buttons. Five callouts.
- **S10.** Capex quick check: verdict, four tiles (NPV, payback, leverage 2.28× of 2.50×, 2.47×), and a table of four
  financing structures with DSCR for months 1–6; cash + credit line shows "—" throughout and is infeasible; 18-month loan
  fails months 1–3; 36-month loan selected; 48-month lease feasible but ¥39,121.18 dearer. Five callouts.
- **S11.** Documents upload card (what it is, who it is with, add a customer, drop zone, Upload and read) and the list of
  three read documents, each confirmed by the owner. Five callouts.
- **S12.** Ask FLOW card: "Are we safe?" and the answer "Not on today's books ... lowest −¥105,000 on day 30", tiles
  ¥405,000 / −¥105,000 / day 12, the plan's ¥3,113.93 and links, suggested questions. Six callouts.

## Not done here, and caveats

- The financial chart is now `fig11a` and `fig11b` (18 Oct), drawn from `work/fin`; `fig11-cash-scenarios.png` is kept
  but superseded.
- "Can I pay everyone?" could not be captured: `apps/web/mocks/nl_ask.json` on `int/final3` has no recording for it, and
  no live model was called. S12 shows the recorded "Are we safe?".
- `fig9`'s 9b is described from `app/api/accept.py` and `app/nl/plans.py`; the code has no status of that name, so the
  label is ours.
- The screenshots are mock mode: the JSON mocks in `apps/web/mocks` (`pnpm test:unit` checks them against
  `fixtures/golden/golden_values.json`), not a live API run. The figures match the
  golden books the document quotes (¥405,000, ¥3,113.93, ¥3,035.99, −¥105,000). Say "web app on mocks" in the
  caption if the document distinguishes the three run modes.
- The Ask FLOW answer (S4) and the Activity audit sentence (S7) still show internal day numbers ("day 12", "day 37 to
  day 47"); that is the product's current text, not an annotation.
- `technical_document.md` is not edited here; the editor swaps the figure lines.
- Regenerate: render each diagram with `uv run --no-project --with matplotlib --with pillow python <script>` from
  `figures/src`; screenshots with `capture_screens.mjs` against a mock dev server on a spare port, then `crop_screens.py`.
