# TermsLedger v2: Pitch Deck Outline

**Deliverable:** the presentation deck (required), at most **10 minutes**, built on the official `docs/research/templates/presentation-template.pptx` (16:9). The template has four slide types: title, a contents slide with **six** numbered items, a content slide and a "THANKS" closing slide. So this outline uses **six sections**, 18 slides and **9:40** of speaking time, leaving 20 seconds of slack. The language is English (the international defence is in English).

**Numbers.** Every figure on a slide comes from `fixtures/golden/golden_values.json` or the evaluation reports, and is synthetic unless marked as a public market fact. The spec v2 §13 wording rules apply throughout: no "first", "best loan", "proof", "atomic", "financial advice", "bank-grade", "safe by construction" or "cannot be fooled", and no claim of bank-covenant compliance. Say "simulation" wherever the clock, the bank feed, the buyer or a lender appears; say "screens the entered obligations only", "cheapest within the bounded search", "reserve-coverage reading" for the bullet-loan DSCR and "internally checkable chain". Figures that depend on the day-0 cash books are listed once in `docs/SYSTEM_WALKTHROUGH.md` section 7; re-check the slides against that table after any change to them.

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
| 4 | Content | 01 | Who we built it for | A persona card: a supplier with 20–100 staff, one bank line, a bookkeeper and no finance team. The label INFERENCE is visible. | 1:05–1:15 |
| 5 | Content | 02 | "60 days going forward" is a ¥210,000 loan | One large number, then a three-line derivation: the extra receivables ¥210,000.00 → funded on invoice financing at 10.84% → **¥24,326.92 over the 13 invoices in a 365-day window** | 1:15–2:00 |
| 6 | Content | 02 | Two features, one engine | Flow: buyer offer → Terms Guard (compile, project, verdict) ⇄ Debt Desk (size the gap, route the funding, marginal cost) → counter, or NO DEAL with the gap funded | 2:00–2:35 |
| 7 | Content | 03 | Scene 1: the offer is a loan | A live demo, or a 60-second clip from the demo video: owner sign-in → Inbox spans → trajectory (day 47) → verdict REJECT with AGG_CONCESSION_EXCEEDED, RESERVE_BREACH@47, DISCOUNT_ABOVE_BREAK_EVEN and EARLY_PAY_DEARER_THAN_PLAN, each with its formula → Counter A accepted | 2:35–3:40 |
| 8 | Content | 03 | Day 34: the agent speaks first | The owner home at `/`: Day 34; the agent's opener (RCV-A's ¥162,800 not paid, cash ¥200,000 below the floor on day 42, a proposed ¥200,000 advance costing ¥1,782.19 at 32.5% a year for 10 days, above the 15% ceiling, so it needs the owner's approval); the Go ahead button queues it as an approval; the owner approves it on the approval card; the alert clears and the cash lands on day 37. Footer: the clock and the bank feed are simulated | 3:40–4:15 |
| 9 | Content | 03 | Scene 2: the buyer walks, and the gap is still covered | The router plan table: line ¥150,000 + invoice financing ¥255,000 = ¥3,113.93, against ¥5,040 for the discount; a note that a pending loan counts as zero | 4:15–4:50 |
| 10 | Content | 03 | Capex, and talking to it | Left: the capex table (the 18-month illustration fails DSCR in month 1, 1.09× after the demo's earlier draws; the 36-month loan is selected on lowest total financing charges, and on untouched books the 48-month lease is, because the loan's first instalment would take cash below the reserve). Evaluating writes nothing; the Apply button is the owner's explicit step that queues the application. It is a screen on the owner's own estimates. Right: the chat panel (goal → plan; "make it 0.8%" corrected; "make it 1%" kept unchanged, above the 0.88% break-even) | 4:50–5:15 |
| 11 | Content | 04 | The model only proposes | The architecture diagram (`architecture.mmd`) with the trust boundary drawn: untrusted text → typed obligations → deterministic verifier → executor → hash-chained log | 5:15–5:50 |
| 12 | Content | 04 | Three tiers, enforced by code | A tier table: Tier 1 act alone (only a proven early-pay discount that is below break-even, needed and cheaper than the plan; draws on committed facilities), Tier 2 ask the owner (every other acceptance), Tier 3 never; the executor's gate order as a strip | 5:50–6:20 |
| 13 | Content | 04 | Attacked 255 ways, then audited | A metrics table: 255 attacks (122 through the API, 133 through chat), 0 with harm, 0 unauthorised operations, ¥0 moved, 0 protected values disclosed; 98.4% of the API attacks detected; twelve findings of our own, all fixed or mitigated; an independent audit (13 findings) and five red-team rounds (26 findings), all fixed with a regression test each; the red-team rounds then stopped | 6:20–6:55 |
| 14 | Content | 05 | Results you can re-run | Four tiles: 49/49 scripted tasks · 5,446 API tests pass, 33 skipped (3 Oct 2026) · every golden value matches an independent oracle, and the router matches a grid-bounded brute force over the plans it can run on 26/26 cases · 49/49 evidence chains verify with one script | 6:55–7:30 |
| 15 | Content | 05 | What we got wrong, and fixed | Left: "Unseen buyer messages, first run: 33/63 verdicts agree with the labels (52%); 8 accepted without the owner, **4 of them wrong**." Four one-line examples (an invoice that doesn't exist; a transfer amount contradicting the rate; a yuan discount contradicting the percentage; a dropped delivery request). Right: "ADR-0005: autonomy requires proof. Since then, **0 wrong autonomous accepts** on every set and both compiler paths." Footnote: `services/api/evals/accuracy_summary.md` | 7:30–8:20 |
| 16 | Content | 06 | What is new, and what is not | The prior-art map (buyer side / lender side / borrower tools / TermsLedger) and the line "none we found is owned by the supplier and bounded by its own mandate across both debt books" | 8:20–8:55 |
| 17 | Content | 06 | Next, and the team | Left: the roadmap (a held-out set written by people outside the team, run before any tuning; a live Claude run; settlement dates as typed terms so good early-pay offers need no click; two pilot suppliers; a borrower file a lender can consume; a PIPL review before any real buyer documents are sent to a model provider; anchoring the log's head outside the system). Right: the team [TEAM: names, universities, roles] | 8:55–9:25 |
| 18 | Closing (THANKS) | – | – | The template's closing image. Say the closing line over it. | 9:25–9:40 |

## Speaker notes

**Slide 1 (0:15).** "We are [TEAM: team name] from [TEAM: universities]. TermsLedger is an agent a small supplier owns, which manages the credit it gives buyers and the credit it takes from lenders."

**Slide 2 (0:10).** Read the six items quickly; no narration beyond the titles.

**Slide 3 (0:40).**
- "Buyers now negotiate with software. Pactum's public material reports a large-retailer deployment with an average 35-day payment-term extension, and roughly seven in ten suppliers agreeing." Spec v2 §1 records these figures as CONFIRMED, noting they vary between Pactum pages; say "roughly".
- "Lenders decide by model. MYbank describes a '310' loan: under three minutes to apply, under one second to approve, and more than 53 million SMEs served by the end of 2023."
- "The supplier in the middle has a bookkeeper and a chat thread."
- Footnotes: the spec v2 §18 sources. Use names only; no logos or screenshots.

**Slide 4 (0:10).**
- "Our user is a supplier with 20 to 100 staff, one credit line and no finance team. That profile is our inference, and we claim only what the numbers show." [TEAM: update if interviews happen.]

**Slide 5 (0:45).** "Move a ¥420,000-a-month buyer from 45 to 60 days and the supplier carries ¥210,000 more receivables, forever. The credit line has a clean-down rule, so it cannot carry a permanent need. The cheapest committed source that can is invoice financing at 10.84%, so that phrase costs ¥24,326.92 over the 13 invoices in a year's window. All numbers here are from our synthetic fixture."

**Slide 6 (0:35).**
- "Terms Guard compiles the offer into typed obligations with the exact words they came from. It projects cash day by day and checks the owner's signed limits and the bank's covenants."
- "Debt Desk prices any gap from the owner's own facilities and gives Terms Guard the firm's marginal cost of funds."
- "So a counter is priced from real borrowing cost, and the agent can say no deal because it already knows the alternative."

**Slide 7 (1:05).** Live, or the video clip. Sign in as the owner first; then hit these numbers:
- the concession meter at ¥28,326.92 against the ¥5,000 cap;
- cash at ¥209,960 on day 47, below the ¥300,000 floor, curable for ¥2,406.67;
- break-even 0.88%: the buyer's 1.2% is above it, so the verdict also carries DISCOUNT_ABOVE_BREAK_EVEN, and taking it costs ¥6,508.05 against ¥3,550.64 for the plan without it (EARLY_PAY_DEARER_THAN_PLAN);
- REJECT with AGG_CONCESSION_EXCEEDED, RESERVE_BREACH@47, DISCOUNT_ABOVE_BREAK_EVEN and EARLY_PAY_DEARER_THAN_PLAN, each with its formula;
- Counter A: 45 days, early settlement on up to ¥257,200 at 0.85%, ¥3,027.77 in total, against ¥3,113.93 for the standing plan; Counter B: 55-day terms with a 0.30% price adjustment, ¥1,260.00 an invoice, which needs the owner (60 days would fail its own re-check);
- the buyer kernel accepts, and the commitment and the line draw are logged.

**Slide 8 (0:35).**
- "The books keep moving. The agreed ¥255,013.80 arrived on day 2. On day 34 the other ¥162,800 has not."
- "The agent speaks first. Cash will fall ¥200,000 below the floor on day 42. It proposes an advance on a later invoice, says it costs ¥1,782.19, 32.5% a year for the ten days it is held, above our 15% ceiling, and waits for the owner."
- "The owner says go ahead. That is not enough: the advance costs more than the agent may borrow alone, so it is queued as an approval. The owner approves it as a second step, the advance runs, the alert clears and the cash lands on day 37. Every step is on the hash chain. Later it proposes repaying the credit line too. The clock and the bank feed are simulated."
- Say "the agent proposed, the owner said go ahead, then approved"; the ceiling is the owner's mandate and the code never approves for the owner.

**Slide 9 (0:35).** "A different buyer refuses every counter within three rounds. No deal is a real outcome. The router finds the line plus invoice financing for ¥3,113.93, against ¥5,040 for taking the discount. The government-guaranteed loan would be cheaper, but it is not committed and arrives after payroll, so it counts as zero. The same offer in other words gets the same verdict."

**Slide 10 (0:25).** "For a ¥600,000 machine, NPV is ¥380,885.77 and payback is month 31. The 18-month illustration breaks DSCR in month 1. After the demo's draws the 36-month loan, the facility's real term, is selected on lowest total financing charges; on untouched books it is the 48-month lease, because the loan's first instalment would take cash below the reserve. Evaluating writes nothing: the owner presses Apply and the application is queued for approval. It is a screen on the owner's own estimates, not an investment appraisal. And the owner can just ask in the chat panel: a goal becomes a plan, and 1% is refused because it costs more than the firm's own borrowing."

**Slide 11 (0:35).**
- "The model has one job: turn text into a typed proposal, tied to exact spans, or abstain."
- "The verifier never reads free text. Operations are built by code and run only by the executor."
- "Only the owner can add a lender. Contingent promises count at their maximum, and uncommitted loans at zero."

**Slide 12 (0:30).** "Tier 1: the agent acts alone, but it may accept a buyer's offer only when it is an early-pay discount that is below break-even, needed and cheaper than the router's plan, and that it can prove it read completely. Every other acceptance is Tier 2: ask the owner. Tier 3: never, not even for the owner, like a personal guarantee. The executor computes the tier itself, checks the signed mandate, the nonce, expiry and idempotency, and logs every outcome, refusals included."

**Slide 13 (0:35).**
- "We attacked it 255 ways, in English and Chinese: 122 through the API (prompt injection, fake lenders, fake 'agreed last month' rebates, data extraction, privilege escalation, replay and failure recovery) and 133 through the chat, as the owner, as a buyer with and without its channel key, and as the agent key, including 41 negated, conditional or malformed instructions."
- "No unauthorised operation, no money moved, nothing leaked. 98.4% of the API attacks were also detected and logged; 47 chat attacks changed nothing but raised no flag, most of them instructions that correctly did nothing. Known limits: a buyer with its key probing the chat can find our accept/counter threshold, and the agent key can read protected labels in chat replies."
- "Then we asked for an independent audit (13 findings) and ran five red-team rounds against the fixes (26 findings), each closed with a regression test, and we stopped there. That is evidence of a process, not a certificate. Two things have not run: the concurrency suite on PostgreSQL, and the language-boundary certification against a live model; both are built and pass on SQLite and on recorded and scripted models."
- "The suite found twelve weaknesses of our own along the way, such as a non-atomic log write and a receipt anyone could record. All are fixed or mitigated, and listed in our self-assessment."
- Say "being attacked"; do not say "cannot be fooled".

**Slide 14 (0:35).**
- "Task completion: 49 of 49 scripted natural-language tasks pass, including the financing comparison, alerts, reconciliation, covenant ratios, capex and the borrower file in chat. Each starts from a reset, and every operation goes through the verifier and the executor."
- "5,446 API tests pass. Every number you saw is checked to the fen against an oracle written separately from the engine, and the router matches a grid-bounded brute-force search over the plans it can run on 26 of 26 cases."
- "Each task's log is a hash chain. One standard-library script re-verifies it. The chain is internally checkable only: its head is not anchored outside the system, and head hashes differ from run to run."

**Slide 15 (0:50).** This is the slide that earns trust; say it plainly.
- "We asked a separate agent to write buyer messages from the spec alone, and to label them before it ever ran our system. On that unseen set, our verdicts matched the labels 52% of the time. Worse, the agent accepted 8 offers without the owner, and 4 of those were wrong."
- "Every one was an early-pay offer where we kept the rate and dropped the clause that contradicted it or added to it: an invoice that doesn't exist, a transfer amount that doesn't match, a yuan discount that doesn't match, an extra delivery request."
- "No grammar can be complete. So we changed the rule, not just the grammar: the agent may only accept on its own when it can prove every amount, date, invoice and request in the message is accounted for. Anything else goes to the owner."
- "Since then, zero wrong autonomous accepts, on every set, with the offline grammar and with live DeepSeek; text the agent cannot fully read goes to the owner. Understanding is still imperfect, about one message in three is decided differently from the labels, but a misread now costs the owner a click, not a commitment."
- Do not quote the after-fix agreement figures as independent: those sets guided the fixes.

**Slide 16 (0:35).**
- "Nothing here is a new algorithm. Pactum works for the buyer. MYbank's 百灵 agent plans financing with MYbank's own products. Xero's JAX spots cash gaps. Cerebro, Capitalise and Lendio match borrowers to lenders. Codat informs the bank."
- "None we found is owned by the supplier and bounded by its own mandate across both debt books."
- Say "that we could find"; the Chinese-language check is still open [TEAM].

**Slide 17 (0:30).** "Next: a held-out set written by people outside the team, run before any tuning; a live Claude run; reading settlement dates as typed terms so good early-pay offers need no click; and pilots with two suppliers. The borrower file is designed so a lender could consume it; today the lenders are simulated." Then introduce the team [TEAM].

**Slide 18 (0:15).** Closing line: "Buyers have an agent that decides how long to pay you. Banks have a model that decides whether to lend to you. TermsLedger is yours."

## Production notes

- **Slide text.** Keep it to a title plus at most three short lines or one table. The numbers are the visuals, so set the key figure in large type on slides 5, 9, 13 and 15. Never cut slide 15.
- **Diagram.** Render `docs/deliverables/architecture.mmd` to PNG (for example `npx -p @mermaid-js/mermaid-cli mmdc -i architecture.mmd -o architecture.png -w 2000`). `scripts/build_deliverables.py` embeds the same PNG in the Technical Document when it exists.
- **Live demo.** Have a fallback: keep the demo video's Scene 1 and 2 clips on the laptop and run the app in mock mode offline.
- **Rehearse to 9:30** with a timer. If you run over, cut slide 4 first, then the chat half of slide 10.
