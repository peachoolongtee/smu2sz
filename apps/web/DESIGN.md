---
name: FLOW web
description: A light fintech surface for a supplier's owner (midnight-blue ink, royal-blue action, sans headlines in weight 800, a sidebar on the canvas), status colour only for status, five section hues for wayfinding, Home seamless with one raised decision card, three card types, one segmented control, one state vocabulary, a seven-role type scale, six motion durations, and the navy block kept for the Demo strip.
colors:
  canvas: "#f5f7fb"
  surface: "#ffffff"
  subtle: "#eff3f8"
  line: "#e6e9ef"
  line-strong: "#d3d9e2"
  track: "#eef1f5"
  line-ui: "#768399"
  ink: "#24324a"
  ink-2: "#4d5767"
  ink-3: "#5a6577"
  brand-50: "#e6f1ff"
  brand-100: "#d0e5ff"
  brand-300: "#8fb6ff"
  brand-600: "#0368e9"
  brand-700: "#0048a5"
  brand-900: "#24324a"
  on-deep: "#ffffff"
  on-deep-muted: "#bcc6d6"
  ok-fg: "#0a6b5f"
  ok-bg: "#e2f6f3"
  ok-line: "#a6e0d7"
  ok-solid: "#12907f"
  ok-bright: "#5ee3d8"
  warn-fg: "#82490a"
  warn-bg: "#fdf2d9"
  warn-line: "#ecd092"
  warn-solid: "#b7791f"
  warn-bright: "#f5b942"
  bad-fg: "#a3241a"
  bad-bg: "#fdecea"
  bad-line: "#f1b9b2"
  bad-solid: "#d2362a"
  bad-bright: "#ffb4ab"
  info-fg: "#0048a5"
  info-bg: "#e6f1ff"
  info-line: "#bcd8fd"
  info-solid: "#0472ff"
  info-bright: "#9bc7ff"
  sec-home-bg: "#e6f1ff"
  sec-home-fg: "#0048a5"
  sec-home-solid: "#0368e9"
  sec-deals-bg: "#f1e9ff"
  sec-deals-fg: "#5b2bbf"
  sec-deals-solid: "#7c4ddb"
  sec-cash-bg: "#dcf5f3"
  sec-cash-fg: "#0a6366"
  sec-cash-solid: "#0f8a8a"
  sec-recv-bg: "#fdeee0"
  sec-recv-fg: "#8f3f05"
  sec-recv-solid: "#c4570c"
  sec-activity-bg: "#fce9f1"
  sec-activity-fg: "#a3225a"
  sec-activity-solid: "#c7366e"
  chart-base: "#0472ff"
  chart-plan: "#12907f"
  chart-reserve: "#a3241a"
  chart-danger: "#fdecea"
  chart-worst: "#b7791f"
  chart-grid: "#e6e9ef"
  chart-axis: "#5a6577"
  chart-teal: "#38d0c7"
  chart-purple: "#9b5fff"
  chart-sky: "#9bc7ff"
  chart-navy: "#24324a"
  focus: "#0368e9"
  focus-on-deep: "#ffffff"
typography:
  display:
    fontFamily: "'Plus Jakarta Sans Variable', 'Plus Jakarta Sans', Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "36px"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.025em"
  value:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "30px"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  section:
    fontFamily: "'Plus Jakarta Sans Variable', 'Plus Jakarta Sans', Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "20px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "-0.015em"
  card-title:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "16px"
    fontWeight: 700
    lineHeight: 1.375
  body:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  supporting:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.38
  label:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "0.025em"
  mono:
    fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.625
rounded:
  pill: "9999px"
  card: "14px"
  decision: "16px"
  tile: "10px"
  control: "8px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  2xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.brand-600}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
    typography: "{typography.body}"
  button-primary-hover:
    backgroundColor: "{colors.brand-700}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-secondary-hover:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-danger:
    backgroundColor: "{colors.bad-solid}"
    textColor: "{colors.surface}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
  button-sm:
    rounded: "{rounded.control}"
    padding: "0 12px"
    height: "32px"
    typography: "{typography.label}"
  toggle-active:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-700}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "40px"
  nav-pill-active:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.brand-700}"
    rounded: "{rounded.pill}"
    padding: "0 14px"
    height: "36px"
  badge-ok:
    backgroundColor: "{colors.ok-bg}"
    textColor: "{colors.ok-fg}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
    typography: "{typography.label}"
  chip-neutral:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    padding: "2px 10px"
    typography: "{typography.label}"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "40px"
    typography: "{typography.body}"
  textarea:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "10px 16px"
    typography: "{typography.body}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px"
  stat-tile:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.tile}"
    padding: "12px 16px"
  demo-strip-deep:
    backgroundColor: "{colors.brand-900}"
    textColor: "{colors.on-deep}"
    rounded: "{rounded.control}"
    padding: "6px 16px"
  decision-card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.decision}"
    padding: "16px 20px"
  selected-card:
    backgroundColor: "{colors.brand-50}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px"
  segmented-track:
    backgroundColor: "{colors.track}"
    rounded: "{rounded.pill}"
    padding: "2px"
    height: "48px"
    border: "1px solid {colors.line-ui}"
  segmented-pill-selected:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    height: "44px"
  avatar:
    backgroundColor: "{colors.subtle}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.pill}"
    size: "36px"
    typography: "{typography.label}"
---

# Design System: FLOW web

The single reference for the look of `apps/web`, recorded from the shipped build (branch `feat/strategy-mvp`, 8 October 2026). The tokens live in `app/globals.css` (`@theme static`, so Tailwind generates a utility for each and a chart can read them with `var()`); components take every colour, radius, shadow and duration from there, and no hex appears anywhere else in `app/`, `components/` or `lib/`. The frontmatter above is normative; the prose says where and why. The colour reasoning is in `docs/research/colour-direction-2026-10-08.md`; the words are in `docs/UX_SIMPLIFICATION_BRIEF.md`; the sidecar for the live panel is `.impeccable/design.json` beside this file.

## Overview

**Creative North Star: "The Owner's Ledger, Lifted"**

A light, flat, calm surface for a supplier's owner who reads cash the way a banker reads a statement: a faintly cool canvas under solid white cards, one confident blue that only ever means "the next step", and status colour that only ever means status and always comes with a word. The one deep moment is the navy Demo strip. Home has no hero card: the status pill, the headline and one chart sit directly on the page, and the attention card is the one raised surface, a solid decision card on one soft shadow. Density is a banking app's: 14 px data in rows and tables, 16 px inside a card, fact tiles with a 12 px label, a 20 px figure and a 13 px caption, 24 px of air between sections.

Depth is "lifted base": a standard card rests on a hairline alone, the decision card on one soft shadow, a row lifts one pixel on hover, a sheet or dialog takes a deeper pop. Motion is six durations and two easings, transform and opacity only; nothing moves the layout (the cash picture's one draw on mount is the single, named exception); under reduced motion only opacity transitions remain. Wayfinding is in colour: each of the five Business sections owns a hue that appears on its icon chip, its tab, its shortcut and a buyer's avatar, never on a status. Both the English and the Chinese shells live in one type stack that falls through to the system's Latin and CJK faces: no web font is fetched from a font host.

Confirmed rejections: no dark theme (`color-scheme: light`), no gradient on a button or a card, no glow, particle, parallax or glassmorphism (no frost, no backdrop blur, no blurred discs), no count-up on load, no decorative badge, no coloured rail on a card's edge (the selected card's 3 px accent rule and the "why" rule are the two left rules there are), no runtime web fonts (a font is bundled with the app or it is not used), no browser-drawn sparklines (a labelled chart drawn from the server's own series, with its figures in the server's strings, is not a sparkline: it has days along its foot, named lines, a named reserve and a table behind it), no text below 12 px, no figure or qualification below 13 px, and no money computed in the browser (every figure, date and sentence arrives formatted from the server).

**Key Characteristics:**
- Light only, flat materials, white cards on a cool `canvas`; three card types (standard, decision, selected); Home is seamless (no hero card, rows with hairlines) with one raised decision card.
- One brand blue for the page's single primary action, links, focus and selection; never a status.
- Status tokens (`ok`, `warn`, `bad`, `info`) in five weights each, always paired with a word.
- Five section hues for wayfinding only; teal and orange pushed away from green and amber.
- One radius scale of five: 8 px controls (buttons, toggles, fields), 10 px inner tiles, 14 px cards, 16 px the decision card, and a pill for badges, chips, avatars and the segmented track and pill.
- 14 px body and data, 13 px for any qualification of a figure, 12 px for metadata only, tabular figures, right-aligned money that never wraps.
- Six motion durations (80 / 140 / 220 / 280 / 350 / 500 ms) and two easings, reduced motion honoured and forced in tests.
- 44 px touch targets wherever a finger is the pointer, through a transparent hit area.

## Colors

A faint cool canvas, white surfaces, three inks, one blue in five weights, four status tones in five weights, five section hues, and one deep navy. Values are in the frontmatter; the roles and the computed WCAG 2.x ratios are here.

### Primary (brand)
- **Brand blue** (`brand-600`): the page's one primary fill, text links, the focus ring, the caret and checkbox accent, the cash line in the chart. White on it is 5.0:1 (`#0472ff` itself, 4.3:1, is for chart marks and information, never for text).
- **Deep brand** (`brand-700`): the primary's hover; link text and the selected toggle's text (8.5:1 on white, 7.9:1 on canvas, 7.4:1 on `brand-50`).
- **Brand tints** (`brand-50`, `brand-100`): the selected toggle's fill, the active nav pill, the next-step band, the "Recommended" badge; `brand-100` is the text selection colour.
- **Navy** (`brand-900`): the deep block, used for the Demo strip and nothing else (Home no longer has one). Text on it is `on-deep` (12.8:1) and `on-deep-muted` (7.4:1); a fact tile on it is `on-deep` at 10% over the navy (`#3a465c`), where `on-deep` is 9.5:1, `on-deep-muted` 5.5:1 and the bright status figures 5.6 / 5.3 / 6.0:1 (bad / warn / ok). Brand blue on navy is only 2.5:1, so the focus ring turns white inside `.on-deep`.

