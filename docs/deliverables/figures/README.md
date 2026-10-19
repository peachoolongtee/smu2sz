# Figures for the technical document

PNG figures and product screenshots for FLOW's final technical document (the 18 Oct 2026 refresh adds `fig11a`,
`fig11b`, the three `fig-eval-*` panels and five frames retaken from `int/final3`; `work/figures.md` maps each to its place). Each figure is 2400 px wide (8 in at
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
| `fig-eval-buyer.png` | Buyer messages: how often FLOW's verdict is the labelled one, on the unseen first runs, after tuning on their misses, against today's policy and with a live model, each with its denominator and its wrong autonomous accepts (6 in the first runs, 0 of 3 today). | `src/fig_eval_panels.py` | `services/api/evals/heldout3_report.md`, `heldout2_report.md`, `heldout3_live_deepseek_report.md` (1 Oct 2026); `../submission/work/eval/offline_reruns_20261018.json` (`571ea64f`, 18 Oct) |
| `fig-eval-contracts.png` | Contract fields: on the unseen batch 2, the first reading got 75% of fields right on the 17 text-layer contracts and 45% over all 30 (13 scans refused); decision-critical fields split into right, missing and wrong; the tuned sets are hatched. | `src/fig_eval_panels.py` | `../submission/work/evaluation.md` §5 (recorded DeepSeek readings re-scored with `eval_contracts.py score`; the documents and keys are outside the repo) |
| `fig-eval-questions.png` | Owner questions: the bank answers 228 of 427 turns the books can answer (0 wrong); everyday wording 326/345 (held-out part 127/142); the live router got 22 fully right of the 63 questions that reached it, 22 of the 33 it answered. | `src/fig_eval_panels.py` | `offline_reruns_20261018.json`; `../submission/work/eval/live_router_outcomes.json` |
| `fig-eval-classes.png` | Superseded by the three panels above (18 Oct 2026), which do not put different oracles on one axis. FLOW's accuracy results grouped by evidence class: unseen held-out first runs, the same sets after tuning on their failures, recorded model replays and live provider calls, each with what its own oracle scores wrong. | `src/fig_eval_classes.py` | Values printed in the script: `services/api/evals/heldout3_report.md`, `heldout2_report.md`, `heldout3_live_deepseek_report.md`; offline re-runs on `571ea64f`, 18 Oct 2026 (`../submission/work/eval/offline_reruns_20261018.json`); contract field scores (`../submission/work/eval/contracts_*_fields.json`); the 18 Oct live router grades (`../submission/work/eval/live_router_outcomes.json`) |

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
| `fig8-system-architecture.png` | FLOW's architecture: the three model-assisted steps see redacted text only and propose typed output; deterministic code computes every figure, and every typed operation goes through the executor; a footnote names the logged writes outside it (clock, books setup, a new customer) and the demo reset. | `src/fig8_system_architecture.py` | Read from the code on `docs/techdoc-chat-fixes` `571ea64f`: `app/main.py` routers, `app/compiler`, `app/nl/classifier.py`, `app/nl/router`, `app/egress/guard.py`, `app/operations/executor.py`, `app/persistence` |
| `fig9-request-to-settlement.png` | One buyer request from request to settlement: a registered buyer on its own channel key is answered by FLOW alone inside the signed mandate (Tier 1), any other request waits for the owner; the figure marks what is only proposed, what is authorised, what is recorded, what has settled, and the end state "agreement recorded; funding incomplete". | `src/fig9_request_to_settlement.py` | `app/api/offers.py`, `decide.py`, `accept.py`, `outbound.py`, the executor's `AcceptOffer`, `app/commitments`, `app/api/alerts.py`, `app/alerts/reconcile.py` (`571ea64f`); the Tier-1 branch and outcome 9b re-checked on `int/final3` `2ce5265c`: `app/api/nl.py` (channel key binds the sender), `app/nl/offers.py` `counterparty_message`, `app/mandate/tiers.py` `tier_for`, `app/api/accept.py` `funding_next` |
| `fig10-authority-matrix.png` | The authority matrix: what FLOW may do inside the signed mandate (Tier 1), what waits for the owner (Tier 2) and what is refused whoever asks (Tier 3), with the demo mandate's limits. | `src/fig10_authority_matrix.py` | `app/mandate/tiers.py` `tier_for`; `fixtures/scenarios/golden_sme.mandate.signed.json` (`571ea64f`) |
| `fig11-cash-scenarios.png` | The demo company's closing cash under four scenarios, days 0 to 62, against the ¥300,000 reserve, with nine dated events. Superseded by `fig11a` and `fig11b` (18 Oct 2026), which separate the like-for-like alternatives from what happened after the choice; kept, and its source still renders. | `src/fig11_cash_scenarios.py` | `../submission/work/fin/daily_cash.csv` and `events.csv` (financial audit, 18 Oct 2026): the independent recomputation from the golden fixtures, equal to the engine replayed through the API to the fen (`work/fin/compare.csv`, 39 of 39) |
| `fig11a-cash-alternatives.png` | The financing alternatives for Foshan's request, like for like: the same events in every series, so the lines differ only by the choice made on day 0. No action falls to −¥105,000; accepting as asked with no funding falls below the ¥300,000 reserve on days 47–61; the standing plan, Option A and Option B each touch the reserve exactly on days 30–31. Day-62 cash is ¥590,000 minus each choice's net cost. | `src/fig11a_cash_alternatives.py` | `daily_cash.csv` columns `baseline_no_funding_cny`, `standing_plan_line150k_if255k_cny`, `ex01_as_asked_no_funding_cny`, `option_a_as_quoted_cny`, `option_b_with_its_funding_cny`; `events.csv`; costs from `work/financial_audit.md` §4 (the script asserts day 62 = 590,000.00 − net cost) |
| `fig11b-cash-disruption.png` | What happened after Option A was agreed, as the demo runs it: a ¥200,000 month-2 payroll added on day 25 and ¥160,000 of the invoice paid late; FLOW's ¥200,000 cure, queued for the owner on day 34 and landing on day 37, keeps cash at or above the reserve on every day, for ¥5,205.36 in all against ¥3,035.99 quoted. | `src/fig11b_cash_disruption.py` | `daily_cash.csv` columns `option_a_as_quoted_cny`, `option_a_as_quoted_plus_month2_payroll_cny`, `demo_actual_option_a_late_residual_cure_cny`; `events.csv` (scenario `demo`); `work/financial_audit.md` §4.4–4.9 (the script asserts each day-62 value) |

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
  mandate, the executor and the hash-chained log. The executor writes every typed operation to storage (PostgreSQL, SQLite or
  in memory) and moves money only on simulated lenders; counter text leaves through the egress guard to the simulated buyer,
  or the owner copies it. A footnote names the writes outside the executor, each logged, and the demo reset.
- **fig9-request-to-settlement.png.** Vertical flow of eleven steps with a status bracket on the right. Steps 1 to 3
  (request, reading, verdict and counters) run for every request. After step 3 the flow splits. Left, step 4a "Tier 1,
  alone": a registered buyer writing on its own channel key; FLOW counters, declines, or accepts a plain early-payment
  discount inside the signed mandate, with no owner step; counters and declines go back on the channel through the egress
  guard and bind nothing; an acceptance goes on to step 7. Right, for any other sender: step 4b, the owner gate, then send
  (5a simulated channel, 5b the owner copies it) and reply (6a simulated buyer, 6b owner-reported), joining step 7. Steps 1
  to 6 are bracketed "proposed terms: nothing binds, no money moves". Step 7, the executor's acceptance screen (a refusal
  records nothing), is "authorised operation"; step 8, commitment recorded in the hash-chained log, is "recorded
  commitment"; step 9, the funding plan, is "authorised funding operations, or queued / refused", with a dashed end-state
  box 9b beside it: "agreement recorded; funding incomplete: a leg queued or refused after step 8". Steps 10 and 11, the
  bank-feed receipt and reconciliation, are "actual settlement". Badge shapes mark who acts: square for code, diamond for
  the model, circle for the owner, hexagon for a simulated party. A footnote says every outcome, refusals included, goes to
  the hash-chained log.

  *Text equivalent.* Request → reading → verdict. Buyer's own channel key → FLOW alone (Tier 1: counter, decline, or accept
  an early-payment discount inside the mandate) → acceptance → executor screen. Any other sender → owner gate → send → reply
  → executor screen. Executor screen → commitment recorded → funding plan → either funded, or agreement recorded with
  funding incomplete (a leg queued for the owner or refused) → bank-feed receipt → reconciliation.
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
- **fig11a-cash-alternatives.png.** A step chart of closing cash in CNY (minus ¥150k to ¥1,000k) over days 0 to 62, with a
  dashed line at the ¥300,000 reserve and the area below it shaded. Five series, each with its own colour, dash pattern and
  marker shape: A0 no action (grey, dash-dot, diamonds), A1 FLOW's standing plan (blue, solid, circles), A2 the request
  accepted as asked with no funding (amber, dashed, squares), A3 Option A with its credit line (purple, dotted, triangles),
  A4 Option B with its funding plan (teal, dash-dot-dot, inverted triangles). Callouts: A0 reaches −¥105,000 on days
  30–31; A2 is ¥209,960 on day 47 and ¥164,960 on days 60–61; A1, A3 and A4 touch ¥300,000 on days 30–31. Eleven numbered
  markers along the top date the shared events, explained in a key below the chart, followed by a table of each series'
  lowest cash, day-62 cash and net cost, and the reconciliation rule. The bottom line names the books, the currency, the
  data files and the build.

  *Text equivalent.* Same events in every series (payroll ¥340,000 on day 12, supplier ¥120,000 on day 20, loan ¥45,000 on
  days 30 and 60, bill ¥100,000 on day 47, each invoice paid on its due day). Lowest cash, day-62 cash, net cost: A0 no
  action −¥105,000.00 (days 30–31, below the reserve from day 12), ¥590,000.00, ¥0.00. A1 standing plan (line ¥150,000 +
  invoice financing ¥255,000) ¥300,000.00, ¥586,886.07, ¥3,113.93. A2 EX01 as asked (60 days, 1.2% early payment), no
  funding ¥164,960.00 (below the reserve days 47–61), ¥584,960.00, ¥5,040.00. A3 Option A (0.85% early payment on ¥260,000,
  line ¥147,210) ¥300,000.00, ¥586,964.01, ¥3,035.99. A4 Option B (55 days, +0.30%; line ¥90,000 + financing ¥315,000 for
  ¥3,706.46, less a ¥1,260.00 premium) ¥300,000.00, ¥587,553.54, ¥2,446.46. Day-62 cash = ¥590,000.00 − net cost.
