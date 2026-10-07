# FLOW web: design system

The single reference for the look of `apps/web`. The tokens live in `app/globals.css` (`@theme static`, so Tailwind generates a utility for each and a chart can read them with `var()`); components take every colour, radius, shadow and duration from there. The colour reasoning is in `docs/research/colour-direction-2026-10-08.md`; the words are in `docs/UX_SIMPLIFICATION_BRIEF.md`.

The rules that do not move: one brand-filled primary action per page; status colour only for status; the deep `brand-900` Home hero with its bright status pill; every text pair at 4.5:1 or better and every visible boundary and icon at 3:1 or better; nothing said by colour alone; no gradients on buttons or cards; the browser computes no money; Business mode shows no engine terms and no day numbers.

## 1. Colour

### Base

| Token | Hex | Use |
|---|---|---|
| `canvas` | `#f3f6fb` | the page behind the cards (a faint cool tint) |
| `surface` | `#ffffff` | cards, sheets, inputs |
| `subtle` | `#eaf0f7` | quiet fills: segmented track, table heads, skeletons |
| `line` / `line-strong` | `#dbe3ee` / `#c2cddc` | hairlines and dividers (decoration, not a boundary that must be seen) |
| `line-ui` | `#74849b` | any boundary that must be seen: inputs, secondary buttons, the segmented track |
| `ink` / `ink-2` / `ink-3` | `#0f1c2e` / `#3f5068` / `#5d6e84` | text: primary, secondary, quiet |
| `brand-50` / `-100` | `#e8f0fe` / `#d3e2fc` | the brand tint (selected toggle, next-step band, nav pill) |
| `brand-600` / `-700` | `#1a5fe0` / `#124bb8` | the primary fill and its hover; links and the focus ring |
| `brand-900` | `#0b1f4d` | the deep block: the Home hero, the Demo strip |
| `on-deep` / `on-deep-muted` | `#ffffff` / `#b7c3d9` | text on the deep block |

### Status (unchanged from Wave 8)

`ok`, `warn`, `bad`, `info` each have `-fg` (text), `-bg` (tint), `-line` (tint border), `-solid` (a mark that must be seen: dot, rail, chart mark, 3:1) and `-bright` (a pill or figure on the deep block). A status colour means that status and nothing else.

### Section hues (wayfinding only)

Each section has a tint (`bg`), the text on that tint (`fg`) and a `solid` (the fill behind a white icon, or an icon on white). Classes: `bg-sec-deals-solid`, `text-sec-deals-solid`, `bg-sec-deals-bg text-sec-deals-fg`.

| Section | bg | fg | solid | Looks like |
|---|---|---|---|---|
| `sec-home` (Home, Approvals, Limits) | `#e8f0fe` | `#124bb8` | `#1a5fe0` | the brand blue |
| `sec-deals` | `#f0ebfd` | `#5532bf` | `#6d4ad8` | violet |
| `sec-cash` | `#e1f4f6` | `#07616e` | `#0a8190` | teal (bluer than `ok` green on purpose) |
| `sec-recv` | `#fdeee0` | `#8f3f05` | `#c4570c` | orange (redder than `warn` amber on purpose) |
| `sec-activity` | `#fce9f1` | `#a3225a` | `#c7366e` | rose |

### Contrast, computed (WCAG 2.x relative luminance)

