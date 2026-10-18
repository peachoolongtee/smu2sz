# Figures for the technical document

Eleven PNG figures and seven product screenshots for FLOW's final technical document. Each figure is 2400 px wide (8 in at
300 dpi) on white. Each has a matplotlib source in `src/` that regenerates it. The style lives in `src/flowstyle.py`:

- **Palette:** the FLOW brand from `apps/web/app/globals.css`. Brand blue `#0368e9`, ink `#24324a`, purple `#9252dc`,
  amber `#b7791f` and grey `#768399`. There is no red-green pair.
- **Fonts:** Microsoft YaHei, so Chinese renders; Noto Sans SC is the fallback.
- **Size:** the smallest text is 13.5 pt at 8 in, which prints at 11 pt when the figure is 6.5 in wide.

`scripts/build_deliverables.py` embeds a figure at 6.4 in, so the smallest text prints at about 10.8 pt.

**Render** one figure from `src/`:

```bash
uv run --no-project --with matplotlib --with pillow python fig1_architecture.py
```

**Embed** a figure in `docs/deliverables/*.md`. The path is relative to that folder:

```markdown
<!-- figure: figures/fig1-architecture.png | Figure 1. ... -->
```

| Figure | Caption | Source | Data |
| --- | --- | --- | --- |
| `fig1-architecture.png` | FLOW in one picture: the compiler is the only model-backed step, the verifier decides on typed obligations, and only the executor writes. | `src/fig1_architecture.py` | Read from the code on dev `975e082f`: `app/compiler` (redaction, grounding, coverage), `app/verifier`, `app/financial`, `app/funding`, `app/operations/executor.py`, `app/mandate/tiers.py`, `app/api/auth.py` (bank feed) |
| `fig2-offer-lifecycle.png` | One buyer request from message to money, marking which steps run on their own, which wait for the owner and which are simulated. | `src/fig2_offer_lifecycle.py` | `app/api/offers.py`, `decide.py` (`/evaluate`, `/negotiate`), `accept.py`, `outbound.py` (`/offered`, `/buyer-accepted`), the executor's `AcceptOffer`, `app/commitments`, `app/alerts/reconcile.py`; outcomes from `app/domain/models.py` `Outcome` |
| `fig3-permission-tiers.png` | Who may do what: the three permission tiers with examples, and the executor's gates in the order the code runs them. | `src/fig3_permission_tiers.py` | `app/mandate/tiers.py` (`tier_for`), `app/operations/executor.py` (`_run`, `_screen_commitment`, `_handle`) |
| `fig4-golden-cash.png` | The golden books' cash over 60 days: without new funding, cash falls below the ¥300k minimum on day 12; FLOW's plan keeps it at or above the minimum. | `src/fig4_golden_cash.py` | `GET /home` on the golden books, in-process (TestClient, `LLM_MODE=cache`, `DATABASE_URL=memory`, `DEMO_MODE=1`), `cash.series` and `cash.plan_series`. The values are printed in the script, and `--fetch` refreshes them. |
| `fig5-heldout-results.png` | The compiler's held-out results, each labelled as unseen or tuned on: no misread message was accepted without the owner after ADR-0005. | `src/fig5_heldout_results.py` | First run and live DeepSeek rows: `services/api/evals/accuracy_summary.md` (1 Oct 2026, 389cfd9). Today rows and form baseline: `../evidence/EVIDENCE_PACK.md` section 1 (dev 975e082f, 17 Oct 2026) |
| `fig6-contract-reading.png` | Reading Chinese contracts, by format: 98% on the tuned batch, 75% on the held-out batch, 86% after the fixes, and nothing from scans or photos, which have no OCR. | `src/fig6_contract_reading.py` | Scoring logs of 16–17 Oct 2026 (`b2fix/b1-redact.log`, `b2fix/b2-redact.log`, `contract-cn2/mismatches.csv` = `b2fix/b2-base.log`). These are not in the repo, so the script quotes the per-format rows. |
| `fig7-security-results.png` | The attack catalogue: 279 stored cases by class (128 API, 151 chat), none violating the defined harm oracles; all reached their path, 120 of 128 API cases stopped by the named control. | `src/fig7_security_results.py` | `services/api/evals/security/latest_report.json` (regenerated on the round-five batch, 18 Oct 2026) |
| `fig-eval-classes.png` | FLOW's accuracy results grouped by evidence class: unseen held-out first runs, the same sets after tuning on their failures, recorded model replays and live provider calls, each with what its own oracle scores wrong. | `src/fig_eval_classes.py` | Values printed in the script: `services/api/evals/heldout3_report.md`, `heldout2_report.md`, `heldout3_live_deepseek_report.md`; offline re-runs on `571ea64f`, 18 Oct 2026 (`../submission/work/eval/offline_reruns_20261018.json`); contract field scores (`../submission/work/eval/contracts_*_fields.json`); the 18 Oct live router grades (`../submission/work/eval/live_router_outcomes.json`) |

