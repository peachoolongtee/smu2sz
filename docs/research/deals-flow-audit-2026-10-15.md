# Deals page UX audit (first-time owner walk), 15 Oct 2026

Build: `origin/feat/slice-b-r3-web` + `origin/feat/slice-b-r3-api` merged uncommitted, live API on :8371 (memory DB, demo mode), web on :3371.
Screenshots: kept outside the repo (the auditor's scratch folder on the second machine); file names are cited as S/<name>.
Use the `*-fold.png` and the plain `*.png` files whose name has no `-full`. The `-full` and full-page captures of the deal pane come out dimmed or with the header drawn in the wrong place. That is how Playwright captures a full page here; the app does not do it, so it is not a finding.

## 1. Verdict

The page shows one deal three to five times over, each time in different words. The deal itself goes by three names: the row says "60-day terms on future invoices and 2 more terms", the pane title says "Counter instead of accepting as asked" (and becomes "Offer from Foshan Home Retail Co." once sent), and the breadcrumb says "Payment terms" or "Early-payment discount". The terms table appears on Overview, again in Compare, and a third time behind "View terms by scope". The outcome table and the headroom plot appear on both Compare and Cash impact. Who may send is stated on Overview, in Compare's outcome table and again under "Who decides, and why".

The owner never gets a plain answer to "what should I do and why". On Overview the recommendation sits under a long ask sentence and a mandate sentence. Where FLOW recommends a reply that costs more than the request (busy Foshan: ¥6,489 against ¥6,300), the only explanation is one footnote. On Cash impact, the "Business consequences" panel shows −¥105k cash, which contradicts the table above it (¥165k / ¥300k).

There are real bugs:
- Sending the server's own Option B, as asked, ends in "No deal". The funding still runs, in amounts that differ from the review.
- The agreed record says "Net economic cost ¥0.00 · Invoice financing" for Option A, which cost ¥3,027.77 and was funded from the credit line.
- One agreed deal shows as two rows, with two purple connectors.
- The tab and its content can disagree: Compare is highlighted while the accept review shows.
- The Agreements section says "Agreed", "Agreement expired 27 days ago" and "Early payment did not arrive" about a deal on which half the early payment did arrive. Above it, the page still says "Nothing needs you today."

Getting back works only through Close, and Close discards the selection. Customers and Activity offer no link into a deal at all.

## 2. The owner's five complaints

**1. The 72 px rail with "Show queue": confirmed.** S/A-d04-cash-fold.png, S/B-d04-foshan-compare-fold.png
- When Compare or Cash impact opens, the queue folds into `QueueRail` (`components/deals/flow/queue-rail.tsx`, triggered from `deals-page.tsx` around line 75).
- The rail is a card holding the underlined, two-line, wrapped text "Show / queue" and one letter per deal.
- On the busy books the rail reads Z, D, F, F, F, F. Four identical "F" tiles cannot be told apart without hovering for the `title`.
- "Show queue" is the only visible way back to the list that keeps the deal. Escape also brings the queue back, but nothing tells the owner that.
- There is no Back control. The pane's "Back to deal" link (at the foot of Compare) goes to Overview, not to the list.
- The rail collapses on a tab click the owner did not intend as "hide my list". The layout jumps sideways each time the owner moves between Overview and Compare.
- On a phone the rail does not exist. There, the only way to the list is Close or scrolling (S/A-m03-compare-fold.png).

**2. The charts do not make sense: confirmed, for every chart.**
- *"As they asked" as a label.* It is the column header, the chip, the plot row and the chart legend. On the chart it is a line the owner cannot act on: the buyer's request is not something the owner can "choose". It also appears as "As asked" in "What caused the difference?" and in "Lowest, as asked". These are two spellings of one idea (S/A-d04-cash.txt, lines 95 and 104).
- *Headroom plot on Compare* (`components/deals/flow/outcomes.tsx`, title key `deals.plot.title` "Headroom against the reserve"; S/A-d04-cash-fold.png, bottom):
  - The plot has no axis and no scale. It shows one dot per row on a bare track and a dashed vertical reserve line.
  - The options' dots sit exactly on the reserve line, which reads as "touching the danger line", not as "safe".
  - The figures (¥165k / ¥300k / ¥300k, with their "in N days") repeat the "Lowest cash" and "When" rows directly above. The plot adds no information.
  - Busy Foshan: the as-asked dot for ¥9k (S/B-d04-foshan-compare.txt) and Zhuhai's −¥405k sit on the same unscaled track.
- *Cash chart on Cash impact* (`components/deals/flow/cash-tab.tsx`; S/A-d04d-cash-inspector.png, S/A-d04-cash.png):
  - **Lines.** By default "As they asked" and Option A are drawn, and Option B is off although it is a live option. The two drawn lines overlap almost exactly for the first 47 days (dark grey on lavender), so the owner sees one line.
  - **Y axis.** The ticks are ¥0, ¥400k and ¥1,000k. ¥400k is today's cash, not a round step, so the spacing is uneven.
  - **Timing switch.** The switch ("Expected payments / Foshan 30 days late") is labelled "Payment timing assumption". Further down, Business consequences has another switch, "Buyer pays 30 days late". That makes two different "30 days late" controls on one page (Playwright found two tabs matching /30 days late/).
  - **Chips.** Clicking the Option A chip left only "As they asked" drawn (`lines=asked`). The chips read as a filter but behave as toggles, with a ✓ after the name.
- *Inspector* ("On this day", S/A-d04d-cash-inspector.png, S/A-m04d-cash-inspector.png):
  - The "When" field shows a sentence in display type ("Lowest, Option A and Option B" / "Lowest, as asked") where a date belongs. It names Option B even when Option B is not drawn.
  - The difference row "Option A against As they asked +¥422,012.23" on day 60 is followed by a disclaimer that the number "includes every assumption … not negotiation alone". In effect the owner is told not to use it.
  - "What caused the difference?" lists cash movements such as "Receipt from Foshan ¥420k in 47 days" under Option A only. The owner cannot tell why that receipt is missing under "As asked".
  - "Each option's lowest point" is the third display of the same two lowest points.
- *Business consequences* (same tab, below the chart):
  - It shows "Lowest cash −¥105k in 30 days, Below your minimum for 20 days … covers the ¥405,000.00 shortfall".
  - That contradicts the outcome table at the top of the same tab (lowest ¥165k as asked, ¥300k with a reply). It is the company with no reply at all ("Your books as they stand"), but nothing on the panel says that it is not about the options.

**3. Breadcrumb at the top of each tab: confirmed, and it does harm as well as repeating.** S/A-d04-cash-fold.png, S/B-d04-foshan-compare-fold.png, S/C-d04-back-after-close.png
- "Foshan / Payment terms / Compare responses" is built by `crumbs()` in `components/deals/flow/decision-pane.tsx` (lines 403–416, used at 718 and 734).
- Each part is already on screen 150 px higher: the customer name is under the title, and the tab is highlighted.
- The middle crumb ("Payment terms", or "Early-payment discount" on busy Foshan) is a third name for the deal. The title says "Counter instead of accepting as asked" or "Offer from Foshan Home Retail Co.", and the row says "60-day terms on future invoices and 2 more terms".
- The first crumb is a link to the customer, a way out of Deals, at the very top of the analysis.

**4. No Option B on the busy books: confirmed, and not explained.** S/B-d04-foshan-compare-fold.png, S/B-d03-foshan.txt
- Busy Foshan ("Early pay at 1.5%") shows two columns, As they asked and Option A, with no word about a second reply.
- On the golden books the owner learned that there are an A and a B, and the Overview there names B ("Option B needs your approval for 55-day terms"). Here nothing says that FLOW withheld B or why.
- The same page also says "I can't safely evaluate this yet. The buyer refers to an earlier arrangement that is not in your books. Clarify". Yet it offers "FLOW's reply · Option A" and a filled "Review the counter".
- Option A costs more than the request (¥6,489.20 against ¥6,300.00, both "one-off"), and the only explanation is the footnote "it does not rank replies by cost".
- To an owner, "A" with no "B" looks like a missing column.

**5. Purple line from the selected row: confirmed.** S/A-d02-overview-fold.png (x≈450–490, y≈374), S/A-dA08-after-send.png (two lines)
- The source is `components/deals/flow/queue-table.tsx` lines 103–104: a `span` with `data-testid="row-connector"`, `h-px w-11 bg-f-purple`, shown from xl up.
- It is 1 px, starts at the row's round arrow button and stops in the gap before the pane. It connects to nothing on the pane, which has no matching purple edge.
- After an agreement the same deal has two rows ("Payment promised" and "Agreed"). Both are selected, so two stray lines appear.
- The selected row is already tinted lavender and its chevron fills black, so the line adds nothing.

## 3. Other findings (most severe first within each screen)

### Send and outcome (golden, Option B)
- **Broken.** The owner picks Option B (Compare → "Review Option B" → "Review the counter" → "Send Option B to Foshan").
  - The result is "No deal: the buyer did not accept … The buyer refused every counter", though only one counter was sent.
  - The pane still says "Waiting for Invoice financing (onboarded platform) to land the funds in 3 days. Received ¥150,000.00 today. ¥255,000.00 arrives in 3 days."
  - So the funding ran for a deal that did not happen. Its split (¥150k credit line + ¥255k) also differs from the review the owner approved: "Draws ¥90,000.00 … Requests ¥315,000.00 of invoice financing".
  - The review itself says, under "What does not happen yet", that "no payment and no financing settles because the counter is sent", one line after "What happens immediately: Draws ¥90,000.00".
  - The deal then leaves the queue ("Your deals 0 · Nothing is open") while still open in the pane. Once closed, it cannot be found again from Deals.
  - Evidence: S/A-d08-after-send.png, S/A-d07-review.txt. The simulated buyer comes from `send-block.tsx` line 80, which defaults to "cooperative".
- **Confusing.** The review for B is headed "Needs your approval", but the button is just "Send Option B to Foshan". The owner cannot tell whether pressing it is the approval or a request for one.

### Agreed deal (golden, Option A)
- **Broken.** In the queue, one deal becomes two rows: "Foshan · Payment promised" under "Awaiting payment (1)", and "Foshan · 60-day terms on future invoices and 2 more terms / Agreed". The counts say "Your deals 1 · All 1" with "2 shown". S/A-dA08-after-send.png.
- **Broken.** The agreed row still names the buyer's ask ("60-day terms … and 2 more terms") although the agreement was 45 days and no rebate. It reads as if 60 days were agreed.
- **Broken.** The tracker (`/decisions/deal:…`), under "What was sent", says "You sent Option A … Net economic cost ¥0.00 · Invoice financing (onboarded platform)". Option A's quoted cost was ¥3,027.77 and its funding was "¥149,986.20 drawn on the Bank credit line" (shown lower on the same page). S/A-dA10-tracker.txt.
- **Broken.** On day 0, right after agreeing, the Overview says "The buyer has kept zero of two promises on this deal." Neither promise was due yet. S/A-dA08-after-send.txt.
- **Confusing.**
  - "Actual so far ¥841.57 … Nothing has been paid under the agreement yet", next to "the charge itself is not yet booked".
  - The Terms tab says "Funding cost ¥841.57 … if the plan runs; it cannot run today", one block after "Funding … has landed".
  - A full-width solid black bar labelled "Funding planned when you agreed" carries no scale. S/A-dA08-after-send.png, S/A-dA09-terms.txt.
- **Confusing.**
  - The stage track changes vocabulary after sending. "Received / Analysed / Reply ready / Sent / Agreed" becomes "Contract read / Terms negotiated / Early payment in / Collecting / Fulfilled".
  - The title changes from "Counter instead of accepting as asked" to "Offer from Foshan Home Retail Co.".
- **Confusing.** After Send the pane keeps its scroll position, so the owner lands mid-content under the sticky pane header ("0.85% off up to ¥257,200.00 if paid early" peeks out). The success sentence and the Deals heading are scrolled away. S/A-dA08-after-send.png.
- **Redundant.** "What was agreed" appears four times: the row's sub-line, the Terms tab's "What was agreed", "This authorizes", and the Agreements section.

### Agreements section through the story (part receipt day 2, late day 34, cure, day 38)
- **Broken.**
  - Day 2, after half the early payment was received (¥127.5k of the ¥255k promised): the Deals page shows no sign of the receipt. The "Payment promised" row disappears, and the agreement still says "On track".
  - Day 34: the agreement shows "Agreed", "Early payment did not arrive" and "Agreement expired 27 days ago" together, although half did arrive. "Next: Chase the ¥291,400.00 still owed" is right.
  - Evidence: S/A-dA12-day2-part-receipt.txt, S/A-dA13-day34-late.png.
- **Broken.** Day 34: the page subtitle says "Nothing needs you today." Below it are a red "Payment late" group, a "needs your approval" funding banner and a red "Chase ¥291,400" box. S/A-dA13-day34-late.png.
- **Confusing.**
  - After the cure was queued from Home and authorized on Approvals, the banner reads "Reserve unsafe today. No funding plan is ready yet." The row reads "This deal is costing more than you agreed to", with no figure.
  - On day 38 (cure cash due day 37) nothing on Deals changes: the row still reads "Payment late".
  - The owner cannot see that the cure ran. I did not verify that the approval executed. S/A-dA14-after-cure.txt, S/A-dA15-settled.txt.
- **Confusing.** The agreement line reads "0.85% off the ¥257,200.00 invoice". The invoice is ¥420,000; the discount applies to up to ¥257,200 of it.
- **Cosmetic.** The Agreements section runs full width (to x≈1408) while the queue and pane above stop at 1342. Its heading is in small caps, unlike every other heading. The first link in it is "All documents" (to /documents), not the deal.

### Overview (golden, before sending)
- **Confusing.** The state and title are jargon from the system's point of view: "Counter ready" and "Counter instead of accepting as asked". The owner's question is "Foshan wants X; what do I reply?"
- **Confusing.** "Option B needs your approval for 55-day terms. Its net economic cost over 12 months is stated as about ¥0 under the model's assumptions." The phrase "is stated as … under the model's assumptions" is the kind of hedge that makes owners distrust the number.
- **Confusing.** The terms table:
  - "instead of 1.20% off ¥420,000.00" under nearly every cell, including "Not offered instead of …".
  - Unlabelled progress-like bars under "Future invoices" with a tick mark.
  - "+15 days requested by buyer" wrapped onto three lines in a narrow cell. S/A-d02-overview-fold.png.
- **Redundant.** "Compare responses" is both a tab and an outlined button at the foot of Overview. "Review the counter" (header) and "Review selected response" (Compare foot) are two names for one act.
- **Confusing.** The page-level banner "FLOW action ready · ¥405k funding plan available · no approval needed · waits for your go · Run or compare →" sits above every deal. It is a company funding action, not this deal's, and "Run or compare" does not say what would run.
- **Cosmetic.** The queue row's "As asked: below your minimum for 15 days." does not say a minimum of what (cash reserve).

### Compare responses
- **Confusing.**
  - "Review Option B" in the table only selects B; it opens nothing. The review is a different button: "Review selected response" at the foot, or "Review the counter" in the header.
  - The A column's "Option A is selected" looks like a button and does nothing.
  - "Back to deal" goes to Overview while the owner is already in the deal.
- **Confusing.**
  - "Economic impact ¥5,040.00 once, ¥28,326.92 over 12 months — Two parts, not added together."
  - "Financing needed: None in this scenario" for As they asked, the one option that breaches the reserve. The reason is "FLOW takes no new funding"; that explanation is three sections lower.
- **Confusing.** "Can FLOW send it?" for As they asked is "Outside mandate" on golden and "—" on busy Foshan. "Over a limit you signed: only a new mandate changes that." The word mandate is never explained on the page.
- **Redundant.** The outcome table and the headroom plot are repeated in full on Cash impact. The terms appear here in a compact form and again behind "View terms by scope".

### Cash impact
(See complaint 2.) Also:
- **Confusing.** "66 days / 120 days" switch, "Funding: Each option with its own funding plan" and "Payment timing assumption": three controls or labels before the chart with no "what am I looking at" sentence.
- **Cosmetic.** "Use the left and right arrow keys…" is in the visible text dump (`.txt`). Check whether it is visually hidden.

### Busy books: list, Zhuhai, Dongguan
- **Confusing.** Six rows, four of them Foshan:
  - "Early payment, 1.5% off · “Early pay at 1.5%”"
  - "Early payment, 1.5% off · “pay this one early at 1.5%”" (the same request in other words)
  - "60-day terms on future invoices and 2 more terms"
  - "1% rebate, scope to confirm"

  The two 1.5% rows are distinguishable only by the quoted buyer wording. S/B-d01-list.png.
- **Confusing.** Zhuhai and Dongguan both stack three statements:
  - The title: "Accept, with your approval".
  - The small label: "FLOW has no reply it can send". Under it: "It changes your terms, so you approve it first" (Zhuhai) or "It is above what FLOW may agree alone, so you approve it first" (Dongguan).
  - The bold line: "FLOW has no reply it can send within your mandate for this offer."

  None of them says whether accepting is advisable. The row's dot is red ("below your minimum for 35 days"). S/B-d02-zhuhai.png.
- **Confusing.** The Zhuhai row says "75-day terms on the next invoice". The terms table says "Future invoices 75 days". Same deal, different scope.
- **Confusing.** The rows say "Accept, decline, or try other terms." On Dongguan's Overview the visible text has no "Try other terms" link and no Compare button, only the outlined "Review the request" in the header (S/B-d05-dongguan.txt).
- **Broken.**
  - Steps: on Zhuhai, open "Review the request", click the Compare tab, press browser Back, click Compare again, press Escape.
  - Result: the Compare tab is highlighted with a focus ring, but the body shows the accept review ("Needs your approval / What it costs / What you are authorizing").
  - Evidence: S/C-d02-escape-on-compare.png.
- **Cosmetic.** The "1 approval waiting" chip appears in the app bar, and the queue's "Waiting 1" tab means something else ("waiting on others").

### Getting back (C)
- **Confusing.** Each tab click is a history entry. Browser Back from Compare returns to Overview, not to the list, so reaching the page you came from takes as many Backs as tabs visited.
  - Close clears the selection (URL `/deals`). Back after Close restores the deal on the tab it was on (S/C-d03-after-close.png, S/C-d04-back-after-close.png).
  - Close is the only visible "leave" control, and it sits beside the primary button.
- **Broken (dead end).** I searched `/customers` and `/activity` for links containing `/deals` in `main` and found none. Neither page offers a link into a deal, and both logged a 404 resource error.
  - Home has one: "All deals ↗".
  - Home's worklist row opens the deal on Home itself (`/?customer=BUYER-3&decision=…`), with its own "Cash impact of this deal" chart, "Deal context" panel and "← Back to overview". That is a second deals UI with a different chart (y axis ¥400k / −¥200k / −¥600k) and a "Customers 3" tab that Deals does not have. S/C-d10-from-home.png.
  - "Open in Deals →" on Home is the bridge.
- **Confusing.** The tracker page (`/decisions/…`) has "Back" and "Open Deals". Browser Back returns to the Terms tab correctly (S/A-dA10b-back-from-tracker).

### Phone (390×844)
- **Confusing.**
  - The deal's tab strip scrolls sideways with the words cut at both ends ("rverview", "mpare responses", "Cash impact"). The title is repeated above the tabs in the sticky header ("Counter instead of accepting as asked" twice).
  - The "Deals" heading sits under the app bar.
  - S/A-m03-compare-fold.png, S/A-m04d-cash-inspector.png.
- **Confusing.** Compare is 3,887 px tall and Cash impact 3,689 px. The only way to the list is Close at the top, or the bottom nav "Deals", which keeps the selection.
- **Cosmetic.** In the inspector, "When: Lowest, Option A and Option B" in display type wraps across the card.

### Chinese (D)
- **Cosmetic.**
  - Customer names stay in English inside Chinese sentences, with no space: "Foshan的要求", "Foshan要求提前结算".
  - Line breaks fall badly: "，另有 2 项条款" splits after the comma, and "此还价延长 10 天" orphans "天" in the terms cell.
  - The rest is translated; I saw no English leakage on the first three screens.
  - S/D-d02-overview-fold.png, S/D-d01-list.txt, S/D-d03-compare.txt.
- **Confusing.** The Chinese title "还价，不按对方要求接受" carries the same system-point-of-view problem as the English one.

## 4. Flow map

```
Home ──"All deals ↗" / "Open in Deals →"──> Deals list (/deals)
Home worklist row ──> deal shown ON HOME (/?decision=…)  [second deals UI; "← Back to overview"]
Customers, Activity ──(no link into a deal)──> dead end

Deals list ──click row (1)──> Overview  [queue stays left]
Overview ──tab (1)──> Compare  [queue collapses to rail]  ──tab──> Cash impact [rail] ──tab──> Messages [queue back]
Compare ──"Review Option B" (1)──> selects B only (stays on Compare)
        ──"Review selected response" / header "Review the counter" (1)──> review (inside Overview tab)
review ──"Send Option X" (1)──> Agreed (Overview / Terms / Messages)   or   No deal (Overview / Messages) → row gone from queue
Agreed ──"Open the decision record"──> /decisions/… ──"Back" / "Open Deals" / browser Back──> Deals (Terms tab)
Agreements section (under list) ──"All documents"──> /documents   [no link to the deal]

Leave a deal: Close (1, clears selection) | "Show queue" on rail (1) | Escape (rail→queue, then clears) | browser Back (one step per tab visited)
Clicks, list → Option B sent: row, Compare, Review Option B, Review selected response, Send = 5.  Option A sent: row, Review the counter, Send = 3.
Loops: Compare "Back to deal" → Overview "Compare responses" → Compare.  Dead ends: refused deal after Close; Customers; Activity.
```

## 5. Ten changes that would most improve intuitiveness (problems to solve, not designs)

1. A deal has three names (row, title, breadcrumb) and changes its title and stage vocabulary after sending. The owner needs one stable name for the deal across list, pane and record.
2. The recommendation and its reason are not the first thing read. "Do this, because…" (including why FLOW recommends a costlier reply, or withholds Option B) is either missing or a footnote.
3. The same facts (terms, lowest cash, reserve, who may send) are repeated across Overview, Compare and Cash impact, with three tables and a plot saying the same thing. Each fact should live in one place.
4. Business consequences contradicts the outcome table (−¥105k against ¥165k / ¥300k) and does not say that it describes the company with no reply.
5. Leaving a deal: there is no plain way back to the list. The rail is unreadable when a customer has several deals, Close discards the selection, and browser Back steps through tabs.
6. Sending a reply the buyer refuses still runs funding, in amounts that differ from the review. The refused deal then vanishes from the queue.
7. Agreed-deal records contradict themselves: the wrong cost and funding source in the tracker, "kept zero of two promises" on day 0, a part receipt not shown, and "Agreed / expired / did not arrive" together.
8. The page's state sentence ("Nothing needs you today") disagrees with what is below it (payment late, chase, approval needed), and the company-funding banner sits on every deal.
9. The charts lack a reading key. Overlapping lines, an uneven axis, a sentence where a date belongs, a difference row that comes with a warning not to trust it, and an unscaled headroom plot leave the owner with no single question the chart answers.
10. Connections between pages are missing or duplicated. Customers and Activity cannot open a deal, Home has its own deal view with a different chart, and Agreements links to documents rather than to the deal.

## Not checked
- Messages tab on busy deals, the "Try other terms" flow, "Clarify" on busy Foshan, and the Zhuhai accept itself (opened, not sent).
- Whether the day-34 cure approval actually executed: the script clicked Authorize on the first approval, and the page afterwards still said "No funding plan is ready yet".
- The zh pass of Cash impact and Messages.
- Phone screenshots of the agreed deal and the Agreements section.
- Keyboard and screen-reader behaviour.
