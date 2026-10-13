# Home V2: the compact card, the compact chart, the honest worklist, the fluid width (owner, 13 Oct 2026, review of dev 4691f566)

## 1. The recommendation card is compact again
Eyebrow "What we recommend" · headline (server) · ONE line that reconciles with the strip (server `action.consequence_text`:
"Cash first falls below your minimum in 12 days. Without new funding, the shortfall reaches ¥405k in 30 days." — the first
breach day and the lowest point, the same figures the KPIs show; never "falls to ¥60k" alone) · the three facts in one row
(Estimated cost · Funding timing · Authority, from `action.facts`) · the ActionGroup [Run funding plan] [Compare funding
options] · the approval line only when approval is needed (when not, the Authority fact already says "Within your limits";
no extra line).
The funding timeline leaves the default card. The "Funding timing" fact carries a disclosure: hover or focus on desktop, tap on
phone, or `?funding=1` in the URL, which opens the **funding composition** under the facts row: one row per leg
("¥150,000 — Credit-line draw · Today · Planned", from `action.legs[]`), the total, and a thin stacked bar of the legs'
shares (`legs[].share_text` from the server, e.g. "37%"; the bar's widths from `amount_fen`, never a percentage computed in
the browser). The timeline component is kept in the repo for Cash & Funding (frozen page; the overhaul decides) and is not
rendered on Home.

## 2. The worklist tells the truth about the plan
While the company alert is up and the plan waits for the owner's go, "Needs you 0 · All caught up" is wrong in spirit.
The alert row reads as the pending action: eyebrow "FLOW action ready", text "¥405k funding plan available · no approval
needed · waits for your go" (server `alert.pending_text`), its link "Run or compare →". The empty state under the tabs
reads "Nothing else needs you." (server `worklist.needs_you_empty_text`, which says "Nothing needs a decision from you."
only when no alert is up). The count stays 0 (the alert is counted nowhere, by design), because the count is decisions in
the queue; the words carry the rest. FLOW never runs the plan on its own (ADR-0005), so no "will run at" line exists.

## 3. The cash chart is compact on Home
Height 200 px at the fluid width (wider than tall), legend of three entries: "Current forecast", "With FLOW's plan
(conditional on execution)", "Minimum reserve"; the below-minimum segments stay red without a legend entry. Under the chart
two lines, not the inspector strip: "Without the plan −¥105,000 in 30 days" and "With the plan ¥300,000" (the KPI words),
then "Explore full forecast →" to Cash & Funding. Clicking the lowest point (or `?inspect=1`) expands the inspector strip and
the events line in place (the existing component); Esc or a second click collapses it. The 36/60/120 window stays.

## 4. Each level has one job
Headline: what is happening (the alert sentence). KPIs: how serious (Cash today with "+¥100k buffer" as the note from
`headroom_text` + the dictionary word "buffer"; Lowest ahead with `short_note`; Funding plan with `status_text`).
Recommendation: what FLOW will do and what it costs. No level repeats another's sentence.

## 5. Fluid width when the rail is collapsed (the owner's exploration)
The page grid becomes fluid: main column `minmax(0, 1fr)`, worklist `minmax(340px, 30%)`, page max width 1680 px with
32 px gutters, so with the rail collapsed (56 px) the cards fill the freed width; pinned open (200 px) the content reflows
narrower. The chart, the strip and the card stretch; the worklist keeps its minimum. Screenshots at 1280, 1440 and 1680 with
the rail collapsed and pinned go to docs/screenshots/home-v2-fluid-2026-10-13/ for the owner to judge; if the strip's values
spread too far apart at 1680, cap the strip at 1200 px and let the chart alone take the width (record which was chosen).

## Server words (batch 5)
`home_v2.action.consequence_text` (first breach day + lowest point, en/zh); `home_v2.action.legs[].share_text` (the leg's
share of the plan total, the percent word the server already has a helper for); `worklist.alert.pending_text` and
`worklist.needs_you_empty_text` (alert-aware); all words, no new numbers.
