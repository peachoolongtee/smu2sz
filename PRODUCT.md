# Product

<!-- impeccable:product-schema 1 -->

<!-- Written 8 October 2026 for wayfinder map #47, Wave 8, by inference from the repository's own documents; the owner was not interviewed. Every line names its source. "(inferred from X)" means X supports the statement and the owner has not confirmed it to this record. The open questions at the end are the gaps that most change future decisions. -->

## Platform

web

## Users

- Primary: the owner (老板) of a small supplier that sells on payment terms, the only human with authority: signs the mandate, approves Tier-2 actions, decides what to offer a buyer, whether cash is safe and whom to chase (inferred from CONTEXT.md and the owner's mission brief).
- The CFO or finance manager reads the same pages; the owner's recorded decision is one user and no separate role views (inferred from docs/STRATEGY_RESEARCH.md, decision 2 and section D).
- Sales reads the buyer's thread on Deals for what can be offered before the buyer asks (inferred from docs/STRATEGY_RESEARCH.md, sections E and K).
- Situation: a buyer asks over WeChat for longer terms, an early-pay discount or a rebate; finance's spreadsheet is two weeks stale; the owner accepts to protect the relationship and the reserve breaks weeks later (inferred from docs/STRATEGY_RESEARCH.md, section E).
- Evaluators: FinTechathon 2026 judges, and the CFO, banker or auditor who must reproduce why a decision was made (inferred from README.md and the owner's mission brief, objective 8).

## Product Purpose

- FLOW is the supplier's agent over both debt books: the credit it gives buyers (Terms Guard) and the credit it takes from lenders (Debt Desk), inside an owner-signed, versioned, revocable mandate the agent can never change (inferred from CONTEXT.md, README.md).
- It reads a buyer's offer, types its obligations, projects cash day by day, prices the gap against committed facilities, checks mandate and covenants, and answers with a business action: accept, counter, decline or wait for approval; NO DEAL is a first-class outcome (inferred from docs/ARCHITECTURE.md, CONTEXT.md).
- Direction for the next quarter: answer three questions before anyone asks them, on the same engine: what can I offer this buyer (the Safe Deal Envelope), what is earlier cash worth to me (the cash price curve), whom should I chase first (collections worth); read-only, behind flags (inferred from docs/STRATEGY_RESEARCH.md section K, docs/STRATEGY_MVP_REPORT.md section 1).
- Success: a cold reader finds the conclusion, the action and the three numbers in one reading; a CFO trusts every level-1 figure; no wrong financial action or unauthorised operation; in the pilot the owner's chosen response falls inside the envelope (inferred from docs/UX_SIMPLIFICATION_REPORT.md, the owner's mission brief section 4, docs/STRATEGY_RESEARCH.md kill criteria).

## Positioning

- The one thing no neighbour holds: the supplier's own living cash state, facilities and mandate, with a verifier that lets no number pass that breaks the floor. Insurers set limits from the buyer's risk, collections tools rank by delinquency on network data, early-pay marketplaces leave the rate to judgment, forecasting tools stop at the forecast (inferred from docs/STRATEGY_RESEARCH.md section D; a source gap, not a proof of novelty).
- "Commercial capital allocation" is the internal principle and the one sentence for judges and investors; it is sold under the categories buyers search (SME cash flow and working capital, AR and collections, 供应链金融) in the owner's words: "what can I offer", "who to chase", "am I safe" (inferred from docs/STRATEGY_RESEARCH.md, decision 1).
- The language model only interprets text; deterministic code decides and executes, in a hash-chained log (inferred from README.md).

## Operating Context

- One surface, `apps/web` (Next.js, `pnpm dev`; mock mode offline by default, `NEXT_PUBLIC_API_MODE=live` against the FastAPI service), with two shells switched by a segmented control (inferred from README.md, apps/web/DESIGN.md).
- Business shell, five sections in a pill navigation and a five-tab phone bar: Home (with Approvals and Limits in the account sheet), Deals, Cash & funding, Receivables, Activity; "Ask FLOW" as a slide-over (inferred from docs/UX_SIMPLIFICATION_REPORT.md, apps/web/DESIGN.md).
- Operate is the Business shell: distances from today, one inbox thread per buyer, business sentences, no tier, hash, code, id or day number at level 1 (inferred from docs/UX_SIMPLIFICATION_REPORT.md, "Business / Demo differences").
- Demo is the same surface with the engine's evidence shown: "Day N", the simulated inbox with every message and the unknown-sender flag, the engine views, raw sentences beside their twins, a flat look with a deep-brand strip, plus the story page `/demo` (inferred from docs/UX_SIMPLIFICATION_REPORT.md and the project handover notes).
- Six disclosure levels: 1 conclusion, 2 recommended action, 3 cost, timing and consequence, 4 reasoning, 5 calculation (sentence before formula), 6 engine and audit evidence; Business interactions stop at 3 by default (inferred from docs/UX_SIMPLIFICATION_REPORT.md).
- Rituals: full-page screenshots per wave under `docs/screenshots/`, cold-user walks read from the DOM at desktop and phone widths, the Impeccable detector on changed files, an independent second agent checking every money figure (inferred from docs/UX_SIMPLIFICATION_REPORT.md).
- Languages: English and Chinese on one switch (`Lang = "en" | "zh"`, `<html lang>` set); Chinese strings follow for every new key (inferred from apps/web/lib/i18n.ts, docs/UX_SIMPLIFICATION_BRIEF.md section 7).

## Capabilities and Constraints

- The browser computes no money: every figure, date and sentence arrives formatted from the server, traceable to a formula; presentation work leaves the engine unchanged and a test proves display fields feed nothing (inferred from apps/web/DESIGN.md, docs/UX_SIMPLIFICATION_REPORT.md).
- Business words: the server's `*_when`, `event_text`, `label_short` twins; no client-side regex rewrites, approval inference or truncation; one plural template for every count (inferred from docs/UX_SIMPLIFICATION_BRIEF.md section 7, docs/UX_SIMPLIFICATION_REPORT.md).
- Vocabulary is CONTEXT.md's: headroom, first breach versus worst point, business action versus verdict, net economic cost with gross and offset beside it, in transit, NO DEAL (inferred from CONTEXT.md).
- One brand-filled primary action per page; status colour only for status, always with a word; section hues for wayfinding only; the deep block only for the Home hero and the Demo strip (inferred from apps/web/DESIGN.md).
- Flags: API `FEATURE_TERMS_GUARD`, `_DEBT_DESK`, `_CAPEX`, `_BORROWER_FILE`, `_BUYER_NEGOTIATION`, `_SECURITY_SCENES`, `_ALERTS`, `_EXPECTED_PLANS`, and default-off `_ENVELOPE`, `_PRICE_CURVE`, `_COLLECTIONS_WORTH`; web `NEXT_PUBLIC_STRATEGY_MVP`, `NEXT_PUBLIC_API_MODE`, `NEXT_PUBLIC_DEMO`. A disabled feature returns `FEATURE_DISABLED` and never breaks the core (inferred from services/api/app/config.py, docs/ARCHITECTURE.md).
- Money is integer fen and rates integer bp; days are offsets from `as_of` with a simulated clock; conservative mode decides, expected mode is shown only (inferred from docs/ARCHITECTURE.md, CONTEXT.md).
- Stability mode: no architecture change; the Home's structure refined, not redesigned; the five sections and the engine views in Demo mode stay (inferred from the owner's mission brief section 9, docs/UX_SIMPLIFICATION_REPORT.md "not changed").
- Undecided: a Demo-only card-by-card walk of a deal; a FLOW visual mark; Chinese twins on `GET /ledger` and the verdict view (inferred from docs/UX_SIMPLIFICATION_REPORT.md "left").

