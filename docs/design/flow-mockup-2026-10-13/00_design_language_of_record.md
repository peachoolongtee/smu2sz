# The design language of record (owner, 13 Oct 2026): the FLOW mockup

The owner's mockup (the HOME screens only: 01–06 desktop states, 18 the phone Home, 19 the phone collection state, plus
`FLOW-interactive.html` with its CSS and `README.txt`) is the final design language for Home. The owner's instruction of
13 Oct: take only the Home page from the mockup; its other screens (funding review, Cash, Receivables, Customer, Documents,
Activity, What-if, Capex, Approvals) are NOT references, because they do not encompass the audit's findings, the flows or
the backend; they were removed from this folder. The visual language below (colours, tones, cards, buttons, type) carries to
the other screens as a style only; their structure comes from the overhaul map #121's decisions and the 12 Oct audit
(`FLOW-dev-audit.md`), never from the mockup.

## The language, as the HTML defines it
- Canvas `#e5e8e8`; panel `#f8f9f9`; card white; text `#151b1c`; muted `#586468`; hairline `#d8dddd`.
- Status tones: amber `#f9d491` / text `#60410e` (needs you, action ready, collection); lavender `#ebdefa` / purple
  `#9252dc` (buyer's turn, waiting, planned; the chart's current line); green `#c7e9b3` / `#234220` (not due, healthy);
  risk red `#a83222` for a figure below the minimum. Dark-mode pairs exist for each.
- Primary button ink `#171d1e` with white text; secondary an outline on white; tertiary a text link with an arrow.
- Large rounded cards (24 px) on the canvas, sections inside separated by hairlines, pills `radius-full`, one soft shadow
  `0 1px 2px -1px rgb(0 0 0 / 8%)`, focus ring 2 px.
- Type: the headline sentence as the page's first line (≈ 40 px), card titles 22 px, figures 44–56 px, labels 15 px muted,
  body 15–16 px. Sentence case everywhere; no uppercase eyebrows.
- Structure on Home: headline sentence + one-line summary + the state pill; three cards (Cash available today with the reserve
  bar, FLOW recommends with the proposed amount, est. cost, authority and the two controls, Company cash outlook with the mini
  chart and Expand); then the worklist as a table (All / Needs you / Waiting / Customers, search, Customer-deal · Next step ·
  Status pill) beside "Upcoming cash movements"; a footer row of secondary destinations (Documents, What-if terms, Evaluate a
  purchase, Approvals). Selecting a worklist row replaces the three cards with the selected item's card (deal: invoice value,
  requested discount, requested term, the breakdown donut with its rows, the next action; agreement: net cash after repayment,
  the repayment waterfall; overdue invoice: the collection breakdown) and a "Deal context" panel (stage pill, one sentence,
  Customer profile, Agreement & supporting evidence); Dismiss or Escape restores the overview. Expand on the outlook opens the
  full forecast in place with the event chips and the selected event's sentence.

## The lead's decisions (binding; "minor improvements while keeping the app's structure")
1. **The side rail stays.** The mockup's top pill group becomes the rail's vertical pill group: the same icons, labels on
   expand, the selected item white on the panel tone. The brand mark and the owner control sit where the mockup has them.
2. **The app's fonts stay** (Inter body, Plus Jakarta Sans display): the mockup uses a system sans; the type scale above
   maps onto the app's scale, not the other way round.
3. **Business words stay honest** (INVARIANT 13 and the audit): "Day 30" becomes "in 30 days"; "Proposed" becomes the
   vocabulary's "planned"; deal and invoice ids (FHR-01, SZ-01) never show in Business, the row's second line is the server's
   subject and differentiator; every percentage on a donut or bar is a server share word; "≈" figures are the server's own
   display; "One funding action ready. Two deal decisions need you." is a server sentence (the worklist's counts in words).
4. **One filled button per state** (the mockup already does this); every decision level keeps a real button.
5. **The chart keeps the step lines**, the minimum line, the shade below it and the lowest point; purple for the current
   line is adopted; "With plan" stays the grey dashed comparator "conditional on execution".
6. **Upcoming cash movements** is the Home read's rail events (the three nearest outflows and inflows with their `when`
   words), never a second computation; "Explore company forecast" goes to Cash & Funding.
7. **The footer row** links to Documents, What-if terms, Evaluate a purchase and Approvals as the mockup shows; these pages
   themselves change only in their own slices.
8. **Dismiss** returns to the overview and clears the URL selection; Escape does the same; the three selections stay in the
   URL as today.
9. **The breakdown donut** is allowed (it reads a composition, not a trend) with server share words; it never animates beyond
   a 150 ms opacity.
10. Everything the Home V2 build already settled and the mockup does not contradict stays (the funding disclosure, the
    approval line's two forms, the compact inspector behind the lowest point, the fluid width when the rail is collapsed).

## The other screens
They take the visual language only. Each overhaul slice (map #121) is structured by its decision tickets and the audit's
findings for that page, prototyped as those tickets say, and styled with the tokens above and the kit that Home's build adds.
