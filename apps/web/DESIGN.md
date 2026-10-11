---
name: FLOW web
description: A light fintech surface for a supplier's owner (midnight-blue ink, royal-blue action, sans headlines in weight 800, a sidebar on the canvas), status colour only for status, five section hues for wayfinding, Home seamless with one raised frosted surface, and the navy block kept for the Demo strip.
colors:
  canvas: "#f5f7fb"
  surface: "#ffffff"
  subtle: "#eff3f8"
  line: "#e6eaf0"
  line-strong: "#d3d9e2"
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
  chart-grid: "#e6eaf0"
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
    fontSize: "40px"
    fontWeight: 800
    lineHeight: 1.12
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "24px"
    fontWeight: 600
    lineHeight: 1.375
  title:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.025em"
  figure:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: 1.4
    fontFeature: "tnum"
  body:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Lato, Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.33
    letterSpacing: "0.025em"
  mono:
    fontFamily: "ui-monospace, 'SF Mono', 'JetBrains Mono', Menlo, Consolas, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.625
rounded:
  pill: "9999px"
  card: "14px"
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
  plan-bar-frosted:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
    padding: "16px 20px"
  segmented-track:
    backgroundColor: "{colors.subtle}"
    rounded: "{rounded.pill}"
    padding: "2px"
    height: "36px"
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

A light, flat, calm surface for a supplier's owner who reads cash the way a banker reads a statement: a faintly cool canvas under solid white cards, one confident blue that only ever means "the next step", and status colour that only ever means status and always comes with a word. The one deep moment is the navy Demo strip. Home has no hero card: the status pill, the headline and one chart sit directly on the page, and the plan is the one raised surface, a frosted bar. Density is a banking app's: 14 px data in rows and tables, 16 px inside a card, fact tiles with a 12 px label, a 20 px figure and a 12 px caption, 24 px of air between sections.

