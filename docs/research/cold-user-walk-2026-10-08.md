# Cold-user walk, 8 Oct 2026 (brief sections 39 and 44)

Branch `dev`, mock mode (`NEXT_PUBLIC_API_MODE=mock`, build in `.next-walk`, served on port 3107). Driven by a one-off Playwright script
(not committed) signed in as the owner, Business mode, at 1440x900 and Pixel 7 (412x839). The rendered text is `innerText`, so the contents
of a closed `<details>` are not counted as visible. States follow `apps/web/e2e/screenshots.spec.ts` (day 34 reached from `/demo`
`home-days`=34 and `home-advance`, which also works in Business mode, so no Demo-mode switch was needed; the Demo pages themselves were not reviewed).

Click rule: a nav page load = 1, a `<details>` summary or a button = 1. The page text is identical at both viewports (line-for-line diff of
all 23 captured states: no difference). The only difference in clicks is that on the Pixel 7 the nav links sit behind the
"Open navigation" button, so every nav page load costs **+1 click** on the phone (shown as "n / n+1" below).

## Table 1. Brief section 39, questions A to N

### Deals, day 0, after the check ("Check against my limits"). Path: Deals (1) > buyer message (2) > Check (3)

| Q | Answer the page gave (exact) | Clicks desktop / phone |
|---|---|---|
| A. What is the buyer asking for? | "We'll settle the ¥420k early at 1.2% if you extend our standard terms to 60 days going forward and give us 1% off next quarter." (inbox preview, visible on load). Itemised after opening the message: "1.20% discount for paying the ¥420,000.00 invoice early / 45 → 60 day payment terms going forward / 1.00% rebate on the next period's purchases" | 1 / 2 (itemised: 2 / 3) |
| B. Should I accept? | "Counter recommended" | 3 / 4 |
| C. Why not? | "The 1.20% early-payment discount also costs more than your available funding (break-even 0.88%)." Fuller, one click more: "The package gives away ¥28,326.92 over 12 months, above your ¥5,000.00 limit." | 3 / 4 (fuller: 4 / 5) |
| D. What will happen to cash? | "First reserve breach in 47 days" and "Cash falls to ¥209,960.00"; "Worst point ¥164,960.00 in 60 days" | 3 / 4 |
| E. How much value am I giving away? | "12-month cost of concessions ¥28,326.92 / Your limit: ¥5,000.00" | 3 / 4 |
| F. What should I offer instead? | "Terms stay at 45 days, no rebate. We will accept early settlement on up to ¥257,200 of this invoice at 0.85%, paid within 2 days." (Option A, Recommended) | 3 / 4 |
| G. What will the counter cost me? | "Estimated cost ¥3,027.77" | 3 / 4 |
| H. Can I send it now? | Yes: an enabled "Send this counter" button (mock reply after pressing it: "The buyer accepted Option A. The agreement is on your books."). Note the button is at 1121 px on desktop (900 px viewport) and 1499 px on the phone (839 px), so it is below the first screen | 3 / 4 |
| I. Why did FLOW choose it? | In "Details": "Early settlement at 0.85% is cheaper than financing the invoice on the marginal committed source; the line covers the rest of the near-term gap." | 4 / 5 |
| J. Can I verify the calculation? | Yes, in "Detailed calculations", Option A: "break-even: d/(1−d) < c, c = 10.8417% × 30/365 = 0.8911% → d < 0.8832%; largest whole-5bp rate below it = 0.85%. ... Cost: discount ¥2,186.20 + funding the rest of the gap ¥841.57 ... = ¥3,027.77" (engine notation) | 4 / 5 |

### Home and Cash & funding (the same text appears on both unless stated). Each page load from the nav = 1 (phone 2)