- **fig11b-cash-disruption.png.** A step chart of closing cash in CNY (¥0 to ¥1,000k) over days 0 to 62, with the dashed
  ¥300,000 reserve and the area below it shaded. Three Option A series: B0 as quoted on day 0 (grey, dash-dot, diamonds,
  a reference), B1 with the month-2 payroll added but the residual paid on time and no cure (amber, dashed, squares), and
  B2 as the demo ran (purple, thick solid, triangles). Callouts: B2 holds at ¥300,000 on days 32–35 with the line not
  repaid; B2 is ¥460,000 on day 42 after the payroll, so the reserve held; B1 falls to ¥111,964.01 on days 42–46,
  ¥188,035.99 short. Eleven numbered markers date the events, explained below, followed by a table of lowest cash, day-62
  cash and cost per series and the reconciliation. The bottom line names the books, the currency, the data and the build.

  *Text equivalent.* Day 0 Option A agreed, line ¥147,210 drawn; day 2 buyer pays ¥257,790 (¥260,000 at 0.85%), ¥160,000
  due day 32; day 25 a ¥200,000 payroll is scheduled for day 42; day 32 the ¥160,000 is not paid and the line cannot be
  repaid (cash ¥300,000); day 34 FLOW proposes ¥200,000 of invoice financing (¥1,782.19, 32.5% a year, above the 15%
  ceiling), queued as APR-000001 and approved by the owner; day 36 the ¥160,000 arrives (¥460,000); day 37 the advance
  lands (¥660,000); day 42 payroll (¥460,000); day 47 invoice +¥420,000, bill −¥100,000, advance repaid ¥201,782.19, line
  repaid ¥148,423.17 (¥429,794.64); day 60 loan −¥45,000 (¥384,794.64). Lowest, day 62, cost: B0 ¥300,000.00,
  ¥586,964.01, ¥3,035.99; B1 ¥111,964.01, ¥386,964.01, ¥3,035.99; B2 ¥300,000.00, ¥384,794.64, ¥5,205.36. Day 62 =
  ¥590,000.00 − ¥200,000.00 payroll (B1, B2) − cost; B2's ¥2,169.37 overrun is ¥387.18 of extra line interest and ¥1,782.19
  for the cure.
