# Home V2 refined 2: an addendum to 07 (13 Oct 2026)

Reference: `refined2/HomeV2Refined2.html` (`?state=default|deal|compare|phone`). No new hue, font or token.

## Findings
1. The recommendation follows eyebrow, headline, line, three facts, then the action group: "Review & run funding" (filled) and "Compare funding options" (outline). The chart's own action is "Compare cash outcomes".
2. The capsules are gone. The mode, window and scenario controls are compact segmented; the worklist uses underline tabs.
3. Deal focus keeps a health band with an outline "Review plan" button above the deal's filled "Review counter".
4. The comparison is a table. Economic impact shows each path's basis words; the asked path takes two lines because the server never adds them. Option B shows its components. "Why" shows authority evidence, not cost. Capacity and concentration sit behind "Financial impact".
5. The scenario control sits under "Payment timing assumption" with one line. It changes the rows, the table and the chart together.
6. "View customer →" is on the customer's line.
7. Worklist rows:
   - Subject, status and consequence only.
   - A quoted differentiator appears only when two subjects collide.
   - Selected: soft fill, a 2 px rule and a focus ring.
   - The counts are neutral, so colour now marks severity only.
8. Header. Left: "Home" and the status sentence. Right: "Updated today" (the read time is in its label), a quiet mode switch and Owner with a glyph.
9. Metric strip: "Cash balance", "Lowest projected cash" with "with plan", and "Funding plan" with "Ready to run". The buffer has an `aria-label`.
11. and 14. The decision preview follows the sketch; `compare` expands it in place.
12. The inspector is a fixed strip under the chart. Below-reserve segments are red. The deal title names the offer, the paths and the assumption.
13. One rhythm, Label → Number → Interpretation → Action.
15. At 1280 the sidebar collapses and the table keeps four columns; it scrolls before it crushes and stacks below 1024 px.

## Kit
- **ActionGroup:**
  - A row with an 8 px gap, aligned left after its content, primary first; 40 px buttons (32 for `sm`).
  - One filled button per page; every other decision level gets an outline button.
  - A text link only for leaving the page without a decision.
  - On a phone the buttons wrap to full width.
- **SegmentedTabs `compact`:** 32 px tall, radius 10, `track` fill, 1 px `line-strong` border. The pill is radius 8, white, bordered, no shadow. Labels 13 px, 600 or 700.
- **ComparisonTable:**
  - A 150 px row head, then one column per path. Rows: Terms, Commercial change, Estimated economic impact with basis, Lowest projected cash, Within limits.
  - 11/14 cell padding on hairline rows.
  - Recommended column: a `brand-50` header with a 2 px `brand-600` top rule, plus a light tint and `info-line` sides.
  - Minimum 600 px, then it scrolls with a sticky first column. Below 1024 px it stacks.
- **Inspector strip:** four cells (When, Projected, Plan or Option A, and Shortfall or Minimum) plus an events line.
- **Decision preview:** verdict, title (the row's words), customer line, the buyer's words, two impact facts, actions, Financial consequence.

## Server words missing (field: state)
- `authority_reason_text`: deal and compare. Composed from the picture's terms meanwhile.
- `recommended_reason_text`: compare.
- `differentiator_text`: default. EX02 and EX03 are identical; the buyer's spans stand in.
- `action.facts[]`: default. The reference splits `action.text`.
- `chart.scenario_title_text`: deal and compare.
- `kpis.lowest_ahead.short_note`, `kpis.funding.status_text`: default.
- `cost_parts[]` with words for "once" and "over 12 months": compare.
- `stress.paths[*].breach_days_text`: compare (late).
- `capacity_text` reworded: compare.
- `series[].when` past day 32: all states.

## Declined
- Greeting: per the lead.
- "Counter recommended · Reply needed": the server says "Counter ready".
- "Why prioritised?" in the focus: the deal read has no such field.
- `chart.lowest.cause`: shown only as "On that day, …", never as the shortfall's cause.