**Alt text, `fig-eval-classes.png`.** A horizontal bar chart in four labelled groups. Unseen held-out, first run (blue):
buyer messages held-out 3, 52% of verdicts right (33 of 63), with 4 of 8 autonomous accepts wrong; held-out 2, 60% (28 of
47), 2 wrong accepts; owner wording held-out part, 89% (127 of 142), 3 wrong topics. After tuning on failures (purple):
held-out 3, 70% (44 of 63), 0 of 1 accept wrong; the same against today's policy, 79% (50 of 63); held-out 2, 81% (38 of
47), 0 of 2 accepts wrong; owner wording tuning part, 98% (199 of 203), 1 wrong topic; owner-question bank, 53% of in-books
turns answered (228 of 427), 0 wrong. Recorded DeepSeek replay (grey): contracts batch 2 first reading, 75% of fields (215
of 285), 12 wrong values and 18 stage items matching no key item; batch 2 after fixes, 86% (hatched, tuned); batch 1, 98%
(hatched, tuned). Live DeepSeek calls (amber): held-out 3 on 1 Oct, 67% (42 of 63), no wrong accepts; Ask router answers
on 18 Oct, 67% right (22 of 33), 1 wrong and 10 partial. A note says each bar is a share of its own row's denominator and
rows with different oracles do not compare.
| `fig8-system-architecture.png` | FLOW's architecture: the three model-assisted steps see redacted text only and propose typed output; deterministic code computes every figure, and only the executor changes the books. | `src/fig8_system_architecture.py` | Read from the code on `docs/techdoc-chat-fixes` `571ea64f`: `app/main.py` routers, `app/compiler`, `app/nl/classifier.py`, `app/nl/router`, `app/egress/guard.py`, `app/operations/executor.py`, `app/persistence` |
| `fig9-request-to-settlement.png` | One buyer request from request to settlement, marking what is only proposed, what is authorised, what is recorded and what has actually settled. | `src/fig9_request_to_settlement.py` | `app/api/offers.py`, `decide.py`, `accept.py`, `outbound.py`, the executor's `AcceptOffer`, `app/commitments`, `app/api/alerts.py`, `app/alerts/reconcile.py` (`571ea64f`) |
| `fig10-authority-matrix.png` | The authority matrix: what FLOW may do inside the signed mandate (Tier 1), what waits for the owner (Tier 2) and what is refused whoever asks (Tier 3), with the demo mandate's limits. | `src/fig10_authority_matrix.py` | `app/mandate/tiers.py` `tier_for`; `fixtures/scenarios/golden_sme.mandate.signed.json` (`571ea64f`) |
| `fig11-cash-scenarios.png` | The demo company's closing cash under four scenarios, days 0 to 62, against the ¥300,000 reserve, with nine dated events. Supersedes `fig4-golden-cash.png` in the technical document (Figure 4). | `src/fig11_cash_scenarios.py` | `../submission/work/fin/daily_cash.csv` and `events.csv` (financial audit, 18 Oct 2026): the independent recomputation from the golden fixtures, equal to the engine replayed through the API to the fen (`work/fin/compare.csv`, 39 of 39) |

Figures 8 to 10 (18 Oct 2026) supersede figures 1 to 3 for the submission: figure 1 named the compiler as the only model
step, while the build has three (the compiler, the chat intent classifier and the Ask FLOW question router). Figure 3 stays
useful for the executor's gate order. Each new figure carries its build identifier in its bottom line.

**Non-colour channels.** Every category is also a word, a shape or a pattern: a `MODEL-ASSISTED` / `OWNER` / `SIMULATED` tag
on the box edge, hatching for simulated parties, step badges shaped by who acts (square code, diamond model, circle owner,
hexagon simulated), tier badges and bullets shaped square / circle / octagon, and a line style per status band in figure 9
(dotted proposed, solid authorised, double recorded, solid bar settled).

**Chart helper for data figures.** `flowstyle.chart()`, `SERIES` (colour, marker and line style per series), `BAR_HATCHES`,
the `yuan` / `yuan_k` tick formatters, `stamp()` for the build and scenario line, and `BUILD`. The docstring at the
helper shows a complete example; the financial chart of `docs/sub-financial-audit` can use it as is.