### Secondary (status, four tones)
Each of `ok`, `warn`, `bad`, `info` has `-fg` (text), `-bg` (tint), `-line` (tint border), `-solid` (a mark that must be seen: the dot, a chart mark, 3:1 or better) and `-bright` (a pill or figure on the deep block). Computed: fg on its own bg 5.7 / 6.4 / 6.5 / 7.4:1; fg on white 6.4 / 7.2 / 7.4 / 8.5:1; solid on its own bg 3.5 / 3.2 / 4.2 / 3.7:1; solid on white 3.9 / 3.6 / 4.8 / 4.3:1; white on `bad-solid` (the danger button) 4.8:1; `ink` on the bright pill (the hero's status) 7.5 / 7.3 / 8.2:1 (bad / warn / ok). A status colour means that status and nothing else.

### Tertiary (section hues, wayfinding only)
Each section has a tint (`bg`), the text on that tint (`fg`) and a `solid` (the fill behind a white icon, or an icon on white). Home is the brand blue, Deals violet, Cash teal (bluer than `ok` green on purpose), Receivables orange (redder than `warn` amber on purpose), Activity rose. Computed: fg on bg 7.4 / 7.0 / 6.1 / 6.4 / 6.1:1; white on solid 5.0 / 5.3 / 4.1 / 4.4 / 5.0:1 (so a solid icon on a white tab bar is the same); fg on white 8.5 / 8.2 / 7.0 / 7.2 / 7.1:1. Buyer avatars use four of the five tints (not orange, which sits next to the warning amber) so an avatar cannot read as a status.

### Chart
Seven tokens for the cash chart's marks and nothing else: `chart-base` (the line you read, 4.3:1 on white, 3.7:1 on the danger band: a 2.5 px line, held to the 3:1 of a mark), `chart-plan` (the recommended plan, 3.9:1: a 2 px dashed line), `chart-reserve` (the floor, 7.4:1), `chart-danger` (the band below the floor, `bad-bg`), `chart-worst` (the worst point, 3.6:1 on white, 3.1:1 on the band: a 2 px mark, not text), `chart-grid` (`line`) and `chart-axis` (`ink-3`, 5.8:1 for the 12 px axis labels). The deal picture adds `chart-teal`, `chart-purple`, `chart-sky` and `chart-navy` for its bars and slices: they separate series, are named beside each mark in words, and carry no text.

### Neutral
- **Canvas** (`canvas`): the page behind the cards (a faint cool tint).
- **Surface** (`surface`): cards, sheets, inputs, the header and the tab bar.
- **Subtle** (`subtle`): quiet fills: the segmented track, the nav track, table heads, skeletons, hover on a secondary button.
- **Line / line-strong** (`line`, `line-strong`): hairlines and dividers (1.2:1 on white: decoration, not a boundary that must be seen). `line-strong` is the dashed edge of an empty state.
- **Line-ui** (`line-ui`): any boundary that must be seen: inputs, secondary buttons, the segmented track, the account button (3.8:1 on white, 3.5:1 on canvas, 3.4:1 on subtle).
- **Ink / ink-2 / ink-3** (`ink`, `ink-2`, `ink-3`): text primary, secondary, quiet. `ink` 12.0:1 on canvas, 12.8 on white; `ink-2` 6.8 on canvas, 7.3 on white, 6.5 on subtle; `ink-3` 5.4 on canvas, 5.8 on white, 5.2 on subtle, 5.1 on `brand-50`, 5.5 on an open table row (`subtle` at 60% on white), 5.5 on a late row (`bad-bg` at 40% on white). `ink-3` is for captions, never for anything the owner must act on.
- **Focus** (`focus`, `focus-on-deep`): the brand ring, 4.7:1 on canvas, 5.0:1 on white, 4.4:1 on `brand-50`; white inside the deep block (12.8:1).

### Named Rules
**The One Primary Rule.** One brand-filled action per page. Every other step is a secondary button, a ghost, or a text link.
**The Status Speaks Rule.** Status colour means status and nothing else, and it is never the only channel: the word is always there, the dot or tint is the second voice.
**The Hue Is a Place Rule.** A section hue says where you are or where a link goes; it never says how things are going.
**The Deep Block Rule.** `brand-900` is the Demo strip only. It stays navy.
**The One Raised Surface Rule.** On Home the attention card is the only raised surface: a `DecisionCard` (solid `surface`, a hairline and `--shadow-decision`), and the plan's bar, where it is sticky, is the same card, sticky at the bottom of the window from `lg` until the reader reaches its place. There is no frost and no backdrop blur anywhere. Everything else on Home sits on the canvas, separated by hairlines; a block that asks the owner to decide something (an approval, the remaining task) keeps the white card.
**The 4.5 / 3 Rule.** Every text pair 4.5:1 or better, every visible boundary and icon 3:1 or better, on the surface it actually sits on (tiles, rows, discs and tints included).

## Typography

**Display Font:** Plus Jakarta Sans, weight 800, then the body sans below (`font-display`: page titles, the Home headline and its cash figure, the plan's title, the deal picture's figures)
**Body Font:** Lato if the machine has it, else Inter, then `ui-sans-serif` / `system-ui` and the platform's Latin and CJK faces (PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC)
**Label/Mono Font:** `ui-monospace`, SF Mono, JetBrains Mono, Menlo, Consolas (hashes, formulas, code)

**Character:** one sans family in two voices: the display voice is Plus Jakarta Sans at weight 800 with `-0.02em` to `-0.025em` tracking, everything else is the body sans. The face is bundled (`@fontsource-variable/plus-jakarta-sans`, imported once in `app/layout.tsx`, registered as "Plus Jakarta Sans Variable"): its woff2 files are served by the app itself, only the subsets a page uses are fetched, and nothing comes from a font host, so "no runtime web font" stays true where Google Fonts cannot be reached (the Demo is judged there). Lato is named first in the body stack so a machine that has it uses it; every stack falls back to faces the platform already has, and the layout must hold in the fallback (it is what the tests and the screenshots see). Weight does the work: 800 for headlines, 600 for titles, figures and labels, 500 for controls and row titles, 400 for sentences. Antialiased, `text-size-adjust: 100%`. The serif and the "Flow Figures" digit workaround are gone: a sans face sets lining figures by itself.

### Hierarchy
Seven roles, each a CSS variable in `app/globals.css` (`--text-*`, with a `--line-height` beside it) and a Tailwind size utility; the four that carry more than a size also have a kit class that adds the face, weight and tracking. Nothing is set between them.
- **Headline** (`.type-headline`, `--text-headline`: 26 px on a phone, 34 px from `md`, 36 px from `lg`; display face, 800, line-height 1.15, `-0.025em`): the one `h1` of a page: the Home headline, every `PageHeader` title (Deals, the customer's name, Receivables' answer), Cash's headline. The headline always dominates a value beside it (a value is never above 30 px), and on a phone 26 px keeps the primary action in the first screen.
- **Major value** (`.type-value`, `--text-value`: 24 px on a phone, 28 px from `sm`, 30 px from `lg`, 700, `tabular-nums`): the large figure of a fact tile (`Stat size="lg"`) and the Customer page's four figures.
- **Section** (`.type-section`, `--text-section`: 18 to 20 px, display face, 800): a block's title inside the page: the attention card's and the plan's title, the Deals queue's heading, the `Stat` figure at `size="md"` (`text-section`, weight 600).
- **Card title** (`.type-card-title`, `--text-card-title`: 16 px, 700): a `Card`'s heading.
- **Body** (`text-body`, 14 px, line-height 1.45; `text-body-lg`, 15 px, for the sentences that carry a page: the note under a headline, the stress sentences): sentences, data in a table or a row, controls. Headlines and card titles are `text-balance`; the sentences under them `text-pretty`.
- **Supporting** (`text-supporting`, 13 px, line-height 18 px): the floor for any financial qualification: a figure, a rate, a limit ("limit: at least 1.25×"), the caption under a fact, the words that say what a number is against, a status word, a table head, a basis sentence, a formula. A fact tile's caption, a `Badge`, a `StateWord` and `thCls` are 13 px.
- **Metadata** (`text-meta`, 12 px; 11 px is allowed, 10 and below is not): a small-caps eyebrow, a column or fact label, a time ("in 3 days"), an index mark, a legend. Never a figure and never a qualification: `e2e/design-system.spec.ts` fails on any visible text under 13 px that carries an amount, a rate, a multiple or a thousands group, on Home, Deals, Cash, Receivables and the Customer page, and, inside an SVG chart, any tick or line label that carries money or a date (`FONT` in `cash-picture.tsx`, the Recharts axes and reference lines are 13 px).
- **Mono** (400, 13 px, line-height 1.625): hashes (shortened, with copy), formulas (`Formula`, in a `subtle` tile).

### Named Rules
**The Thirteen Pixel Qualification Rule.** No text is set below 12 px, on any surface, in any language; metadata (a label, a time, a legend) may be 12 px, and nothing that states or qualifies a figure is below 13 px.
**The Tabular Money Rule.** A figure is `tabular-nums` and semibold or heavier; in a column it is right-aligned and never wraps. Figures are lining in every stack.
**The Sentence Before the Formula Rule.** A calculation is said in body text first; the formula follows in mono, in its own tile.

## Layout

From `lg` a sidebar of 15 rem on the canvas (the active item a white pill) and a centred column of 1120 px at most beside it, 16 px of side padding (40 px from `lg`), 20 px under the sticky header (32 px from `lg`). The header is the solid canvas: no blur, no translucency, no border. Sections sit 24 px apart (`space-y-6`, 28 px on Home); inside a card the padding is 20 px (`p-5`; 16 px in a selected strip or on a phone), a card's header row is 20 px by 16 px; tiles sit 12 px apart (`gap-3`); the chips and controls in a row sit 8 px apart (`gap-2`); the hero keeps its own 20 px. Everything is on a 4 px base.

Breakpoints are Tailwind's: `sm` 640 px, `lg` 1024 px, `xl` 1280 px, plus a 1440 px (`90rem`) step for the dock and a `touch:` variant that is "below `lg`, or a coarse pointer at any width". A row of three tiles is `grid-cols-2 sm:grid-cols-3` with the first tile spanning two columns on a phone. `KeyValueList` stacks label over value on a phone and goes two-column from `sm`. The cash chart on `/cash` is 256 px tall (320 px from `sm`); the Home cash picture is 250 px (300 px from 520 px wide) and is drawn at the width it has. Below `lg` the desktop pill nav is replaced by the fixed phone tab bar and the Demo sidebar by a menu.

**The dock.** A fixed bottom bar (the phone tab bar, the Demo stepper) publishes its measured height as `--dock-h` on `html` (`useDock` in `app-shell.tsx`; 0 when the bar is not fixed). `main` takes `.dock-pad`: the bar plus 24 px below `sm`, the bar plus 72 px (room for the Ask FLOW pill) from `sm`, 80 px from `lg` where there is no bar, and the pill sits in the sidebar's foot, not beside the column. `html` takes a matching `scroll-padding-bottom`, so the last row of a page and a focused control always clear both the bar and the pill.

**Touch.** Wherever a finger is the pointer every control reaches 44 px: `Button`, `toggleClass` and a `Disclosure` summary grow to `min-h-11` (the desktop 32 / 40 px look is unchanged); a small chip that must stay small (a segmented option, the account button, the copy-hash icon, a text link) keeps its look and takes `.hit`, a transparent 44 x 44 pseudo-element centred on it. Inline links in a sentence are exempt.

### Named Rules
**The 14 / 20 / 24 Rule.** 14 px data, 20 px inside a card (a `Card`'s body is `p-5`, its header 20 px by 16 px; the decision card 20 px, 16 px on a phone; a selected card 16 px), 24 px between sections.
**The Dock Rule.** Nothing fixed to the bottom covers content or another fixed thing: the bar measures itself and the page pads to it.
**The 44 px Rule.** Every control a finger can press reaches 44 px, by growing or by a transparent hit area; the desktop look does not change.

## Elevation & Depth

A lifted base: solid white cards on a cool canvas. Depth is a response to role and state, not decoration. A standard card rests on a 1 px hairline and no shadow; the decision card (the one thing the owner is asked to decide) takes `--shadow-decision`; a row, tile or option that leads somewhere lifts 1 px and takes `--shadow-lift` on hover (only on devices that hover); a sheet, menu, dialog, the chat panel and the Ask FLOW pill take `--shadow-pop`; a segmented control's selected pill takes the one-pixel `--shadow-pill`; the Demo strip fixed to the bottom of a phone casts `--shadow-up`. There is no tonal layering of surfaces (`subtle` is a fill for a track or a head, not a level), no translucent surface and no backdrop: the top bar is the solid canvas and the pages sit on the plain canvas.

### Shadow Vocabulary
- **Decision** (`--shadow-decision`: `0 1px 2px rgb(16 24 40 / 0.06), 0 8px 24px rgb(16 24 40 / 0.06)`): the decision card and nothing else.
- **Pill** (`--shadow-pill`: `0 1px 1px rgb(16 24 40 / 0.08)`): the selected pill of a segmented control.
- **Lift** (`box-shadow: 0 2px 4px rgb(15 28 46 / 0.06), 0 12px 22px -14px rgb(15 28 46 / 0.22)`): a row, tile or option on hover (`motion-lift`).
- **Pop** (`box-shadow: 0 4px 8px rgb(15 28 46 / 0.06), 0 18px 36px -12px rgb(15 28 46 / 0.24)`): the account sheet, the chat slide-over, the walkthrough card, the floating Ask FLOW pill, the skip link.
- **Up** (`box-shadow: 0 -4px 12px rgb(15 28 46 / 0.08)`): the Demo strip fixed to a phone's bottom edge.

### Named Rules
**The Hairline First Rule.** A card's edge is a 1 px `line`; the shadow is the whisper under it, never the boundary.
**The No Rail Rule.** No gradient on a button or a card, and no coloured rail on a card's edge but two: the selected card's 3 px accent rule (the choice the detail is about) and the "why" rule beside a reason. A status is a pill with a word, a tone is a 1 px tone line.

## Shapes

Five radii and nothing else (8, 10, 14, 16 and the pill). A control is a rounded rectangle (`8px`, `rounded-control`): buttons, toggles, text fields and selects. A container is a card (`14px`; the decision card alone is `16px`): cards, the hero, disclosure cards, tables, dialogs, the chat panel's edge, empty and error states, the drop zone, the walkthrough card and its spotlight. What sits inside a card is a tile (`10px`): fact tiles, list rows with a border, option rows, callouts, skeletons, formulas. What is a mark or a label is a pill (`9999px`): badges, chips, the segmented track and its pill, icon chips, avatars, the chat composer, the account button, a text link's hover. A button is not a pill: it is a control (`8px`). A state word has no container at all. A multi-line text area takes the card radius (a pill clips the corners of a second line). Borders are 1 px: `line` when decorative, `line-ui` when the edge must be seen, a tone's `-line` when the surface is a tint, dashed `line-strong` on an empty state. Icons are from `components/icons.tsx` only, at 16 or 20 px, `currentColor`; the one exception is a section chip, a 40 px disc (48 px `lg`) with a white 20 px icon on the section's solid.

## Components

All in `components/ui.tsx` unless noted. Motion classes are in `app/globals.css`.

### Buttons
- **Shape:** an 8 px rounded rectangle (`rounded-control`), 40 px tall (`min-h-10`), 16 px of horizontal padding, 14 px medium; compact is 32 px, 12 px padding, 12 px text; 44 px wherever a finger is the pointer. `motion-press`: scales to 0.98 while pressed, eases colour in 200 ms.
- **Primary:** the brand fill, white text, hover to `brand-700`. **One primary per page.** A link that is the next step is a `ButtonLink` (same shape); `buttonClass()` is the class for a span inside a link.
- **Secondary:** white with a `line-ui` border, hover `subtle`. **Ghost:** text only in `ink-2`, hover `subtle` and `ink`. **Danger:** `bad-solid` fill, white text, hover darkens 10%.
- **Focus:** the global ring, 2 px `focus` offset 2 px, following the element's own radius; white inside `.on-deep`. Never remove an outline.
- **Disabled / loading:** 50% opacity, `not-allowed`; a loading button shows the `Spinner` before its label and sets `aria-busy`; under reduced motion the arc is an ellipsis after the label.
- **Toggle** (`toggleClass(active)`): the pill that toggles (a preset, a scene, a filter), `aria-pressed`, in a `role="group"` above the list it filters. The selected one takes `brand-50`, a `brand-600` border (4.4:1 on the tint) and `brand-700` text; the rest look secondary. A filter that would repeat the whole list is not offered.
- **Text link** (`textLinkClass`, `a.underline`): `brand-700`, underlined, 12 px medium, a pill hover of `brand-50`; the underline thickens to 2 px on hover (no colour change). A card's quiet links ("All receivables", "Open approvals") are text links; a button is for a step.

### Chips and badges
- **Badge** (`tone`): a pill with its tint, its `-line` border and (for a status) a 6 px `-solid` dot; 13 px medium, 10 px by 2 px padding, `whitespace-nowrap`. Neutral and brand badges (a tier, a count, "Recommended") carry no status and no dot.
- **Chip:** a Badge without the dot, for a tag that carries no status (a channel, a kind). A label that is a whole server sentence (a plan's `role_reason`) takes `wrap`: it breaks inside its pill and never runs wider than its row.
- **Ranking:** wherever the server ranks, the rank is a numeral (a column in a table, `#1` on a Cash plan, a number before a buyer on a phone) and the order is the server's. "Recommended" is the brand badge wherever the server marks a row; an alternative says why in a neutral chip.

### Cards and containers
- **Card, DecisionCard, SelectedCard:** the three card types (see Design system, below, for when to use which). `Card`: `14px` radius, white, `line` hairline (`#e6e9ef`), no shadow (`.card-standard`), reveals on mount (`motion-reveal`). An optional header row (title 16 px bold, subtitle 13 px `ink-3`, actions on the right) with a hairline under it; the body is 20 px padding. A card's `tone` is a 1 px tone line, never a rail. A section with nothing in it is not a card around nothing: on Activity the empty Agreements and Refused sections are one quiet `ink-3` line each (title, colon, the sentence), and the empty Timeline is the same line inside its card.
- **Callout** (`tone`): a `10px` tile on the tone's tint and line; its title in the tone's fg, its body in `ink-2`.
- **TableWrap / table:** a scrollable `role="region"` with a card radius and hairline; heads are 13 px semibold `ink-2` on `subtle`; cells are 14 px with a `line` rule, 12 px by 8 px padding, last row unruled.
- **Link tile** (`DoorTile` in `app/cash/page.tsx`): a quiet bordered card-radius tile with what the door is for (14 px semibold, 12 px `ink-3` under it) and one text link stretched over the whole tile; lifts on hover.
- **Stat:** the one fact tile (hero tiles, Cash facts, Receivables summary, the Deals ceilings and recommendation facts, the Mandate limits, the next step's cost, landing and authority). A `10px` tile, 16 px by 12 px padding, in a `<dl>`: an uppercase 12 px semibold tracked label (`ink-3`), the figure (`tabular-nums`, 18 → 20 px, 20 → 24 px with `size="lg"`; its colour is a status only when `tone` names one), a 12 px `ink-3` caption (when, of what, against what; a second line is a second `block` span) and, only when the server sent a `delta_display`, a delta chip (neutral unless the server names its tone; the browser never subtracts). Two surfaces: `surface` (white, a `line` hairline) and `deep` (the Home hero: `on-deep` at 10%, label and caption in `on-deep-muted`, a status figure in its `-bright` tone). `tint` fills the tile with its status tint for the one tile that says who decides. A caption may carry a related figure (the headroom under the reserve and under the lowest point) with its own test id.
- **Avatar** (`kit.tsx`): a 36 px disc, 12 px bold. A change row's icon sits on its status tint; a buyer's initials sit on a section tint (`toneFor(name)` is stable per name, four hues, never orange).
- **Row** (`kit.tsx`): an avatar, the title (14 px medium) with a quiet 12 px line under it (in `bad-fg` or `warn-fg` only when the row's `tone` is that status), on the right the figure (14 px semibold tabular) with its note; with `href` the whole row is a link with the chevron and lifts on hover (`10px` radius, `subtle`). Rows are 48 px minimum and divided by hairlines.

### Inputs / Fields
- **Style:** `inputClass`: an 8 px rounded rectangle, 40 px, `line-ui` border, white, 16 px padding, 14 px `ink`, placeholder `ink-3`. `textareaClass`: the same in a card radius with 10 px by 16 px padding and relaxed leading. The caret is `brand-600`; checkboxes and radios take the brand accent.
- **Focus:** the global ring. **Disabled:** inherited from the button rules (50% opacity).
- **SegmentedTabs** (`components/ui/segmented-tabs.tsx`): the one segmented control, the owner's reference rendered light: a pill track (`track`, `#eef1f5`, inside a `line-ui` hairline so it reads on the canvas, 2 px inset), a raised white selected pill with its own hairline and `--shadow-pill`, each option an icon and a label and an optional count badge. The choice is not the pill alone (it is 1.15:1 on the track): the selected label is weight 800 with its icon in `brand-600`, the rest 600 in `ink-2`. It is a `role="tablist"` of `role="tab"` with `aria-selected`, one tab stop (the selected tab), the arrow keys, Home and End to move (the selection follows the focus), 44 px tall options. Each option is as wide as its own label (a weight-800 twin reserves the width, so choosing never resizes a tab); a long label wraps to two lines at the same height or is cut with its full text as the title, and never stretches its siblings. The pill is measured from the chosen tab and slides to it (`--dur-fast`, `--ease-select`, no overshoot; width and transform on an absolutely positioned span, so nothing in the layout moves; no transition under reduced motion, through `useReducedMotion`). With `scroll` (the queue's four tabs on a phone) the track scrolls sideways, fades out at the edge that has more, and keeps the chosen tab in view by its own `scrollLeft`, never the window's. Drop the icon where every option would carry the same one (the window tabs). It replaced the Receivables filter, the Deals queue tabs, the Home window and scenario switches, the Cash horizon and picture-view switches and the Activity filter; test ids are unchanged and the state is `aria-selected` now. The older `Segmented` (a radio group, because it is a form field: the Business/Demo and language switches, the chat's actor choice, the Deals buyer profile) keeps its track and takes the same `--shadow-pill` thumb.

### Navigation
- **Sidebar** (`app-shell.tsx`, from `lg`): the five sections as 44 px rows (icon and word) on the canvas, no fill of its own; the active one is a white pill with a whisper of shadow, `brand-700` bold text and `aria-current="page"`, the rest `ink-2` with a `subtle` hover. The header above it is sticky and solid canvas; the brand mark is a 32 px brand-blue disc. On a laptop (1024 to 1366 px, the `laptop:` variant) an icon button at its foot collapses it to a 4.5 rem rail of icons (see Design system, below).
- **Phone tab bar** (below `lg`): fixed to the bottom, white with a hairline over it and safe-area padding; five tabs of 56 px, icon over a 12 px word. The active tab's icon takes its section's solid, its word stays `ink`; inactive tabs are `ink-3`. A 2 px, 40 px wide bar in the section's solid slides to the active tab (`motion-slide`). Its last 3 rem below `sm` is Ask FLOW. A section whose word is too long for a fifth of a phone takes a shorter word (the link keeps its full name for assistive tools).
- **Ask FLOW** (`components/chat/chat-panel.tsx`, `.ask-trigger`): never floats over content (from `lg` the sidebar leaves no gutter, so the pill sits in the foot of the sidebar, in the room both sidebars keep for it). Below `sm` it is the last cell of the bottom bar, 48 by 56 px, icon over "Ask"; from `sm` a brand pill 16 px above the bar; from `lg` 12 px from the sidebar's left edge and 24 px above the bottom. It opens a native modal `<dialog>` that slides in from the right (`motion-panel`), 32 rem wide at most, white, a `line` left edge, `--shadow-pop`, over a 30% ink backdrop; its close button is a 40 px pill with a `line-ui` border.
- **Account sheet** (`AccountSheet`): a native `<details>` under a small 32 px pill button (`line-ui` border, a 24 px `brand-50` initial disc); the sheet is a 288 px card with `--shadow-pop` that drops in from its top-right corner (`motion-sheet`); its rows are 44 px pills. Escape closes it and returns focus to the button, a press outside closes it. Business: the identity, Limits, the tour, the language. Demo, below `lg`: mock or live data, who is signed in, the language.
- **Approvals shortcut:** a warn-tinted 32 px pill in the header (`warn-bg`, `warn-line`, `warn-fg` at 6.4:1 on `warn-bg`) when something awaits the owner.
- **Skip link:** visible on focus as a white pill with `--shadow-pop` at the top-left.
- **Demo strip:** the `brand-900` bar across the top of the Demo shell (`.on-deep`, 36 px, 12 px text); fixed to the bottom of a phone with `--shadow-up`.

### Page header
`PageHeader` (`section`, optional `icon`): a 20 px semibold title, a 14 px `ink-2` subtitle, actions on the right, 20 px under it. In the Business shell the title takes a 40 px round chip, a white 20 px icon on the section's `solid` (`components/section.tsx`, `PageIcon`). Every Business page and Approvals has one; the Demo shell keeps the flat look.

### Disclosure
`Disclosure` (`components/business/kit.tsx`) is the one fold, with the one chevron (`FoldChevron`, right-pointing, a quarter turn in 200 ms when open; the same chevron opens a table row). A native `<details>` whose body opens by height (`.disclosure-body`, a one-row grid from `0fr` to `1fr` with a fade). The summary is a 40 px pill row (44 px on touch), 14 px medium, `brand-700` inside a card, `ink` semibold when the fold is its own card (`card`: a card radius, hairline, shadow, a hairline between summary and body), `on-deep` on the hero. Use it instead of a hand-rolled `<details>`; `summaryClass` + `bare` let a row draw its own summary (a Cash option) and `flush` removes the body padding. Its label comes from one small set: **Details**, **Why**, **Show the calculation**, **Audit details** (ids, tiers, hashes, the executor's sentence). A fold that names its own subject ("Original message", "Debt readings", "Show 3 more", "Other plans considered") says so; two folds on one page never share a label. Other `<details>` (a transcript's fold) take the browser's `::details-content` height transition where it exists.

**Row disclosure** (`components/business/receivables-table.tsx`): in a table a row opens from a trailing chevron button (`aria-expanded`, `aria-controls`) into a second row spanning the table, on `subtle` at 60%; on a phone the same facts are a stacked list whose row ends in a Disclosure.

### Hero and status
- **Home headline** (`components/business/status-block.tsx`): no card. The status pill is a light tint of the status (`ok-bg` / `warn-bg` / `bad-bg` with the status `-line` edge and `-fg` word, a 6 px `-solid` dot that pulses once (`motion-pulse`) for ACTION_NEEDED and CRITICAL only), then the one `h1` (the server's sentence as it is, never parsed or part-coloured), the note in `ink-2`, and what is still arriving as a quiet line. When nothing is unsafe the worst point is one quiet line. `home-status` (with `data-status`) is the header's test id.
- **Cash status row:** Cash says it once in a compact row (the status pill and the sentence, then the note) above the facts as `Stat` tiles. The same fact never has two voices.
- **Next-step band** (`NextStep`) only where the step is a navigation; the **Recommended-next-step card** where there is a priced action (on `/cash`).
- **Plan bar** (Home, `NextActionBlock variant="bar"`): the one raised surface (see The One Raised Surface Rule). The eyebrow, the plan's title, a thin funding bar whose parts are sized by their amounts (`brand-600`, then `brand-300`; decorative, each part is named in the legend under it with the server's amount, words and landing), "Estimated cost", "Your approval" in the server's authority words, the one primary and "Compare options". The confirm step opens inside it; the details are one fold, "See the calculation", under it. It is `position: sticky; bottom: 16px` from `lg` only; below `lg` it is in flow directly after the headline (the phone order: the answer, the priced action, the chart) and never covers the tab bar.

### States
- **Loading** (`LoadingBlock`): `role="status"`, `aria-live="polite"`, a visually hidden label, and `subtle` tile-radius skeletons (a 32 px third-width line, then 64 px rows) that pulse.
- **Empty** (`EmptyState`): a card-radius box with a dashed `line-strong` edge, 40 px by 24 px padding, centred 14 px semibold title, 14 px `ink-2` body, an optional action under 16 px of air.
- **Error** (`ErrorState`): `role="alert"`, a card-radius `bad-bg` box with a `bad-line` edge, "Something went wrong" in `bad-fg`, the message in `ink-2`, a compact secondary "Retry". A failure the client recognises carries a code (`ApiError.code`) and is said through the dictionary (`err.<code>`, `errorText` in `lib/error-text.ts`); a failure the server explained shows the server's own words.
- **Signed out (401 / 403):** not an error. `role="status"`, a standard card, "Sign in to see this" in `ink`, the reason in `ink-2`, and the page's one primary "Sign in" (`data-testid="signin-needed"`).

### Dialogs and the tour
The chat and the walkthrough (`components/business/tour.tsx`) are native `<dialog>`s (`showModal`: the page behind is inert, Escape closes, focus returns). The walkthrough's card is 24 rem wide at most, card radius, white, `--shadow-pop`, scaling in (`motion-pop`); its spotlight is a card-radius hole ringed in white, cut from `ink` at 60%, tracked with a `ResizeObserver` and scroll, never a timer, and it jumps between steps. The tour returns focus to the account button when it closes.

### Cash picture (`components/business/cash-picture.tsx`)
Home's one chart, plain inline SVG drawn in pixels from the measured width (so its 13 px type is 13 px at any width), fed by the same `HomeView` as the forecast on Cash. Two step-after lines: "If you do nothing" (`bad-solid`, `brand-600` when nothing is unsafe, 3.5 px alone and 2.5 px at 60% beside the plan) and "With FLOW's plan" (`ok-solid`, 3.5 px; drawn only when a plan exists and differs); a segmented toggle (`SegmentedButtons`) above, right-aligned, only when there is a plan, defaulting to the plan. The window runs from today to the later of 30 days and four days past the last interesting day (the first breach, the lowest point, the day the line is back above the reserve, the plan's last landing), capped at 60 days and the server's horizon. The scale comes from the data with zero and the reserve always inside. The reserve is a dashed `warn-solid` line named with the server's `floor_short`; the area between the line and the reserve where it is under is `bad-solid` at 10%, the part under zero at 15%. The first breach is a dot with one pulse; the lowest points are labelled with `lowest_short` and `after_lowest_short`; the three largest events of the do-nothing line and the plan's own draws and advances are labelled with the server's `label_short` and `amount_short` beside their step. **A label that would touch a line, another label or the plot's edge is skipped** (its box is estimated from its characters), never drawn over; below `sm` the reserve label is only ever tried under the dashed line and is skipped like the rest. The two lines are named beside themselves, so colour is never the only channel. No axis figure is made in the browser: the foot is days ("Today", "in 10 days", from `biz.when.*`), and the figures are the server's strings. Under the picture "What moves your cash" is one button per event in the window (label, amount, distance, `aria-pressed`); pressing one lays a soft `brand-600` band over that day, pressing it again clears it. The SVG is `role="img"` with an `aria-label` assembled from the server's headline, note and after-plan sentences, and a visually hidden table lists the labelled days.

### Cash forecast (`components/business/cash-forecast.tsx`)
A step-after area chart with a horizontal-only grid in `chart-grid`, axis text in `chart-axis` at 13 px, the cash line 2 px `chart-base` with an 8% fill, the plan a 2 px dashed `chart-plan` (9 / 5), the reserve a 2 px dashed `chart-reserve` (6 / 4) named in the legend rather than on the line, the first unsafe day a 2 px dotted `chart-reserve` vertical with its label, the band below the reserve in `chart-danger`, event marks as 4 px white discs stroked in `chart-plan` (money in) or `chart-reserve` (money out), the breach a 6 px `chart-reserve` disc, the worst point a `chart-worst` mark with a bold label. Labels are 12 px (the floor), placed in pixels against the measured drawing: event labels alternate above and below the line, none within 24 px of another or of the first unsafe day and the lowest point, up to four; below `sm` there are no event labels (the marks stay, up to three, and the tooltip lists the day's events). The worst-point label is dropped when the worst point is the reserve. A label is pushed in from whichever edge it would cross; two events that read the same (one buyer's two receipts) share one label and the tooltip names the later one. The tooltip is a white card-radius box with the day's events as the server's `label: amount_display`; its cursor is a 3 / 3 dashed `chart-axis` line. The horizon is a `SegmentedButtons` track; a "Show the figures as a table" Disclosure carries the same rows as text. Recharts' focusable SVG takes the global ring. Chart animation is off; the browser draws no sparklines.

### Browser surfaces and first paint
Text selection is `brand-100` on `ink`; the caret and checkboxes are `brand-600`. `color-scheme: light` on `html`: there is no dark theme; the scrollbars, form controls and dialog backdrop must not take a dark phone's. An inline script in `<head>` (`lib/pre-hydration.ts`) reads `tl-lang` and `tl-mode`, sets `lang` and `data-mode` at once, and keeps the body hidden (`data-pending`) while the server's Business/English markup would be the wrong shell or language; the shell clears it after hydration (a 2 s timer is the way out). The tab title of every route is server metadata (`lib/route-title.ts`, one `layout.tsx` per route); the shell puts the owner's language in.

### Motion
Six durations and two easings; nothing else moves the app. Transform and opacity only. Two deliberate exceptions: a disclosure's height, and the cash picture's one draw (`stroke-dashoffset`, once, on mount).

| Token | Value |
|---|---|
| `--ease-ui` | `cubic-bezier(0.2, 0, 0, 1)`: the one ease-out |
| `--ease-select` | `cubic-bezier(0.25, 1, 0.5, 1)`: an ease-out that settles without overshoot (a pill must never leave its track on a multi-tab jump), for a choice settling into place (the segmented pill) |
| `--dur-instant` | 80 ms (a press, a toggle's mark) |
| `--dur-fast` | 140 ms (a hover, a colour, the segmented pill sliding, a label appearing beside a collapsed sidebar icon) |
| `--dur` | 220 ms (a switch, a sheet, a disclosure, a detail replacing in place) |
| `--dur-expanded` | 280 ms (a card or row arriving, a panel sliding in, a chart cursor) |
| `--dur-scenario` | 350 ms (a scenario or window switch: the figures that change update together; the picture's labels fading in) |
| `--dur-narrative` | 500 ms (the one story the Home picture tells: the lines draw, the first breach pulses; the skeleton's breathing and the spinner's turn are multiples of it) |

Every `duration-`, `transition` and `animation` in the app names one of these; a delay is a multiple of `--dur-instant` or a 30 ms stagger. A transition is never queued: a new target replaces the running one.

| Class | What it does |
|---|---|
| `motion-reveal` | a block fades in and rises 6 px on mount (the hero, `Card`, `PageHeader`, disclosure cards, the next-step band, empty and error states) |
| `motion-rise` on a list | rows rise one after another, 30 ms apart, for the first eight; a ninth row just appears |
| `motion-lift` | hover lifts 1 px and takes the next shadow step (rows, tiles, option rows, link tiles), only where hover exists |
| `motion-press` | a button scales to 0.98 while pressed and eases its colour |
| `motion-slide` | a thumb or indicator moves by transform (the segmented thumb, the tab bar's active bar) |
| `motion-sheet` / `motion-panel` / `motion-pop` | the account sheet drops in from its corner; the chat slide-over enters from the right; the walkthrough card scales in |
| `motion-pulse` | the status dot's ring grows to 3x and fades once (`--dur-narrative`, after `--dur-scenario`), for ACTION_NEEDED and CRITICAL only (never on a calm status) |
| `.disclosure-body` | a one-row grid from `0fr` to `1fr` with a fade; other `<details>` use the browser's `::details-content` height transition where it exists |
| `.picture-draw` / `.picture-fade` / `.picture-pulse` | **the chart's one draw**: on mount the do-nothing line draws (`stroke-dashoffset`, `--dur-narrative`), the plan line after it, then the shortfall and the labels fade in and the first breach pulses once; later toggles and chips never replay it. A deliberate exception to "transform and opacity only", on one SVG, once. |

The Tailwind transition utilities (`transition-colors`, `-opacity`, `-transform`) take `--dur` and `--ease-ui` as their default, so a bare one still comes from this kit. Nothing animates width, height (but the disclosure), margin or position, so nothing shifts the layout. Under `prefers-reduced-motion: reduce` animations end at once (0.001 ms), delays and loops are removed, the hover and press transforms are cancelled, and of the transitions only opacity remains, at its own token's duration (`transition-property: opacity`: a colour, a transform or a height changes at once); the `Spinner` arc is replaced by an ellipsis after the label. Components that choose in script (the chart cursors, the segmented pill) read the same signal through the one hook, `lib/use-reduced-motion.ts`. `e2e/design-system.spec.ts` asserts the six tokens, that no stylesheet rule names a duration that is not one, and that under reduced motion a transition on each token keeps only opacity. The Playwright config sets `reducedMotion: "reduce"` so every spec runs without animation.

### Language and figures
Every string is in the dictionary in both English and Chinese (`lib/dictionary.ts`: 1608 keys each, `zh` typed as `Record<DictKey, string>` so a missing twin fails the build); `<html lang>` follows the owner's choice (`en` / `zh-CN`). One plural template (`{n|invoice|invoices}`) serves every count. The browser computes no money: every figure, date and sentence arrives formatted from the server as a display string (`*_display`, `*_short`, `*_when`, `event_text`, `label_short`), traceable to a formula; the client does no regex rewrite, approval inference, subtraction or truncation. Business mode shows no engine terms and no day numbers.

## Do's and Don'ts

### Do:
- **Do** take every colour, radius, shadow and duration from `app/globals.css`; no hex lives in a component.
- **Do** give each page one brand-filled primary; make every other step a secondary pill, a ghost or a text link.
- **Do** pair every status colour with a word (the pill, the dot and the tint are the second channel).
- **Do** use a section hue only to say where you are or where a link goes: the page chip, the tab, a shortcut, a buyer's avatar.
- **Do** keep text at 12 px or above (metadata only), every figure and qualification at 13 px or above, body and data at 14 px, and set every figure `tabular-nums`, right-aligned in a column, never wrapping.
- **Do** use `Stat` for a fact, `Disclosure` for a fold, `Badge` for a status, `Chip` for a tag, `Row` for a list line, and the one `FoldChevron`.
- **Do** hold every text pair at 4.5:1 and every boundary and icon at 3:1 on the surface it actually sits on; use `line-ui` for any edge that must be seen.
- **Do** reach 44 px on touch by growing a control or giving it `.hit`; keep the desktop 32 / 40 px look.
- **Do** publish and read `--dock-h` so nothing fixed to the bottom covers content.
- **Do** animate transform and opacity only, with the six durations and two easings, and respect `prefers-reduced-motion` (opacity only).
- **Do** show every figure, date and sentence as the server sent it, in both languages.

### Don't:
- **Don't** ship a dark theme, a gradient on a button or a card, a glow, a particle or parallax effect, glassmorphism (frost or a backdrop blur) anywhere on the dashboard, a count-up on load, a decorative badge, an internal label ("Executive snapshot", "Autonomous strategy", "Retained yield", "Treasury engine", "Live stress simulation"), a coloured rail on a card's edge (the selected card's accent rule excepted), or a font fetched from a font host.
- **Don't** let the brand blue mean a status, or a status colour mean anything but that status.
- **Don't** use `brand-900` anywhere but the Demo strip, put a card around the Home headline, or add a second decision card to Home.
- **Don't** set text below 12 px (there is no `text-2xs`), or a figure or qualification below 13 px.
- **Don't** hand-roll a `<details>`, a second chevron, a second fact tile, a pill group (use `SegmentedTabs`), a state word (use `StateWord`), or a second radius; the scale is pill / 16 / 14 / 10 / 8.
- **Don't** compute, subtract, round, truncate or reword money in the browser, or draw a sparkline there.
- **Don't** remove a focus outline, animate height or position (the disclosure's height excepted), or let Ask FLOW float over content.
- **Don't** tint a buyer's avatar orange, and don't give two folds on one page the same label.
- **Don't** draw a chart label over a line or another label (skip it), or build an axis figure in the browser.
- **Don't** wrap an empty section in a card; one quiet `ink-3` line says it.

## Amendments from the finish review (8 October 2026, Wave 8 pass E)

- **Cash forecast labels** also avoid the gridlines and the reserve line: a label whose text box would cross one flips to the other side of its mark before the same-side overlap rule runs. Labels may still cross the series lines (open).
- **Receivables worth is one figure**: the word "Saves" beside the server's net figure, right-aligned and tabular; when the server says there is no saving, its short sentence stands in. The full worth sentence is the first line of the row's details.
- **Fold labels**: on a page that already has a "Details" fold, every other fold names its subject ("Option A details"; Home's foot card "Details: what is on its way, warnings, facilities and debt readings").
- **The recommended funding row** is titled by the server's plan name, "Recommended plan" only as the fallback; the grey "a cheaper option exists" note is not drawn when the rows carry a role (the alternative's chip says it).
- **The envelope card** draws the three fact tiles, the caption, the reason and the money sentence; the server's primary sentence is not drawn (the tiles carry its figures).
- **A decision headline** ("Counter recommended") is a card title: 20 px semibold, its weight from position.
- **Lists in a card** (the Activity timeline) are divider-separated rows with no per-row border, radius or tint; the audit fold sits inline at the trailing edge.
- **The Cash status card** carries the note and the cash-price sentence; the debt-readings fold is the Forecast card's footer.
- **Copy**: time passing carries no "Executed" chip; an expiry reads in the past tense once the day has gone ("Expired 27 days ago"); "Debt readings, this month"; a recovered promise is a full sentence; a receipt says "of the invoice".

## Amendments from Wave 3 (9 October 2026, map #65 ticket #72)

- **The Deals workspace** is one column in the server's `workspace.order` (Wave 7 order, see the Wave 7 part C amendment): a compact selected-buyer card, "FLOW recommends", the priced response, "What the buyer asks", "What it costs you" (with why it matters), the agreements and, last, one "Advanced details" fold whose sections follow `workspace.advanced.keys`. The Inbox folds to one row ("Inbox (N)" with one "Back to inbox" button) once a deal is selected; the full list shows when nothing is selected or on request. Buyer terms appear once. No jump band and no stage links.
- **What it costs you** keeps the immediate discount on its own line and the forward lines with their total in a tinted tile of their own (`subtle`, hairline), with the limit, an "Over your limit" pill when the server says so, and the server's note that the two are not added. A valuation window shared by the forward lines is said once above them. The first breach and the worst point are two hairline rows, not tiles.
- **The funding comparison** is drawn in the server's groups and order, each group under its `group_text` as a small uppercase heading, one sentence above the groups saying how the list is ordered. A numeral is the server's `rank` and appears only on the recommended plan and the ranked alternatives. Each row shows its cost, `arrival_text`, `remaining_gap_text` (an insufficient plan says its shortfall in red), `consent_text` and `basis_text` in 12 px text; the browser sorts nothing. The Demo funding view sorts by `router_order` to keep the spec order.
- **The forecast** says what it counts in its subtitle (`forecast_basis_text`) and keeps the facts behind a "Basis" fold. A day with several events is labelled "Net {net_short}", never by its largest component; the tooltip and the table list the components and the net. The freshness of the read sits beside the Cash conclusion as 12 px `ink-3` text.
- **Activity rows** are three sentences under each other: what changed (14 px medium), why it matters with a neutral "Now" chip when it is today's forecast, what remains. An approval request is history: its label ("Approval requested"), the decision's state today and a link to the record. The Audit details fold sits under the row. The chain badge speaks only for the log's own hash chain; what it covers is in its tooltip and in a fold.

## Amendments from Wave 7 (9 October 2026, map #65 ticket #76)

- **Phone order** (`lib/use-narrow.ts`, below 1024 px): the order of the parts changes, never what they say, and it changes in the DOM, so the focus order and the reading order are what is on screen. A part keeps its key, so what it holds survives a resize. A desktop keeps the Wave 3 order. Home reads: the hero (the status pill with "Read {when}", the sentence, the note, "Cash today" with "Arriving" beside it; the three tiles wait behind "Why", the first spanning both columns when there are three), then the recommended-next-step card (or, with no plan to run, the remaining-task card with its first route as the one primary), then the open question, "Waiting on", Receivables, Recent changes, Details. Cash reads: the status card (the price sentence folded), the plan card or the remaining-task card, the four facts as a short list of `Stat` rows (`row`: label left, figure right, caption under both, below `sm` only), the options, the forecast, the doors. Deals reads: the inbox as one folded row, a compact buyer card (buyer, ask, received, one state chip from the record, no step line), what FLOW recommends with its first reason, the priced response with its bound Send, then the asks, the cost, why it matters, the agreements, Advanced details. At 412 x 915 each page's primary action ends above the tab bar (`phone-measure-after.json`).
- **One primary while a plan waits:** the card says "Waiting for your approval" and holds the filled "Review and decide"; the decision row below it is a plain row.
- **Freshness and recovery:** `ReadWhen` ("Read {when}", 12 px `ink-3`, `on-deep-muted` on the hero) sits beside the conclusion on Home, Cash, Receivables and Approvals; nothing is shown when the server did not say. `PartialRead` is an error-tone row (`bad-bg`, `role="alert"`) with a compact Retry when `partial.missing` names supporting facts that could not be read. A strategy read that fails is an `ErrorState` with Retry; a feature that is off says nothing.
- **Slow requests** (`SlowNotice`): a request that runs out of time (20 s; 60 s for the model turn, the evaluation and the strategy reads) is `role="status"` in the warning tone, "This is taking longer than usual…", never red. For a write the notice says it may already have gone through, and its Retry reads the state again and sends nothing; afterwards a quiet line says the state was checked. A model turn is replayed under the same request id.


## Amendments from Wave 7 part C (10 October 2026, map #65 ticket #76, the design review)

- **Deals order, one at every width** (the server's `workspace.order`): the folded inbox row, the selected-buyer card (the buyer, when it came, when it was checked, and ONE state word: the record's `state_text` as a `StateWord`, its tone the server's `state_tone`; no ask line, no step line), "FLOW recommends" with its first reason under it, the priced response, then what the buyer asks, what it costs and why it matters, the agreements, the folded details. Once the deal has an outcome the eyebrow reads "Where this deal stands", never "FLOW recommends: {outcome}", and the card carries the Money line ("Received {amount} {when}." / "{amount} arrives {when}.", from the record's lots, neutral until the cash has landed) and "What is left" (the record's remaining task). The Action band appears only where it names a real action (the approval to answer, the way back to the offers).
- **Send** asks once, as Home's Run does. Above the button, in 14 px `ink`, "This will" and the server's `send_scope_lines` (the agreement it records, the funding it draws or requests, the estimated cost); the first press opens a confirm box ("Send {label} to the buyer?", the reply is simulated), the second sends exactly what is shown. Another counter keeps the server's one sentence.
- **`StateWord`** (`components/ui/state-word.tsx`; the old `StatePill` and the pill variant are retired) is the one way a state the server names is drawn: icon, colour and the server's word (a `state` of the twelve, or the server's `state_tone` / `result_tone` for any other status); the browser never colours a state itself. 13 px, no container, no dot (below). The execution summary is green only when cash has landed; until then a request that ran is "Requested" (info).
- **The approval card** (decided): the result block first (the state word and its server tone in the header, what the decision run did, "Your minimum cash reserve is still ... short" when the cure left one, when it was decided), then the facts and terms, then "Quoted when requested" and the stale After behind a fold; no subtitle when the Source and Invoice facts say it, no landing in the quote when a Timing fact shows it. The Approvals page has no next-step band and no token note; its sections are 24 px apart.
- **One primary per decision card.** An approval waiting is held by the next-step card's "Review and decide" (the Decisions card and the "Waiting" change row are not shown beside it); a record waiting for the owner has the same one primary. A remaining-task card's first route is its primary (when no approval waits) and the others are text links. An in-page jump is a text link (`textLinkClass`), never a brand button. Standalone links are `textLinkClass` (32 px, 44 px under `touch:`); the Chase button follows the same `touch:` rule.
- **Owner words.** Cash against the minimum is "{amount} above your minimum" / "{amount} below your minimum" and "Lowest point: ..." (`lib/minimum.ts`: the server's figure and the sign of its integer; no arithmetic). "Estimated cost" is the headline figure and "Total" only a sum. "What is left" is the one word for what remains ("Needs your decision" is the warning variant). Future give-aways are "Future costs you have promised". A funding arrives ("Cash arrives {when}") or has arrived ("Cash received {when}"). One state vocabulary: Needs your approval, Declined, Agreed, Agreed and settled, Expired, Revoked. The assistant is FLOW; a Business chat turn shows one outcome in the owner's words (no verdict panel, tier badge or intent chip) and confirms with "Yes, run it".
- **Part-paid invoice.** Home says it once, in the server's sentence. Receivables says a short lead ("Part-paid by {buyer}, {when}.") and the four named facts at 14 px, the remaining balance largest, then the window in words; the long sentence waits behind Audit details.
- **Activity** says today's forecast once above the timeline ("Now"); a row says its own only when it differs from the row before (`why_it_matters_changed`).
- **Fresh state:** every request to a route that takes a language carries the language on screen (`lib/live/http.ts`); a Business chat turn also carries `mode=business`.

## Amendments from Wave 8 part C (10 October 2026, the cold screenshot review)

- **Phone first screen:** every primary ends above y 840 at 412 x 915 (the tab bar starts at 858). To get there, the reason an approval is needed waits in the next-step card's Details on a phone (the tile still says "Needs your approval"), "Quoted when requested" sits behind its fold on a waiting approval (as it does once decided), and the page subtitle gives way on Cash, Approvals with a decision waiting, and Deals with a deal open. At 1366 x 768 (`short:`, a window at most 800 px tall) the Home hero's tiles wait behind Why, as on a phone, and the hero and the card tighten.
- **Tablet:** the open invoices are a list below 1024 px, a table from 1024 px; no column is clipped.
- **Already under the minimum:** the tile reads "Short of your minimum today" with the shortfall as its figure and "Cash today {amount}" as its caption, never today's cash under a "below" label. The reserve tile's sub-line is about the cash, so it cannot be read as the reserve: "Your cash is {amount} above it".
- **Activity:** a request that waited for the owner is history once the owner has decided: it wears where the decision stands now (`current_decision_state`, a neutral `StateWord`), not "Waiting for your approval", and the decision's actor is "You".
- **Deals once there is an outcome:** the offer's cost, the most the owner could give and the first reserve breach sit folded under "The original ask (not agreed)". A missed early payment's card carries "Compare your funding options" and Chase payment beside "What is left". The server's `approve_label`, `why_text`, `next_step_text` / `next_step_href` and `kind_text` are used when it sends them.
- **Demo:** the strip reads "Scene 5 of 6, step 7 of 11". While the cure waits there is one filled Approve on the page, the approval card's; the strip's and the story page's buttons read "Open the approval" (the story page's step shows its state instead of a second button), and they move the story on once the owner has decided. The sidebar reserves the strip's height so its footer is never cut at 768 px.
- **Ask FLOW:** the prompt chips wrap inside the panel; they never run off its edge.

## Amendments from the debt wave (10 October 2026, map #65 tickets #82, #85, #86)

- **Receivables, overdue first:** an overdue invoice (the server's `past_due`, or `overdue_text` on its worth row; the browser compares no date) is pinned above the savings-ranked rows. With the whole list showing and something overdue, a 12 px uppercase `ink-3` heading says "Overdue first" over those rows and "Ranked by what collecting saves you" over the rest ("Not overdue" when the ranking is not loaded); the server's ranking note stays in the filter row, and every row keeps the server's own rank numeral. A filtered view (Late, Due soon) has no headings. The red Overdue tile is a `Stat` with `press`: one quiet text button stretched over the tile ("Show the late invoices") that applies the Late filter and brings the list into view.
- **Approvals:** the cards are left-aligned with the page header (width capped at `max-w-3xl`, not centred), so the header and the card share one edge.
- **Cash, the plan once:** while the plan card holds the recommended plan, the options card below it lists the alternatives only, without the server's "recommended first" ordering sentence; once covered, the decision-time comparison keeps the plan that was chosen. The cash price sentence is its first clause on one line (cut at the sentence's own first break, `lib/price-sentence.ts`) with the rest under a "More" fold.
- **Deals, the stage line:** the compact buyer card carries one line of chips under its meta line, Received · Analysed · Response ready · Sent · Agreed, from the record's state alone (`components/deals/deal-steps.tsx`). One chip per stage; the stage behind is neutral with a check (the check is dropped on a phone), the stage the deal is at is brand-tinted and bold with `aria-current="step"`, the ones ahead are `ink-3`. Nothing in the line links anywhere; a closed deal's last chip reads the record's own words.
- **Demo story on a phone:** below 1024 px "More to show", "Today" and "The books" are one closed card-Disclosure each (`story-fold-<card id>`); a desktop keeps the three cards. The page is the story, and these are tools for after it.
- **Home changes:** a change row whose `superseded_by` names another row on the page is not drawn (`lib/home-changes.ts`).

## Amendments from the reskin pass (11 October 2026)

The owner asked for a look and flow in the manner of a wealth platform; the palette was modelled on that reference and is now
this system's own. Where the sections above still describe the earlier look (pills for buttons and fields, 16 px cards, the
single type family, a top navigation), this section and the front matter win. Midnight blue `#24324a` is the ink and the deep
block, royal blue `#0472ff` marks charts and information, and the action fill is the pressed shade `#0368e9` (white on it is
5.0:1; `#0472ff` itself is 4.3:1 and fails AA for 14 px text). The canvas is a pale blue-grey, the hairlines `#e6e9ef`, and the
chart series take a turquoise `#38d0c7` and a purple `#9b5fff` (`chart-teal`, `chart-purple`, plus `chart-sky` and `chart-navy`).
Success shifts toward teal to sit with them.

- **Type.** Lato for reading; a serif for page titles, the home hero's headline and figure, and the deal picture's figures
  (`font-display`, Libre Caslon Text first). **The two faces are not shipped.** The stacks name them first, so a machine that
  has them uses them; any other falls back to Inter, the platform's system and CJK faces (sans) or Georgia and Songti (serif).
  No stylesheet or preconnect to a font host is in the root layout, because Google Fonts is unreachable from mainland China,
  where the Demo is judged, and a font file may not be downloaded into the repository.
- **Shape.** Buttons, toggles and text fields are 8 px rounded rectangles (`rounded-control`), not pills. Badges, chips, avatars
  and the segmented track stay round. Cards are 14 px with no rule under the header and 20 px of padding.
- **Shell.** Business mode keeps the top bar (brand, approvals, mode, account) and puts the five sections in a white left
  sidebar from `lg`, each an icon and a word; the current one takes the brand tint and a 4 px rail. Phones keep the bottom
  tab bar. The sidebar's nav keeps `data-testid="nav-pills"`.
- **Documents.** The upload is a drop zone: dropping a file reads it at once, and a demo document can be dragged from the list
  onto it. The review opens on **This deal at a glance** (`components/deal-picture.tsx`): the money-moving terms as tiles, the
  cash position over the forecast with the counterparty's receipts as bars (a lender agreement draws the recommended funding
  instead), the cash the owner can reach (a donut), each source's interest rate, and every loan and line with its drawn part.
  Every figure is a server string; fen and bp only size marks (INVARIANT 13).

## Amendments from the Home redesign (12 October 2026, mockup A1 "Seamless")

- **Home is seamless.** No hero card: the status pill, the one `h1`, the note and the cash picture sit on the canvas; the attention card is the one raised surface, a decision card (the plan's bar sticky from `lg`); the owner's deals are rows with hairlines; the other blocks lose their card chrome (a small-caps heading, hairlines), except a block that asks the owner to decide. Warnings are "Also on your radar", a quiet row above the details fold.
- **The shell.** The sidebar is on the canvas with a white active pill; the top bar is the canvas at 70% with blur and no border at rest.
- **Type.** The display voice is sans (Plus Jakarta Sans, 800); the serif and the Flow Figures workaround are removed.
- **A new token:** `brand-300`, the lighter second part of the funding bar (decorative, named in its legend).
- **Motion.** The cash picture's one draw is the second named exception to "transform and opacity only".

<!-- pages A1 (part 1): one separate block; the second pass (Approvals, Cash, the secondary pages) adds its own below. -->
## Page pattern, A1 (Receivables and Activity; Home is the model)

**The page pattern.** Every Business page answers one question at the top, shows one picture where the data supports one, has at most one raised surface (the action), and leaves everything else unboxed on hairlines. The `h1` is the answer in the server's own sentence (never composed in the browser): Home's headline, Activity's "now" sentence, Receivables' `receivables.headline` (else the collections read's top action while someone is late, else the plain page title). A section is a 16 px extrabold title, a 12 px `ink-3` line and a hairline, then rows divided by hairlines; a block that asks the owner to decide keeps the white card.

**Action bar (`components/business/action-bar.tsx`).** The one raised surface, a `DecisionCard` (solid `surface`, `--shadow-decision`; it was frosted until #112), in flow below `lg` and sticky 16 px above the window's foot from `lg`. Home's plan and Receivables' "Chase payment" use it; nobody late, no bar.

**Facts row.** The outstanding, overdue and next-payment facts are one inline row: a 12 px uppercase `ink-3` label, a 24 px extrabold tabular figure (the overdue one in `bad-fg` only while something is late) and a 12 px caption, hairlines between from `sm`, a hairline above and below. No tiles.

**Who pays when (`components/business/who-pays-when.tsx`).** Plain inline SVG on a day axis with a "Today" line; every open invoice is a mark at its due day, late ones left of today on a faint `bad-bg` band. Size is three steps by face amount (radius 5.5, 8, 11); state is fill and outline as well as hue: late is filled `bad-solid`, due soon is outlined `warn-solid`, later is outlined `ink-3`, a promised early payment is an outlined `info-solid` diamond. Each mark is labelled with the server's amount and the day in `biz.when.*` words and the buyer's avatar (a section tint, never orange). Marks that overlap stack into lanes; a label that would touch another mark, label or the Today line is dropped (the row has it); room is kept left of the earliest late mark for its label. A mark is a button (`aria-pressed`, `aria-controls` the row): the page shows every invoice, scrolls to the row and tints it `brand-50`. A visually hidden table mirrors the marks. It fades in once (`picture-fade`); under reduced motion it is in its final state.

**Activity rail.** A vertical hairline rail; a day caption (12 px uppercase `ink-3`, the entry's distance from today in `biz.when.*` words) per day; a 32 px node per entry with an icon for who acted (you `brand-50`, FLOW the Home tint, the bank or system `subtle`, the buyer the Deals tint), the sentence as a 14 px semibold title, the status pill, the plain operation name and the actor in 12 px `ink-3`, and one quiet "Details" toggle at the right that opens the audit details (the executor's sentence, the ids, the tier, the hashes). Time passing is a thin separator on the rail with its sentence and no node, pill or toggle. Filter chips (`toggleClass`, `aria-pressed`) above the rail narrow it by kind (Money, Decisions, Documents, from a fixed map of operation kinds); a kind with nothing in it is not offered, and the order never changes.

**Shared cash picture (`components/business/cash-picture.tsx`).** The drawing of Home's picture with props that do not assume Home (`baseline`, `alternative`, labels, `floorFen`, `floorLabel`, `markers`, `horizonDays`, `chips`, `ariaLabel`, `testIdPrefix`, a `header` slot). With two lines each name sits beside its own line, on the longest stretch where the lines are more than a label's height apart (the upper line's above it, the lower line's below it); with no such stretch both names go to a small legend row above the chart.

**Sidebar count.** Deals and Receivables carry a small count pill at the right of the sidebar row and on the tab bar's icon (Deals `warn`, Receivables `bad`), nothing at zero. The link's accessible name says what the count means ("Deals, 1 needs you", "Receivables, 1 is late"); the number itself is hidden from assistive tools. One read of `GET /nav/counts` per navigation and per action; a failed read shows no count and no error.

## pages A1 (part 2): Approvals, Cash and funding, the secondary pages

- **The approval.** With one approval waiting, its question (the server's sentence) is the page's one `h1` and the card does not repeat it; with several, the `h1` is a counted sentence and each card carries its own question; with none, the plain title. A waiting approval is the page's one raised surface (a `DecisionCard`, in flow, not sticky): three facts (what you get, what it costs with its rate beneath, when it lands), "Why it needs you" in one sentence, then the picture (the shared cash picture with "If you decline" as the baseline and "If you approve" as the alternative, the minimum line, each line's lowest point in the server's short string, no chips), the server's "If you decline" and "After" sentences as its two captions, the quote behind one fold, Approve (the page's one brand-filled primary) and Decline, the record link and Audit details. An approval with no cash line (an agreement's terms) keeps its terms and shows no picture. Below `lg` the two buttons sit right after the reason, before the picture, so they stay in the first screen. Decided approvals are unboxed rows on hairlines under "Already decided" (state pill, the question, the outcome, the record link). The reserve and today come from the home read; if it fails the picture is simply absent.
- **Cash and funding, in order.** The headline is the `h1` (status pill, the server's sentence, the note, "Cash read ..."; the price sentence stays a quiet line with its fold), then the picture with a 30 / 60 / 120-day switch (`windowDays`) and the facts on its header row (cash today, the minimum with its headroom, when cash becomes unsafe, the worst point), the Basis and "figures as a table" folds under it, then the plan bar (`NextActionBlock variant="bar"`: sticky from `lg`, in flow right after the headline below it), "Ways to cover the gap", "Your funding sources", the debt readings fold and one quiet row of two links. The recharts forecast is gone from this page.
- **Option rows and their bars.** The rows are a radio group in the server's order and groups, the recommended plan chosen by default; choosing one draws its `series` as the picture's alternative line under its name (the toggle says "Chosen plan"), and a row with no series shows the server's `series_note` and leaves the baseline alone. Each row: the name and a role pill, the legs, when the money arrives, a **cost bar** (`total_fen` against the dearest row, `brand-600` on a `subtle` track) and a **coverage bar** (the legs' amounts against `remaining_gap_fen`: `ok-solid` then `bad-solid`), with "Covered" and "Uncovered {amount}" beside it so colour is never the only channel. Bars are plotting only; every word and figure is the server's. The selected row is marked by a filled radio, a light tint and "On the chart".
- **Facility bars.** Each funding source is a row: its name, how fast the money arrives (the router's `time_to_cash_display`), a utilisation bar (`drawn_fen` against `limit_fen`, `brand-600` on `subtle`, labelled for a screen reader with the server's drawn and limit strings) and the server's limit, drawn and available. The plain-words explainer stays behind its fold.
- **The secondary pages** (Limits, Documents and its review, the decision record, What-if, Capex): sections lose their card through `Card`'s `flat` prop (a small-caps heading, a hairline), `Stat` takes a `bare` prop (an unboxed fact with a hairline above it), and the one block that asks the owner to act stays raised (the upload and the review, the record's status, the what-if controls, Capex's tier and apply). No content, order or behaviour changes.

## Deals A1 (the verdict, the reply bar, three paths on one chart, the asks)

- **The page's order** (one order at every width; the DOM order is the visual order, nothing is reordered by CSS). With an offer selected the `h1` is the verdict in a few words (`open_offer.headline_short`, no figures; else FLOW's whole read, `open_offer.read_text`, else the workspace's recommendation; once the deal has an outcome, the record's own words), 20 px on a phone and 24 px from `lg`, weight 800, under a status pill from `needs_you_text`; the quiet line beneath is `headline_note` (the figures, 14 px `ink-2`, hidden on a phone at most 800 px tall), else `action_text` (hidden on a phone). Received and not yet checked, the `h1` is the server's sentence about it and the one Action ("Check against my limits") follows. Then, in the remediation's order: the reply bar directly under the heading (the priced decision; its Send is inside the first screen of a 360 x 740, 390 x 844 and 412 x 915 phone, above the tab bar, and inside the first screen at 1280 x 800), the picture with its moments and the path columns, who and where (the buyer, the five stages), "What they ask, and what each costs you" and "Why it matters" behind closed folds, then the strategy block, the agreements and the advanced fold. Once the deal has an outcome the original ask (the asks, the strategy block, why it mattered) is folded under "The original ask (not agreed)", unfolded inside it. The page stays within two screens (900 px) with the folds closed.
- **The asks, folded.** One row per ask in the server's words with its kind label (12 px, `ink-3`) and a bar (`amount_fen` against the largest line, `brand-600` on `subtle`; a one-off line `brand-300`; the ongoing lines `bad-solid` only while the total is over the limit), its amount and its window words. The ongoing total is one bar against the signed limit, the limit a 2 px `ink` tick, with the server's note beneath. "Why it matters" holds the reasons and the two cash facts of the offer as asked ("If you accept the offer as asked": first breach, worst point).
- **The paths picture (`components/deals/paths-picture.tsx`).** Three lines, the minimum, one cursor with its band, and nothing else: no event labels (payroll, rent and the like hit every path alike and stay in the shape of the lines), no end names, no legend, no lowest-point labels; the three tiles under the cursor are the legend at every width. The shared cash picture's scale, step path and axis (`cash-picture.tsx` exports them), drawn from the offer's `paths[]` in the server's window (`picture_days`, `axis`). Lines are told apart by pattern as well as colour: the asked path thin and solid in `bad-solid`, the recommended reply thicker and solid in `ok-solid`, a further reply dashed in `series-c`; the tiles' 10 x 3 swatches repeat the pattern. The emphasised line (the picked path, or the path whose column or tile is pointed at or focused) is full opacity and 1.5 px thicker; the others are at 85%, and 40% while a path is pointed at. The picked path stays emphasised.
- **The cursor and the moments.** The cursor (a dashed `ink` line, a 14 px band and a dot on each path) visits the server's `moments` only. The chips are the moments, labelled by the server's `word` (else `label`), never a day number: `toggleClass` buttons in a `role="group"` named "Moments", `aria-pressed`; the arrow keys move focus between them, Enter keeps one. Pointing at or focusing a chip previews its moment (band, dots, sentence and tiles move) without changing the selected one; a click keeps it. Previous and next buttons and one Play toggle (`aria-pressed`; "Play the moments", "Pause" while it runs, "Resume" after a stop part-way, which continues from the current moment; "4 of 6" beside it) always sit on the chips' row, wrapping under the chips on a phone. Play steps one moment every two seconds, ends on the last, never starts by itself, waits (and says "Paused while you look") while a mouse is over the picture, and a step made by hand halts it. The moment's sentence reserves about three lines on a phone and the "What moved cash" slot stays (empty where nothing moved), so nothing below shifts during Play. The cursor's dot is the path's marker (a square for the asked path, a circle for the recommended reply, a diamond for a further reply), repeated in the middle of the tile's swatch, so the solid red and green lines are told apart without colour. Picking a path says "Reply bar now shows Option B" in a polite status. Under reduced motion the cursor and dots carry no transition class (they jump) and Play still steps; hover emphasis and the tooltip are not motion and stay. The moment's sentence is 15 px, weight 500; a separate polite live region announces the selected moment's word and sentence once per step, never on a preview.
- **Pointing at the picture.** A mouse over a day shows a tooltip (the day's word, else its distance from today, and each path's figure from the series' own strings) that follows the pointer, flips at the right edge and stays inside the chart, so it never covers the tiles or the bar; the focused picture (`tabIndex 0`, Space plays and stops, the arrows step) shows it at the cursor's day. With a mouse the cursor line, its dots and the three tiles follow the pointer's day as a preview (the series' own display strings; the moment's sentence and tones only when the pointer is on a moment's day), without changing the selected chip or speaking, and return to the selected moment on leave; they jump without a transition, and under reduced motion as always. A click or a tap moves the cursor to the nearest moment, never to an arbitrary day, and commits it. Every hover has a keyboard equivalent and none carries information the tiles or the fold do not.
- **Under the cursor.** The moment's sentence, then three tiles in a row: the path's name with its swatch, the server's `closing_short` (else its display figure), the note in the bad tone when the path is below the minimum (the server's `below_floor` / `tone`; the browser compares nothing), the gap against the asked path as a 12 px caption in the server's `vs_asked_tone` (replies only), and a reply's `assumption_text` as a 12 px caption. "What moved cash on this day" is a closed fold listing `events_text` per path in words; absent when the server gives none.
- **The columns (`path-columns.tsx`).** A radio group, one column per path in the server's order: the swatch and name, the tag (`tag_text`, `tag_tone`), the cost total (`cost_total_display`, one basis across the three) with its basis words beneath and, for a net, its two parts as hairline rows (`cost_components`; an older server's counter economics supply the same two parts, so a zero net never stands alone), the three terms, the path's lowest point and first breach in the server's words, who decides (`authority_text`, else `decides_text`) as a `StateWord` in the class's tone (`flow_may` ok, `needs_owner` warn, `over_limit` bad) and the button "Show this path". The picked column has a 2 px border in its colour and `shadow-card`.
- **The reply bar.** The page's one raised surface (`ActionBar`, sticky from `lg`): for a sendable path its `reply_text`, the class caption, "This will" and the one brand-filled button, which opens the existing send confirmation (keyed by the counter, so a confirmation never carries from one column to another); a path that needs the owner says "you approve first"; a path that cannot be sent says why and offers a secondary "Back to Option A". The counter cards remain only as the fallback for an older API answer with no paths.

## Deals as a decision queue (ticket #109, map #88; the server's exposure read decides)

The Deals page becomes a queue when `GET /offers/{id}/exposure` answers for the open offer (the server's FEATURE_EXPOSURE); when the read is absent (flag off, an older server) the page is the Deals A1 page above, unchanged. No client flag decides it. The queue shows once an offer is open and stays for the visit.

- **Order** (the DOM order is the visual order; below `lg`, and on a short window, the folded inbox row comes last) (`components/deals/queue/*`): the header and one sentence; four count tiles as a tablist (needs your response, awaiting the buyer, agreed in force, customer setup; `aria-selected`, arrow keys, `?tab=`; a horizontal scroll of pills on a phone); the list (customer link, request, cost as asked, FLOW recommends, a status word; `aria-current` on the selected row; two lines per row below `lg`); then one detail beside its aside (the aside follows the detail on a phone).
- **The detail replaces in place** (`motion-select`, one `--dur` fade, nothing inside it reveals again; no motion under reduced motion; the title is announced once in a polite status that sits outside the keyed section): the customer link, `headline_short` as the one `h2`, the ask, "Why counter?" as a left rule (the verdict's reasons), the one blue card (the reply sentence, the one-off cost if the buyer accepts, one sentence on who decides, and the one filled primary "Review and send the counter"), "Cash on each path" always visible (the #105 picture and columns, the paid-late toggle above, the cash facts of the offer as asked and "Your exposure to {buyer}" under the columns), then one fold "Compare accepting, countering and doing nothing" holding the seven-row table and two closed folds, the buyer's message and the calculations (never versions, ids or the engine's checks). Where the reply cannot be reviewed here (the picture cannot be drawn, no reply to send, the Demo view) the page's own response stands in the card's place, so the owner can always send.
- **One filled primary.** "Review and send the counter" is replaced, while open, by the existing send (`RecommendedResponse` with `bare`): the server's "This will" lines, the confirmation, the 409 COUNTER_CHANGED refusal and the slow notice are unchanged. A deal with an outcome shows its own parts (where it stands, the answer, the agreements) in the detail's place.
- **Context lives in the address and nowhere else:** `decision` (the deal's record), `path` (the picked path), `tab`; the customer is not written (it would say the page was opened from that customer). The address leads (a back link from the Customer page, or a reload, selects the deal and the path it names) and an owner's pick or selection is written to it with `history.replaceState` (no navigation; two quick picks never undo each other; another deal starts on its own recommended path). Every customer name links to `/customers/{id}?customer&decision&path`; the aside's late-payment link is `/cash?stress=<buyer>:<days>&invoice=<first unpaid invoice>&<context>`. Opened with `customer` or `invoice` in the address, the deals read answers `open_offer.context.back` and the page shows it as "‹ {label}" above the queue.
- **Every figure is a server string.** The comparison's cells are the exposure read's words per path (`lowest_display` with `lowest_when` and `lowest_when_text`, `limit_text`, `share_after_text`; a null `limit_word` is a dash with the authority text, never a word of ours); its first column is the appended `do_nothing` path, which has words only (no line on the chart, no tile in the band, no room entry). The aside is `customer_context` (the contribution with its note, what they owe, their share, the profile link). The recheck sentence beside the button is `priced_response.recheck_text`. A cell the server has no word for is a dash. Counts of tabs are counts of lines. Small caps labels are 13 px; supporting text 13 px minimum.

## Receivables in three layers (map #110)

- **The order.** Status (a dot, the word, "Read today"), the `h1` in two lines (what is expected and from whom; what becomes available at collection once the financing is repaid, only while some invoice is financed), one sentence (nothing is overdue, else the count; then the server's `repays_text` and "it is not money lost"), three `Stat` cards (Customers owe you, Next expected payment, Expected cash at collection; the last takes the `ok` figure only while nothing is late), the filter pills, the invoices, then the selected invoice with the late-payment aside in one card, then what was promised early and what arrived. Every figure and sentence is the server's string; the dictionary supplies labels and glue.
- **Pills.** All, Due soon, Overdue (an overdue invoice or a missed promise), Payment promises, by the server's `collection_state`. A pill with nothing in it is disabled with its count, never hidden. The board's four pills stay even where one would repeat the list.
- **The table.** One `role="table"` of `div`s on `lg` (customer, outstanding, due, financing, net to you, status) and one card per invoice below it. A row is chosen with a single stretched button (its amount); the customer is a link above it (`relative z-10`) to `/customers/{id}` carrying the context. The chosen row is `brand-50` and `aria-current`; focus draws the ring on the row (`has-[button:focus-visible]`). Financing is the amount and three steps (Arranged, Received, Repaid): done steps `ok`, the current one `brand` (`ok` once Repaid), the rest a hollow dot; the dot and word ease in 200 ms (none under reduced motion) and the current step is `aria-current="step"`. No financing says so in one quiet word.
- **The selected invoice** replaces in place (`motion-swap`, 200 ms, the base duration; a polite status announces the invoice once): the condition as the `h2`, the breakdown (invoice, less the financing with its state, less the charges with the per-period note, the cash), the server's recourse and unrecorded-financing sentences, terms, early payment (with the pending counter as a link to the deal) and payment history, then the actions in the server's order as secondary buttons at 44 px. Chase payment and Prepare reminder open the existing handoff dialog; View terms goes to the customer.
- **The aside** is the card's second column from `lg` and follows the invoice on a phone. A left hairline, not a box. The test sentence is the dictionary's; the result (cash at its lowest and when, the shortfall sentence, the financing's extra cost) is the server's, shown only for a deal in context (`?decision=` or the invoice's `pending_counter`); "Explore the cash impact" is the page's one primary and opens Cash with `stress`, `invoice`, `customer` and the rest of the context. Without a deal there is no result and no error.
- **Context** is `customer`, `decision`, `path`, `invoice` in the address (`lib/receivables-context.ts`); the filter is local. Links to routes another ticket builds use `prefetch={false}`.

## Customer overview (`/customers/[id]`, map #88 ticket #108)

A drill-down, never a tab: it opens from a customer's name (`CustomerName` in `components/customer-link.tsx`, one `customerHref(id, ctx)` in `lib/customer-href.ts`) on Deals, Receivables and Activity, carrying `decision`, `path` and `invoice` from the current URL; the server's `context.back` is the back link. In the A1 pattern: the eyebrow and back link, the name as the `h1`, a facts row of the four figures (no tiles; the share figure takes its tone), the one commercial decision as a white card with a `warn-line` border (its primary is the page's one filled button; with no decision the server's `none_text` and the two other links stand unboxed, so no primary), then the economics and the exposure as flat panels on hairlines, and the history as rows. A section is drawn only when the server sent it; while the exposure read is off its panel holds the server's `note`. Every word is the server's.

## Home (V2) as built, in the owner's mockup language

Home V2 is the Home: `app/page.tsx` reads `GET /home` and renders `HomeV2Page` (inside `Suspense`, since the selection is the address). The look is the owner's mockup (`docs/design/flow-mockup-2026-10-13/`: `00_design_language_of_record.md` and its lead's ten decisions are binding; the Home screens 01-06, 18 and 19 are the reference). Every word and figure is the server's or the dictionary's label (INVARIANT 13); Business mode shows no id, code or day number ("Day 30" is "in 30 days", the server's `when`); figures and qualifiers are 13 px or larger; one filled button per state.

- **Tokens** (`app/globals.css`, `@theme static`, each a light and a dark value; the app is light unless `<html data-theme="dark">`). Canvas `#e5e8e8` (app-wide: `--color-canvas`), panel `#f8f9f9` (`--color-panel`), card white (`--color-card`), ink `#151b1c` (`--color-f-ink`), muted `#586468`, hairline `#d8dddd`, the amber, lavender (purple) and green tone pairs (`--color-f-amber` / `-amber-ink`, `-purple-soft` / `-purple-ink`, `-green` / `-green-ink`), the one risk red `#a83222` (`--color-f-risk`), the ink primary button `#171d1e` (`--color-f-btn`), the 24 px card radius and the one soft shadow `0 1px 2px -1px rgb(0 0 0 / 8%)` (`--shadow-f`). The fonts stay (Inter body, Plus Jakarta Sans display).
- **The `.home-f` scope.** Home's root wraps the page in `.home-f`, which maps the kit's own tokens onto the mockup's (ink, muted, hairline, surface to the panel, `brand-600` to the ink button, `brand-50` to the lavender selection, the chart's current line to purple, `bad` to the risk red, the card radii to 24), so the kit (Button, DecisionHighlight-era blocks, the worklist rows, SegmentedTabs, the comparison table, CashPreview) changes look without new primitives and no other page moves. `.f-card` is the card (panel, 24 px, the soft shadow), `.f-card-white` the selected item's.
- **Primitives added.** `StatusPill` (`components/ui/status-pill.tsx`): the server's word on an amber (the owner's turn), lavender (somebody else's turn, waiting, planned) or green (healthy) fill; `StateWord` stays the container-free form for the twelve states. Nothing else is new.
- **Overview** (`components/home/v2/`). The header (`home-v2.tsx`): the headline sentence as the first line, the server's one-line summary (`home_v2.summary_text`, none until it sends it), "Updated today", and the state pill (the alert's `kind_text`, else the status word). Three cards (`home-cards.tsx`, `action-bar.tsx`): Cash available today (the figure, the server's note, the reserve bar: a track to the minimum and a green buffer; risk red and "Short by" when below), What we recommend (a "Planned" pill, the server's title, the planned amount as the figure with the server's hint, the cost to the owner, the plan's control as the page's one filled button, "Compare funding options" outlined, "Funding sources" the disclosure of the composition, and the approval line), Company cash outlook (the lowest figure in risk red, "Without new funding", a mini step chart, "With plan ...", Expand). Then the worklist table (`worklist.tsx`: All / Needs you / Waiting / Customers with counts, a search, Customer / deal, Next step (the server's consequence), Status (the pill with the server's status words); the alert as one line above) beside Upcoming cash movements (the Home read's rail events that move cash, never a second computation) and the footer row (Documents, What-if terms, Evaluate a purchase, Approvals).
- **Selection.** A worklist row replaces the cash and recommendation cards with the selected card (`deal-focus.tsx`: the name and subject, Dismiss, three figures in the server's words (outstanding, the early payment asked, the payment terms asked), FLOW's recommendation, the next-action line with the one filled button, and below it the existing Decision / Consequence / Investigate levels, compare behind the toggle; `customer-focus.tsx` for a customer), keeps the outlook card, and replaces Upcoming cash movements with the Deal context panel (`context-card.tsx`: the stage as the row's own pill, one server sentence, Customer profile, the Agreement and supporting evidence fold). While a selection is open the recommendation is the one-row band (company cash, minimum reserve, an outlined "Review funding plan"). Dismiss and Escape restore the overview and clear the address.
- **Expand** (`company-chart.tsx`, `?expand=1`): the full forecast opens in place under the cards: the current books (purple, the stretches under the minimum in red), the plan as a grey dashed line named "conditional on execution", the minimum with its band, the lowest point, a window switch (compact `SegmentedTabs`), the events of the Home read as chips ("in 12 days . payroll is paid") and the selected event's sentence (the server's `explain`), Open full analysis to Cash and Close. Escape closes it before it clears a selection.
- **States.** Loading is a `LoadingBlock`; a failed Home read is the `ErrorState` with Retry; a `home_v2` the server could not read leaves the header, the server's `partial` sentence (or the dictionary's) with Retry; a failed worklist says so in its card with Retry; "Needs you" empty is the server's `needs_you_empty_text`; a search with no match and a decision that is not open say so; the plan's own states (asking, running, slow, rechecked) are `FixResult`.
- **URL keys** (the address is the only selection state; `lib/home-v2-href.ts`): `customer`, `decision` (`deal:<offer>`), `scenario` (server-validated, unused now), `timing` (`late`), `compare` (`1`), `chart` (`1`, the deal's chart), `funding` (`1`, the composition), `expand` (`1`, the forecast).
- **Layout.** Cards in one row from `lg` (1 : 1.4 : 1), the worklist and the side card in one row (1.7 : 1); one column below, in the mockup's order (cash, recommendation, outlook, worklist as a list with the status pill under the subject, upcoming movements, the footer). The phone has no sheet. The page is fluid: `main#main` holds at most 1680 px with its gutters while the rail is collapsed.
- **The rail** (the Business navigation from `lg`; `components/app-shell.tsx`, `.rail` in `globals.css`). A vertical pill group of the five sections on the canvas: icons only while collapsed (56 px), labels on hover or keyboard focus (a 200 px overlay), the selected one white with the soft shadow; "Keep open" pins it. The brand mark is an ink rounded square. "Ask FLOW" is a quiet outline pill (it is not a second filled button).
- **The server's words for the mockup** (bound): `home_v2.summary_text` (the line under the headline, none when nothing waits), `home_v2.upcoming[]` (the three nearest movements), the asked path's `ask_facts` (invoice value, requested discount, requested term) and `ask_breakdown[]` (the donut's rows with their share words), the receivables rows' `breakdown[]`, `net_after_repayment_display` ("about ¥163k") and `collection_due_text`, which the selected customer's invoice card shows with "View invoice" (`/receivables?invoice=<id>`). The recorder's `--home-v2` mode records them with `receivables_<point>.json`. A donut is sized by the share words and never animates; a row with no share word has no donut. No bank-repayment leg exists on the Demo, so the invoice breakdown has two rows. The authority word beside the cost is the approval line.
- **The history.** The next two sections ("Home V2, wave 2" and "Home V2, refined") record how it was built; where they differ from this section, this one is right.

## Design system (map #88, ticket #112)

One system for the five pages. Where an older section above says something different (a frosted bar, a 12 px floor, three durations, a pill group), this section is right and the older sentence is history.

### Tokens
All in `app/globals.css`, `@theme static`: colours as above (`line` is `#e6e9ef`; `track` is `#eef1f5`, the segmented control's track), radii pill / 16 (`--radius-decision`) / 14 (`--radius-card`) / 10 / 8, shadows decision / lift / pop / pill / up, and the type and motion scales below. Brand `#0368e9`; `ok`, `warn` and `bad` keep their meanings. No new font, no new hue.

### Three card types
| Card | Look | Use it for |
|---|---|---|
| `Card` (`.card-standard`) | 14 px radius, `line` hairline, no shadow, white | Everything that is content in a box: a block of facts, a table, a list, an empty or error state. The default; most things on a page are not boxed at all. |
| `DecisionCard` (`.card-decision`) | 16 px radius, hairline, `--shadow-decision`, white | The one thing the owner is asked to decide: Home's attention card and plan bar, the Deals reply bar, the first waiting approval (the others are standard cards), Receivables' chase bar, a document's decision bar (`ActionBar` is its sticky form). One per page; its one filled primary is a child inside it (there is no separate action slot: the cards that exist lay their action out in their own row). Solid: no frost, no blur. |
| `SelectedCard` (`.card-selected`) | `brand-50` fill, a 3 px `brand-600` left rule, `brand-100` hairline | The item whose detail the page is showing: Receivables' chosen invoice strip, the chosen path column on Deals. A chosen row in a list (the queue's line, the invoice's row) is the same selection, `.row-selected`: the same tint and the same 3 px rule. It says "this is the one", never a status. |

Padding: a `Card` is 20 px (`p-5`), a decision card 20 px (16 px on a phone), a selected card 16 px. A card is a card by its class and nothing else: no `shadow-*` or `bg-surface/…` on a card, no second box inside a card for the same thing, and a status colour on a card is a 1 px tone line (`Card`'s `tone`), never a tint behind prose.

### SegmentedTabs
`components/ui/segmented-tabs.tsx` (behaviour in `segmented-tabs-model.ts`, unit-tested): a tablist for choosing among two to five views of the same thing, an icon and a label on each (icons from `components/icons.tsx` only), an optional count `badge` (a small filled circle: `bad-solid` only for a count that needs the owner, `line-strong` for any other, and "0" is shown). Use it where the choice changes what is shown below it and the owner will move between options: the Receivables filter, the Deals queue's four tabs, the Home window and scenario. Do not use it for a form field (a radio group), an on/off (a toggle button) or navigation between pages (links). A disabled option is one with nothing behind it, never hidden. Keyboard: Tab enters at the selected tab; Left / Right (and Up / Down) move and wrap and skip a disabled option, Home and End jump, the selection follows the focus.

### StateWord
`components/ui/state-word.tsx` (the table in `state-word-model.ts`, unit-tested) is the one way a status is drawn: icon, colour and the word the server wrote, with no container (the old `StatePill` and the pill variant are retired). Two ways in. `state` is one of the twelve states the owner's money moves through, each with a glyph of its own and a fixed tone that nothing overrides, so "arranged" is the same blue on Home and on Receivables: `planned` (a dashed ring, blue), `arranged` (a ring with a dot, blue), `received` (a check, green), `repaid` (a check in a ring, green), `owed` (a document, grey), `scheduled` (a calendar, grey), `agreed` (two rings, blue), `pending` (an hourglass, amber), `current` (a ring, green), `due_soon` (a clock, amber), `overdue` (an alert, red), `promise_missed` (a cross, red). `tone` is for a status the server names that is not one of the twelve (an approval's result, a deal's "Needs your response"): the server's `state_tone` / `result_tone`, with the tone's own mark (check, alert, cross, ring with a dot, ring). The text is always the server's (`collection_state_text`, a `basis_text`, the lifecycle's three words). Three shapes: the word (a table cell, the rail's "planned"), the line (a receipt's basis sentence in the quiet ink) and the step (the lifecycle's word alone, its disc drawn by the list). In the lifecycle a step reached is its state's word in the state's own tone; a step still to come is quiet text, because it is not a state yet. Colour is never the only channel: the mark and the word say it too. No page composes a state word itself. The Customer overview carries no state field yet; it takes `StateWord` when the server sends one.

### Type scale
Seven roles as CSS variables (`--text-headline`, `--text-value`, `--text-section`, `--text-card-title`, `--text-body`, `--text-supporting`, `--text-meta`), the first four with kit classes (`.type-headline`, `.type-value`, `.type-section`, `.type-card-title`): headline 26 / 34 / 36 px by width (phone / `md` / `lg`), major value 24 / 28 / 30 px tabular (the headline always dominates it), section 18 to 20, card title 16, body 14 (15 for the sentences that carry a page), supporting 13, metadata 12. 13 px is the floor for a figure or any qualification of one; 12 px is for a label, a time or a legend. The audit of the five pages lifted every 12 px figure and qualification (caption, table head, badge, basis line, formula) and every chart tick or line label that carries money or a date (SVG text included) to 13 px, and `e2e/design-system.spec.ts` keeps it so.

### Sidebar
From `lg` the Business sidebar is 15 rem. On a laptop (1024 to 1366 px) an icon button at its foot (a chevron that points the way it will move, `aria-expanded`, its name "Collapse the sidebar" / "Expand the sidebar" in both languages as its accessible name and as a tooltip on hover and keyboard focus) collapses it to 4.5 rem of icons: each destination keeps its full accessible name, its word appears beside the icon on hover and on keyboard focus (opacity, `--dur-fast`), a count becomes a badge on the icon's corner, the note at the foot is hidden and the Ask FLOW pill is its icon. The choice is in `localStorage` (`tl-sidebar`, read and written inside try/catch: storage that refuses it still collapses for the visit) and is on `<html data-sidebar="collapsed">` before the first paint (`lib/pre-hydration.ts`, read in a try of its own so a bad value cannot skip the language), so a collapsed sidebar never flashes open. Wider than 1366 px there is no toggle and the sidebar is always full; below `lg` the phone tab bar replaces it. The five destinations and the Customer drill-down (which has no destination of its own) are unaffected.

### Reduced motion
Only opacity transitions remain, at their own token's duration; animations end at once; a native `<details>` opens at once (its `::details-content` height transition is off too). The one hook is `lib/use-reduced-motion.ts`.

### The banned list
No gradients, no glows, no particles, no parallax, no glassmorphism on the dashboard (no frost, no backdrop blur, no blurred discs: the page backdrop is gone), no count-ups on load, no decorative badges (a badge says a status or a count), no internal labels ("Executive snapshot", "Autonomous strategy", "Retained yield", "Treasury engine", "Live stress simulation": "FLOW recommends" is the only product voice). A reviewer who finds one on a page removes it.

## Home V2, wave 2 (history)

- **When it renders.** Always (history: it was first behind the server's `FEATURE_HOME_V2` and a session key in the mock).
- **Order** (`components/home/v2/`). The header ("Home", the status dot and word, "Read today"), the company strip (one `Card`, three cells on hairlines, rows on a phone; the cash cell carries the `CashBufferIndicator`, a thin scale with the minimum mark and the cash dot, never a progress bar; no sparklines), the action bar (the page's one `DecisionCard` when there is an action, an unraised `Card` for the quiet variant; the plan's confirm-and-run control is the one filled primary with the same `fix-open-*` ids, Compare beside it), the company cash chart (`EventPicture` with `compact`: the current books solid, the plan that is ready as the grey dashed comparator, the server's legend and scope title, one pressable lowest point that opens the server's inspector under the chart, Escape closes it; no rail, no numbered marks), the link row and the worklist.
- **Worklist.** A 360 px `Card` from `xl`, a "Worklist (N)" button and a native modal bottom sheet on a phone. The company alert is pinned above the tabs and counted nowhere; `SegmentedTabs` Needs you / Waiting / Customers (the badge is on Needs you only, and only above zero); a search over the rows already fetched by the customers' `search_terms`; three row shapes with a `StateWord` severity at the right; a fresh read never reorders the list while focus is in it. Wave 2 opens a decision in Deals and a customer in the Customer overview (`lib/home-v2-href.ts`).

### Home V2, refined (13 October 2026, the owner's second and third reviews)

- **Kit (components/ui).** `OpenSection` (a hairline above, 32 px margin and padding, sentence-case display headings, a 13 px scope label), `MetricStrip` + `Metric` (hairlines, a 32 px display figure, one note, a 20 px info control opening the second sentence in a `--shadow-pop` popover), `DecisionHighlight` + `HealthBand` (the tinted recommendation; the one-row band with an OUTLINED button while a selection is open), `ActionGroup` (one filled button per page, every other decision level outlined, a text link only to leave the page), `WorklistRows` (underline tabs with neutral counts, a hairline search, a one-line alert with a 2 px rule, three-line rows with a severity dot and word for CAUTION and CRITICAL only, selected = `brand-50` + a 2 px rule) and `ComparisonTable` (a 150 px row head, the recommended column tinted, a 600 px minimum with sticky row heads, stacked below 1024). `SegmentedTabs` gains `compact` (32 px, radius 10, a thin border, a white pill with its own border and no shadow) for the window and the payment-timing assumption.
- **Page.** `components/home/v2/`: the header ("Home", the status sentence with its dot, "Updated today"), the strip, the recommendation, `CashPreview` (280 px, three gridlines, the reserve with the danger tone, the current books with the stretches under the reserve in red, the plan dashed and named "conditional on execution", a fixed inspector strip under the chart: When, projected cash, the plan, the shortfall, then "On that day, ..." from the server's cause and events), the one chart link, the link row, the worklist pane. The page's background is the shell's canvas, so the tinted blocks are `surface` and a row's hover is `surface`.
- **A deal, in three levels.** Level 1, the decision (breadcrumb, verdict word, subject, the customer line with "View customer", the buyer's ask, FLOW's recommendation with its sentence and cost, the request's cost, and the action group: "Review counter" filled, "Compare responses" and "Cash impact" outlined toggles that expand in place and keep focus, "Open in Deals"); level 2, the consequence (the payment-timing assumption as compact tabs and one table of the request against the recommended option: lowest cash, reserve, within limits, approval, then the scenario's assumption sentence); level 3 only on request (the full table of every response with the authority evidence under each name, "Why FLOW recommends", a "Financial impact" fold, and the deal's own chart with a same-day inspector: the recommended option solid, the request grey with its stretches under the reserve in red). The address keeps `customer`, `decision`, `compare`, `chart` and `timing`.
