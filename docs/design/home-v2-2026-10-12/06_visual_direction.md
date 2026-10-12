# Home V2 visual direction (owner, 13 Oct 2026): a focused visual refinement, not an IA redesign

The owner's direction, verbatim in substance. Functionality, the four states, the worklist and the customer/deal interaction
model stay. The visual styling is NOT frozen: redesign the presentation around open sections, a unified metric strip, a
lightweight featured action and a clean inbox-style worklist. Aggressively reduce nested cards, thick outlines and repeated
explanations. Improve typography, spacing, hierarchy, chart styling and consistency of radii. No decorative charts or
animations to compensate for weak structure. One polished desktop reference and one mobile reference, compared against the
current implementation before any shared component changes. All financial semantics, authority rules, API contracts and
interactions unchanged. Shared design-system changes go through the lead as one coordinated proposal.

## What makes the current screen clunky
Too many containers (KPI box, action box, chart box, worklist box, alert box); borders on nearly every section; weak type
hierarchy (most text small, numbers and conclusions do not stand out); too much explanatory text (each KPI a miniature
report); the main column squeezed beside the worklist; the worklist overloaded (title, alert, tabs, search, explanation,
empty state, link: scaffolding around a panel with no human decision in it); the cash danger explained in several places;
almost entirely white, grey and blue boxes.

## Direction
Between Mercury, Linear, Ramp and the Sypher reference: a calm, intelligent financial workspace where conclusions feel
effortless and the complexity is available when needed. Open layout, fewer borders, stronger typography, selected accents.

Target layout (desktop):
```
 Good afternoon / Your cash reserve is at risk in 12 days.         (greeting + one-line status, from the server read)
 ────────────────────────────────────────────────────
 CASH AVAILABLE        LOWEST AHEAD          FUNDING PLAN           (one metric strip, hairline separators, no cards)
 ¥400,000              −¥105,000             ¥405,000
 ¥100k above minimum   ¥405k below minimum   Ready to run
 ────────────────────────────────────────────────────
 RECOMMENDED ACTION                              [ Run plan → ]     (one featured action: heading, three facts, one primary,
 Secure ¥405,000 before payroll in 12 days.                          a quiet "Review details"; soft tint or a thin blue rule,
 Estimated cost ¥3,114 · No additional approval needed.              never a thick coloured border)
 ────────────────────────────────────────────────────
 CASH FORECAST                       36 days  60 days  120 days     (chart in the page, divider above, wider, fewer gridlines,
                                                                     hover reveals amount, date and business event; steps kept,
                                                                     never smoothed; subtle shade below the reserve)
                                         YOUR WORKLIST     3 items  (inbox: tabs as an underline, search, rows with faint
                                         Needs you  Waiting  Customers                dividers, dot only when status needs it,
                                         ⌕ Search customers or deals                  selected row = soft background; empty:
                                         ● Foshan Home Retail                         "All caught up." + one line; the company
                                           Payment terms · Counter recommended        alert visible above or beside the queue
                                           Reply required                             but never a second funding-action card)
                                         View all activity →
```

## The metric strip
Three values aligned horizontally with very subtle vertical separators; no miniature paragraphs, no multi-line conditional
explanation, no badge; numbers about 30–36 px, tabular numerals; a thin reserve indicator for cash; the red value alone says
danger (no red-tinted container); proposed funding in blue, not green (money not yet arrived); assumptions and financing
detail behind a small information control or a click on the metric. No decorative charts behind the numbers.

## The featured action
"FLOW recommends securing ¥405,000" / "Protect your ¥300k reserve before payroll in 12 days." / Estimated cost · Funding ·
Approval as three labelled facts / [Run funding plan →] and a quiet "Review details". The heading dominates. The worklist
references the same alert; it does not repeat the action.

## The chart
Wider; no heavy container; fewer gridlines (the reserve stays visible); cleaner strokes, deliberate colours, a clear
selected-point indicator; contextual hover (amount, date, event) instead of technical labels; subtle shade below the reserve;
steps preserved.

## Layout system
Left nav 190–210 px; main workspace about 70% of the remaining width, worklist about 30% with a sensible minimum; page
padding 28–36 px; 28–36 px between major sections; 8–16 px between related elements; radius 12–16 px where a card is
needed; borders only where they clarify grouping; shadows only for overlays; one radius family, not several.

## Typography
Refine the existing pairing (no third font): larger, more confident financial values; smaller, restrained section labels;
slightly more readable supporting text; sentence case for most headings, uppercase reserved for a few financial labels.

## Motion (150–250 ms; none decorative)
Selected-row highlight transitions; tab underline or pill moves; opening a customer crossfades the main context; opening a
deal changes the recommendation while global cash stays fixed; scenario switch crossfades the paths over ~300 ms; financing
details expand without layout jumps; funding state changes (planned → submitted → settled) only after the server confirms.
No animated gradients, glowing borders, bouncing buttons, continuous background motion.

## Kit additions (through the lead, one proposal; #112 stays)
OpenSection (content grouped by whitespace and typography, no enclosing card); MetricStrip (values grouped by subtle
dividers); Worklist rows (compact, not nested cards); DecisionHighlight (one prominent recommendation without a heavy box);
CashPreview (the chart integrated in the page).

## Priority
P1 metric strip; P1 inbox worklist; P1 remove outer containers; P1 type hierarchy and whitespace; P1 concise featured action;
P2 chart elegance and space; P2 radii, shadows, dividers; P2 restrained transitions; P3 subtle brand details. Not: gradients,
glassmorphism, animation libraries.