| Q | Day 0, before the go-ahead | Day 0, after the go-ahead | Day 34, pending approval | Day 34, approved |
|---|---|---|---|---|
| K. Am I currently safe? | "Your cash reserve becomes unsafe in 12 days." (1 / 2) | "You're covered. Cash stays above your ¥300k minimum cash reserve for the next 120 days. It comes close: cash sits exactly on the minimum cash reserve in 30 days." (1 / 2) | "Your cash reserve becomes unsafe in 8 days." (1 / 2) | "You're covered. ... cash sits exactly on the minimum cash reserve today." (1 / 2) |
| L. What funding is active? | No sentence at level 1. Home "Details: ... facilities ..." table: Bank credit line Drawn ¥0.00, Invoice financing Drawn ¥0.00 (2 / 3) | Cash "Current funding": "¥150,000.00 Bank credit line / Received today" and "¥255,000.00 Invoice financing (onboarded platform) / Arrives in 3 days" (1 / 2). Home shows it only as two "Recent changes" lines | Not stated at level 1 ("Nothing has run yet and the alert stays open until you approve."). Home Details table: Bank credit line ¥149,986.20 drawn, ¥13.80 available (2 / 3) | Cash: "¥149,986.20 Bank credit line / Received 34 days ago" and "¥200,000.00 Invoice financing (onboarded platform) / Arrives in 3 days" (1 / 2) |
| M. What money is on its way? | "The next receipt, ¥420k, lands only in 32 days." and "Next expected: ¥420,000.00 from Foshan Home Retail Co. in 32 days." (1 / 2). No funding on its way | "¥255k funding arriving in 3 days" and "Arriving ¥255,000.00" (1 / 2) | "The next receipt, ¥420k, lands only in 13 days."; late: "¥162,800.00 was due 2 days ago: 2 days late". No funding on its way (1 / 2) | "¥200k funding arriving in 3 days"; "Next expected: ¥420,000.00 from Foshan Home Retail Co. in 13 days." (1 / 2) |
| N. Need more funding? | "Secure ¥405k of funding" (¥150k Bank credit line + ¥255k invoice financing) (1 / 2) | Cash: "No additional funding is needed." (1 / 2). Home does not say it, only "You're covered." | "Secure ¥200k of funding ... Needs your approval" (1 / 2) | Cash: "No additional funding is needed." (1 / 2). Home does not say it |

## Table 2. Brief section 44, per page (desktop first, phone where it differs)

"Level 1" = visible without opening a disclosure. "day N" means the literal word "day" plus a number: none appears at level 1 on any Business page
(only in disclosures such as "(day 12)", "day 37 to day 47", and on the Demo story page). Relative phrases such as "in 12 days" are not counted.

