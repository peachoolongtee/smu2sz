# TermsLedger v2: Pitch Deck Outline

**Deliverable:** the presentation deck (required), at most **10 minutes**, built on the official `docs/research/templates/presentation-template.pptx` (16:9). The template has four slide types: title, a contents slide with **six** numbered items, a content slide and a "THANKS" closing slide. So this outline uses **six sections**, 16 slides and **9:40** of speaking time, leaving 20 seconds of slack. The language is English (the international defence is in English).

**Numbers.** Every figure on a slide comes from `fixtures/golden/golden_values.json` or the evaluation reports, and is synthetic unless marked as a public market fact. The spec v2 §13 wording rules apply throughout: no "first", "best loan", "proof", "atomic", "financial advice", "bank-grade" or "cannot be fooled".

## Open decision: the template's 2025 branding

The official template reuses last year's file. The **2025** FinTechathon logo is baked into the background images of the title slide, the closing slide and the content-slide header band (file metadata dated 18 Sep 2025). Its placeholders are in Chinese (作品名, 团队名, 目录内容, 演示主标题), and it uses HarmonyOS Sans SC, which judges' machines may not have. Options:

| Option | For | Against |
| --- | --- | --- |
| A. Use the official file as it is, replacing only the placeholder text with English | The official file, untouched artwork; lowest risk of looking non-compliant | A visible "2025" on every slide |
| B. Ask the organisers whether a 2026 template exists, and use it if one appears before 20 Oct | Correct year; the templates' footer says a newer version prevails | Depends on a reply |
| C. Edit the background images to read 2026 | Correct year | Alters official artwork; could look like imitation of the organiser's branding |

**Recommendation: B, falling back to A.** Do not do C. Re-download the template before 20 Oct. [TEAM: decide A or B, and who emails the organisers.] Whatever the choice, embed or substitute fonts (Arial is safe for Latin text) and export a PDF copy.

## Contents slide (the template's six items)

1. The asymmetry
2. The reframe: a terms extension is a loan
3. Live demo
4. How it stays safe
5. Results and evidence
6. What is new, what is next, and the team

## Slide by slide

| # | Template slide | Section | Title | Key visual | Time |
| --- | --- | --- | --- | --- | --- |
| 1 | Title | – | TermsLedger: the supplier's agent for both of its debt books | Project name and team name in the placeholders (作品名 → "TermsLedger v2", 团队名 → [TEAM: team name]) | 0:00–0:15 |
| 2 | Contents | – | Contents | The six items above | 0:15–0:25 |
| 3 | Content | 01 | Three parties. Only one has no agent. | Three text columns: Buyer (a negotiation agent) · Supplier (an owner and a chat thread) · Lender (a model that approves in seconds). Small source footnotes. No logos. | 0:25–1:10 |
| 4 | Content | 01 | Who we built it for | A persona card: a supplier with 20–100 staff, one bank line, a bookkeeper and no finance team. The label INFERENCE is visible. | 1:10–1:35 |
| 5 | Content | 02 | "60 days going forward" is a ¥207,123.29 loan | One large number, then a three-line derivation: the extra receivables ¥207,123.29 → funded on invoice financing at 10.84% → **¥22,455.62 a year** | 1:35–2:20 |
| 6 | Content | 02 | Two features, one engine | Flow: buyer offer → Terms Guard (compile, project, verdict) ⇄ Debt Desk (size the gap, route the funding, marginal cost) → counter, or NO DEAL with the gap funded | 2:20–2:55 |
| 7 | Content | 03 | Scene 1: the offer is a loan | A live demo, or a 60-second clip from the demo video: Inbox spans → trajectory (day 47) → verdict REJECT with formulas → Counter A accepted | 2:55–4:15 |
| 8 | Content | 03 | Scene 2: the buyer walks, and the gap is still covered | The router plan table: line ¥150,000 + invoice financing ¥210,000 = ¥2,712.94, against ¥5,040 for the discount; a note that a pending loan counts as zero | 4:15–4:50 |
| 9 | Content | 03 | Capex, and talking to it | Left: the capex table (18-month loan fails DSCR at 1.13×; 36-month loan selected). Right: a `/chat` exchange (goal → plan; "make it 1%" refused above the 0.88% break-even) | 4:50–5:30 |
| 10 | Content | 04 | The model only proposes | The architecture diagram (`architecture.mmd`) with the trust boundary drawn: untrusted text → typed obligations → deterministic verifier → executor → hash-chained log | 5:30–6:10 |
| 11 | Content | 04 | Three tiers, enforced by code | A tier table (Tier 1 act, Tier 2 ask the owner, Tier 3 never), with the executor's gate order as a strip | 6:10–6:40 |
| 12 | Content | 04 | Attacked 122 ways | A metrics table: 118 catalogue attacks with 0 unauthorised operations, ¥0 moved and 0 protected values disclosed; 94.3% detection; 4 documented findings listed by name | 6:40–7:25 |
| 13 | Content | 05 | Results you can re-run | Four tiles: 37/37 scripted tasks · every golden value matches an independent oracle · 37/37 evidence chains verify · one command to reproduce | 7:25–8:10 |
| 14 | Content | 06 | What is new, and what is not | The prior-art map (buyer side / lender side / borrower tools / TermsLedger) and the line "none we found is owned by the supplier and bounded by its own mandate across both debt books" | 8:10–8:50 |
| 15 | Content | 06 | Next, and the team | Left: the roadmap (fix F-01/F-02/F-04/F-07; held-out validation E2 and E9; two pilot suppliers; a borrower file a lender can consume). Right: the team [TEAM: names, universities, roles] | 8:50–9:25 |
| 16 | Closing (THANKS) | – | – | The template's closing image. Say the closing line over it. | 9:25–9:40 |

