# TermsLedger v2: Pitch Deck Outline

**Deliverable:** the presentation deck (required), at most **10 minutes**, built on the official `docs/research/templates/presentation-template.pptx` (16:9). The template has four slide types: title, a contents slide with **six** numbered items, a content slide and a "THANKS" closing slide. So this outline uses **six sections**, 17 slides and **9:40** of speaking time, leaving 20 seconds of slack. The language is English (the international defence is in English).

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
5. Results, and what we got wrong
6. What is new, what is next, and the team

## Slide by slide

| # | Template slide | Section | Title | Key visual | Time |
| --- | --- | --- | --- | --- | --- |
| 1 | Title | – | TermsLedger: the supplier's agent for both of its debt books | Project name and team name in the placeholders (作品名 → "TermsLedger v2", 团队名 → [TEAM: team name]) | 0:00–0:15 |
| 2 | Contents | – | Contents | The six items above | 0:15–0:25 |
| 3 | Content | 01 | Three parties. Only one has no agent. | Three text columns: Buyer (a negotiation agent) · Supplier (an owner and a chat thread) · Lender (a model that approves in seconds). Small source footnotes. No logos. | 0:25–1:05 |
| 4 | Content | 01 | Who we built it for | A persona card: a supplier with 20–100 staff, one bank line, a bookkeeper and no finance team. The label INFERENCE is visible. | 1:05–1:25 |
| 5 | Content | 02 | "60 days going forward" is a ¥207,123.29 loan | One large number, then a three-line derivation: the extra receivables ¥207,123.29 → funded on invoice financing at 10.84% → **¥22,455.62 a year** | 1:25–2:10 |
| 6 | Content | 02 | Two features, one engine | Flow: buyer offer → Terms Guard (compile, project, verdict) ⇄ Debt Desk (size the gap, route the funding, marginal cost) → counter, or NO DEAL with the gap funded | 2:10–2:45 |
| 7 | Content | 03 | Scene 1: the offer is a loan | A live demo, or a 60-second clip from the demo video: owner sign-in → Inbox spans → trajectory (day 47) → verdict REJECT with AGG_CONCESSION_EXCEEDED, RESERVE_BREACH@47 and DISCOUNT_ABOVE_BREAK_EVEN, each with its formula → Counter A accepted | 2:45–4:00 |
| 8 | Content | 03 | Scene 2: the buyer walks, and the gap is still covered | The router plan table: line ¥150,000 + invoice financing ¥210,000 = ¥2,712.94, against ¥5,040 for the discount; a note that a pending loan counts as zero | 4:00–4:35 |
| 9 | Content | 03 | Capex, and talking to it | Left: the capex table (18-month loan fails DSCR at 1.13×; 36-month loan selected). Right: the chat panel (goal → plan; "make it 0.8%" corrected; "make it 1%" kept unchanged, above the 0.88% break-even) | 4:35–5:15 |
| 10 | Content | 04 | The model only proposes | The architecture diagram (`architecture.mmd`) with the trust boundary drawn: untrusted text → typed obligations → deterministic verifier → executor → hash-chained log | 5:15–5:50 |
| 11 | Content | 04 | Three tiers, enforced by code | A tier table: Tier 1 act alone (only a proven early-pay discount below break-even; draws on committed facilities), Tier 2 ask the owner (every other acceptance), Tier 3 never; the executor's gate order as a strip | 5:50–6:20 |
| 12 | Content | 04 | Attacked 122 ways | A metrics table: 122 attacks, 0 unauthorised operations, ¥0 moved, 0 protected values disclosed; 97.5% detected; twelve findings of our own, all fixed or mitigated | 6:20–6:55 |
| 13 | Content | 05 | Results you can re-run | Four tiles: 37/37 scripted tasks · 3,556 API tests pass · every golden value matches an independent oracle, and the router matches brute force on 26/26 cases · 37/37 evidence chains verify with one script | 6:55–7:30 |
| 14 | Content | 05 | What we got wrong, and fixed | Left: "Unseen buyer messages, first run: 33/63 verdicts agree with the labels (52%); 8 accepted without the owner, **4 of them wrong**." Four one-line examples (an invoice that doesn't exist; a transfer amount contradicting the rate; a yuan discount contradicting the percentage; a dropped delivery request). Right: "ADR-0005: autonomy requires proof. Since then, **0 wrong autonomous accepts** on every set and both compiler paths." Footnote: `services/api/evals/accuracy_summary.md` | 7:30–8:20 |
| 15 | Content | 06 | What is new, and what is not | The prior-art map (buyer side / lender side / borrower tools / TermsLedger) and the line "none we found is owned by the supplier and bounded by its own mandate across both debt books" | 8:20–8:55 |
| 16 | Content | 06 | Next, and the team | Left: the roadmap (a held-out set written by people outside the team, run before any tuning; a live Claude run; settlement dates as typed terms so good early-pay offers need no click; two pilot suppliers; a borrower file a lender can consume). Right: the team [TEAM: names, universities, roles] | 8:55–9:25 |
| 17 | Closing (THANKS) | – | – | The template's closing image. Say the closing line over it. | 9:25–9:40 |

## Speaker notes

**Slide 1 (0:15).** "We are [TEAM: team name] from [TEAM: universities]. TermsLedger is an agent a small supplier owns, which manages the credit it gives buyers and the credit it takes from lenders."

**Slide 2 (0:10).** Read the six items quickly; no narration beyond the titles.

**Slide 3 (0:40).**
- "Buyers now negotiate with software. Pactum's public material reports a large-retailer deployment with an average 35-day payment-term extension, and roughly seven in ten suppliers agreeing." Spec v2 §1 records these figures as CONFIRMED, noting they vary between Pactum pages; say "roughly".
- "Lenders decide by model. MYbank describes a '310' loan: under three minutes to apply, under one second to approve, and more than 53 million SMEs served by the end of 2023."
- "The supplier in the middle has a bookkeeper and a chat thread."
- Footnotes: the spec v2 §18 sources. Use names only; no logos or screenshots.

**Slide 4 (0:20).**
- "Our user is a supplier with 20 to 100 staff, one credit line and no finance team."
- "This profile is our inference. In two interviews, one of our assumed pains was contradicted, so we only claim what the numbers show." [TEAM: update if interviews happen.]

**Slide 5 (0:45).** "Move a ¥420,000-a-month buyer from 45 to 60 days and the supplier carries ¥207,123.29 more receivables, forever. The credit line has a clean-down rule, so it cannot carry a permanent need. The cheapest committed source that can is invoice financing at 10.84%, so that phrase costs ¥22,455.62 a year. All numbers here are from our synthetic fixture."

**Slide 6 (0:35).**
- "Terms Guard compiles the offer into typed obligations with the exact words they came from. It projects cash day by day and checks the owner's signed limits and the bank's covenants."
- "Debt Desk prices any gap from the owner's own facilities and gives Terms Guard the firm's marginal cost of funds."
- "So a counter is priced from real borrowing cost, and the agent can say no deal because it already knows the alternative."

**Slide 7 (1:15).** Live, or the video clip. Sign in as the owner first; then hit these numbers:
- the concession meter at ¥26,455.62 against the ¥5,000 cap;
- cash at ¥254,960 on day 47, below the ¥300,000 floor, curable for ¥802.70;
- break-even 0.88%: the buyer's 1.2% is above it, so the verdict also carries DISCOUNT_ABOVE_BREAK_EVEN;
- REJECT with AGG_CONCESSION_EXCEEDED, RESERVE_BREACH@47 and DISCOUNT_ABOVE_BREAK_EVEN, each with its formula;
- Counter A: 45 days, early settlement on up to ¥211,900 at 0.85%, ¥2,642.24 in total;
- the buyer kernel accepts, and the commitment and the line draw are logged.

**Slide 8 (0:35).** "A different buyer refuses every counter within three rounds. No deal is a real outcome. The router finds the line plus invoice financing for ¥2,712.94, against ¥5,040 for taking the discount. The government-guaranteed loan would be cheaper, but it is not committed and arrives after payroll, so it counts as zero. The same offer in other words gets the same verdict."

**Slide 9 (0:40).** "For a ¥600,000 machine, NPV is ¥380,885.77 and payback is month 31. The loan with the least interest breaks DSCR in month 1 at 1.13×, so the 36-month loan is selected and queued for the owner with a borrower file. And the owner can just ask, in the chat panel: a goal becomes a plan with a fallback, 0.8% is a correction it accepts, and 1% is refused because it costs more than the firm's own borrowing."

**Slide 10 (0:35).**
- "The model has one job: turn text into a typed proposal, tied to exact spans, or abstain."
- "The verifier never reads free text. Operations are built by code and run only by the executor."
- "Only the owner can add a lender. Contingent promises count at their maximum, and uncommitted loans at zero."

**Slide 11 (0:30).** "Tier 1: the agent acts alone, but it may accept a buyer's offer only when it is an early-pay discount below break-even that it can prove it read completely. Every other acceptance is Tier 2: ask the owner. Tier 3: never, not even for the owner, like a personal guarantee. The executor computes the tier itself, checks the signed mandate, the nonce, expiry and idempotency, and logs every outcome, refusals included."

**Slide 12 (0:35).**
- "We attacked it 122 ways, in English and Chinese: prompt injection, fake lenders, fake 'agreed last month' rebates, data extraction, privilege escalation, replay and failure recovery."
- "No unauthorised operation, no money moved, nothing leaked. 97.5% of attacks were also detected and logged."
- "The suite found twelve weaknesses of our own along the way, such as a non-atomic log write and a receipt anyone could record. All are fixed or mitigated, and listed in our self-assessment."
- Say "being attacked"; do not say "cannot be fooled".

**Slide 13 (0:35).**
- "Task completion: 37 of 37 scripted natural-language tasks pass. Each starts from a reset, and every operation goes through the verifier and the executor."
- "3,556 API tests pass. Every number you saw is checked to the fen against an oracle written separately from the engine, and the router matches a brute-force search on 26 of 26 cases."
- "Each task's log is a hash chain. One standard-library script re-verifies it, and a re-run at the same commit reproduces the same hash."

**Slide 14 (0:50).** This is the slide that earns trust; say it plainly.
- "We asked a separate agent to write buyer messages from the spec alone, and to label them before it ever ran our system. On that unseen set, our verdicts matched the labels 52% of the time. Worse, the agent accepted 8 offers without the owner, and 4 of those were wrong."
- "Every one was an early-pay offer where we kept the rate and dropped the clause that contradicted it or added to it: an invoice that doesn't exist, a transfer amount that doesn't match, a yuan discount that doesn't match, an extra delivery request."
- "No grammar can be complete. So we changed the rule, not just the grammar: the agent may only accept on its own when it can prove every amount, date, invoice and request in the message is accounted for. Anything else goes to the owner."
- "Since then, zero wrong autonomous accepts, on every set, with the offline grammar and with live DeepSeek. Understanding is still imperfect, about one message in three is decided differently from the labels, but a misread now costs the owner a click, not a commitment."
- Do not quote the after-fix agreement figures as independent: those sets guided the fixes.

**Slide 15 (0:35).**
- "Nothing here is a new algorithm. Pactum works for the buyer. MYbank's 百灵 agent plans financing with MYbank's own products. Xero's JAX spots cash gaps. Cerebro, Capitalise and Lendio match borrowers to lenders. Codat informs the bank."
- "None we found is owned by the supplier and bounded by its own mandate across both debt books."
- Say "that we could find"; the Chinese-language check is still open [TEAM].

**Slide 16 (0:30).** "Next: a held-out set written by people outside the team, run before any tuning; a live Claude run; reading settlement dates as typed terms so good early-pay offers need no click; and pilots with two suppliers. The borrower file is designed so a lender could consume it; today the lenders are simulated." Then introduce the team [TEAM].

**Slide 17 (0:15).** Closing line: "Buyers have an agent that decides how long to pay you. Banks have a model that decides whether to lend to you. TermsLedger is yours."

## Production notes

- **Slide text.** Keep it to a title plus at most three short lines or one table. The numbers are the visuals, so set the key figure in large type on slides 5, 8, 12 and 14. Never cut slide 14.
- **Diagram.** Render `docs/deliverables/architecture.mmd` to PNG (for example `npx -p @mermaid-js/mermaid-cli mmdc -i architecture.mmd -o architecture.png -w 2000`). `scripts/build_deliverables.py` embeds the same PNG in the Technical Document when it exists.
- **Live demo.** Have a fallback: keep the demo video's Scene 1 and 2 clips on the laptop and run the app in mock mode offline.
- **Rehearse to 9:30** with a timer. If you run over, cut slide 4 first, then the chat half of slide 9.