| Pair | Ratio | Needs |
|---|---|---|
| ink / canvas | 15.8 | 4.5 |
| ink-2 / canvas | 7.6 | 4.5 |
| ink-3 / canvas | 4.8 | 4.5 |
| ink-3 / white | 5.2 | 4.5 |
| ink-3 / subtle | 4.5 | 4.5 |
| ink-2 / subtle | 7.2 | 4.5 |
| ink-3 / brand-50 | 4.6 | 4.5 |
| ink-3 / backdrop disc at its strongest point (blue `#eaf0fa`, teal `#e9f1f6`) | 4.55 / 4.56 | 4.5 |
| white / brand-600 | 5.6 | 4.5 |
| white / brand-700 | 7.7 | 4.5 |
| brand-700 / brand-50 | 6.7 | 4.5 |
| brand-700 / white | 7.7 | 4.5 |
| white / bad-solid (danger button) | 4.9 | 4.5 |
| focus ring (brand-600) / canvas | 5.2 | 3 |
| focus ring / white | 5.6 | 3 |
| white focus ring / brand-900 | 15.9 | 3 |
| line-ui / white | 3.8 | 3 |
| line-ui / canvas | 3.5 | 3 |
| line-ui / subtle | 3.3 | 3 |
| brand-600 border / brand-50 (selected toggle) | 4.9 | 3 |
| sec-home: white / solid; fg / bg; fg / white | 5.6; 6.7; 7.7 | 3; 4.5; 4.5 |
| sec-deals: white / solid; fg / bg; fg / white | 5.8; 6.9; 8.1 | 3; 4.5; 4.5 |
| sec-cash: white / solid; fg / bg; fg / white | 4.6; 6.3; 7.1 | 3; 4.5; 4.5 |
| sec-recv: white / solid; fg / bg; fg / white | 4.5; 6.4; 7.3 | 3; 4.5; 4.5 |
| sec-activity: white / solid; fg / bg; fg / white | 5.0; 6.2; 7.2 | 3; 4.5; 4.5 |

A section `solid` as an icon on a white tab bar has the same ratio as white on the solid. The Wave 8 status pairs are unchanged (their tints sit on their own backgrounds).

### Roles: what each colour may mean

- **brand** (`brand-600`): the page's one primary action, links, the focus ring, the selected state of a toggle. Never a status.
- **status** (`ok`, `warn`, `bad`, `info`): how things are going. Always with a word; the dot or tint is the second channel, never the only one.
- **section hues** (`sec-*`): where you are or where a link goes (a page's icon chip, the phone tab bar, the Home "Where to next" row, a buyer's avatar tint). Never how things are going. Buyer avatars use four of the five tints (not orange, which sits next to the warning amber) so an avatar cannot read as a status.
- **deep** (`brand-900`): the Home hero and the Demo strip, nothing else. The block stays navy; the status is the pill on it.
- **ink**: text. `ink-3` is for captions, never for anything the owner must act on.

## 2. Shape

| Token | Value | For |
|---|---|---|
| `--radius-pill` (`rounded-pill`) | 9999px | buttons, chips, badges, pills, segmented controls and their thumb, inputs, selects, the chat composer, icon chips, avatars |
| `--radius-card` (`rounded-card`) | 16px | cards, the hero, disclosure cards, tables, dialogs, empty and error states |
| `--radius-tile` (`rounded-tile`) | 12px | what sits inside a card: fact tiles, list rows with a border, option rows, callouts |

A multi-line text area takes `rounded-card` (a pill clips the corners of a second line); the chat composer is a pill with a fixed two-line height.

Shadows: `--shadow-card` (a card at rest), `--shadow-lift` (a row, tile or option on hover), `--shadow-pop` (a sheet, menu, the chat panel, a floating button). No gradient on a button or a card.

## 3. Components

All in `components/ui.tsx` unless noted.