## Speaker notes

**Slide 1 (0:15).** "We are [TEAM: team name] from [TEAM: universities]. TermsLedger is an agent a small supplier owns, which manages the credit it gives buyers and the credit it takes from lenders."

**Slide 2 (0:10).** Read the six items quickly; no narration beyond the titles.

**Slide 3 (0:45).**
- "Buyers now negotiate with software. Pactum's public material reports a large-retailer deployment with an average 35-day payment-term extension, and roughly seven in ten suppliers agreeing." Spec v2 §1 records these figures as CONFIRMED, noting they vary between Pactum pages; say "roughly".
- "Lenders decide by model. MYbank describes a '310' loan: under three minutes to apply, under one second to approve, and more than 53 million SMEs served by the end of 2023."
- "The supplier in the middle has a bookkeeper and a chat thread."
- Footnotes: the spec v2 §18 sources. Use names only; no logos or screenshots.

**Slide 4 (0:25).**
- "Our user is a supplier with 20 to 100 staff, one credit line and no finance team."
- "This profile is our inference. In two conversations, one of our assumed pains was contradicted, so we only claim what the numbers show." [TEAM: update if interviews happen.]

**Slide 5 (0:45).** "Move a ¥420,000-a-month buyer from 45 to 60 days and the supplier carries ¥207,123.29 more receivables, forever. The credit line has a clean-down rule, so it cannot carry a permanent need. The cheapest committed source that can is invoice financing at 10.84%, so that phrase costs ¥22,455.62 a year. All numbers here are from our synthetic fixture."

**Slide 6 (0:35).**
- "Terms Guard compiles the offer into typed obligations with the exact words they came from. It projects cash day by day and checks the owner's signed limits and the bank's covenants."
- "Debt Desk prices any gap from the owner's own facilities and gives Terms Guard the firm's marginal cost of funds."
- "So a counter is priced from real borrowing cost, and the agent can say no deal because it already knows the alternative."

**Slide 7 (1:20).** Live, or the video clip. Hit these numbers:
- the concession meter at ¥26,455.62 against the ¥5,000 cap;
- cash at ¥254,960 on day 47, below the ¥300,000 floor, curable for ¥802.70;
- break-even 0.88%;
- REJECT with AGG_CONCESSION_EXCEEDED and RESERVE_BREACH@47, each with its formula;
- Counter A: 45 days, early settlement on up to ¥211,800 at 0.85%, ¥2,641.94 in total;
- the buyer kernel accepts, and the commitment and the line draw are logged.