## Brand Commitments

- Name: FLOW 流 on the surface, "Ask FLOW", "Why FLOW recommends this"; the repository, glossary and package are still TermsLedger v2 (inferred from the project handover notes, CONTEXT.md, README.md; see open question 1).
- Voice: calm and plain, the owner's words, conclusions first, distances from today ("in 47 days", "arrives in 3 days"), sentences before formulas, named facts ("First breach", "Worst point"), no claim of a gain where the verifier floors at zero, refusals said once and quietly ("1 message from an unknown sender was set aside") (inferred from docs/UX_SIMPLIFICATION_BRIEF.md section 7, docs/UX_SIMPLIFICATION_REPORT.md).
- Identity: `apps/web/DESIGN.md` is the incumbent system (colour option C, section hues, one radius scale, the motion kit, lifted base) and is referenced, not restated, here (inferred from apps/web/DESIGN.md, docs/UX_SIMPLIFICATION_REPORT.md).
- The owner's recorded taste: "a middle ground" on colour; coloured icons, pill buttons and animations wanted; the muted palette found stale; gradients, rainbow icons and runtime web fonts left out (inferred from docs/UX_SIMPLIFICATION_REPORT.md).
- References for the finish: the two light dashboards in `docs/research/inspiration/` set the bar for density, hierarchy and finish; not a redesign brief; the dark variant is not adopted (inferred from docs/research/inspiration/README.md).

