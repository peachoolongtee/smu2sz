# Home V2: information architecture, component contracts, what is removed (12 Oct 2026, ticket #117)

Status: proposal for the owner's review. Nothing is built. The four boards are beside this file (HomeV2Default, HomeV2Customer,
HomeV2Critical, HomeV2Healthy; also on the canvas, version 19). Build starts only after the connected-pages integration
(int/connected) is in dev and stable, behind a server feature flag, on its own integration branch.

## 1. Information architecture

Three regions, in every state, in this order:

1. **Your company** (the top strip): three KPIs, company-wide, never customer-specific and never hypothetical:
   Cash today; Lowest projected cash (with the plan when one exists, with its day and its distance from the minimum);
   Incoming (the next receipts and arranged financing, each with its basis word: owed / scheduled / arranged / planned).
   This strip stays visible and unchanged when a customer is selected.
2. **The workspace** (the main column):
   - Default mode: one next action (the decision card: title, one sentence, one filled primary, one secondary; or the quiet
     "nothing needs you" variant with no filled button), then the compact cash forecast (the plan line, the reserve, the lowest
     point marked, the window word, the legend "If you run FLOW's plan" / "With FLOW's plan" / "If you do nothing"), then one
     line of three links (Deals · Receivables · Activity) with their counts.
   - Customer mode (a customer selected in the panel; URL `?customer=`): the customer header with "‹ Your company", four
     relationship facts (contribution a year with its provenance word; owes you; financing linked with its state; share of what
     you are owed), the current decision card (verdict, the ask in one sentence, FLOW's recommendation, the consequence row:
     cost if accepted, lowest cash, spare capacity, share after; the one filled primary "Review and send the counter" opening the
     existing response flow; "Customer profile" secondary), the compact forecast with the pending path dashed and labelled
     "if Foshan accepts Option A (hypothetical)", and one hypothetical line (the 30-day-late stress) tagged HYPOTHETICAL with
     "Explore in Cash ›".
3. **Customers** (the right panel, 312 px): a search box, one row per customer (name, one status line, a tone dot), "All
   customers ›". Selecting a row switches the workspace to customer mode without navigation; the selection lives in the URL.

Phone (390): the panel becomes a sheet opened from a "Customers" button under the KPI strip; the KPIs stack as three rows; the
action precedes the forecast; the primary is in the first viewport.

States: Action needed (amber dot; a filled primary), Reserve unsafe / critical (red dot; the action card carries a red rule and a
deadline; the forecast shades the gap), Covered / healthy (green dot; no filled primary anywhere on the page).

## 2. Component contracts (reads; nothing computed in the browser)

| Component | Read | Fields (all existing or already specified) |
| --- | --- | --- |
| KPI strip | `GET /home` | `cash.facts[]` (today, lowest, arriving) with `value_short`, `note`, `tone`; the basis words from #116 (`basis_text` on the incoming receipts) |
| Action card | `GET /home` | `attention.items[primary_key]` (eyebrow, title, facts, primary, secondary), `funding_line.text`, `next_action` for the run-the-plan control (`usePlanRun`, the same ids as today) |
| Compact forecast | `GET /home` | `cash.plan_series` or `series`, `cash.counterfactual_series` (not drawn by default), `cash.plan_line_label` (#111), `cash.lowest_*`, `cash.picture_days`; `cash.pending` (#116) in customer mode |
| Links line | `GET /home` | `deals_card`, `receivables_card`, `changes_card` (their one-line summaries and hrefs only) |
| Customer panel | NEW `GET /customers?lang=` (compose, server-side: name, status line, tone, href) | status line from the open offer / overdue / promise state the Customer overview already derives |
| Customer header + facts | `GET /customers/{id}/overview` | `figures[4]`, `decision`, `actions`, `economics_note`, `context.back` |
| Decision consequence row | `GET /offers/{id}/exposure` | per-path `lowest_display`, `share_after_text`, `capacity.after/spare`, the offer's cost display |
| Hypothetical line | `GET /buyers/{id}/exposure` | `stress.now.text`, the Cash deep link with `from=home` |

One new read only (`GET /customers`, a list). Everything else is the Home hybrid read, the Customer overview, the exposure reads and
#116's basis words. No calculation is duplicated.

## 3. Removed from the default Home (present today, absent in V2)

- The full event rail (numbered rows, hover preview, cursor following the pointer) and its inspector panel with the
  effect table: they live in Cash & Funding as the full Financial Timeline (#113).
- The counterfactual line drawn by default (available on Cash; on Home only its label in the forecast heading).
- The window switch (36 / 60 / 120) as buttons: a quiet word with the others muted; the switch itself stays on Cash.
- The scenario switch (expected / late): on Cash; on Home only the HYPOTHETICAL line in customer mode.
- The funding line with its two costs and the authority sentence under the attention card: one sentence in the action card
  ("Cost ¥3,113.93 · no approval needed").
- The three cards row (Your deals, Receivables, Recent changes) and the "Also on your radar" / "What changed" folds: one line
  of three links with counts.
- The conditional headline and its note with the assumptions disclosure: replaced by the KPI strip and the action title; the
  assumptions move behind the forecast's "Full timeline" link on Cash.
- The remaining-task and waiting-on blocks: folded into the one action (the queue beyond the primary is reachable via Deals).
- Raised, frosted surfaces and the large shadow: standard cards with hairlines; one decision card with a soft shadow.

Kept: the status dot and word with "Read today"; the run-the-plan control and its test ids; the Business / Demo mode and zh.

## 4. Reconciliation with #112, #113, #114

- #112 (design system) ships first: V2 is the first consumer of the tokens, the three card types and the type scale; no
  V2-only styles.
- #113 (Financial Timeline): the compact forecast IS the timeline component in its compact variant (same SVG, same data, no
  rail); the full variant stays on Cash. No second chart.
- #114 (polish) runs over V2 and the four pages together.

## 5. Waves (after int/connected is in dev; each wave reviewed and gated; the flag `FEATURE_HOME_V2`, server-side, default off)

1. Contracts: `GET /customers`; the Home read's `home_v2` capability; mocks recorded with the flag on; types optional.
2. The default mode: KPI strip, action card (the existing run-the-plan control), compact forecast, links line; existing Home
   untouched when the flag is off; desktop and phone specs; the whole live project.
3. Customer mode: the panel, the URL selection, the header, facts, decision card, consequence row, the pending dashed path,
   the hypothetical line; navigation-context tests with Deals, Receivables, Customer and Cash.
4. States: critical and healthy variants; action-state validation (plan ready / waiting / approved / executed); scenario
   consistency (the same strings as Cash and the deal for the same buyer).
5. Swap: the flag on by default once the full existing gate, the screenshot set in en and zh, and the owner's walkthrough pass.