### Alt text

- **fig8-system-architecture.png.** Architecture diagram. Top row: a simulated buyer, the owner, the web app and a simulated
  bank feed, all calling one FastAPI service. Below it, three dashed trust zones. The model-assisted zone holds the question
  router, the intent classifier and the compiler, each sending redacted text to a model backend (recorded cache by default,
  a live provider only when opted in) and passing only typed output down. The deterministic core holds the read-only tools,
  the financial engine, the verifier and the funding router. The action path holds the egress guard, the owner-signed
  mandate, the executor and the hash-chained log. The executor alone writes the books to storage (PostgreSQL, SQLite or
  in memory) and moves money only on simulated lenders; counter text leaves through the egress guard to the simulated buyer,
  or the owner copies it.
- **fig9-request-to-settlement.png.** Vertical flow of eleven steps with a status bracket on the right. Steps 1 to 6
  (request, reading, verdict and counters, owner gate, send by simulated channel or by the owner's manual copy, reply from
  the simulated buyer or reported by the owner) are bracketed "proposed terms: nothing binds, no money moves". Step 7, the
  executor's acceptance screen, is "authorised operation"; step 8, commitment recorded in the hash-chained log, is
  "recorded commitment"; step 9, the funding plan, is "authorised funding operations"; steps 10 and 11, the bank-feed
  receipt and reconciliation, are "actual settlement". Badge shapes mark who acts: square for code, diamond for the model,
  circle for the owner, hexagon for a simulated party.
- **fig10-authority-matrix.png.** A three-column matrix, Tier 1 (FLOW may act inside the signed mandate), Tier 2 (needs the
  owner's approval) and Tier 3 (never, whoever asks), with rows for buyer offers, funding, cash received, purchases and
  contracts, and ownership and control. Examples: Tier 1 counters, rejects, accepts early payment on a named invoice, draws
  on a committed facility, repays, books a bank-feed receipt; Tier 2 longer terms or concessions, commitments above
  ¥100,000, uncommitted facilities, applying for a facility, a payment reported by the agent or a buyer, buying equipment,
  setting up a contract's terms; Tier 3 a facility the owner did not request, personal guarantees, collateral, equity,
  changing the mandate and any unknown operation. Below: the demo mandate's limits.
- **fig11-cash-scenarios.png.** A step chart of closing cash in CNY (minus ¥100k to ¥900k) over days 0 to 62, with a dashed
  line and a shaded band below the ¥300,000 reserve. Four lines: today's books with no new funding (grey, dash-dot) fall
  below the reserve on day 12 and to −¥105,000 on days 30–31; FLOW's standing plan (blue, solid; credit line ¥150,000 plus
  invoice financing ¥255,000, cost ¥3,113.93) touches the reserve exactly on day 30 and never goes below it; the buyer's
  request accepted as asked with no new funding (amber, dashed) stays above the reserve until day 47, then falls to
  ¥209,960 (¥90,040 short) and to ¥164,960 on day 60; Option A as the demo runs it (purple, dotted) holds the reserve on
  every day, reaching ¥460,000 on day 42 after the month-2 payroll, because the owner approved a ¥200,000 advance on day 34.
  Nine numbered markers along the top date the events: early payment (day 2), payroll (12), the month-2 payroll being
  scheduled (25), loan payment (30), the invoice due with ¥160,000 unpaid (32), the advance proposed and approved (34), the
  advance landing (37), the next invoice paid and the bill (47), loan payment (60). The bottom line names the books, the
  currency, the data file and the build.

## Product screenshots (`screens/`)

Seven frames of one end-to-end product walk, taken on 18 Oct 2026 from `docs/techdoc-chat-fixes` at `571ea64f` with the web
app in **mock mode** (`NEXT_PUBLIC_API_MODE=mock`: the JSON mocks in `apps/web/mocks`, checked against the golden values; no API, no
model, no money), Chromium at 1440×900 and device scale 2, signed in with the published demo owner token. `src/capture_screens.mjs`
takes them and `src/crop_screens.py` crops them and adds the orange numbered callouts and the legend band (the style of
`../screenshots`). `screenN-*.png` is annotated; `screenN-*-raw.png` is the same crop without annotations. Each frame's
legend is sized to print at about 9 pt or more at 6.4 in. The numbered circles on the Home and Cash charts are the product's
own markers, not callouts.