- **fig-eval-buyer.png.** Horizontal bars in four labelled groups, each bar a share of its own row's labelled messages,
  split into "right" (solid blue, or hatched when the set was tuned on, with a TUNED tag) and "other verdict" (white). The
  words under each bar repeat the counts; a column gives the share and another the wrong autonomous accepts. A footnote
  defines both measures and says the panel is not comparable with the other two.

  *Text equivalent.* Unseen first runs, rules path, 1 Oct 2026: held-out 3, 33 of 63 right (52%), 4 of 8 autonomous accepts
  wrong; held-out 2, 28 of 47 (60%), 2 wrong accepts. After tuning on their misses (571ea64f, 18 Oct): held-out 3, 44 of 63
  (70%), 0 of 1 accept wrong; held-out 2, 38 of 47 (81%), 0 of 2. Against today's policy, reading only: held-out 3, 50 of 63
  (79%); held-out 2, 44 of 47 (94%). Live DeepSeek, 1 Oct: held-out 3, 42 of 63 (67%), no wrong accepts.
- **fig-eval-contracts.png.** Horizontal stacked bars in two groups, each bar split into right (blue; hatched on tuned
  sets, tagged TUNED), missing (white), wrong (amber) and refused (light grey), with the counts written under each bar, the
  share right and the number stated wrongly beside it, and a footnote defining the terms.

  *Text equivalent.* Batch 2, first reading, unseen, recorded DeepSeek readings: all scored fields on the 17 text-layer
  contracts, 215 right, 58 missing, 12 wrong of 285 (75%); over all 30 contracts, the same plus 189 fields of the 13 scans
  and photos refused before reading, 215 of 474 (45%); decision-critical fields, 178 right, 45 missing, 11 wrong of 234
  (76%), plus 18 payment-stage items matching no key item. Tuned sets, decision-critical fields: batch 2 after five fixes,
  198 right, 34 missing, 2 wrong of 234 (85%), plus 18 stage items; batch 1, 412 right, 12 missing, 0 wrong of 424 (97%).
