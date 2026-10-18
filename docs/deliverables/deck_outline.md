# FLOW: Pitch Deck Outline

Team ISMOGGER · FinTechathon 2026 · International AI Track, Topic E: SME Finance Copilot. FLOW is the product name; the code still uses the working name TermsLedger.

**Deliverable:** the presentation deck (required), at most **10 minutes**, built on the official `docs/research/templates/presentation-template.pptx` (16:9). The template has four slide types: title, a contents slide with **six** numbered items, a content slide and a "THANKS" closing slide. So this outline uses **six sections**, 18 slides and **9:40** of speaking time, leaving 20 seconds of slack. The language is English (the international defence is in English).

**Numbers.** Every figure on a slide comes from `fixtures/golden/golden_values.json`, a report in the repository or a test count the README states, and each figure below names its source in a parenthesis. All data is synthetic unless marked as a public market fact. The spec v2 §13 wording rules apply throughout: no "first", "best loan", "proof", "atomic", "financial advice", "bank-grade", "safe by construction" or "cannot be fooled", and no claim of bank-covenant compliance. Say "simulation" wherever the clock, the bank feed, the buyer or a lender appears; say "screens the entered obligations only", "cheapest within the bounded search", "reserve-coverage reading" for the bullet-loan DSCR and "internally checkable chain". Slide text and speaker lines use the owner's words (what the owner sees and decides); reason codes and ids belong to the technical slides only.

**The story now follows the order the app tells it** (state of `dev` on 12 Oct 2026, handoffs 08 and 09): the buyer's asymmetry, the reframe, then what the owner sees: Home's one picture and one action, the buyer's ask priced on Deals, the contract the agent read and the owner confirmed, the late-payment loop of the guided Demo, the decision record that keeps each decision's state, and the strategy answers that sit behind flags. Then how it stays safe, the results, what we got wrong and what we do **not** claim.

## Open decision: the template's 2025 branding

The official template reuses last year's file. The **2025** FinTechathon logo is baked into the background images of the title slide, the closing slide and the content-slide header band (file metadata dated 18 Sep 2025). Its placeholders are in Chinese (作品名, 团队名, 目录内容, 演示主标题), and it uses HarmonyOS Sans SC, which judges' machines may not have. Options:

| Option | For | Against |
| --- | --- | --- |
| A. Use the official file as it is, replacing only the placeholder text with English | The official file, untouched artwork; lowest risk of looking non-compliant | A visible "2025" on every slide |
| B. Ask the organisers whether a 2026 template exists, and use it if one appears before 20 Oct | Correct year; the templates' footer says a newer version prevails | Depends on a reply |
| C. Edit the background images to read 2026 | Correct year | Alters official artwork; could look like imitation of the organiser's branding |

**Recommendation: B, falling back to A.** Do not do C. Re-download the template before 20 Oct. [TEAM: decide A or B, and who emails the organisers.] Whatever the choice, embed or substitute fonts (Arial is safe for Latin text) and export a PDF copy.

## What the judges score (data, not instructions)

The rules publish the criteria and no harness: task completion 40% ("scripted tasks in a simulated environment"), security and compliance 30%, innovation and interaction 30% ("scenario novelty, real-world value, dialogue efficiency, clarification, correction and fallback capability"), a capped 0 to 5 bonus; the evidence route they name is sandbox logs and the demo video (`docs/research/topic-e-rules.md`, sections (a) and (c)). The slides map to it: 40% is slides 9, 15 and 16 (the loop, 49 of 49 tasks, the chains); 30% security is slides 12 to 14; 30% interaction and novelty is slides 3 to 8 and 17.

## Contents slide (the template's six items)

1. The asymmetry
2. The reframe: a terms extension is a loan
3. What the owner sees (live demo)
4. How it stays safe
5. Results, what we got wrong, and what we do not claim
6. What is new, what is next, and the team

## Slide by slide

