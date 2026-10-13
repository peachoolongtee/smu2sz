# Home V2: the recommendation card and the navigation rail (owner, 13 Oct 2026, after seeing dev)

Owner's ask: the card should read "what we recommend", the cost to you bigger with an accent, the funding shown as a chart
with details on hover, "no approval needed" smaller; the navigation collapsed by default and shown on hover or approach.

## The card (DecisionHighlight on Home only)
- **Eyebrow** "What we recommend" (zh 我们的建议): a dictionary label; "we" is FLOW speaking, so the one-product-voice rule
  holds (DESIGN.md's banned list unchanged; "FLOW recommends" stays elsewhere until the overhaul decides the voice page by page).
- **Headline** unchanged (the server's action title) and its one line under it.
- **Cost to you** becomes the hero fact: label 13 px "Cost to you", the figure 28 px tabular in ink with a 2 px brand rule
  under it, the basis word beside it in the quiet ink ("one-off" / the server's cost basis). It is the second-largest figure on
  the page after the metric strip, never larger than the cash balance: the cost is important, the position is more important.
- **Funding as a timeline, not a bar.** The owner's question is "when does the money land", so the chart is a thin
  horizontal timeline from today to the plan's last repayment: one marker per leg, sized by amount, in the planned tone with
  the dashed-ring glyph while planned (solid once arranged, the received check once landed: the states from `state_of`),
  the source and amount under each marker, the total at the right end. Hover or keyboard focus on a marker opens a small card:
  source, amount, lands when, this leg's cost, repaid when, the authority word. Phone: the legs as stacked rows with a tap
  disclosure, no hover. Reduced motion: no slide, opacity only. Nothing decorative: no area fill, no gradient, no animation
  of the line. Every word from the server's `action.legs[]` (batch 4); until it lands the funding fact stays as text.
- **Approval** shrinks to one 13 px line under the action group with the check glyph ("No approval needed" / the approval
  sentence in the warn tone when one is needed), not a fact column.
- The action group stays: [Run funding plan] filled, [Compare funding options] outline.

## The navigation rail (app shell, desktop and laptop only)
- Collapsed by default to a 56 px icon rail with the page icons and an accessible name each; tooltips on hover.
- Expands to 200 px as an OVERLAY (the content does not reflow) when the pointer hovers the rail or enters a 12 px hot strip
  at the window's left edge, or when keyboard focus is inside it; collapses 150 ms after the pointer leaves or focus moves out,
  so a brush past the edge does not flicker it.
- The foot toggle becomes "Keep open" (a pin), persisted in the existing `tl-sidebar` store and applied before first paint as
  today; pinned = the old open layout with the content reflowed.
- `--dur-fast` / `--ease-ui`; reduced motion: instant. Phone and tablet keep the bottom bar; nothing changes there.
- Acceptance: the five-second test still holds with the rail collapsed (the page title and the status sentence are the first
  things read); keyboard users reach every destination without the pointer; the rail never covers a primary button.

## Server words (batch 4)
`home_v2.action.legs[]`: {label (source), amount_display, lands_when, cost_display | null, repaid_when | null, state,
state_text, authority_text} from the plan's actions the hybrid already reads (operation kind, amount_fen, lands_when, the
facility name, the lot's repayment day and the plan's per-action cost where the engine has it; null where it has not).
