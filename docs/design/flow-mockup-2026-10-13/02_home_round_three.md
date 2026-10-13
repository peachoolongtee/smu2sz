# Home in the mockup language, round three (owner, 13 Oct 2026, after seeing dev 4fdad9ae)

Owner: Home feels buggy; the cards are still a little too big; clicking a deal "brings me into the deals itself instead of the
flow we talked about". The lead reproduced it on the owner's mock build at 1440, 1100, 768 and 375: the row DOES select in place
(the address becomes `/?customer=…&decision=…` and the cards transform), but the page then lands in the MIDDLE of the long deal
card (its comparison table, which looks like the Deals page) at 1100 and 768, and at 375 it stays down at the worklist with the
transformed cards offscreen above. The selection works; the scroll and the card's length make it feel like a navigation.
Owner, on Ask FLOW: "I like that it spells out when does money arrive; have a few more placeholders, an 'Ask FLOW anything'
at the end, and make it the centre."

## 1. A selection always lands at the top of what changed
- On every width, after a row is selected the viewport scrolls so the company line and the selected card's top edge sit at the
  top of the content (under the sticky header), `block: "start"`, smooth unless reduced motion; never "only when the row was far
  below". The same on Enter, on a slice click that changes nothing (no scroll), and on browser Back/Forward between two
  selections. Dismiss / Back to overview / Escape scroll back to the top of the overview (the headline).
- The crossfade must not show a skeleton for seconds: the picture read for a row is prefetched on hover/focus (the "Select →"
  affordance appears, the read starts), so the selection paints at once; a skeleton only after 300 ms, and the card's height is
  reserved so nothing jumps.
- Spec: at 1440, 1100, 820 and 390, after clicking the fifth row, `#home-focus`'s top is within 8 px of the content top and the
  headline is above the fold.

## 2. The deal card opens compact
- Default: the title row (Customer · Decision, the × Dismiss), the three facts, the donut with its rows, "Why first", the
  recommendation (FLOW recommends … with the cost lines), the one commit area ([Review the counter] filled; Compare responses
  and Cash impact as quiet toggles; Open in Deals). That is the whole card at first paint: ≤ 560 px tall at 1440.
- "Financial consequence" (the scenario tabs and the comparison table) and everything under it is CLOSED by default behind the
  Cash impact toggle (`?chart=1` keeps it open, as today); Compare responses stays behind its toggle. The ask sentence and the
  "wants …" sentence that repeat each other: keep the ask sentence only (the server's `ask_text`); the second is a duplicate.
- The invoice and customer cards follow the same rule: facts, donut, the one action; history and evidence behind a toggle.

## 3. Smaller cards, round two's sizes reduced once more
- Card padding 16 px; card title 16 px; the three figures 32 px (the recommended amount 36 px); the row of three cards ≤ 260 px
  tall at 1440; the recommendation card: eyebrow + pill, headline 18 px, amount, ONE line, facts row, ActionGroup, the quiet
  row. The worklist rows 56 px, the table header 12 px uppercase is allowed (it is not a financial qualifier). Upcoming
  movements: 44 px rows. Nothing wraps to a third line at 1280.
- The headline 32 px at ≥ lg (was 40); the subtitle 15 px.

## 4. Ask FLOW in the header: centred, wider, more examples
- The input sits in the centre of the header (between the brand and the right-hand controls, centred on the viewport at ≥ lg),
  width 420 px, 520 px on focus (`--dur-fast`), 36 px tall, the pill radius; on the phone unchanged (the bottom-bar Ask).
- The typewriter cycles six placeholders, each a question the chat answers, en and zh, ending on a resting line that holds until
  focus: "What changed today?", "What needs my attention?", "When does the money arrive?", "What happens if Foshan pays 30 days
  late?", "Who should I chase first?", then "Ask FLOW anything…" (rests; no further cycling until the next page load). zh:
  今天有什么变化？ / 有什么需要我关注的？ / 资金什么时候到账？ / 如果 Foshan 晚付 30 天会怎样？ / 该先催谁？ / 向 FLOW 提问… The
  customer name in the late-payment example is the first worklist customer's short name when one exists (the server's word),
  else the dictionary example. Reduced motion: the resting line only.
- Enter sends under the page's scope as today; the panel's own suggested prompts are unchanged.

## Gates
Focused: the Home batch under mock, `home-v2-states` live, `ask-header` mock + live, design-system; the full pair at the merge.

## 5. "FLOW action ready" is said once (owner, after seeing round two)
The same fact appears three times: the pill beside the headline, the worklist's alert row ("FLOW action ready · ¥405k funding
plan available · no approval needed · waits for your go · Run or compare →") and the recommendation card itself. The card is
the one place: the headline's pill goes; the worklist's alert row goes whenever the recommendation card is on the page (the
card IS the alert, with Run and Compare); the subtitle under the headline keeps the count sentence ("Four deal decisions, one
approval and one collection need you.") and drops "One funding action ready." when the card says it. The worklist's empty
words stay honest ("Nothing else needs you." while the plan waits). The server's `worklist.alert` is still read: it is shown
as the row only when the Home carries NO recommendation card (a state the matrix has: funding NONE with an alert).