## Evidence on Hand

- All data is synthetic: `fixtures/scenarios/golden_sme.json` (cash ¥400,000, floor ¥300,000, Foshan Home Retail's ¥420,000 monthly invoice on 45-day terms, a ¥5,000 concession budget, a standing plan of ¥405,000 at ¥3,113.93), recorded API answers in `apps/web/mocks/`, hash-chain evidence in `services/api/evals/e2e/latest/evidence/` (inferred from README.md, docs/STRATEGY_RESEARCH.md).
- Screenshots per wave in `docs/screenshots/`; cold-user walks and the colour research under `docs/research/`; the inspiration images in `docs/research/inspiration/` (inferred from docs/UX_SIMPLIFICATION_REPORT.md, docs/research/inspiration/README.md).
- Absent, and not to be fabricated: real customers, pilot data, testimonials, pricing, an outbound channel ("Send this counter" runs the demo's buyer kernel and says so), a bank feed, a FLOW mark (inferred from README.md, docs/UX_SIMPLIFICATION_REPORT.md).

## Product Principles

1. Conclusion first, evidence folded: the status words and the business action at level 1, the engine at level 6 (inferred from docs/UX_SIMPLIFICATION_REPORT.md).
2. The server says it: every number, date and sentence is computed and worded once, on the server, and traceable (inferred from apps/web/DESIGN.md, docs/UX_SIMPLIFICATION_BRIEF.md).
3. One owner, one mandate: nothing acts beyond the mandate, and an approval is the owner's explicit act on the exact item shown; code never approves (inferred from the owner's mission brief, invariants I and M).
4. Fail closed and say so: abstain, NO DEAL, "not available until", a set-aside message, rather than a confident guess (inferred from the owner's mission brief objective 4, CONTEXT.md).
5. Features are not progress: delete, merge and simplify; correctness outranks the current demo numbers (inferred from the owner's mission brief sections 2 and 3).

## Accessibility & Inclusion

- WCAG 2.x AA as the floor: every text pair 4.5:1 or better, every visible boundary and icon 3:1, nothing said by colour alone, the focus ring never removed, `prefers-reduced-motion` honoured and forced in the test runs, phone widths first-class (inferred from apps/web/DESIGN.md, docs/UX_SIMPLIFICATION_REPORT.md).

## Out of Scope

- A portfolio optimiser, buyer scoring or any ML, customer profitability, proposing looser mandates, and new action in the pilot windows (inferred from docs/STRATEGY_RESEARCH.md section K).
- Real payments, lending, brokerage or advice: a simulation and decision support under the owner's own limits (inferred from README.md).
- Dark theme, a "Buy equipment" navigation section, gradients on buttons or cards, runtime web fonts (inferred from docs/research/inspiration/README.md, docs/UX_SIMPLIFICATION_REPORT.md, apps/web/DESIGN.md).

## Open Questions for the Owner

1. Is the product name on the surface FLOW 流 everywhere, and does TermsLedger survive anywhere a user reads? Is a visual mark wanted?
2. Beyond the owner, which readers are confirmed users: CFO, finance clerk, sales? Does one product record serve the whole repository or does `apps/web` need its own?
3. Phone web is first-class today; is any native (iOS or Android) surface intended?
4. For the Impeccable finish, which Business surfaces are frozen (the Home's structure, the five sections) and which may change shape?
5. Does the inspiration set's dark variant stay rejected?
6. Is the Demo-only card-by-card walk of a deal wanted back as a showcase?
7. Which SMEs and which month for the shadow pilot (decision 5), so that evidence can replace the synthetic books here?
