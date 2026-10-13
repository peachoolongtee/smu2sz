# Home in the mockup language, round two (owner, 13 Oct 2026, after seeing dev 40ce8e26)

Owner: the visual direction is right. The cards are too big; the middle card's hierarchy and clarity must improve; selecting a
worklist row should transform the cards into that item's view with pie-chart breakdowns, animation and clickable slices, as the
mockup's selected states show, with an always-visible way back to the default page; and Ask FLOW gets an animated entry in the
top header where the owner can ask anything about negotiations and cash flow.

## 1. Card size and the middle card's hierarchy
- Card padding 20 px (was 28), title 18 px, figures 36 px (the three cards) and 40 px for the recommended amount; the row of
  three cards fits in 320 px of height at 1440. Nothing in a card wraps to a third line.
- The middle card, top to bottom: eyebrow "What we recommend" with the Planned pill at the right; the headline sentence 20 px;
  the amount 40 px; ONE muted line under it (the consequence sentence); a facts row in 13 px: Cost to you (bold) · Authority;
  the ActionGroup [Run funding plan] [Compare funding options]; "Funding sources ⌄" and the approval line as one quiet row.
  "Conditional on you running the plan; not counted as cash" leaves the card (it is the pill's meaning; it stays in the
  disclosure's first line).
- Cash available today: figure, the one note, the reserve/buffer bar; nothing else. Outlook: figure, "Without new funding",
  the mini chart, "With plan" and Expand.

## 2. Selection transforms the cards (the mockup's 02–05)
- Click or Enter on a worklist row selects it (`?decision=` / `?invoice=` / `?customer=` as today). Hover and focus only
  highlight the row and reveal a "Select →" affordance; hover never changes the cards (a brush past a row must not move the
  page).
- On selection the three cards crossfade (`--dur`, 200 ms, opacity only under reduced motion) into: the company line
  ("Company cash ¥400k · Minimum reserve ¥300k · Review ¥405k funding plan", the server words), the selected item's card and
  the Deal context panel beside the outlook card. The outlook card switches to the deal's own paths (CashPreview deal mode:
  as asked vs recommended) so the owner sees how the deal affects the company's cash; "Company cash stays separate from
  selected deals" as the footer sentence.
- The selected card's pie chart: a donut of the breakdown rows the server sends (`ask_breakdown` for a deal, `breakdown` for an
  invoice or agreement; the shares are server words), slices draw in over 300 ms on first paint (none under reduced motion);
  a slice or its row is clickable: it highlights both and shows that row's sentence (the server's label and share, nothing
  computed); a second click clears. Never a slice without a server share word.
- The way back is always visible: the × Dismiss on the selected card, "Back to overview" at the top of the Deal context
  panel, and Escape; all three clear the selection and crossfade the overview back. The browser's Back does the same.
- The deal card keeps the Decide/Consequence/Investigate levels under it (compare behind the toggle), restyled to the cards.

## 3. Ask FLOW in the header
- A rounded input in the top header, left of the mode switch, labelled "Ask FLOW": placeholder examples cycle with a quiet
  typewriter animation ("What happens if Foshan pays 30 days late?", "What does the counter cost me?", "When does the
  invoice financing land?"; the dictionary, en and zh; no animation under reduced motion; the cycle pauses on focus).
- Focus widens it (`--dur-fast`); Enter sends the typed question to Ask FLOW with the page's scope chip (the URL contract) and
  opens the Ask FLOW panel with the question already sent; the input clears. The floating pill goes on desktop (the header
  entry replaces it); the phone keeps the bottom-bar "Ask".
- Nothing new on the server: the chat route and the scope contract (Slice B) are used as they are.

## Gates
Focused: the Home batch under mock, the live state matrix, design-system; the full pair at the merge.