- **fig-eval-questions.png.** Horizontal stacked bars in two groups, each split into right (blue; hatched when tuned),
  partly (light blue), declined (white), wrong (amber) and rejected (light grey), with the counts under each bar, the share
  right and the wrong count beside it, and a footnote defining the terms.

  *Text equivalent.* Offline, rules path, 571ea64f, 18 Oct 2026: owner-question bank (tuned), 427 turns the books can
  answer, 228 answered (53%), 45 partly, 154 declined, 0 wrong; everyday wording, all 345 phrasings (mostly tuned), 326 right
  (94%), 15 missed, 4 wrong topic; its held-out part, 127 of 142 right (89%), 12 missed, 3 wrong topic. Live question
  router, DeepSeek, 18 Oct, one unblinded grader: of the 63 questions that reached it, 22 fully right (35%), 10 partly, 1
  wrong topic, 29 "cannot answer yet", 1 rejected; of the 33 it answered, 22 right (67%), 10 partly, 1 wrong.

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

### Refreshed frames from the submission build candidate (18 Oct 2026)

Five frames retaken from `int/final3` at `2ce5265c` in **mock mode** (an export of that commit's `apps/web`, `pnpm install
--frozen-lockfile`, `NEXT_PUBLIC_API_MODE=mock next dev -p 3571`; no API, no model, no money), same browser settings and
annotation style. They replace the `../screenshots` frames of the same names (taken 17 Oct from `dev` `975e082f`).
Capture: `SET=final WEB_DIR=<that apps/web> node src/capture_screens.mjs http://localhost:3571 <raw dir>`; cut:
`uv run --no-project --with pillow python src/crop_screens.py <raw dir> final`.

| Screen | Caption | Intended place |
| --- | --- | --- |
| `shot1-home.png` | Home on the opening books: without new funding cash falls to −¥105,000 within 30 days; the red card recommends securing ¥405,000 before payroll in 12 days (credit line ¥150,000 today, invoice financing ¥255,000 in 3 days) for ¥3,113.93, with no approval needed. | 01, "What the owner sees", or Appendix E (replaces `screenshots/shot1-home.png`) |
| `shot3-approval.png` | An approval waiting (story scene 5, day 34): FLOW queued a ¥200,000 invoice-financing request because 32.5% a year is above the 15% ceiling the owner signed. It costs ¥1,782.19; nothing runs until the owner authorizes or declines. | 04 or 05, beside the tiered permissions (replaces `screenshots/shot3-approval.png`) |
| `shot6-capex.png` | Capex, the quick check of the demo's ¥600,000 machine: worth doing on the owner's estimate (NPV ¥380,885.77, payback in month 31); the 48-month lease is selected and the cheaper 36-month loan is rejected (reserve breach on day 44); the 18-month loan fails DSCR in months 1–3 (1.13×); captured live against the submission build on 19 Oct (`crop_screens.py <raw> capex-live`); figures that do not apply read "—", not "None". | 03, the capex screen, or Appendix E (replaces `screenshots/shot6-capex.png`) |
| `shot9-attach.png` | Documents, attaching a contract: say what the file is and who it is with, then drop or upload a PDF with text, Word or plain text up to 5 MB; below, the documents already read, each confirmed by the owner. | 02, "Models, tools, data sources", or Appendix E (replaces `screenshots/shot9-attach.png`) |
| `shot10-ask-answer.png` | Ask FLOW, full page, in its card: "Are we safe?" answered from the books, with the lead sentence, three key figures, the plan's cost and links. The mocks hold no recording of "Can I pay everyone?", so the frame shows the recorded "Are we safe?". | 03, Ask FLOW (replaces `screenshots/shot10-ask-answer.png` and `screen4-ask-answer.png`) |

**Alt text and text equivalents.**

- **shot1-home.png.** Home. Left, "Company cash outlook": −¥105,000 without new funding, ¥300,000 with plan, over a 36-day
  step chart with the product's own numbered markers. Right, a red-bordered card: "Action needed: without funding your cash
  falls to −¥105k in 30 days. What we recommend: Secure ¥405,000 before payroll in 12 days", cost to you ¥3,113.93, a bar
  split into a credit-line draw of ¥150,000 today (37%) and invoice financing of ¥255,000 in 3 days (63%), "No approval
  needed", and buttons "Check funding plan" and "Compare funding options". Callouts: 1 the −¥105,000 outlook, 2 the red
  card, 3 the ¥405,000 to secure, 4 the ¥3,113.93 cost, 5 the split, 6 no approval needed.
- **shot3-approval.png.** Approvals, one card: "Request ¥200,000 of invoice financing", marked "Waiting for your approval".
  Why it needs you: "The yearly cost of 32.5% is above the 15.00% limit you signed for funding without your approval." What
  you get ¥200,000.00; what it costs ¥1,782.19 (32.5% a year); when it lands: in 3 days if approved today. Funding source:
  invoice financing (onboarded platform), on the ¥420,000.00 invoice to Foshan Home Retail Co. What if you decline:
  ¥200,000.00 below the minimum cash reserve in 8 days. Buttons "Authorize the financing request" and "Decline". Callouts:
  1 waiting, 2 why, 3 cost, 4 decline, 5 the two buttons.
- **shot6-capex.png.** Retaken live against the submission build's API on 19 Oct (the 18 Oct capture came from a stale
  recorded mock). The "Test a machine without a contract" card. A purple verdict: worth doing on the owner's estimate, NPV
  ¥380,885.77 at 10.00%, payback in month 31; finance with the 48-month lease at 7.20% (¥14,423.49 a month), the lowest total
  charges, ¥92,327.32, of the structures that pass; the lower-charge 36-month term loan is rejected (RESERVE_BREACH); a new
  facility is Tier 2. Tiles: NPV, payback month 31, leverage 1.90× (limit 2.50×), 2.10× if the extension were also funded. A
  table of four structures with monthly payment, interest, charges, DSCR for months 1–6 and the result: cash + credit line
  shows "—" and is infeasible (only ¥250,000 above the reserve); the 18-month loan fails months 1–3 at 1.13× and is an
  illustration only; the 36-month loan passes DSCR but is rejected, RESERVE_BREACH on day 44; the 48-month lease is feasible
  and selected. Callouts: 1 the verdict, 2 the tiles, 3 the "—" row, 4 the failing DSCR months, 5 the rejected loan, 6 the
  selected structure.
