# Impeccable critique: FLOW web app (Wave 8, map #47)

8 October 2026 · target `apps/web` (slug `apps-web`) · mode Operate · a refinement: the identity in `apps/web/DESIGN.md` is kept.

⚠️ DEGRADED: single-context (Assessment A, the design review, ran inline in the critique agent at the orchestrator's instruction; Assessment B, the detector, ran as an isolated sub-agent and was read only after A was complete. No browser overlay: not requested; screenshots were the evidence.) No `.impeccable/critique/` snapshot was written: the orchestrator asked for this one file only, so there is no trend line.

Evidence: 27 desktop and 27 phone captures in `docs/screenshots/impeccable-before-2026-10-08/` (strategy flag on; Business and Demo; English only was recorded, no zh captures exist), the two reference dashboards, and the components where a capture raised a question. Paths below are relative to that screenshots folder.

**Detector (Assessment B):** `impeccable detect --json apps/web/app apps/web/components` exit 0, `[]`: no slop findings over 67 `.tsx`, 1 `.ts`, 1 `.css`. A fixture test showed the detector's coverage is narrow (it catches palette tells, not hex, alt or focus), so "clean" means "no AI-palette anti-patterns". B's manual sweep confirmed: no gradients, no runtime web fonts (`--font-sans` names Inter first but nothing is fetched), no raw hex/rgb in TSX, every colour from `@theme static`, no `<img>` at all, every `<button>` typed, one `bg-brand-600` per page file, 54 `aria-label`s, reduced-motion block present. Two real misses (findings 23 and 24 below).

## 1. Heuristic scores per page (Nielsen 0–4; n/a where the page cannot exhibit it)

| Page (mode) | 1 Status | 2 Real world | 3 Control | 4 Consistency | 5 Error prev. | 6 Recognition | 7 Efficiency | 8 Minimal | 9 Recovery | 10 Help | Total | Band |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Home (Business; 01, 08, 09, 12, 14, 17) | 4 | 3 | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 2 | 27/40 | Acceptable |
| Deals (Business; 02–04, 26) | 3 | 2 | 3 | 3 | 3 | 2 | 2 | 2 | 2 | 2 | 24/40 | Acceptable |
| Cash & funding (Business; 05, 10, 13b, 18) | 3 | 3 | 3 | 2 | 3 | 3 | 3 | 2 | 2 | 3 | 27/40 | Acceptable |
| Receivables (Business; 06, 13) | 3 | 2 | 3 | 2 | 3 | 3 | 2 | 2 | 2 | 2 | 24/40 | Acceptable |
| Activity (Business; 07, 11, 19) | 3 | 1 | 3 | 3 | n/a | 3 | 2 | 3 | n/a | 2 | 20/32 | Acceptable |
| Approvals (Business; 15, 16) | 4 | 3 | 3 | 3 | 3 | 3 | 2 | 2 | 2 | 3 | 28/40 | Good |
| Demo story (20) | 3 | 3 | 4 | 2 | 3 | 3 | 3 | 2 | 2 | 3 | 28/40 | Good |
| Mandate (Demo; 21) | 3 | 3 | n/a | 3 | n/a | 3 | 2 | 3 | n/a | 3 | 20/28 | Good |
| Verdict (Demo; 22, 23) | 3 | 2 | 3 | 3 | n/a | 2 | 2 | 1 | n/a | 3 | 19/32 | Acceptable |
| Funding (Demo; 24) | 3 | 2 | 3 | 2 | n/a | 2 | 3 | 1 | n/a | 3 | 19/32 | Acceptable |
| Trajectory (Demo; 25) | 3 | 3 | 3 | 3 | n/a | 3 | 3 | 3 | n/a | 3 | 24/32 | Good |

Read-only pages score n/a on 5 and 9 (nothing to prevent or recover); Mandate also on 3. Bands read off the percentage.

**Design specificity verdict.** Authored, not interchangeable: the navy hero with a bright status pill, section-hue chips, the "in 12 days" headline voice, "Your limits, not an opening offer", the "If you do nothing / With the recommended plan" legend. Nobody would mistake this for a template dashboard. Where it slips: the Demo engine views (Verdict, Funding) are generic data dumps, and the Business pages reach 2.1–2.5 screens because every fact is a 16 px card with 24 px padding, which is the opposite of the references' density.

**Cognitive load.** Fails 3 of 8 (Chunking: the Receivables Action cell carries three levels of text; Single focus: Home day-34-pending says the same pending approval four times; Progressive disclosure: Deals shows the envelope, the recommendation and Option A as three full cards before the first fold). Moderate.

## 2. Ranked findings

P0 blocks the owner's task or misstates something; P1 should be fixed in this wave; P2 is polish. Each fix respects: the browser computes no money (every figure is a server string), one brand-filled action per page, status colour only for status, no gradients, no runtime web fonts, testids and dictionary keys stay, Business mode never shows "day N" or engine terms at level 1.

### P0

**1. Engine terms at level 1 on the Business Activity page.** `desktop/19-activity-day34-approved.jpg`, `phone/19`. Timeline rows read "Clock moved from 4 days ago to today: 0 scheduled flow(s) posted (net ¥0.00), 1 invoice(s) issued, 0 commitment(s) expired, 1 existing-debt payment(s) posted (−¥45,000.00)", with the kind label `ADVANCE_CLOCK`, actor `System`, and the agreement row shows `CMT–a78afaa5becb5273` and "future give-aways booked". `app/activity/page.tsx:59,63` falls back to `o.kind` when `te("opkind", kind)` has no entry. Why: the owner and finance director read this as the system talking to itself; it breaks the Business-mode contract and the cold reader's trust. Fix: the server's `event_text` for a clock move in owner words ("4 days passed: the ¥45,000 debt payment went out and one invoice was issued"), an `opkind.ADVANCE_CLOCK` dictionary entry ("Time passed"), and the commitment id moved into Audit details; System rows could sit under a quiet "Time passed" group. `clarify` + `distill`.

**2. Cash & funding day 34 ranks a plan #1 that is not the recommended one.** `desktop/13b-cash-day34.jpg`, `phone/13b`. The next-step card says "Secure ¥200k · ¥1,782.19 · Queue it for my approval". Below, "Plans that fully protect your cash" lists "#1 Invoice financing ¥1,425.75 + ¥1,069.32 = ¥1,706.10" and "#2 ¥5,040.00"; the ¥1,782.19 plan is absent and no row carries the Recommended badge (`app/cash/page.tsx:68` passes `recommendedKey` only when `plan_source === "router"`). The note "A cheaper option exists (¥1,706.10 in all) but it would need 2 separate approvals; this plan needs one" is 12 px grey. Why: "#1" is read as "do this"; the owner sees two different first choices on one page, a misstatement by layout. Fix: the comparison carries the chosen plan as a row with status `recommended` and the two-approval plan as `alternative` with its reason as a chip ("needs 2 approvals"); numbering follows. Strings from the server; no sums in the browser. `clarify` + `layout`.

### P1

**3. The one decision on phone is squeezed into a 100 px column.** `phone/14-home-day34-pending.jpg`. "Needs your decision: Approve ¥200,000.00 of invoice financing? Cost ¥1,782.19 · lands in 3 days · …" wraps nine lines beside the Review and decide pill. Fix: below `sm`, stack the text and put the button full-width under it. `adapt`.

**4. The pending approval is said four times on Home.** `desktop/14`. "The agent's answer · 1 waiting for approval" card, the "Waiting for your approval / Open the approval card" tile in the next-step button slot (`components/business/next-action.tsx:96`), the "Needs your decision" row, and the Recent changes entry. Fix: keep the Needs your decision row (it owns the brand action) and the next-step tile; drop the agent's-answer card when its only content is "waiting". `distill`.

**5. "Open Option A / Open Option B" carry no sentence.** `desktop/04-deals-evaluated.jpg`, `phone/04`. Under the envelope two secondary pills name options that are not described until clicked; Option A then appears again as a card below, so the pills duplicate "Compare another option". The envelope card itself is a bold two-line paragraph, a grey caveat, and two more sentences of near-identical weight. Fix: remove the two pills (Option A is already the card; "Compare another option" opens B), and give the envelope the KPI-tile treatment: three facts (terms ceiling 55 days at +0.30%, early payment 0.85% on ¥257,200, rebate 1.25%) with the sentence as caption. `distill` + `typeset`.

**6. Receivables: a paragraph inside a table, and ids at level 1.** `desktop/06`, `desktop/13`, `phone/06`, `phone/13`. The Action column holds a chip, a sentence and three lines of 12 px small print; Worth collecting carries two rates ("Saves ¥788.28 at the 0.45% limit; ¥1,288.28 if they take 0.20%"); `RCV–A`, `RI:BUYER-1:2` sit under the buyer name; on phone the stacked cell right-aligns the Worth text so it wraps ragged-left and "take 0.20%" sits alone. Why: the negotiator wants the ranking and the one figure; the finance director wants the small print only on demand. Fix: columns Buyer (monogram + name), Amount (right, tabular), Due, Status, Worth (the one `worth_text` figure), Action (chip); the sentence and small print open from a chevron per row; ids live in Audit details. `layout` + `adapt` + `distill`.

**7. Forecast chart labels collide.** `desktop/13b` and `desktop/18` ("Debt service –¥45k" on "Minimum cash reserve ¥300k"; "Worst point ¥300k" over the ¥300k tick), `desktop/10` ("Payroll –¥340k" over "Supplier payment –¥120k"), `phone/10` and `phone/05` (truncated "Receipt from Foshan Home Retail Co."). `components/business/cash-forecast.tsx:127–140` places every label by a fixed position. Fix: the reserve label moves to the legend (it is already there) and off the line; event labels alternate above/below and drop to the tooltip when two fall within 24 px or on narrow; the worst-point label is suppressed when it equals the reserve. `layout` + `polish`.

**8. Phone fixed chrome covers content.** Every phone capture; `components/app-shell.tsx:272` (tab bar) and the floating Ask FLOW pill. The pill sits on the Receivables "Call now" row (`phone/13`) and the Approvals "Show details" (`phone/15`); the tab bar hides the last line of cards. Fix: give the scroll container bottom padding of the bar plus the pill, and dock Ask FLOW above the bar at the right with the content inset by its width; or make it the bar's fifth item. `adapt`.

**9. Unlabelled sums on Cash day 0.** `desktop/05-cash-day0.jpg`, `phone/05`. "¥841.64 + ¥2,272.29 = ¥3,113.93" with no leg names. Fix: "Credit line ¥841.64 · Invoice financing ¥2,272.29" with the total bold, from server `legs[].name_display` and `cost_display`; the equals sign goes. `clarify`.

**10. Approvals says the same thing twice and leaves half the page empty.** `desktop/15`. The Next step band and the info Callout (`app/approvals/page.tsx:64`) both say approving runs and declining records; the card is 556 px wide at left. Fix: one band; the facts list in two columns inside a centred `max-w-3xl` card. `distill` + `layout`.

**11. Three brand-filled buttons on the Demo story.** `desktop/20`. Start demo in the strip (`components/demo-stepper.tsx:95`), Start demo in the header (`app/demo/page.tsx:28`), Advance time. Fix: the strip keeps the primary; the header one becomes secondary and Advance time secondary. `polish`.

**12. Phone Demo shell spends 130 px on chrome.** `phone/20`–`26`. Four stacked rows (Business/Demo, Mock data, Owner · Sign out, English/中文) before the title, then a sticky strip. Fix: Mock data, Owner, Sign out and language into the hamburger sheet; the strip stays. `adapt`.

**13. Receivables day 0 small print does not reconcile (cold walk §5).** `desktop/06`. "¥86.16 at the 0.85% limit … 0.90% would cost ¥54.51 more than the plan" cannot be tied to the plan cost by a reader. These are server strings; the browser must not recompute. Flag for the worth endpoint's sentence, not the page. `clarify` (server).

### P2

14. Home hero: the three tiles carry identical weight and the "Available headroom ¥100k · Lowest forecast headroom −¥405k" pair hangs below them as an inline afterthought (`desktop/01`). Make them the eyebrow/figure/caption tiles of the references, on the deep surface. `typeset` + `layout`.
15. Home day 0: "Who owes you" at half width with nothing on the right (`desktop/01`). Full width when alone, or an empty Recent changes card that teaches ("Your first action will appear here"). `layout` + `onboard`.
16. Cash: "Try a change" and "Buy equipment" are two 180 px cards for two links (`desktop/05`). One row of two quiet link tiles. `distill`.
17. Deals: the "Estimate" pill is unexplained (cold walk §3). A caption "Priced on today's books; re-checked before sending". `clarify`.
18. Approvals approved: "Result: Advance ¥200,000.00 … today; the cash lands in 3 days after the 3-day lead time, not today" and the lowercase fragment under "Why it needs you" (`desktop/16`). Owner sentences, capitalised. `clarify`.
19. Activity day 0: two empty cards ("No commitments yet", "Nothing has been refused yet") each a full card (`desktop/07`). One quiet line each under the timeline. `distill`.
20. Demo Funding: the covenant-effect cell makes the first row 300 px tall; "Alternatives compared" values overlap their labels (`desktop/24`, `phone/24`). Covenant text behind a Disclosure; values on their own line below `md`. `layout`.
21. Demo Trajectory: amounts wrap "–" alone on a line (`desktop/25`, `phone/25`). `whitespace-nowrap tabular-nums text-right` on amount cells. `polish`.
22. Deals Demo inbox (`desktop/26`): "No deal" in grey on a row reads as a status without colour or chip. A neutral Chip. `polish`.
23. Chart wrapper removes focus: `app/globals.css:378–381` sets `outline: none` on `.recharts-wrapper:focus-visible` with no replacement. Use the global ring. `harden`.
24. Nine sub-12 px arbitrary sizes (`text-[0.6rem]`…`text-[0.7rem]`); `components/business/status-block.tsx:42` and `components/whatif-results.tsx:261` may carry information. Lift to `text-xs` or add a `text-2xs` token. `typeset`.
25. One non-token shadow: `app-shell.tsx:401` `shadow-[0_-4px_12px_…]` for the bottom Demo strip. Add `--shadow-up`. `polish`.

## 3. Cross-page consistency (the same thing done two ways)

- **Status header.** Home says "unsafe in 12 days" in a navy hero with a bright pill; Cash & funding repeats the sentence verbatim in a white card with an amber rail, a small pill, a red third line and four grey tiles. Same fact, two voices. Keep the hero idiom for Home; Cash risk becomes one compact status row (pill + sentence) above the tiles, no rail (the rail is status colour on a boundary).
- **Fact tiles.** Five idioms: hero tiles (navy), Cash risk tiles (`subtle` fill), Receivables `Stat` cards (white), the Deals Recommendation stats (bare coloured figures), Mandate limit tiles (bordered). One `Stat` with eyebrow / figure / caption and two surfaces (on-deep, on-surface).
- **Folds.** "Why", "Details", "How the agent read it", "Show the calculation", "Show the figures as a table", "Audit details", "Show details". Approvals and Home's agent's-answer use a native ▸ `<details>`, not the kit `Disclosure`. One component, one chevron, verbs from one small set.
- **Ranking.** Cash numbers rows "#1 #2"; Receivables says "Ranked by…" without numerals; Deals letters "Option A / B". Numerals wherever the server ranks.
- **Ids.** `RCV–A`, `RI:BUYER-1:2`, `CMT–…`, `OFF-…` appear in Business Receivables and Activity but are hidden on Home and Deals. Level 2 only.
- **"Recommended" badge.** Brand-tinted on Cash day 0 and Option A; missing on Cash day 34 (finding 2).
- **"What to do now".** Deals and Approvals use the brand Next-step band; Home and Cash use the Recommended-next-step card. Pick one: the card where there is a priced action, the band where the step is a navigation.
- **Links as actions.** "All receivables", "All activity", "Open approvals", "Open the evidence export." are underlined text; "Compare options" is a pill. Quiet actions in a card header are text links; the pill is for a step.
- **Time words.** "today, 11:30" on the inbox; "today" elsewhere; "in 3 days" vs "Arrives in 3 days" vs "after the 3-day lead time". One `*_when` voice.

## 4. What the references do that FLOW should take, and where

The bar is density, hierarchy and finish; the identity stays.

| Reference pattern | FLOW place | Constraint |
|---|---|---|
| KPI tile: uppercase eyebrow, large figure, delta pill, caption ("compared to previous 7 days") | Receivables Stat row; Cash risk tiles; Home hero tiles (on-deep); Deals envelope (finding 5) | A delta pill only where the server sends a `delta_display` and the direction is a status (overdue up is `bad`); otherwise a caption. Never a browser subtraction. |
| Proportion bar with legend and percentages | Cash "Current funding" drawn/available (already bars: add the legend row and server `pct_display`); Deals Recommendation "¥28,326.92 of a ¥5,000 cap" as the Trajectory give-aways bar, which already exists in Demo; Receivables outstanding split (late / due soon / later) above the table | Segment widths from server percentages; colours: status for the late segment, ink tints for the rest. |
| Table: monogram, pill filters, right-aligned tabular numerals, quiet row action, paging | Receivables: `Avatar` monogram in Buyer, filters All / Late / Due soon, Amount and Worth right-aligned `tabular-nums`, a chevron that opens the row's sentence (finding 6). Activity: filters All / Agent / You / System (System folds the clock rows), "Show 10 more" paging on the timeline. | `tabular-nums` is already in `ui.tsx`; apply to every money column. Paging slices arrays, no money. |
| Chart: dashed hairline gridlines, a tooltip card with a date header and legend bullets, lighter area fills | `cash-forecast.tsx`: `CartesianGrid strokeDasharray`, `ForecastTooltip` gains the "in 12 days" header and series bullets, event labels move into the tooltip when crowded (finding 7) | Tooltip values are the server's `cash_display`; the x header uses relative words in Business mode, never "day 47". |
| Density: 13–14 px table body, 16 px card padding, 24 px between sections | Business pages at 2.1–2.5 screens; a 14 px table body and 16 px padding brings Cash day 0 near 1.8 screens | Body text stays 16 px; only data and captions tighten. |
| Section header with a quiet kebab for secondary actions | Card headers with "All receivables" / "All activity" links | Keep the text link; a kebab hides the one link the owner wants. Take the quietness, not the menu. |

**Do not take.** The dark variant (DESIGN.md has no dark theme). The green-to-red segmented utilisation bar (reads as a gradient and uses status colour for a quantity). Mini sparklines computed in the browser (no server series exists; the browser computes no money). The sidebar navigation (FLOW keeps the pill top nav and the phone tab bar). The monospace figures of the markets dashboard (FLOW uses one sans with `tabular-nums`). Row checkboxes and bulk actions (no bulk operation exists). The "Generate report" top-right button (a second filled action). Decorative tile icons.

## 5. What is already good

The deep hero with its bright pill is the product's signature and it carries the headline the owner needs ("unsafe in 12 days", "You're covered") in one glance; the three-tile fact row under it names first breach and worst point as two days, which the brief fought for. "Your limits, not an opening offer" and Option A's single sentence with a price are the clearest negotiation copy in the app, and the "Who decides" tile with the signed-limit reason makes autonomy legible. The Approvals card states the consequence of declining before the buttons. The forecast legend's "If you do nothing / With the recommended plan" is plain and honest, and the "Current funding" card after execution shows drawn and available per source without a chart. Section hues on the chips and the phone tab bar give wayfinding without touching status colour. Under the surface the system is disciplined: zero detector findings, no hex in TSX, no gradients, no web fonts, every button typed, one brand fill per page file, a defined focus ring and a reduced-motion block. The 2×2 tile grid on phone Cash shows the responsive grammar already exists; the fixes above are about applying it everywhere and taking the references' density.

## 6. Questions to consider (for the owner, before the fix waves)

1. Priority: the two P0s are copy-and-structure (Activity engine words; Cash day-34 ranking). Fix those first, or lead with the Receivables table rebuild (finding 6) that the cold reader named as the top debt?
2. Scope: all 25 findings in Wave 8, or P0 + P1 (13 items) with P2 deferred to the polish pass?
3. Density: accept a 14 px table body and 16 px card padding on Business pages (the references' density), or keep today's 16 px everywhere and accept 2+ screens?