Depth is "lifted base": a card rests on a hairline and a whisper of shadow, a row lifts one pixel on hover, a sheet or dialog takes a deeper pop. Motion is ease-out, under 300 ms, transform and opacity only; nothing moves the layout (the cash picture's one draw on mount is the single, named exception). Wayfinding is in colour: each of the five Business sections owns a hue that appears on its icon chip, its tab, its shortcut and a buyer's avatar, never on a status. Both the English and the Chinese shells live in one type stack that falls through to the system's Latin and CJK faces: no web font is fetched from a font host.

Confirmed rejections: no dark theme (`color-scheme: light`), no gradient on a button or a card, no coloured rail on a card's edge, no runtime web fonts (a font is bundled with the app or it is not used), no browser-drawn sparklines (a labelled chart drawn from the server's own series, with its figures in the server's strings, is not a sparkline: it has days along its foot, named lines, a named reserve and a table behind it), no text below 12 px, and no money computed in the browser (every figure, date and sentence arrives formatted from the server).

**Key Characteristics:**
- Light only, flat materials, white cards on a cool `canvas`, lifted by shadow steps rather than tone; Home is seamless (no hero card, rows with hairlines) with one raised, frosted surface.
- One brand blue for the page's single primary action, links, focus and selection; never a status.
- Status tokens (`ok`, `warn`, `bad`, `info`) in five weights each, always paired with a word.
- Five section hues for wayfinding only; teal and orange pushed away from green and amber.
- One radius scale: 8 px controls (buttons, toggles, fields), 14 px cards, 10 px inner tiles, and a pill for badges, chips, avatars and the segmented track.
- 14 px body and data, 12 px floor, tabular figures, right-aligned money that never wraps.
- Ease-out motion kit (120 / 200 / 280 ms), reduced motion honoured and forced in tests.
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
- **Ink / ink-2 / ink-3** (`ink`, `ink-2`, `ink-3`): text primary, secondary, quiet. `ink` 12.0:1 on canvas, 12.8 on white; `ink-2` 6.8 on canvas, 7.3 on white, 6.5 on subtle; `ink-3` 5.4 on canvas, 5.8 on white, 5.2 on subtle, 5.1 on `brand-50`, 5.5 on an open table row (`subtle` at 60% on white), 5.5 on a late row (`bad-bg` at 40% on white), 5.1 / 5.2 on the strongest point of the backdrop discs (`#ebf1fa`, `#ebf2f6`). `ink-3` is for captions, never for anything the owner must act on.
- **Focus** (`focus`, `focus-on-deep`): the brand ring, 4.7:1 on canvas, 5.0:1 on white, 4.4:1 on `brand-50`; white inside the deep block (12.8:1).

### Named Rules
**The One Primary Rule.** One brand-filled action per page. Every other step is a secondary button, a ghost, or a text link.
**The Status Speaks Rule.** Status colour means status and nothing else, and it is never the only channel: the word is always there, the dot or tint is the second voice.
**The Hue Is a Place Rule.** A section hue says where you are or where a link goes; it never says how things are going.
**The Deep Block Rule.** `brand-900` is the Demo strip only. It stays navy.
**The One Raised Surface Rule.** On Home the plan bar is the only raised surface: a frosted `surface` at 84% with a backdrop blur, a hairline and `--shadow-pop`, sticky at the bottom of the window from `lg` until the reader reaches its place. Everything else on Home sits on the canvas, separated by hairlines; a block that asks the owner to decide something (an approval, the remaining task) keeps the white card.
**The 4.5 / 3 Rule.** Every text pair 4.5:1 or better, every visible boundary and icon 3:1 or better, on the surface it actually sits on (tiles, rows, discs and tints included).

## Typography

**Display Font:** Plus Jakarta Sans, weight 800, then the body sans below (`font-display`: page titles, the Home headline and its cash figure, the plan's title, the deal picture's figures)
**Body Font:** Lato if the machine has it, else Inter, then `ui-sans-serif` / `system-ui` and the platform's Latin and CJK faces (PingFang SC, Hiragino Sans GB, Microsoft YaHei, Noto Sans CJK SC)
**Label/Mono Font:** `ui-monospace`, SF Mono, JetBrains Mono, Menlo, Consolas (hashes, formulas, code)

**Character:** one sans family in two voices: the display voice is Plus Jakarta Sans at weight 800 with `-0.02em` to `-0.025em` tracking, everything else is the body sans. The face is bundled (`@fontsource-variable/plus-jakarta-sans`, imported once in `app/layout.tsx`, registered as "Plus Jakarta Sans Variable"): its woff2 files are served by the app itself, only the subsets a page uses are fetched, and nothing comes from a font host, so "no runtime web font" stays true where Google Fonts cannot be reached (the Demo is judged there). Lato is named first in the body stack so a machine that has it uses it; every stack falls back to faces the platform already has, and the layout must hold in the fallback (it is what the tests and the screenshots see). Weight does the work: 800 for headlines, 600 for titles, figures and labels, 500 for controls and row titles, 400 for sentences. Antialiased, `text-size-adjust: 100%`. The serif and the "Flow Figures" digit workaround are gone: a sans face sets lining figures by itself.

### Hierarchy
- **Display** (800, 28 px, 36 px from `sm`, 40 px from `lg`, line-height 1.12, `-0.025em`): the Home headline, the one `h1` on the page; the cash figure beside the picture is 24 px; the Today card's day number is 30 px.
- **Headline** (800, 24 px / 30 px from `lg`, line-height 1.375): page titles, a deal's recommendation, a plan total, the plan bar's title at 22 px.
- **Title** (600, 20 px, tight tracking): a page title (`PageHeader`), and the `Stat` figure at `size="lg"` (24 px from `sm`; 20 px on a phone).
- **Figure** (600, 20 px, `tabular-nums`): the `Stat` figure (18 px on a phone), a row's amount at 14 px; every money column is `tabular-nums`, right-aligned, and a cell that holds an amount never wraps.
- **Body** (400, 14 px, line-height 1.45): sentences, data in a table or a row, the subtitle under a page title, controls. Headlines and card titles are `text-balance`; the sentences under them `text-pretty`.
- **Label** (600 / 500, 12 px, `0.025em` tracking when uppercase): a tile's label and caption, table heads, badges and chips, tab words, captions, the nav's section heading in Demo. 12 px is the floor: nothing is set below it, so there is no `text-2xs`.
- **Mono** (400, 12 px, line-height 1.625): hashes (shortened, with copy), formulas (`Formula`, in a `subtle` tile).

### Named Rules
**The Twelve Pixel Floor Rule.** No text is set below 12 px, on any surface, in any language.
**The Tabular Money Rule.** A figure is `tabular-nums` and semibold or heavier; in a column it is right-aligned and never wraps. Figures are lining in every stack.
**The Sentence Before the Formula Rule.** A calculation is said in body text first; the formula follows in mono, in its own tile.

## Layout

From `lg` a sidebar of 15 rem on the canvas (the active item a white pill) and a centred column of 1120 px at most beside it, 16 px of side padding (40 px from `lg`), 20 px under the sticky header (32 px from `lg`). The header is the canvas at 70% with a blur and no border at rest, so it is invisible at the top of the page and reads as frosted glass once content passes under it. Sections sit 24 px apart (`space-y-6`, 28 px on Home); inside a card the padding is 16 px (`p-4`), a card's header row is 16 px by 12 px with a hairline under it; tiles sit 12 px apart (`gap-3`); the chips and controls in a row sit 8 px apart (`gap-2`); the hero keeps its own 20 px. Everything is on a 4 px base.

Breakpoints are Tailwind's: `sm` 640 px, `lg` 1024 px, `xl` 1280 px, plus a 1440 px (`90rem`) step for the dock and a `touch:` variant that is "below `lg`, or a coarse pointer at any width". A row of three tiles is `grid-cols-2 sm:grid-cols-3` with the first tile spanning two columns on a phone. `KeyValueList` stacks label over value on a phone and goes two-column from `sm`. The cash chart on `/cash` is 256 px tall (320 px from `sm`); the Home cash picture is 250 px (300 px from 520 px wide) and is drawn at the width it has. Below `sm` the Cash backdrop disc is dropped; below `lg` the desktop pill nav is replaced by the fixed phone tab bar and the Demo sidebar by a menu.

**The dock.** A fixed bottom bar (the phone tab bar, the Demo stepper) publishes its measured height as `--dock-h` on `html` (`useDock` in `app-shell.tsx`; 0 when the bar is not fixed). `main` takes `.dock-pad`: the bar plus 24 px below `sm`, the bar plus 72 px (room for the Ask FLOW pill) from `sm`, 80 px from `lg` where there is no bar, and the pill sits in the sidebar's foot, not beside the column. `html` takes a matching `scroll-padding-bottom`, so the last row of a page and a focused control always clear both the bar and the pill.

**Touch.** Wherever a finger is the pointer every control reaches 44 px: `Button`, `toggleClass` and a `Disclosure` summary grow to `min-h-11` (the desktop 32 / 40 px look is unchanged); a small chip that must stay small (a segmented option, the account button, the copy-hash icon, a text link) keeps its look and takes `.hit`, a transparent 44 x 44 pseudo-element centred on it. Inline links in a sentence are exempt.

### Named Rules
**The 14 / 16 / 24 Rule.** 14 px data, 16 px inside a card, 24 px between sections.
**The Dock Rule.** Nothing fixed to the bottom covers content or another fixed thing: the bar measures itself and the page pads to it.
**The 44 px Rule.** Every control a finger can press reaches 44 px, by growing or by a transparent hit area; the desktop look does not change.

## Elevation & Depth

A lifted base: solid white cards on a cool canvas, each resting on a 1 px hairline and a soft two-layer shadow. Depth is a response to role and state, not decoration: a card at rest takes `--shadow-card`; the plan bar takes `--shadow-pop` on a frosted surface; a row, tile or option that leads somewhere lifts 1 px and takes `--shadow-lift` on hover (only on devices that hover); a sheet, menu, the chat panel and the Ask FLOW pill take `--shadow-pop`; the Demo strip fixed to the bottom of a phone casts `--shadow-up`. There is no tonal layering of surfaces; `subtle` is a fill for a track or a head, not a level. The translucent surfaces are the plan bar (`surface` at 84%, 18 px blur) and the top bar (`canvas` at 70%, blur). The Business pages sit on a backdrop of two blurred discs (Home blue, Cash teal; 64 px blur at 35%) that drift once over 40 s and then rest; cards stay solid on top.

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 2px rgb(15 28 46 / 0.05), 0 6px 14px -10px rgb(15 28 46 / 0.12)`): a card at rest, the segmented thumb, a link tile.
- **Lift** (`box-shadow: 0 2px 4px rgb(15 28 46 / 0.06), 0 12px 22px -14px rgb(15 28 46 / 0.22)`): a row, tile or option on hover (`motion-lift`).
- **Pop** (`box-shadow: 0 4px 8px rgb(15 28 46 / 0.06), 0 18px 36px -12px rgb(15 28 46 / 0.24)`): the account sheet, the chat slide-over, the walkthrough card, the floating Ask FLOW pill, the skip link.
- **Up** (`box-shadow: 0 -4px 12px rgb(15 28 46 / 0.08)`): the Demo strip fixed to a phone's bottom edge.

### Named Rules
**The Hairline First Rule.** A card's edge is a 1 px `line`; the shadow is the whisper under it, never the boundary.
**The No Rail Rule.** No gradient on a button or a card, and no coloured rail on a card's edge: a status is a pill with a word, a tone is a 1 px tone line.

## Shapes

Four radii and nothing else. A control is a rounded rectangle (`8px`, `rounded-control`): buttons, toggles, text fields and selects. A container is a card (`14px`): cards, the hero, disclosure cards, tables, dialogs, the chat panel's edge, empty and error states, the drop zone, the walkthrough card and its spotlight. What sits inside a card is a tile (`10px`): fact tiles, list rows with a border, option rows, callouts, skeletons, formulas. What is a mark or a label is a pill (`9999px`): badges, chips, status pills, the segmented track and its thumb, icon chips, avatars, the chat composer, the account button, a text link's hover. A multi-line text area takes the card radius (a pill clips the corners of a second line). Borders are 1 px: `line` when decorative, `line-ui` when the edge must be seen, a tone's `-line` when the surface is a tint, dashed `line-strong` on an empty state. Icons are from `components/icons.tsx` only, at 16 or 20 px, `currentColor`; the one exception is a section chip, a 40 px disc (48 px `lg`) with a white 20 px icon on the section's solid.

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
- **Badge** (`tone`): a pill with its tint, its `-line` border and (for a status) a 6 px `-solid` dot; 12 px medium, 10 px by 2 px padding, `whitespace-nowrap`. Neutral and brand badges (a tier, a count, "Recommended") carry no status and no dot.
- **Chip:** a Badge without the dot, for a tag that carries no status (a channel, a kind). A label that is a whole server sentence (a plan's `role_reason`) takes `wrap`: it breaks inside its pill and never runs wider than its row.
- **Ranking:** wherever the server ranks, the rank is a numeral (a column in a table, `#1` on a Cash plan, a number before a buyer on a phone) and the order is the server's. "Recommended" is the brand badge wherever the server marks a row; an alternative says why in a neutral chip.

### Cards and containers
- **Card:** `14px` radius, white, `line` hairline, `--shadow-card`, reveals on mount (`motion-reveal`). An optional header row (title 14 px semibold, subtitle 12 px `ink-3`, actions on the right) with a hairline under it; the body is 16 px padding. A card's `tone` is a 1 px tone line, never a rail. A section with nothing in it is not a card around nothing: on Activity the empty Agreements and Refused sections are one quiet `ink-3` line each (title, colon, the sentence), and the empty Timeline is the same line inside its card.
- **Callout** (`tone`): a `10px` tile on the tone's tint and line; its title in the tone's fg, its body in `ink-2`.
- **TableWrap / table:** a scrollable `role="region"` with a card radius and hairline; heads are 12 px semibold `ink-2` on `subtle`; cells are 14 px with a `line` rule, 12 px by 8 px padding, last row unruled.
- **Link tile** (`DoorTile` in `app/cash/page.tsx`): a quiet bordered card-radius tile with what the door is for (14 px semibold, 12 px `ink-3` under it) and one text link stretched over the whole tile; lifts on hover.
- **Stat:** the one fact tile (hero tiles, Cash facts, Receivables summary, the Deals ceilings and recommendation facts, the Mandate limits, the next step's cost, landing and authority). A `10px` tile, 16 px by 12 px padding, in a `<dl>`: an uppercase 12 px semibold tracked label (`ink-3`), the figure (`tabular-nums`, 18 → 20 px, 20 → 24 px with `size="lg"`; its colour is a status only when `tone` names one), a 12 px `ink-3` caption (when, of what, against what; a second line is a second `block` span) and, only when the server sent a `delta_display`, a delta chip (neutral unless the server names its tone; the browser never subtracts). Two surfaces: `surface` (white, a `line` hairline) and `deep` (the Home hero: `on-deep` at 10%, label and caption in `on-deep-muted`, a status figure in its `-bright` tone). `tint` fills the tile with its status tint for the one tile that says who decides. A caption may carry a related figure (the headroom under the reserve and under the lowest point) with its own test id.
- **Avatar** (`kit.tsx`): a 36 px disc, 12 px bold. A change row's icon sits on its status tint; a buyer's initials sit on a section tint (`toneFor(name)` is stable per name, four hues, never orange).
- **Row** (`kit.tsx`): an avatar, the title (14 px medium) with a quiet 12 px line under it (in `bad-fg` or `warn-fg` only when the row's `tone` is that status), on the right the figure (14 px semibold tabular) with its note; with `href` the whole row is a link with the chevron and lifts on hover (`10px` radius, `subtle`). Rows are 48 px minimum and divided by hairlines.

### Inputs / Fields
- **Style:** `inputClass`: an 8 px rounded rectangle, 40 px, `line-ui` border, white, 16 px padding, 14 px `ink`, placeholder `ink-3`. `textareaClass`: the same in a card radius with 10 px by 16 px padding and relaxed leading. The caret is `brand-600`; checkboxes and radios take the brand accent.
- **Focus:** the global ring. **Disabled:** inherited from the button rules (50% opacity).
- **Segmented / SegmentedButtons:** a pill track (`line-ui` border on `subtle`, 2 px inset) with a sliding white pill thumb carrying `--shadow-card`; options are 32 px, 12 px medium, `ink` when selected and `ink-2` otherwise, each with `.hit`. `Segmented` is a radio group (the Business/Demo switch, the language switch); `SegmentedButtons` is the same track made of `aria-pressed` buttons (the forecast horizon). The thumb moves by transform (`motion-slide`).

### Navigation
- **Sidebar** (`app-shell.tsx`, from `lg`): the five sections as 44 px rows (icon and word) on the canvas, no fill of its own; the active one is a white pill with a whisper of shadow, `brand-700` bold text and `aria-current="page"`, the rest `ink-2` with a `subtle` hover. The header above it is sticky and frosted (see Layout); the brand mark is a 32 px brand-blue disc.
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
- **Signed out (401 / 403):** not an error. `role="status"`, a white card with `--shadow-card`, "Sign in to see this" in `ink`, the reason in `ink-2`, and the page's one primary "Sign in" (`data-testid="signin-needed"`).

### Dialogs and the tour
The chat and the walkthrough (`components/business/tour.tsx`) are native `<dialog>`s (`showModal`: the page behind is inert, Escape closes, focus returns). The walkthrough's card is 24 rem wide at most, card radius, white, `--shadow-pop`, scaling in (`motion-pop`); its spotlight is a card-radius hole ringed in white, cut from `ink` at 60%, tracked with a `ResizeObserver` and scroll, never a timer, and it jumps between steps. The tour returns focus to the account button when it closes.

### Cash picture (`components/home/cash-picture.tsx`)
Home's one chart, plain inline SVG drawn in pixels from the measured width (so its 12 px type is 12 px at any width), fed by the same `HomeView` as the forecast on Cash. Two step-after lines: "If you do nothing" (`bad-solid`, `brand-600` when nothing is unsafe, 3.5 px alone and 2.5 px at 60% beside the plan) and "With FLOW's plan" (`ok-solid`, 3.5 px; drawn only when a plan exists and differs); a segmented toggle (`SegmentedButtons`) above, right-aligned, only when there is a plan, defaulting to the plan. The window runs from today to the later of 30 days and four days past the last interesting day (the first breach, the lowest point, the day the line is back above the reserve, the plan's last landing), capped at 60 days and the server's horizon. The scale comes from the data with zero and the reserve always inside. The reserve is a dashed `warn-solid` line named with the server's `floor_short`; the area between the line and the reserve where it is under is `bad-solid` at 10%, the part under zero at 15%. The first breach is a dot with one pulse; the lowest points are labelled with `lowest_short` and `after_lowest_short`; the three largest events of the do-nothing line and the plan's own draws and advances are labelled with the server's `label_short` and `amount_short` beside their step. **A label that would touch a line, another label or the plot's edge is skipped** (its box is estimated from its characters), never drawn over; below `sm` the reserve label is only ever tried under the dashed line and is skipped like the rest. The two lines are named beside themselves, so colour is never the only channel. No axis figure is made in the browser: the foot is days ("Today", "in 10 days", from `biz.when.*`), and the figures are the server's strings. Under the picture "What moves your cash" is one button per event in the window (label, amount, distance, `aria-pressed`); pressing one lays a soft `brand-600` band over that day, pressing it again clears it. The SVG is `role="img"` with an `aria-label` assembled from the server's headline, note and after-plan sentences, and a visually hidden table lists the labelled days.

### Cash forecast (`components/business/cash-forecast.tsx`)
A step-after area chart with a horizontal-only grid in `chart-grid`, axis text in `chart-axis` at 12 px, the cash line 2 px `chart-base` with an 8% fill, the plan a 2 px dashed `chart-plan` (9 / 5), the reserve a 2 px dashed `chart-reserve` (6 / 4) named in the legend rather than on the line, the first unsafe day a 2 px dotted `chart-reserve` vertical with its label, the band below the reserve in `chart-danger`, event marks as 4 px white discs stroked in `chart-plan` (money in) or `chart-reserve` (money out), the breach a 6 px `chart-reserve` disc, the worst point a `chart-worst` mark with a bold label. Labels are 12 px (the floor), placed in pixels against the measured drawing: event labels alternate above and below the line, none within 24 px of another or of the first unsafe day and the lowest point, up to four; below `sm` there are no event labels (the marks stay, up to three, and the tooltip lists the day's events). The worst-point label is dropped when the worst point is the reserve. A label is pushed in from whichever edge it would cross; two events that read the same (one buyer's two receipts) share one label and the tooltip names the later one. The tooltip is a white card-radius box with the day's events as the server's `label: amount_display`; its cursor is a 3 / 3 dashed `chart-axis` line. The horizon is a `SegmentedButtons` track; a "Show the figures as a table" Disclosure carries the same rows as text. Recharts' focusable SVG takes the global ring. Chart animation is off; the browser draws no sparklines.

### Browser surfaces and first paint
Text selection is `brand-100` on `ink`; the caret and checkboxes are `brand-600`. `color-scheme: light` on `html`: there is no dark theme; the scrollbars, form controls and dialog backdrop must not take a dark phone's. An inline script in `<head>` (`lib/pre-hydration.ts`) reads `tl-lang` and `tl-mode`, sets `lang` and `data-mode` at once, and keeps the body hidden (`data-pending`) while the server's Business/English markup would be the wrong shell or language; the shell clears it after hydration (a 2 s timer is the way out). The tab title of every route is server metadata (`lib/route-title.ts`, one `layout.tsx` per route); the shell puts the owner's language in.

### Backdrop (`components/business/backdrop.tsx`)
Two blurred discs (Home blue, Cash teal: the section solid at 12% in the canvas, 64 px blur, 35% opacity) that drift once over 40 s and then rest, at a strength that keeps `ink-3` above 4.5:1 on their strongest point (the Cash disc is left out on a phone). Behind the Business pages only; cards stay solid.

### Motion
Ease-out, short, transform and opacity only. Two deliberate exceptions: a disclosure's height, and the cash picture's one draw (`stroke-dashoffset`, once, on mount).

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.2, 0.8, 0.2, 1)` |
| `--dur-fast` | 120 ms (a press) |
| `--dur` | 200 ms (hovers, switches, sheets, disclosures) |
| `--dur-slow` | 280 ms (a card or row arriving, a panel sliding in) |

| Class | What it does |
|---|---|
| `motion-reveal` | a block fades in and rises 6 px on mount (the hero, `Card`, `PageHeader`, disclosure cards, the next-step band, empty and error states) |
| `motion-rise` on a list | rows rise one after another, 30 ms apart, for the first eight; a ninth row just appears |
| `motion-lift` | hover lifts 1 px and takes the next shadow step (rows, tiles, option rows, link tiles), only where hover exists |
| `motion-press` | a button scales to 0.98 while pressed and eases its colour |
| `motion-slide` | a thumb or indicator moves by transform (the segmented thumb, the tab bar's active bar) |
| `motion-sheet` / `motion-panel` / `motion-pop` | the account sheet drops in from its corner; the chat slide-over enters from the right; the walkthrough card scales in |
| `motion-pulse` | the status dot's ring grows to 3x and fades once (900 ms, after 400 ms), for ACTION_NEEDED and CRITICAL only (never on a calm status) |
| `.disclosure-body` | a one-row grid from `0fr` to `1fr` with a fade; other `<details>` use the browser's `::details-content` height transition where it exists |
| `.biz-disc` | the backdrop's one 40 s drift, then rest |
| `.picture-draw` / `.picture-fade` / `.picture-pulse` | **the chart's one draw**: on mount the do-nothing line draws (`stroke-dashoffset`, about 900 ms), the plan line after it, then the shortfall and the labels fade in and the first breach pulses once; later toggles and chips never replay it. A deliberate exception to "transform and opacity only", on one SVG, once. |

The Tailwind transition utilities (`transition-colors`, `-opacity`, `-transform`) take `--dur` and `--ease-out` as their default, so a bare one still comes from this kit. Nothing animates width, height (but the disclosure), margin or position, so nothing shifts the layout. `prefers-reduced-motion: reduce` sets every duration to 0.001 ms, removes delays and loops, cancels the hover and press transforms, stops the backdrop and replaces the `Spinner` arc with an ellipsis after the label. The Playwright config sets `reducedMotion: "reduce"` so every spec runs without animation.

### Language and figures
Every string is in the dictionary in both English and Chinese (`lib/dictionary.ts`: 1608 keys each, `zh` typed as `Record<DictKey, string>` so a missing twin fails the build); `<html lang>` follows the owner's choice (`en` / `zh-CN`). One plural template (`{n|invoice|invoices}`) serves every count. The browser computes no money: every figure, date and sentence arrives formatted from the server as a display string (`*_display`, `*_short`, `*_when`, `event_text`, `label_short`), traceable to a formula; the client does no regex rewrite, approval inference, subtraction or truncation. Business mode shows no engine terms and no day numbers.

## Do's and Don'ts

### Do:
- **Do** take every colour, radius, shadow and duration from `app/globals.css`; no hex lives in a component.
- **Do** give each page one brand-filled primary; make every other step a secondary pill, a ghost or a text link.
- **Do** pair every status colour with a word (the pill, the dot and the tint are the second channel).
- **Do** use a section hue only to say where you are or where a link goes: the page chip, the tab, a shortcut, a buyer's avatar.
- **Do** keep text at 12 px or above, body and data at 14 px, and set every figure `tabular-nums`, right-aligned in a column, never wrapping.
- **Do** use `Stat` for a fact, `Disclosure` for a fold, `Badge` for a status, `Chip` for a tag, `Row` for a list line, and the one `FoldChevron`.
- **Do** hold every text pair at 4.5:1 and every boundary and icon at 3:1 on the surface it actually sits on; use `line-ui` for any edge that must be seen.
- **Do** reach 44 px on touch by growing a control or giving it `.hit`; keep the desktop 32 / 40 px look.
- **Do** publish and read `--dock-h` so nothing fixed to the bottom covers content.
- **Do** animate transform and opacity only, with the kit's three durations and one easing, and respect `prefers-reduced-motion`.
- **Do** show every figure, date and sentence as the server sent it, in both languages.

### Don't:
- **Don't** ship a dark theme, a gradient on a button or a card, a coloured rail on a card's edge, or a font fetched from a font host.
- **Don't** let the brand blue mean a status, or a status colour mean anything but that status.
- **Don't** use `brand-900` anywhere but the Demo strip, put a card around the Home headline, or add a second raised surface to Home.
- **Don't** set text below 12 px; there is no `text-2xs`.
- **Don't** hand-roll a `<details>`, a second chevron, a second fact tile, or a second radius; the scale is pill / 16 / 12.
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

- **Deals order, one at every width** (the server's `workspace.order`): the folded inbox row, the selected-buyer card (the buyer, when it came, when it was checked, and ONE state chip: the record's `state_text` in a `StatePill`, its colour the server's `state_tone`; no ask line, no step line), "FLOW recommends" with its first reason under it, the priced response, then what the buyer asks, what it costs and why it matters, the agreements, the folded details. Once the deal has an outcome the eyebrow reads "Where this deal stands", never "FLOW recommends: {outcome}", and the card carries the Money line ("Received {amount} {when}." / "{amount} arrives {when}.", from the record's lots, neutral until the cash has landed) and "What is left" (the record's remaining task). The Action band appears only where it names a real action (the approval to answer, the way back to the offers).
- **Send** asks once, as Home's Run does. Above the button, in 14 px `ink`, "This will" and the server's `send_scope_lines` (the agreement it records, the funding it draws or requests, the estimated cost); the first press opens a confirm box ("Send {label} to the buyer?", the reply is simulated), the second sends exactly what is shown. Another counter keeps the server's one sentence.
- **`StatePill`** (`components/ui.tsx`) is the one pill for a state the server names: the words, a glyph for the tone (never colour alone) and the server's tone (`state_tone`, `result_tone`); the browser never colours a state itself. 12 px, no dot. The execution summary is green only when cash has landed; until then a request that ran is "Requested" (info).
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
- **Activity:** a request that waited for the owner is history once the owner has decided: it wears where the decision stands now (`current_decision_state`, a neutral `StatePill`), not "Waiting for your approval", and the decision's actor is "You".
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
5.0:1; `#0472ff` itself is 4.3:1 and fails AA for 14 px text). The canvas is a pale blue-grey, the hairlines `#e6eaf0`, and the
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

- **Home is seamless.** No hero card: the status pill, the one `h1`, the note and the cash picture sit on the canvas; the plan is the one raised, frosted surface (sticky from `lg`); the owner's deals are rows with hairlines; the other blocks lose their card chrome (a small-caps heading, hairlines), except a block that asks the owner to decide. Warnings are "Also on your radar", a quiet row above the details fold.
- **The shell.** The sidebar is on the canvas with a white active pill; the top bar is the canvas at 70% with blur and no border at rest.
- **Type.** The display voice is sans (Plus Jakarta Sans, 800); the serif and the Flow Figures workaround are removed.
- **A new token:** `brand-300`, the lighter second part of the funding bar (decorative, named in its legend).
- **Motion.** The cash picture's one draw is the second named exception to "transform and opacity only".

<!-- pages A1 (part 1): one separate block; the second pass (Approvals, Cash, the secondary pages) adds its own below. -->
## Page pattern, A1 (Receivables and Activity; Home is the model)

**The page pattern.** Every Business page answers one question at the top, shows one picture where the data supports one, has at most one raised surface (the action), and leaves everything else unboxed on hairlines. The `h1` is the answer in the server's own sentence (never composed in the browser): Home's headline, Activity's "now" sentence, Receivables' `receivables.headline` (else the collections read's top action while someone is late, else the plain page title). A section is a 16 px extrabold title, a 12 px `ink-3` line and a hairline, then rows divided by hairlines; a block that asks the owner to decide keeps the white card.

**Action bar (`components/business/action-bar.tsx`).** The one raised surface, extracted from Home's plan bar: frosted `surface` at 84%, 18 px blur, `--shadow-pop`, in flow below `lg` and sticky 16 px above the window's foot from `lg`. Home's plan and Receivables' "Chase payment" use it; nobody late, no bar.

**Facts row.** The outstanding, overdue and next-payment facts are one inline row: a 12 px uppercase `ink-3` label, a 24 px extrabold tabular figure (the overdue one in `bad-fg` only while something is late) and a 12 px caption, hairlines between from `sm`, a hairline above and below. No tiles.

**Who pays when (`components/business/who-pays-when.tsx`).** Plain inline SVG on a day axis with a "Today" line; every open invoice is a mark at its due day, late ones left of today on a faint `bad-bg` band. Size is three steps by face amount (radius 5.5, 8, 11); state is fill and outline as well as hue: late is filled `bad-solid`, due soon is outlined `warn-solid`, later is outlined `ink-3`, a promised early payment is an outlined `info-solid` diamond. Each mark is labelled with the server's amount and the day in `biz.when.*` words and the buyer's avatar (a section tint, never orange). Marks that overlap stack into lanes; a label that would touch another mark, label or the Today line is dropped (the row has it); room is kept left of the earliest late mark for its label. A mark is a button (`aria-pressed`, `aria-controls` the row): the page shows every invoice, scrolls to the row and tints it `brand-50`. A visually hidden table mirrors the marks. It fades in once (`picture-fade`); under reduced motion it is in its final state.

**Activity rail.** A vertical hairline rail; a day caption (12 px uppercase `ink-3`, the entry's distance from today in `biz.when.*` words) per day; a 32 px node per entry with an icon for who acted (you `brand-50`, FLOW the Home tint, the bank or system `subtle`, the buyer the Deals tint), the sentence as a 14 px semibold title, the status pill, the plain operation name and the actor in 12 px `ink-3`, and one quiet "Details" toggle at the right that opens the audit details (the executor's sentence, the ids, the tier, the hashes). Time passing is a thin separator on the rail with its sentence and no node, pill or toggle. Filter chips (`toggleClass`, `aria-pressed`) above the rail narrow it by kind (Money, Decisions, Documents, from a fixed map of operation kinds); a kind with nothing in it is not offered, and the order never changes.

**Shared cash picture (`components/business/cash-picture.tsx`).** The drawing of Home's picture with props that do not assume Home (`baseline`, `alternative`, labels, `floorFen`, `floorLabel`, `markers`, `horizonDays`, `chips`, `ariaLabel`, `testIdPrefix`, a `header` slot). With two lines each name sits beside its own line, on the longest stretch where the lines are more than a label's height apart (the upper line's above it, the lower line's below it); with no such stretch both names go to a small legend row above the chart.

**Sidebar count.** Deals and Receivables carry a small count pill at the right of the sidebar row and on the tab bar's icon (Deals `warn`, Receivables `bad`), nothing at zero. The link's accessible name says what the count means ("Deals, 1 needs you", "Receivables, 1 is late"); the number itself is hidden from assistive tools. One read of `GET /nav/counts` per navigation and per action; a failed read shows no count and no error.
