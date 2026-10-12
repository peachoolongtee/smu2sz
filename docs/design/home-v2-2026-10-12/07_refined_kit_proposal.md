# Home V2 refined: one kit proposal for the lead (13 Oct 2026)

Reference: `refined/HomeV2Refined.html` (`?state=default`, `?state=deal`), with `refined/compare.png`. No new font, hue or token.

Layout: nav 200 px; page padding 32 (20 on a phone); sections 32 apart; related items 12 apart; columns main 7fr and worklist `minmax(340px,3fr)`, 40 gap.

Radii come from one family: 16 for the tinted block, 10 for rows and the hover card, 8 for buttons, and a pill for tracks.

## OpenSection
- **Purpose.** Group content by space and type, without a card.
- **Values.** A hairline above (`line`), then 32 px of padding and 32 px of margin.
- **Headings.** The scope label is 13 px 700, uppercase, `ink-3`; it is used for financial scopes only. Other headings are sentence case, Jakarta 800.
- **Kit.** Replaces `Card` as Home's default.
- **Home stops using** the chart and link-row `Card`s.

## MetricStrip
- **Purpose.** Three company values on one line.
- **Values.**
  - Hairlines above, below and between the cells. Cell padding is 20/24.
  - Each label has a 20 px info control.
  - The value is Jakarta 700 at 34 px (30 and 26 on a phone), `tnum`. The lowest is in `bad-fg`, the proposed funding in `brand-600`.
  - One note, 14 px `ink-2`.
  - Buffer: a 2 px `line` track, a `warn-solid` minimum tick and a 10 px `brand-600` dot.
  - The popover uses `--shadow-pop`, radius 14, and fades over `--dur`.
- **Kit.** Replaces the strip's `Card`. It wraps `CashBufferIndicator`.
- **Home stops showing** `with_plan_hint`, `hint` and the assumptions inline. They move behind the info control.

## DecisionHighlight
- **Purpose.** The page's one recommendation.
- **Values.**
  - A `canvas` fill, radius 16, padding 26/28, with no border and no shadow.
  - Eyebrow 13 px in the tone's `-fg`; title Jakarta 800 at 26 px.
  - Three `dl` facts: a 13 px label over a 15 px 700 value.
  - One filled primary: 44 px, `brand-600`, hover `brand-700`. One quiet text button: `brand-700`, hover `brand-50`.
  - While a deal is the focus it collapses to one line with a 2 px `bad-solid` rule, crossfading over `--dur`.
- **Kit.** Replaces `DecisionCard` on Home only. It is still one decision surface per page.
- **Home stops using** `--shadow-decision` and the outlined secondary.

## WorklistRows
- **Purpose.** The worklist as an inbox.
- **Values.**
  - Pane: a 1 px `line` left edge and a 28 px inset.
  - Tabs: text with a 2 px `ink` underline that slides (`--dur`, `--ease-select`). Each count is 13 px; the Needs-you count is `bad-fg` when above zero.
  - Search: a bottom hairline only.
  - Row: padding 14/10, radius 10, hover `canvas`. Subject 15/700, status 13 `ink-2`, consequence 13 `ink-3`.
  - Dividers are inset to the text and hidden beside the selected row.
  - Dot: 8 px, only for CAUTION (`warn-solid`) or CRITICAL (`bad-solid`), always with its severity word.
  - Selected: a `brand-50` fill, no rule, `--dur-fast`.
  - Alert: one line with a 2 px `bad-solid` rule.
  - Empty: "All caught up." and one line.
- **Kit.**
  - It sits beside `SegmentedTabs`: list filters become underlines, and `SegmentedTabs` keeps window and scenario.
  - Rows drop `.row-selected`'s 3 px rule, which `SelectedCard` keeps.
  - `StateWord` draws the severity word.
- **Home stops using** the worklist `Card`, the boxed alert, the pill tabs and the hint lines. Each hint moves to its tab's `title`.

## CashPreview
- **Purpose.** The compact forecast, in the page.
- **Values.**
  - 280 px tall (220 on a phone), full width, no container.
  - Gridlines at ¥0, ¥400k and ¥800k only.
  - Reserve: a 1.25 px `chart-reserve` line with `chart-danger` shade below it.
  - Current books: 2.25 px `chart-base`, mitered steps, never smoothed.
  - Plan: 1.5 px `ink-3`, dashed.
  - Lowest point: a `bad-solid` ring.
  - The selected dot and guide snap to event days.
  - The hover card (radius 10, `--shadow-pop`) shows the amount, the when, the events and, at the lowest point, the shortfall.
  - The window control is `SegmentedTabs`.
- **Kit.** It is #113's compact variant. The hover card replaces the press-to-open inspector.
- **Home stops using** the chart `Card`, the extra gridlines and the cause title.

Under reduced motion only opacity transitions remain.

## Server words missing
1. `greeting_text`: "Good afternoon" is written in the browser.
2. `action.facts[]` as `{label, value}`. Today the server sends one sentence, which the reference splits at " · ". The labels "Estimated cost", "Funding" and "Approval" are its own.
3. The owner's "Review details". The server sends "Compare".
4. Short KPI notes ("¥405k below minimum") and the word "Ready to run".
5. `series[].when` past day 32. The reference uses the dictionary's "in {n} days".
6. Per-path cost and counter text on `/offers/{id}/exposure`. They were taken from the evaluate response.
7. "All caught up." and "View all activity". The reference shows "All deals".
8. The path labels "Three paths", "Room for another payment" and "Foshan's share after".