| Page | Eye goes first (first heading / first figure in main) | One primary action? | Engine terms, codes, ids, hashes at level 1 | Figures shown 3+ times (by value; literal forms in brackets) | Contradiction a CFO would see | Height in screens (desktop / phone) |
|---|---|---|---|---|---|---|
| Home, day 0 | Eyebrow "ACTION NEEDED", heading "Your cash reserve becomes unsafe in 12 days.", first figure ¥60k | Yes: "Run funding plan" (the only filled button; "Compare options" is a link) | Only the disclosure label "...facilities and debt readings". No ids, no "day N" | ¥420,000 x6 (¥420,000.00 x4, ¥420k x2); ¥300,000 x3; ¥405,000 x3; ¥150,000 x3; ¥255,000 x3 | None at level 1. Level 2: "Why this" says "finance an invoice ... ¥336,000.00, cost ¥2,994.08 (11.2% a year for 29 days)" while the plan is ¥255,000.00 for ¥3,113.93 | 1.62 / 2.44 |
| Home, day 34 (before the fix) | "ACTION NEEDED", "Your cash reserve becomes unsafe in 8 days.", first figure ¥100k | Yes: "Queue it for my approval" | Only the disclosure label "...facilities..." | ¥200,000 x8 (¥200k x4, ¥200,000.00 x4); ¥300,000 x4; ¥420,000 x4 | None at level 1 | 1.51 / 2.43 |
| Home, day 34 pending (extra) | same heading | No: none filled; four links to the approval ("Open the approval card" x2, "Open approvals", "Review and decide") | "APR-000001" x2, "Audit details", "OPERATIONS", "0 executed / 0 refused" | ¥200,000 x11; ¥300,000 x4; ¥420,000 x4 | "Cash stays above your minimum cash reserve for the next 120 days" (plan card) vs "It keeps cash above your minimum cash reserve for the next 12 days." (approval card) | 2.07 / 3.23 |
| Deals, evaluated | Heading "Deals", first figure ¥420k (inside the buyer message) | Partly: filled "Send this counter", but the banner link "See what we'd offer back" is also styled as a filled primary | "break-even 0.88%", "The buyer's reply is simulated in this demo.", "View parsed terms", "Option A". No ids | none | None on the page. Across pages: Option A (early settlement + credit line) costs ¥3,027.77 here, the same structure on Cash is ¥3,938.81 (rate 1.2% not 0.85%, not explained at level 1); inside Detailed calculations the credit-line cost is ¥841.57, on Cash ¥841.64 | 1.65 / 2.33 |
| Cash & funding, day 0 | Heading "Cash & funding", first figure ¥60k | Yes: "Run funding plan" (plus 4 more buttons/links: horizon toggles, sandbox, purchase) | "admissible" x2, "verdict", "what-if sandbox", "Debt readings". No ids | ¥300,000 x5; ¥420,000 x5; ¥255,000 x4; ¥841.64 x4; ¥405,000 x3; ¥150,000 x3; −¥105,000 x3 | None at level 1 | 2.66 / 4.55 |
| Cash & funding, funded | Heading "Cash & funding", first figure ¥300k | No action needed; none filled (correct: "No additional funding is needed.") | "verdict", "what-if sandbox", "Debt readings" | ¥300,000 x6; ¥0 x3 (¥0.00, ¥0k axis); ¥255,000 x3 | Chart legend and table column say "If you do nothing" but carry the funded numbers (¥550,000.00 today). Level 2: Home Details "Debt to earnings 1.72×" vs Cash "Debt readings" 1.35× | 1.79 / 2.42 |
| Cash & funding, day 34 pending (extra) | same | No filled button (approval link only) | "APR-000001", "admissible" x2, "verdict", "sandbox" | ¥200,000 x7; ¥300,000 x6; ¥420,000 x3; ¥841.64 x3 | **Stale day-0 comparison under a day-34 headline**: #1 plan "Bank credit line + Invoice financing ... ¥3,113.93" while "Recommended" is ¥200k for ¥1,782.19; "Credit line only: Cash still falls below your reserve 22 days ago; ¥255,000.00 short at the worst point" while the gap is ¥200k in 8 days; "gap opens in 12 days" vs 8 days | 2.59 / 4.24 |
| Receivables, day 0 | Heading "Receivables", first figure ¥420,000.00 | No action, none needed (read-only page) | "RCV-A" in the table | ¥420,000 x3 | None | 1.00 / 1.00 |
| Receivables, day 34 (extra) | Heading "Receivables", first figure ¥1,002,800.00 | No action | "RCV-A" x3, "RI:BUYER-1:2", "RI:BUYER-1:32", "CMT-a78afaa5becb5273" x2 (hash-like), "DEMO-RCPT-1" | ¥420,000 x3; ¥255,013.80 x3 | Here "commitment CMT-..." is listed, while Activity says "Agreements with buyers: No commitments yet" | 1.07 / 1.77 |
| Activity (funded) | Heading "Activity", first figure ¥255,000.00 ("Chain valid / 2 entries" chip first in the list) | No action, none needed | "hash-chained", "Operations the executor refused", "every hash", "audit trail", "Audit details" x2, "Executed", "Chain valid". Day 0 empty state: "Operations appear here..." | none | Day 34 approved: Activity lists both "You approved ¥200,000.00 ..." and "Waiting for your approval: ¥200,000.00 ..." for the same operation; Home "Recent changes" does the same | 1.00 / 1.23 |
| Approvals, pending | Heading "Approvals", first figure ¥200,000.00 | Yes: "Approve ¥200,000.00" filled, "Decline" outlined | "annualised = 32.52%", "(from in 3 days to in 13 days)"; empty state "Tier 2 requests, such as the capex loan". Level 2: "Tier 2", "FAC-IF", "RI:BUYER-1:2", "alert:ALERT-RESERVE-42:v7:0", "day 37 to day 47" | ¥200,000 x7 | "for the next 12 days" vs "120 days" on Home/Cash (see Home pending). Level 1 also gives the yearly cost twice with different precision: 32.5% (Home) vs 32.52% (card) | 1.00 / 1.33 |
| Approvals, approved (extra) | same | No action left | "annualised = 32.52%", "3-day lead time" | ¥200,000 x5; ¥420,000 x3 | None | 1.00 / 1.14 |