**Slide 8 (0:35).** "A different buyer refuses every counter within three rounds. No deal is a real outcome. The router finds the line plus invoice financing for ¥2,712.94, against ¥5,040 for taking the discount. The government-guaranteed loan would be cheaper, but it is not committed and arrives after payroll, so it counts as zero. The same offer in other words gets the same verdict."

**Slide 9 (0:40).** "For a ¥600,000 machine, NPV is ¥380,885.77 and payback is month 31. The loan with the least interest breaks DSCR in month 1 at 1.13×, so the 36-month loan is selected and queued for the owner with a borrower file. And the owner can just ask: a goal becomes a plan with a fallback, and a correction to 1% is refused because it costs more than the firm's own borrowing." [TEAM: drop the `/chat` half if the page does not ship.]

**Slide 10 (0:40).**
- "The model has one job: turn text into a typed proposal, tied to exact spans, or abstain."
- "The verifier never reads free text. Operations are built by code and run only by the executor."
- "Only the owner can add a lender. Contingent promises count at their maximum, and uncommitted loans at zero."

**Slide 11 (0:30).** "Tier 1: act inside the mandate. Tier 2: ask the owner. Tier 3: never, not even for the owner, like a personal guarantee. The executor computes the tier itself, checks the signed mandate, the nonce, expiry and idempotency, and logs every outcome, refusals included."

**Slide 12 (0:45).**
- "We attacked it 122 ways, in English and Chinese: prompt injection, fake lenders, fake 'agreed last month' rebates, data extraction, privilege escalation, replay and failure recovery."
- "On the 118 catalogue attacks: no unauthorised operation, no money moved, nothing leaked."
- "Four more attacks reproduce weaknesses we found ourselves: a non-atomic log write, a receipt anyone can record, a live-mode contingency label, and an offer swapped after its verdict. They are in our self-assessment, with fixes."
- Say "being attacked"; do not say "cannot be fooled".

**Slide 13 (0:45).**
- "Task completion: 37 of 37 scripted natural-language tasks pass. Each starts from a reset, and every operation goes through the verifier and the executor."
- "Every number you saw is checked to the fen against an oracle written separately from the engine."
- "Each task's log is a hash chain. One standard-library script re-verifies it, and a re-run at the same commit reproduces the same hash."
- [TEAM: add the green test count once the 21 failing API tests are updated; see the Technical Document, section 05.]

**Slide 14 (0:40).**
- "Nothing here is a new algorithm. Pactum works for the buyer. MYbank's 百灵 agent plans financing with MYbank's own products. Xero's JAX spots cash gaps. Cerebro, Capitalise and Lendio match borrowers to lenders. Codat informs the bank."
- "None we found is owned by the supplier and bounded by its own mandate across both debt books."
- Say "that we could find"; the Chinese-language check is still open [TEAM].

**Slide 15 (0:35).** "Next: fix the four findings, run the held-out tests with offers written by people outside the team, and pilot with two suppliers. The borrower file is designed so a lender could consume it; today the lenders are simulated." Then introduce the team [TEAM].

**Slide 16 (0:15).** Closing line: "Buyers have an agent that decides how long to pay you. Banks have a model that decides whether to lend to you. TermsLedger is yours."

## Production notes

- **Slide text.** Keep it to a title plus at most three short lines or one table. The numbers are the visuals, so set the key figure in large type on slides 5, 8 and 12.
- **Diagram.** Render `docs/deliverables/architecture.mmd` to PNG (for example `npx -p @mermaid-js/mermaid-cli mmdc -i architecture.mmd -o architecture.png -w 2000`). `scripts/build_deliverables.py` embeds the same PNG in the Technical Document when it exists.
- **Live demo.** Have a fallback: keep the demo video's Scene 1 and 2 clips on the laptop and run the app in mock mode offline.
- **Rehearse to 9:30** with a timer. If you run over, cut slide 4 first, then the `/chat` half of slide 9.