- **Button** (`variant` primary, secondary, ghost, danger; `size` md, sm): a pill, 40 px tall (32 px compact), 16 px of horizontal padding, medium weight. Secondary has a `line-ui` border, ghost is text only, primary is the brand fill. **One primary per page.** A link that is the next step is a `ButtonLink` (same shape); `buttonClass()` is the class for a span that sits inside a link. `toggleClass(active)` is the pill that toggles (a preset, a demo scene): the selected one takes `brand-50` and a `brand-600` border.
- **Badge** (`tone`): a pill with its tint, line and (for a status) a solid dot. **Chip**: a Badge without the dot, for a tag that carries no status (a channel, a kind).
- **Segmented / SegmentedButtons**: a pill track (`line-ui` border on `subtle`) with a sliding pill thumb on `surface`. `Segmented` is a radio group (the Business/Demo switch, the language switch); `SegmentedButtons` is the same track made of `aria-pressed` buttons (the forecast horizon).
- **Inputs**: `inputClass` (pill, 40 px, `line-ui` border) and `textareaClass` (`rounded-card`).
- **Card**, **Stat**, **Callout**, **EmptyState**, **ErrorState**, **TableWrap**: radii from the scale above. `Card` reveals on mount.
- **PageHeader** (`section`, optional `icon`): in the Business shell the title takes a 40 px round chip, a white 20 px icon on the section's `solid` (`components/section.tsx`, `PageIcon`). Every Business page and Approvals has one; the Demo shell keeps the flat look.
- **Disclosure** (`components/business/kit.tsx`): the one fold. A native `<details>` with a turning chevron and a body that opens by height. Use it instead of a hand-rolled `<details>`.
- **Avatar / toneFor / initials** (`kit.tsx`): a 36 px disc. A change row's icon sits on its status tint; a buyer's initials sit on a section tint (`toneFor(name)` is stable per name).
- **Icons**: from `components/icons.tsx` only, at 16 or 20 px, `currentColor`. The exception is a section chip, which sets a white icon on its solid.
- **Focus**: every focusable element gets the global ring (2 px, offset 2 px, `focus`; white inside `.on-deep`). Never remove an outline.
- **Home "Where to next"** (`components/home/where-next.tsx`): four round chips (Deals, Cash & funding, Receivables, Ask FLOW) in the section solids under the hero, on phones and tablets only; the nav pills cover desktop.
- **Phone tab bar** (`app-shell.tsx`): the active tab's icon in its section solid, its label in ink; inactive in `ink-3`; a bar slides to the active tab.
- **Backdrop** (`components/business/backdrop.tsx`): two blurred discs (Home blue, Cash teal) drifting over 40 s at a strength that keeps `ink-3` above 4.5:1 on their strongest point. Behind the Business pages only; cards stay solid.

## 4. Motion

Ease-out, short, transform and opacity only. A disclosure's height is the one deliberate exception.

| Token | Value |
|---|---|
| `--ease-out` | `cubic-bezier(0.2, 0.8, 0.2, 1)` |
| `--dur-fast` | 120 ms (a press) |
| `--dur` | 200 ms (hovers, switches, sheets, disclosures) |
| `--dur-slow` | 280 ms (a card or row arriving, a panel sliding in) |

| Class | What it does |
|---|---|
| `motion-reveal` | a block fades in and rises 6 px on mount (the hero, `Card`, `PageHeader`, disclosure cards, the next-step band) |
| `motion-rise` on a list | rows rise one after another, 30 ms apart, for the first eight; a ninth row just appears |
| `motion-lift` | hover lifts 1 px and takes the next shadow step (rows, tiles, option rows), only where hover exists |
| `motion-press` | a button scales to 0.98 while pressed and eases its colour |
| `motion-slide` | a thumb or indicator moves by transform (the segmented thumb, the tab bar's active bar) |
| `motion-sheet` / `motion-panel` / `motion-pop` | the account sheet drops in; the chat slide-over enters from the right; the walkthrough card scales in |
| `motion-pulse` | the status dot's ring pulses once on mount, for ACTION_NEEDED and CRITICAL only (never on a calm status) |
| `.disclosure-body` | a one-row grid from `0fr` to `1fr`; other `<details>` use the browser's `::details-content` height transition where it exists |

Rules: nothing animates width, height (but the disclosure), margin or position, so nothing shifts the layout. `prefers-reduced-motion: reduce` sets every duration to 0.001 ms, removes delays and loops, and cancels the hover and press transforms; the backdrop stops. The Playwright config sets `reducedMotion: "reduce"` so every spec runs without animation.
