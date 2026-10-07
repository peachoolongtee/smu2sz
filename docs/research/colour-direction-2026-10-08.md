# Colour direction for FLOW: blending `dev` and `feat/upgrading`

Date: 2026-10-08. Branch read: `dev` (apps/web/app/globals.css, components/ui.tsx, charts.tsx) and `feat/upgrading` (globals.css with the `.biz` theme, components/business/kit.tsx, status-block.tsx, next-action.tsx, cash-forecast.tsx). Screenshots: docs/screenshots/wave7-2026-10-08 and docs/screenshots/upgrading-2026-10-08, Home day 0, Deals evaluated, Cash day 0, Home day 34 pending, Approvals pending, Demo story. Swatch page: `colour-direction-2026-10-08.html` beside this file.

The brief, in the owner's words: add colour and make things pop where it brings attention or contrast to something, and blend the two looks. The readers are a CEO, a finance director and a negotiator. The product must look trustworthy, calm when healthy, unmistakable when action is needed, and the same on Home, Deals, Cash & funding, Receivables, Activity and Approvals.

## 1. What the research says

1. [W3C, Understanding WCAG 2.2 SC 1.4.11 Non-text Contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast): component boundaries that must be seen (inputs, buttons, focus rings, chart lines, status marks) need 3:1 against adjacent colours; text needs 4.5:1 (3:1 at 18.66 px bold or 24 px).
2. [Material Design, tone-based surface colour](https://material.io/blog/tone-based-surface-color-m3): hierarchy on a light theme comes from a small ladder of tinted surfaces (lowest to highest), not from shadows or from colouring each card differently.
3. [Salt (J.P. Morgan), semantic use of colour](https://main.saltdesignsystem.com/salt/foundations/color/semantic-use-of-color): status tokens are named by meaning (error, warning, success, info), each with a background, border and foreground, and are never borrowed for decoration.
4. [SAP Fiori, using semantic and industry-specific colours](https://www.sap.com/design-system/fiori-design-web/v1-96/foundations/best-practices/ui-elements/how-to-use-semantic-colors): semantic colours only where they carry a state, always paired with text or an icon, and kept apart from brand and chart colours.
5. [Inkbot, the 60-30-10 rule and the "one accent"](https://inkbotdesign.com/60-30-10-rule/): 60 % neutral canvas, 30 % structure, 10 % one accent used strictly for the primary action; the accent works because it is scarce (the von Restorff effect).
6. [Refactoring UI, 7 practical tips](https://medium.com/refactoring-ui/7-practical-tips-for-cheating-at-design-40c736799886): design buttons by hierarchy, not semantics: one filled primary per page, outlined secondaries, link-style tertiaries; a destructive action is red only when it is also primary.
7. [Datawrapper, emphasise with colour](https://www.datawrapper.de/blog/emphasize-with-color-in-data-visualizations): grey is the most important colour in a chart; colour the one series the reader must see and let the rest recede.
8. [Progress, choosing colours for fintech](https://www.progress.com/blogs/how-choose-right-colors-fintech): blue is the anchor colour of trust in finance; gradients are the disruptor's move and should be a deliberate brand decision, not a default.
9. [Windmill Digital, psychology of colour in financial apps](https://windmill.digital/insights/psychology-of-color-in-financial-app-design): cool, restrained palettes read as professional; cultural meaning matters (in China red is prosperity and markets show gains in red), so red and green must never be the only carrier of direction.
10. [Eggradients, gradient UI in 2026](https://www.eggradients.com/blog/gradient-ui-in-2026): a gradient earns its place in at most one hero or one CTA; text over a gradient must pass contrast at every stop or the gradient is clutter.
11. [Betterment design capture](https://www.shadcn.io/design/betterment/raw): a midnight-navy block above the fold, then a light canvas below, is a proven finance pattern: the dark block takes attention once, the light sections feel open after it.

## 2. What each look does for the three readers

### `dev` (flat, white cards, one blue)

Does well. Colour already means something: `ok`, `warn`, `bad`, `info` each have a bg, line and fg, and every status colour is paired with a word ("ACTION NEEDED", "Worst point", "Does not cover the gap"). Text contrast is excellent everywhere (ink 17:1, ink-3 5.2:1, every status fg on its bg 5.8 to 7.4:1). One brand blue, one filled primary per card. The finance director gets a calm, tabular page; the chart reads correctly (blue actual, green dashed plan, red dashed reserve, red band, amber worst point).

Does badly. The level-1 answer does not lead. On Home day 0 the hero is a white card distinguished from the next card only by a 1 px `warn-line` edge (#ecd092, 1.5:1 against white, invisible at a glance) and a small pill; the eye lands on the blue "Run funding plan" button two cards down before it reads the headline. Two blue filled buttons compete on Deals ("See what we'd offer back" in the next-step bar and "Send this counter"), so the one-accent rule is broken. Secondary buttons, inputs and the account button use `line-strong` (#c3cdd9, 1.6:1), which fails SC 1.4.11 for a boundary that must be seen. Status colour is also used as decoration: the WeChat channel chip is `ok` green and the owner's initial disc is `ok` green, so green stops meaning "fine". On day 34 the home has three amber blocks (hero edge, the agent's answer strip, the decision row) plus a red receivable row and a red activity dot; everything is a warning, so nothing is. The pending home also shows a subtle-grey "agent's answer" band that is neither card nor status. Overall the CEO gets the right words but no visual order; the negotiator gets no single "do this" on Deals.

### `feat/upgrading` (`.biz` theme, navy-to-purple hero, pills, backdrop art)

Does well. Level 1 finally leads: the hero is a dark block with the status word, the one-line answer and today's cash at 60 px, and the three small figures sit in translucent tiles beneath. The breach and worst-point figures are tinted red on the block (#fca5a5 on #0d2a7a, 6.8:1). Pill nav with a filled active state, pill buttons, larger radii and bigger type make the pages feel like a consumer banking app; the inner pages keep white cards; the option list on Cash & funding is clean, with the three badges (Recommended, Does not cover the gap, Not available) carrying the only colour.

Does badly. The hero's colour is constant: SAFE and CRITICAL get the same navy-to-violet gradient and only a 6 px dot changes (`bg-emerald-400`/`bg-amber-300`), so the block pops equally when the business is healthy and when payroll is at risk; "calm when healthy" is lost. Inside the hero four rainbow shortcut bubbles (violet, teal, orange, pink) compete with the answer, and their white icons fail non-text contrast (white on #f59e0b 2.2:1, on #2dd4bf 1.9:1). The gradient primary button fails AA text contrast at its middle stop (white on #3b6dff 4.4:1 for 14 px semibold), and the gradient repeats on the page icons and the "Recommended next step" spark tile, so the brand accent is no longer scarce. Each page gets its own hue (Deals violet, Cash teal, Approvals orange), and buyer avatars are hashed across six hues, so colour that should mean status now means "which page" or "which initial". Summary tiles are tinted by position (`nth-child(4n+1)` blue, red, green, violet), which gives a cost figure a red tint and a date a green one for no reason. The `.biz` hairlines (#eceef1, 1.16:1) and borderless grey secondary pills (#f1f2f4 on white, 1.1:1) make boundaries disappear; the drifting blobs and dot grid add noise behind the figures. `kit.tsx` reaches for 45 raw Tailwind palette classes outside the token file, so the system cannot be retuned from one place. The finance director sees decoration where she expects meaning; the negotiator's "Recommended" badge has to fight a violet page icon.

## 3. The blend

### 3.1 Tokens (light theme; `dev` has no dark theme)

Everything below extends `dev`'s `@theme`. Existing values are kept where they pass; new tokens are marked. Ratios are WCAG 2.x luminance contrast.

| Token | Hex | Use | Checked pair, ratio |
|---|---|---|---|
| `canvas` | #f5f7fa | page background | ink on canvas 15.96 |
| `surface` | #ffffff | cards | ink 17.13, ink-2 8.21, ink-3 5.21 |
| `subtle` (surface-2) | #eef2f6 | tiles inside cards, table heads, segmented track | ink 15.23, ink-3 4.63 |
| `brand-50` (surface-brand) | #eaf1fc | selected row, recommended option, next-step bar | brand-700 on it 7.70; ink 15.08 |
| `line` | #dde3ea | decorative hairlines only | 1.29 vs white (not a UI boundary) |
| `line-strong` | #c3cdd9 | dividers between dense rows | 1.61 vs white (decorative) |
| `line-ui` new | #7f8ea3 | borders that must be seen: inputs, secondary buttons, account button | 3.33 vs white (SC 1.4.11 pass) |
| `ink` | #0f1c2e | headlines, figures | see above |
| `ink-2` | #3f5068 | body, labels | 8.21 on white, 7.30 on subtle |
| `ink-3` | #5d6e84 | captions, axis text | 5.21 on white, 4.63 on subtle, 4.86 on canvas |
| `brand-600` | #1558c0 | the one filled primary, active nav text/icon, links, focus ring | white on it 6.59; on white 6.59 |
| `brand-700` | #0f479c | primary hover, text on brand-50 | white on it 8.74; on brand-50 7.70 |
| `brand-100` | #d6e4f9 | brand badge line | decorative |
| `brand-900` new (deep) | #0b1f4d | the Home hero block, Demo top strip | white on it 15.94 |
| `on-deep` new | #ffffff | hero headline and figures | 15.94 |
| `on-deep-muted` new | #b7c3d9 | hero captions | 8.97 on brand-900 |
| `ok-fg` / `ok-bg` / `ok-line` | #0b6b48 / #e5f5ed / #b2dec6 | status "fine" on light | fg on bg 5.80, on white 6.54 |
| `ok-solid` new | #1a8a5a | dots, 3 px rails, chart marks | 4.35 vs white |
| `ok-bright` new | #6fdcae | filled pill on the deep block | 9.51 vs brand-900; ink on it 10.22 |
| `warn-fg` / `warn-bg` / `warn-line` | #82490a / #fdf2d9 / #ecd092 | "needs you", pending | fg on bg 6.50, on white 7.23 |
| `warn-solid` new | #b7791f | dots, rails, worst-point dot | 3.64 vs white |
| `warn-bright` new | #f5b942 | filled pill on the deep block | 9.03 vs brand-900; ink on it 9.71 |
| `bad-fg` / `bad-bg` / `bad-line` | #a3241a / #fdecea / #f1b9b2 | breach, late, refused | fg on bg 6.50, on white 7.43; white on fg 7.43 |
| `bad-solid` new | #d2362a | dots, rails | 4.88 vs white |
| `bad-bright` new | #ffb4ab | breach and worst-point figures on the deep block | 9.39 vs brand-900; ink on it 10.09 |
| `info-fg` / `info-bg` / `info-line` | #1447a6 / #e8f0fd / #b9cff4 | neutral notices | fg on bg 7.38 |
| `info-solid` new | #2f6fe0 | dots | 4.70 vs white |
| `info-bright` new | #a9c8ff | WATCH pill on the deep block | 9.41 vs brand-900; ink on it 10.11 |
| `chart-base` | #1558c0 | "If you do nothing" line (= brand-600) | 6.59 vs white |
| `chart-plan` | #0b6b48 | "With the recommended plan", dashed (= ok-fg) | 6.54 |
| `chart-reserve` | #a3241a | minimum reserve, dashed (= bad-fg) | 7.43 |
| `chart-danger` | #fdecea at 80 % | band below the reserve (= bad-bg) | fill, not a boundary |
| `chart-worst` | #b7791f | worst-point dot with white ring (= warn-solid) | 3.64 |
| `chart-grid` / `chart-axis` | #dde3ea / #5d6e84 | grid, axis text | axis 5.21 |
| `focus` | #1558c0, 2 px, 2 px offset | focus ring on light | 6.59 vs white, 5.80 vs brand-50 |
| `focus-on-deep` new | #ffffff | focus ring inside the hero block | 15.94 (brand-600 on brand-900 is 2.42, fails) |

Every text pair above is at or above 4.5:1; every boundary that must be seen is at or above 3:1. The chart's `chart-worst` and `line-ui` sit near the floor on purpose: they are marks, not text.

### 3.2 Component map

| Component | Treatment |
|---|---|
| Home hero | A deep brand block: solid `brand-900`, no gradient, no backdrop, 1.25 rem radius. Status word as a filled pill (`warn-bright`/`bad-bright`/`ok-bright`/`info-bright` with `ink` text), the one-line answer in `on-deep`, today's cash large, three figure tiles in white at 8 % with `on-deep-muted` labels; the breach and worst-point figures take `bad-bright`; the reserve stays white. Why this surface: the research pattern (dark block then light canvas) gives level 1 the attention once; a solid navy is calm when the pill is green and unmistakable when it is amber or red, because the status element changes, not the block; a tinted brand surface would read as an info callout and a white card with a 1 px edge did not lead. The same block is reused only on Home. Cash & funding's "Cash risk" card stays white with a 3 px `-solid` left rail and a light pill. |
| Status pill | On the deep block: filled `-bright` bg, `ink` text, uppercase 11 px, no dot. On light: `dev`'s tinted pill plus a 6 px `-solid` dot. Always a word. |
| Headline figures | `ink` on light, `on-deep` on the hero. A figure is coloured only when it is the status (first breach, worst point, cost over limit): `bad-fg`/`warn-fg` on light, `bad-bright` on deep. Never tint a figure by position. |
| Three fact tiles | `subtle` surface, `line` hairline, label `ink-3`, value `ink`. The "Who decides" tile alone takes `ok-bg`/`ok-fg` when within mandate or `warn-bg`/`warn-fg` when it needs the owner. |
| Primary button | One per page: `brand-600` fill, white text, hover `brand-700`, 0.5 rem radius (pill shape optional, colour not). On Deals it is "Send this counter"; the next-step bar's button becomes secondary. |
| Secondary / ghost / danger | Secondary: `surface`, `line-ui` border, `ink` text, hover `subtle`. Ghost: `ink-2` text only. Danger (`bad-fg` fill, white) only when destructive and primary (Decline on Approvals is secondary). |
| Next-step bar | `brand-50` surface, `brand-100` hairline, arrow and bold lead in `brand-700`, body `ink-2`; its action is a secondary button or link. |
| Inbox rows | White; the shown row gets `brand-50` with a 3 px `brand-600` rail; channel chip neutral (`subtle`/`ink-2`), never `ok`; the blocked-message footer `bad-fg` text on white with a `bad-solid` dot. |
| Decision cards by action | Within mandate / executed: `ok` rail and pill. Needs your approval / pending: `warn`. Refused, blocked, does not cover the gap, late: `bad`. Counter recommended: `brand-50` surface with `brand-600` rail and "Recommended" badge (a recommendation is brand, not status). No deal / closed: neutral with the reason in `ink-2`. |
| Counter cards (Options A/B/C) | Recommended option: `brand-50`, `brand-600` rail, brand badge; others white with `line` border; the price in `ink`; only the status badge is coloured. |
| Options groups and badges | Rows on white, `subtle` group headers; badges: Recommended = brand (`brand-50`/`brand-100`/`brand-700`), Not available = neutral, Does not cover the gap = bad, Needs approval = warn. |
| Current-funding card | White; utilisation bar `brand-600` on a `subtle` track, the over-limit segment `bad-solid`; headroom figure `ink`, turning `warn-fg` under 10 %. |
| Chart | `chart-base` solid 2 px, `chart-plan` dashed, `chart-reserve` dashed, `chart-danger` band, `chart-worst` dot with white ring, breach dot `bad-fg`; grid/axis greys; event labels `ink-2`. Legend uses the same five tokens and nothing else. |
| Navigation pills (desktop) | Text `ink-2`; active `brand-50` bg + `brand-700` text (keeps `dev`); the branch's black active pill is dropped as a fifth colour. |
| Phone tab bar | `surface`, top `line` hairline, inactive `ink-3`, active `brand-600` icon and label (6.59), approvals count as a `warn` badge. |
| Account button | `surface`, `line-ui` border, initial disc `brand-50`/`brand-700` (not green). |
| Badges and chips | Status: tinted bg/line/fg. Non-status (tier, count, channel, "Demo data"): `subtle`/`ink-2`. Brand badge only for "Recommended". |
| Warning and refused states | Callout `warn-bg`/`warn-line`, title `warn-fg`, body `ink-2`, icon `warn-fg`. Refused: `bad-bg`/`bad-line`, title `bad-fg`, body `ink-2` (not the whole paragraph in red). |
| Demo mode shell | Visibly different from Business: `canvas` page, flat white cards as `dev`, plus a 2.25 rem top strip in `brand-900` carrying "DEMO" in `info-bright` and "synthetic data, no funds move" in `on-deep-muted`; the Demo shell never shows the deep hero. |
| Buyer avatars | `subtle` disc, `ink-2` initials; no hashed hues. |

### 3.3 Rules

1. Level 1 (what is visible before scrolling) may carry at most four chromatic colours: `brand-900` (the hero), `brand-600` (one primary), one status tone, and the chart set if a chart is on screen. Everything else is ink and grey.
2. Gradients: nowhere. Not on the hero, buttons, icons or tiles. If the lead wants one, the only admissible place is a tone-on-tone depth in the hero (`brand-800` to `brand-900`) with no hue shift and text checked at every stop.
3. Icons are `currentColor`: `ink-3` in rows, the status fg inside a status callout, white on brand fills. No coloured icon discs, no per-page hue.
4. Pop is earned: one `brand-600` fill per screen marks the thing to do; status colour marks status and nothing else; a figure is coloured only when it is the status; the hero is the only deep block.
5. Every boundary that must be seen (inputs, secondary buttons, rails, dots, chart lines, focus) uses `line-ui` or a `-solid`/`-bright` token (3:1); `line` and `line-strong` are decoration.
6. Colour never speaks alone: every status colour sits beside a word or an icon (red and green have opposite market meanings for the Chinese reader).
7. Raw Tailwind palette classes are forbidden in components; every colour comes from the token file.

## 4. Options and verdict

**A. `dev` flat plus a tinted brand hero and stronger status colour.** The hero becomes a `brand-50` card with a 3 px status rail and a filled pill; `line-ui` fixes the boundaries; the rest stays. Verdict: the cheapest change and the calmest page, and it fixes every contrast failure, but the hero now looks like the next-step bar and the recommended option (all `brand-50`), so level 1 still does not lead and the CEO's eye still goes to the blue button first. Adequate for the finance director, weak for "pop" and for the negotiator.

**B. The branch's hero toned down to one gradient-free navy block with white cards below.** Keep `feat/upgrading`'s layout, pills and radii; make the hero solid `brand-900`; drop the gradient button for `brand-600`. Verdict: level 1 leads and the banking-app feel survives, but if the rest of the `.biz` system stays (rainbow shortcuts and avatars, per-position tile tints, page-icon hues, blobs, 45 palette classes) the status still competes with decoration and the token file still cannot retune the product. B fixes the one block, not the system.

**C. The middle (recommended).** Take the branch's one idea that serves the readers, the answer as a deep balance card, and `dev`'s discipline that colour is meaning. Solid `brand-900` hero on Home only, status carried by a filled bright pill and status-tinted figures; four surface tiers for hierarchy; one `brand-600` primary per page; `-solid` tokens for rails, dots and chart marks so every mark passes 3:1; the chart set fixed; no gradients, no rainbow, no backdrop; status tokens never borrowed for channels, avatars or pages; the Demo shell distinct by a dark strip. Verdict: calm when the pill is green (a navy card with white figures is quiet), unmistakable when it is amber or red (the brightest object on the page is the status word), trustworthy because the palette is blue, white and grey with colour only where it means something, and consistent because every page is built from the same tokens and the deep block appears once.

Recommendation: C. Implementation order: add the new tokens to `globals.css`; replace `line-strong` with `line-ui` on buttons and inputs; recolour the channel chip and account disc; build the hero from `brand-900` with the pill logic; demote the next-step bar's button; then port the branch's layout (pill nav, tiles, option rows) without its palette classes.