- **shot9-attach.png.** Documents. "Your own file": a "What it is" select (Contract with a buyer), a "Who it is with" select
  with "+Add a new customer", and a dashed drop zone, "Drag and drop a document to check it" (PDF, Word or plain text, up to
  5 MB) with an "Upload and read" button. Below, "Review a document": supply agreement FHR-2026-07 (Foshan Home Retail Co.,
  18 terms read, 3 left blank), credit line agreement MB-CL-2026-031 (main bank, ¥150,000 at 6.40%) and invoice financing
  agreement GBR-IF-2026-118 (¥350,000 at 7.80%), each "Confirmed by you today". Callouts: 1 what it is, 2 who it is with,
  3 the drop zone, 4 upload and read, 5 the confirmed documents.
- **shot10-ask-answer.png.** The Ask FLOW card. A warning, "Cash is close to your minimum in 30 days". The owner asks "Are
  we safe?". FLOW: "Not on today's books: without new funding, cash falls below your ¥300,000 reserve from day 12, lowest
  −¥105,000 on day 30 (¥405,000 short of the reserve)." Three tiles: ¥405,000 funding needed, −¥105,000 lowest cash, day 12
  below reserve from. "FLOW's plan covers it for ¥3,113.93, and your loan covenants hold", with links to the cash forecast
  and FLOW's plan and a collapsed "How FLOW worked this out". Suggested questions and the input box below. Callouts: 1 the
  question, 2 the lead, 3 the figures, 4 the links, 5 how it was worked out, 6 the suggestions.

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