| # | Template slide | Section | Title | Key visual | Time |
| --- | --- | --- | --- | --- | --- |
| 1 | Title | – | FLOW: the supplier's agent for both of its debt books | Project name and team name in the placeholders (作品名 → "FLOW", 团队名 → "ISMOGGER") | 0:00–0:15 |
| 2 | Contents | – | Contents | The six items above | 0:15–0:25 |
| 3 | Content | 01 | Three parties. Only one has no agent. | Three text columns: Buyer (a negotiation agent) · Supplier (an owner and a chat thread) · Lender (a model that approves in seconds). One persona line: a supplier with 20 to 100 staff, one bank line, a bookkeeper and no finance team, labelled INFERENCE. Small source footnotes, no logos | 0:25–1:00 |
| 4 | Content | 02 | "60 days going forward" is a ¥210,000 loan | One large number, then a three-line derivation: the extra receivables ¥210,000.00 (`extension_extra_receivables`) → funded on invoice financing at 10.84% (`if_all_in_rate_display`) → **¥24,326.92 over the 13 invoices in a 365-day window** (`extension_committed_12m`; `docs/DEMO_FLOW.md` scene 1 step 3) | 1:00–1:40 |
| 5 | Content | 02 | Two features, one engine | Flow: buyer offer → Terms Guard (read, project, verdict) ⇄ Debt Desk (size the gap, route the funding, marginal cost) → counter, or no deal with the gap funded | 1:40–2:10 |
| 6 | Content | 03 | Home: one picture, one action | The Home capture: "Your cash reserve becomes unsafe in 12 days." Cash against FLOW's plan on one chart; one recommended step, "Secure ¥405k of funding", ¥3,113.93, "Within your signed limits. No additional approval required." (`docs/screenshots/ui-overhaul-2026-10-12/home-day0-1280-en.png`; `fixtures/golden/golden_values.json` `v2_optimum_total`). Caption: the answer is the heading, the browser computes no money (INVARIANT 13) | 2:10–2:40 |
| 7 | Content | 03 | The buyer asks. FLOW prices it. | The Deals capture: "Don't accept as asked: it would cost ¥28,326.92 over the next 13 invoices, plus the ¥5,040 immediate discount, above your ¥5,000.00 limit." Three paths on one chart: as asked, Option A (¥3,035.99, FLOW recommends), Option B (¥0.00, needs your approval) (`deals-evaluated-1280-en.png`, `deals-paths-option-a-1280-en.png`; `docs/DEMO_FLOW.md` scene 1 steps 4 and 6). The standing funding plan is ¥3,113.93 | 2:40–3:30 |
| 8 | Content | 03 | The agent reads the contract. The owner confirms. | The Documents page and Your agreements on Deals: every term beside its quoted clause, "AI-generated, for reference"; the owner's confirmation is an owner-only entry on the hash chain, bound to the text shown, and changes no books (`documents-day0-1280-en.png`, `deals-agreed-1280-en.png`; ADR-0012). A box, in plain words: **no reading-accuracy claim: the held-out contracts are not yet written** | 3:30–4:00 |
| 9 | Content | 03 | The late-payment loop (the guided Demo) | Six scenes as a strip: the buyer asks · FLOW decides · the agreement acts · reality diverges · the owner stays in control · the proof. Figures under it: ¥257,790.00 arrives early; ¥160,000.00 does not; the cure costs ¥1,782.19, 32.5% a year, above the 15.00% limit, so the owner approves it with their own click (`docs/DEMO_FLOW.md`; `apps/web/e2e/demo.spec.ts`; Approvals capture `approvals-pending-1280-en.png`). Footer: the bank event and the clock are simulated | 4:00–4:45 |
| 10 | Content | 03 | Every decision has a state, and a record | The deal's stage strip as Deals shows it (Received · Analysed · Reply ready · Sent · Agreed) and the line "28 of 28 audit findings fixed" (`docs/UX_REMEDIATION_REPORT.md` section 1). The record is derived from stored reality plus three append-only facts, never from a clicked button (ADR-0011); the Activity capture shows "Record chain checks passed" (`activity-day34-1280-en.png`) | 4:45–5:10 |
| 11 | Content | 03 | Before the buyer asks: three answers, off by default | Three sentences, each labelled "read-only, flagged": what you can offer this buyer (up to 55-day terms with a 0.30% price rise, or early payment up to 0.85% on ¥260,000.00); what cash arriving earlier is worth (¥89.11 per ¥10,000 for the next 30 days); whom to chase first (`docs/STRATEGY_MVP_REPORT.md` section 2). Footer: backtest passed with 0 failures (`docs/research/strategy/06-backtest-2026-10-08.md`); the pilot that tests them against real owners is planned, not run | 5:10–5:35 |
| 12 | Content | 04 | The model only proposes | The architecture diagram (`architecture.mmd`) with the trust boundary: untrusted text and uploaded contracts → typed readings → deterministic verifier → executor → hash-chained log; the decision record and the strategy layer beside the engine, importing none of it | 5:35–6:05 |
| 13 | Content | 04 | Three tiers, enforced by code | A tier table: Tier 1 act alone (only a proven early-pay discount that is below break-even, needed and cheaper than the plan; draws on committed facilities), Tier 2 ask the owner (every other acceptance; a cure over the signed rate limit), Tier 3 never. The concession cap is a hard rule: over it means a new signed mandate, never "owner approval" (handoff 08 section 4) | 6:05–6:30 |
| 14 | Content | 04 | Attacked 279 ways, then audited | A metrics table: 279 attacks (128 through the API, 151 through chat), 0 with harm, ¥0 moved, 0 protected values disclosed; 97.7% of the API attacks detected (125 of 128; `python -m app.security.attacks`, 18 Oct 2026, `b0cc7a4b`); four attacks added for contract ingestion; an independent audit (13 findings) and five red-team rounds (26 findings), all fixed with a regression test each (README, step 4; `services/api/evals/security/latest_report.md`; `docs/SECURITY_SELF_ASSESSMENT.md` section 02) | 6:30–7:00 |
| 15 | Content | 05 | Results you can re-run | Four tiles: 49/49 scripted tasks, 49 evidence chains verify with one script (`scripts/verify_evidence.py`) · API 6,895 passed, 37 skipped · web unit 91; mock browser tests 211 (221 with the strategy flag); live browser tests 96 (104) · every golden value matches an independent oracle, and the router matches a grid-bounded brute force on 26 of 26 cases (README, step 3; handoff 09 section 3; `services/api/evals/latest_report.md`) | 7:00–7:30 |
| 16 | Content | 05 | What we got wrong, and what we do not claim | Left: "Unseen buyer messages, first run: 33/63 verdicts agree with the labels (52%); 8 accepted without the owner, **4 of them wrong**." Then "ADR-0005: autonomy requires proof. Since then, **0 wrong autonomous accepts** on the held-out sets and both compiler paths" (`services/api/evals/accuracy_summary.md`). Right, a list headed "Not claimed": a reading-accuracy figure for contracts (held-out set pending); results of the strategy answers on a real owner (read-only, flagged, pilot planned); any execution outside the signed mandate; reviewed Chinese wording (templates await a native reader); bank-covenant compliance; PostgreSQL concurrency and the live-model language-boundary run (built, not yet run) | 7:30–8:25 |
| 17 | Content | 06 | What is new, what is next, the team | Left: the prior-art map (buyer side / lender side / borrower tools / FLOW) and the line "none we found is owned by the supplier and bounded by its own mandate across both debt books". Middle: next (held-out contracts and a reader outside the team; a pilot with two suppliers; a live Claude run; a money-in-and-out chart and customer economics wait on the owner's decision and are not built). Right: the team [TEAM: names, universities, roles] | 8:25–9:20 |
| 18 | Closing (THANKS) | – | – | The template's closing image. Say the closing line over it. | 9:20–9:40 |

## Speaker notes

**Slide 1 (0:15).** "We are ISMOGGER from [TEAM: universities]. FLOW is an agent a small supplier owns, which manages the credit it gives buyers and the credit it takes from lenders."

**Slide 2 (0:10).** Read the six items quickly; no narration beyond the titles.

**Slide 3 (0:35).**
- "Buyers now negotiate with software. Pactum's public material reports a large-retailer deployment with an average 35-day payment-term extension, and roughly seven in ten suppliers agreeing." Spec v2 §1 records these figures as CONFIRMED, noting they vary between Pactum pages; say "roughly".
- "Lenders decide by model. MYbank describes a '310' loan: under three minutes to apply, under one second to approve, and more than 53 million SMEs served by the end of 2023." (spec v2 §1, §18.)
- "The supplier in the middle has a bookkeeper and a chat thread. Our user is a supplier with 20 to 100 staff and no finance team; that profile is our inference." [TEAM: update if interviews happen.] Names only, no logos or screenshots.

**Slide 4 (0:40).** "Move a ¥420,000-a-month buyer from 45 to 60 days and the supplier carries ¥210,000 more receivables, for good. The credit line has a clean-down rule, so it cannot carry a permanent need. The cheapest committed source that can is invoice financing at 10.84%, so that phrase costs ¥24,326.92 over a year's invoices. All numbers are from our synthetic fixture."

**Slide 5 (0:30).**
- "Terms Guard reads the offer into typed obligations with the exact words they came from, projects cash day by day, and checks the owner's signed limits and the bank's covenants."
- "Debt Desk prices any gap from the owner's own facilities and gives Terms Guard the firm's marginal cost of funds."
- "So a counter is priced from real borrowing cost, and the agent can say no deal because it already knows the alternative."

**Slide 6 (0:30).** "This is the first thing the owner sees. The heading is the answer: your cash reserve becomes unsafe in twelve days. One picture: cash if you do nothing, against cash with FLOW's plan. One action: secure ¥405k, for about ¥3,100, within the limits you already signed. The browser never computes money: every figure and every 'when' is written by the server." Source: INVARIANT 13.

**Slide 7 (0:50).**
- "The buyer asks for three things at once. FLOW's heading says it plainly: do not accept as asked; it would cost ¥28,326.92 over the next thirteen invoices, plus the ¥5,040 discount straight away, above your ¥5,000 limit."
- "Two replies are ready. Option A keeps the terms at 45 days and offers early payment at 0.85% on up to ¥260,000: ¥3,035.99, less than the ¥3,113.93 the standing plan costs. Option B takes 55 days with a 0.30% price rise, which pays for the longer terms but needs the owner. Sixty days is not offered because it would fail its own check."
- "The chart draws all three paths; the cursor steps through the days that matter. The reply goes out bound to the exact figures the owner saw."

**Slide 8 (0:30).**
- "Owners forget what a contract says. So they can upload it. The agent reads it and shows every term beside its quoted clause, labelled AI-generated, for reference."
- "The owner confirms or rejects. That is an owner-only entry on the record chain, tied to the exact text they saw. Confirming changes no books: the contract is shown beside them, never booked."
- "We make no accuracy claim for the reading. The three demo documents were written to match our synthetic books, and the contracts that would test it, written by someone who has not seen our schema, do not exist yet." (ADR-0012, Consequences; `services/api/evals/contracts_heldout_report.md`.)

**Slide 9 (0:45).**
- "The guided Demo is one loop in six scenes. The agreed early payment of ¥257,790.00 arrives, as one simulated bank event. The other ¥160,000.00 does not."
- "A month on, cash would fall ¥200,000 below the minimum. FLOW speaks first, with a cure and its price: ¥1,782.19, 32.5% a year for the ten days it is held. That is above the 15% limit the owner signed for borrowing alone, so it waits."
- "The owner clicks Approve. The demo's stepper never does it for them. The cash lands, and every step is in one record. The bank event and the clock are simulated." Say "the agent proposed, the owner approved".

**Slide 10 (0:25).** "An independent audit found 28 flow problems. All 28 are fixed, at the cause: every deal and every cure now has a state that is derived from what the books and the record say, never from a button someone clicked. The record is kept beside the engine; a test pins that the engine does not import it."

**Slide 11 (0:25).**
- "Three answers FLOW can give before the buyer asks: what you can offer this buyer, what cash arriving earlier is worth, whom to chase first."
- "They are read-only, they compute on copies of the books, they execute nothing, and they are off by default. Their backtest passed with no failures; whether owners find them useful is a pilot we have planned, not one we have run."

**Slide 12 (0:30).**
- "The model has one job: turn text into a typed proposal, tied to exact spans, or abstain. A contract is read the same way: every term quotes its clause."
- "The verifier never reads free text. Operations are built by code and run only by the executor."
- "Only the owner can add a lender. Contingent promises count at their maximum, and uncommitted loans at zero."

**Slide 13 (0:25).** "Tier 1: the agent acts alone, but it may accept a buyer's offer only when it is an early-pay discount that is below break-even, needed and cheaper than the plan, and that it can prove it read completely. Every other acceptance is Tier 2: ask the owner. Tier 3: never, not even for the owner. The cap on concessions is a hard rule: over it means a new signed mandate, not an approval click."

**Slide 14 (0:30).**
- "We attacked it 279 ways, in English and Chinese: 128 through the API and 151 through the chat, as the owner, as a buyer with and without its key, and as the agent key. No unauthorised operation, no money moved, nothing leaked."
- "97.7% of the API attacks were also detected and logged. Known limits: a buyer with its key probing the chat can find our accept-or-counter threshold, and the agent key can read protected labels in chat replies."
- "An independent audit and five red-team rounds found 39 issues, all fixed with a regression test each; then we stopped. That is evidence of a process, not a certificate." Say "being attacked"; do not say "cannot be fooled".

**Slide 15 (0:30).**
- "49 of 49 scripted tasks pass. Each starts from a reset and every operation goes through the verifier and the executor."
- "6,895 API tests pass and 37 are skipped; the browser tests pass with zero retries. Every number you saw is checked to the fen against an oracle written separately from the engine."
- "Each task's log is a hash chain, and one standard-library script re-verifies all 49. The chain is internally checkable only: its head is not anchored outside the system."

**Slide 16 (0:55).** This is the slide that earns trust; say it plainly. Never cut it.
- "We asked a separate agent to write buyer messages from the spec alone and to label them before it ever ran our system. On that unseen set, our verdicts matched the labels 52% of the time. Worse, the agent accepted 8 offers without the owner, and 4 of those were wrong."
- "So we changed the rule, not just the grammar: the agent may only accept on its own when it can prove every amount, date, invoice and request in the message is accounted for. Since then, zero wrong autonomous accepts on the held-out sets, with the offline grammar and with a live model. Understanding is still imperfect; a misread now costs the owner a click, not a commitment."
- "And here is what we do not claim: no accuracy figure for reading contracts, because the held-out contracts are not written. The strategy answers are read-only and off by default, with no real-owner results yet. Nothing executes outside the mandate the owner signed. The Chinese wording awaits a native reader. Everything is a simulation."
- Do not quote the after-fix agreement figures as independent: those sets guided the fixes.

**Slide 17 (0:55).**
- "Nothing here is a new algorithm. Pactum works for the buyer. MYbank's 百灵 agent plans financing with MYbank's own products. Xero's JAX spots cash gaps. Cerebro, Capitalise and Lendio match borrowers to lenders. Codat informs the bank. None we found is owned by the supplier and bounded by its own mandate across both debt books." Say "that we could find"; the Chinese-language check is still open [TEAM].
- "Next: contracts written by people outside the team to measure the reading; a pilot with two suppliers; a live Claude run. A money-in-and-out chart and customer economics wait on the owner's decision, so neither is built." (handoff 08 section 3.) Then introduce the team [TEAM].

**Slide 18 (0:20).** Closing line: "Buyers have an agent that decides how long to pay you. Banks have a model that decides whether to lend to you. FLOW is yours."

## Production notes

- **Slide text.** Keep it to a title plus at most three short lines or one table. The numbers are the visuals, so set the key figure in large type on slides 4, 7, 14 and 16. Never cut slide 16.
- **Screens.** Use the captures under `docs/screenshots/ui-overhaul-2026-10-12/` (1280 wide) named above; they are mock-mode captures, so a Chinese page in them shows English sentences, and none is shown in Chinese on a slide. The Deals capture in `docs/screenshots/contracts-reskin-2026-10-12/` is the earlier layout and must not be used.
- **Diagram.** Render `docs/deliverables/architecture.mmd` to PNG (for example `npx -p @mermaid-js/mermaid-cli mmdc -i architecture.mmd -o architecture.png -w 2000`). `scripts/build_deliverables.py` embeds the same PNG in the Technical Document when it exists.
- **Live demo.** Have a fallback: keep the demo video's clips on the laptop and run the app in mock mode offline.
- **Rehearse to 9:30** with a timer. If you run over, cut slide 11 first, then fold slide 10 into slide 9.
- **Contract ingestion.** If the deal summary or the documents page is shown live, say plainly that the demo contract and lender agreements were written to match the synthetic scenario, that the held-out contract set is pending (no accuracy figure is quoted), and "the agent read it, you confirmed it": a confirmed contract changes no books.
