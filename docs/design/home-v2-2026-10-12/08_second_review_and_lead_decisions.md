# Home V2 refined reference: the owner's second review (13 Oct 2026) and the lead's decisions

The owner's verdict on refined/HomeV2Refined.html: much cleaner; not final. Keep about 80% and redesign 20% deliberately.
The remaining problems are placement, relationships, control hierarchy and how financial decisions are compared, not clutter.
Principle: **every component appears exactly where the user expects it, next to the information or action it relates to.**

## The owner's findings (ordered as given)
1. **Compare is floating.** The secondary sits centred under the primary with no relationship and an ambiguous name. Put the
   two actions in one horizontal group; the secondary an outline button or a text link aligned with the primary; name the
   comparison: "Compare funding options" with the funding action, "Compare cash outcomes" with the chart, never one generic
   "Compare". Make the recommendation less boxy: eyebrow, headline, one explanatory line, a three-column facts row
   (Estimated cost · Funding timing · Authority), then the action group.
2. **The pills look out of place.** Three capsule controls doing different jobs (Business/Demo, Expected/30 days late,
   36/60/120). Control categories: a compact mode switch in the header; underline tabs for the worklist; a compact
   segmented control (radius 10–12, subtle grey, white selected, thin border, 32–36 px, no shadow) for scenario and window;
   the scenario control placed directly above the analysis it changes, under a heading that says what it is ("Payment timing
   assumption") and one line saying what it changes.
3. **Hierarchy in deal focus.** The company cash action shrinks to a text link while the deal's action gets the big button;
   the dominant action changes with navigation, not with financial priority. Two persistent levels: business health (always
   near the top with a properly sized action) and the selected task (changes with selection). Revisit the one-filled-primary
   rule rather than let it force an awkward layout.
4. **The three-path comparison is the weakest part.** (a) Costs are not comparable (a one-off transaction cost, a net
   economic cost after a price offset, a 12-month concession value) under one label "Cost"; separate immediate cost, gross
   financing cost, commercial offsets and net impact over a stated horizon, say "not applicable" where it is. (b) Why Option
   A (¥3,028) over Option B (¥0)? The reason is not visible: one line "Why Option A?" under the recommendation, only if the
   comparison supports it; otherwise reassess. (c) Too many low-value metrics (100% concentration on all three; "room for
   another payment" is unclear language); move capacity and concentration behind "Financial impact". (d) The selected column
   as a full-height blue block is heavy: a tinted header, a small "Recommended" label, a thin accent. Prefer a compact
   comparison TABLE (Terms · Commercial change · Estimated economic impact · Lowest projected cash · Within limits) the owner
   reads in ten seconds, then "Why FLOW recommends Option A →", "Detailed economics →", "Cash impact →".
5. **The payment-scenario selector** beside "Three paths" reads as switching offers and does not say which figures change.
   Move it under its own heading beside the analysis it changes; update every affected figure together.
6. **Customer profile floats** under the deal's primary. Put "View customer →" beside the customer's name; the deal action
   stands alone.
7. **Worklist.** (a) Two rows read identically ("Foshan · Early-payment discount"): distinguish by invoice, scope or date, or
   it is a data problem. (b) Strengthen the selected state (soft fill, 2–3 px left indicator, focus ring) and make the focus
   title match the row. (c) Rows too verbose: subject, "Counter recommended · Reply needed", one consequence line; "Why
   prioritised?" lives in the focus, not the row. (d) Counts must mean distinct tasks / distinct pending outcomes / unique
   relationships. (e) Colour must not carry both financial severity and action ownership.
8. **Header.** Too many ideas in one line. Left: context (greeting, the status sentence). Right: the mode switch, the
   account control with a recognisable glyph and label. Fold "Action needed" into the status sentence; "Read today" →
   "Updated today" (and distinguish read time from source freshness if they differ); the mode switch quieter.
9. **Metric strip** copy too dense: "Cash balance / ¥400,000 / ¥100k above minimum", "Lowest projected cash / −¥105,000 /
   ¥405k shortfall in 30 days", "Funding plan / ¥405,000 / Ready to run · Two funding sources"; assumptions on click. "Cash
   available" may imply free to spend: prefer "Cash balance". The buffer line needs an accessible description.
10. **Recommendation card oversized.** Compact: "FLOW recommends / Secure ¥405k before payroll. / ¥3,114 estimated cost ·
    Funds in two stages · Within your limits / [Review & run funding] [Compare options]". The button must say what it does:
    "Review & run" only if a confirmation step follows.
11. **Deal focus reproduces the whole Deals page.** Two levels: a decision preview (subject, verdict, the buyer's ask in one
    line, the original's cost, the recommended option's cost, [Review counter] [Compare alternatives], a compact financial
    consequence) and the detailed comparison only on request (expand, or go to Deals). Home makes the decision discoverable;
    Deals makes it fully reviewable.
12. **Chart.** The lowest-point tooltip covers the line: a fixed strip under the chart or a tooltip anchored away; it must
    not imply one outflow caused the whole shortfall. Below-reserve segments of the current path emphasised in red; the plan
    line visibly distinct with a legend "conditional on execution". In deal focus the chart's title must say which offer and
    payment assumption it shows ("Company cash, if Foshan's original terms are accepted" vs "Current books").
13. **Four visual systems** (open strips, grey filled card, blue filled column, outlined capsules) should feel related: see
    the component language table in the owner's text. Fewer uppercase labels; secondary text more readable; one rhythm
    Label → Number → Interpretation → Action.
14. The owner's sketch of the selected-deal state: business-health band at the top with "Review plan →"; the deal preview on
    the left ("Counter recommended", the ask's cost, the recommendation's cost, [Review counter] [Compare responses]), a
    "Financial consequence" block (original request: reserve breached 15 days; recommended counter: reserve preserved*),
    "Explore comparison →"; the worklist on the right.
15. Flows to test interactively (select customer, select deal A then B, compare funding vs compare responses, scenario
    change, review counter, run funding, return to Home, tab counts, a new deal arriving, pending vs settled, current vs
    hypothetical); laptop widths; the comparison as a scrollable table or stacked on narrow screens.
16. Priority: P0 verification: comparable costs; why Option A over Option B. P1: the demoted cash action; the floating
    Compare; the scenario selector; the long deal focus; duplicate rows; the floating profile link; "room for another
    payment"; priority explanation; chart scope label. P2: the pills; comparison text; the blue column; metric copy; the
    card size; repeated status; verbose rows; the tooltip. P3: geometry tokens.
17. Design-system evolution: action groups; control categories; compact analysis components.

## Lead's decisions (binding for the second reference and the build)
- **Greeting:** none. The browser computes no time-of-day word (INVARIANT 13; the Demo runs on a simulated day). The
  header's left is the page name "Home" small and the status sentence from the server as the headline; "Action needed" folds
  into it; the freshness word becomes "Updated today" (dictionary) and the read time stays in the accessible text.
- **One filled primary stays, the rule is refined:** one FILLED button per page, but the other level keeps a real button.
  Default: the company action is filled ("Review & run funding", because the existing control opens a confirmation step),
  its secondary "Compare funding options" an outline button in the same group. Deal focus: the deal's "Review counter" is
  filled; the business-health band keeps "Review plan" as an OUTLINE button, never a text link. This is the DecisionHighlight
  + a new ActionGroup; the one-decision-surface rule becomes "one filled primary per page; every decision level has a
  button".
- **Controls:** mode switch (header, compact, quiet); underline tabs (worklist); compact segmented (scenario, window) at
  radius 10, 32 px, thin border; the big capsule retires from Home. SegmentedTabs gains a `compact` variant for this (one
  component, two sizes), nothing else changes in the kit.
- **Deal focus = decision preview**, per the owner's sketch, with the detailed comparison behind "Compare responses" as an
  expandable state on Home (the fourth reference state), the full workspace still at /deals.
- **Comparison table** (Terms · Commercial change · Estimated economic impact with its scope word · Lowest projected cash ·
  Within limits) replaces the three prose columns; the recommended column has a tinted header and a thin accent; "Why
  Option A?" is one server sentence (`recommendation_reason`; the verifier checks whether the engine has it). Capacity and
  concentration go behind "Financial impact".
- **Words that change are server or dictionary words:** "Cash balance" (eyebrow), "Updated today", "Compare funding options",
  "Compare cash outcomes", "Compare responses", "Payment timing assumption", "Review & run funding", "Review counter", "View
  customer", "Financial consequence", "Explore comparison" are dictionary labels (no money or date inside); the cost scope
  words ("one-off", "net over 12 months", "not applicable"), the row differentiator (invoice or scope), the reason line and the
  chart's scenario title are SERVER words and go on the server list.
- **Scenario control** sits under "Payment timing assumption" directly above the consequence block it changes; one line says
  what changes ("Changes the figures below and the cash chart").
- **Chart:** the lowest-point inspector is a fixed strip under the chart (not a floating card); below-reserve segments in
  red; the plan legend "If FLOW's plan runs · conditional on execution"; in deal focus the title names the offer and the
  assumption from the server's scope words.
- **Worklist rows:** subject · status line · one consequence line; the reason in the focus; the differentiator from the
  server; selected = soft fill + 2 px left indicator + focus ring.
- The two P0 questions go to a verifier against the engine's words before the build; the reference shows the table with
  the scope words the engine actually has, and "not applicable" where it does not.