| Screen | Caption |
| --- | --- |
| `screen1-home.png` | Home on the opening books: without new funding cash falls to −¥105,000 within 30 days, and the red recommendation card asks to secure ¥405,000 before payroll, for ¥3,113.93, with no approval needed. |
| `screen2-deal-verdict.png` | Foshan's request after FLOW checked it: the verdict (counter with Option A), why the request cannot be accepted as asked, and the priced choices. Nothing is sent until the owner sends it. |
| `screen3-cash-plan.png` | Cash & funding: the plan (¥150k credit line today, ¥255k invoice financing in 3 days) for ¥3,113.93 within the signed limits, and the cash line with and without it. |
| `screen4-ask-answer.png` | Ask FLOW, full page: "Are we safe?" answered as a card, with the lead sentence, three key figures and links; the answer reads the books and acts on nothing. |
| `screen5-documents.png` | Documents: the agent's reading of supply agreement FHR-2026-07; the focused term (Price, §3.1) lights its clause in the contract text. |
| `screen6-deal-tracker.png` | The deal tracker after the buyer's early payment arrived from the simulated bank feed: on plan, the stages, and the cost expected at agreement against the actual so far. |
| `screen7-activity.png` | Activity after the owner approved a Tier 2 funding request: "Record chain checks passed", and the request's log entry with its hash, the previous hash and the executor's audit sentence. |

### Alt text

- **screen1-home.png.** FLOW's Home page. Left: "Company cash outlook, −¥105,000 without new funding, ¥300,000 with plan" over
  a step chart of cash for 36 days. Right: a red-bordered card, "Action needed: without funding your cash falls to −¥105k in
  30 days. What we recommend: secure ¥405,000 before payroll in 12 days", split into a ¥150,000 credit-line draw today and
  ¥255,000 of invoice financing in 3 days, cost ¥3,113.93, "No approval needed", with a "Check funding plan" button.
- **screen2-deal-verdict.png.** The deal page for Foshan Home Retail Co.'s request for 60-day terms. "FLOW recommends
  Option A: terms stay at 45 days, no rebate; early settlement on up to ¥260,000 at 0.85%, paid within 2 days." Tiles: cash
  held at the minimum, cost ¥3,035.99, within your mandate. "Why not accept as asked: breached by ¥135k for 15 days; cannot
  be accepted within your signed limits." Buttons to review and send Option A or decline. Below, a table compares accepting
  as asked, Option A and Option B on terms, lowest cash and cost.
- **screen3-cash-plan.png.** Cash & funding. "Recommended next step: secure ¥405k of funding", ¥150k from the bank credit
  line today and ¥255k against the ¥420k Foshan invoice in 3 days, estimated cost ¥3,113.93, within the signed limits, with a
  "Run funding plan" button. Below, a 60-day cash chart: doing nothing falls to a lowest of −¥105k; the chosen plan stays at
  or above the ¥300k minimum reserve.
- **screen4-ask-answer.png.** The Ask FLOW page. The owner asks "Are we safe?". FLOW answers: "Not on today's books: without
  new funding, cash falls below your ¥300,000 reserve from day 12, lowest −¥105,000 on day 30." Three figures: ¥405,000
  funding needed, −¥105,000 lowest cash, below reserve from day 12. "FLOW's plan covers it for ¥3,113.93", with links to the
  cash forecast and the plan.
- **screen5-documents.png.** The Documents page. Left, the contract text with clauses 2.1 and 3.1 highlighted and numbered
  markers; clause 3.1, "The Buyer shall pay the Supplier RMB 420,000 for each Batch", is outlined. Right, the list of terms
  the agent read, each with its quoted clause; term 8, Price, ¥420,000.00 per delivery batch, §3.1, is focused.
- **screen6-deal-tracker.png.** The deal tracker. "This deal is on the agreed terms so far. On plan: the buyer paid the early
  part it promised." Stages: contract read, terms negotiated, early payment in (done), collecting (now), fulfilled (still to
  come). "What it costs you": expected ¥3,035.99, actual so far ¥3,035.99, with a table of each cost line, how sure it is
  and a link to its evidence.
- **screen7-activity.png.** The Activity page with a green "Record chain checks passed" badge. Entries: "You approved
  ¥200,000.00 of invoice financing" and "Approval requested: ¥200,000.00 of invoice financing at 32.5% a year, above the
  15.00% limit you signed". The second entry's evidence is open: entry 9, its hash, the previous hash, and the audit
  sentence "Queued for owner approval (APR-000001): effective annual cost 32.52% is above the mandate's 15.00% ceiling".
