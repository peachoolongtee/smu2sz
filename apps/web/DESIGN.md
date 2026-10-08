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

`ok`, `warn`, `bad`, `info` each have `-fg` (text), `-bg` (tint), `-line` (tint border), `-solid` (a mark that must be seen: dot, chart mark, 3:1) and `-bright` (a pill or figure on the deep block). A status colour means that status and nothing else.

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
| on-deep-muted / the deep tile (`on-deep` at 10% over brand-900) | 6.7 | 4.5 |
| on-deep / the deep tile | 12.0 | 4.5 |
| bad-bright / warn-bright / ok-bright on the deep tile | 7.1 / 6.8 / 7.1 | 4.5 |
| ink-3 / the open row of a table (`subtle` at 60% on white) | 4.8 | 4.5 |
| ink-2 / brand-700 on that row | 7.6 / 7.1 | 4.5 |
| ink-3 / a late row (`bad-bg` at 40% on white) | 4.9 | 4.5 |
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
- **section hues** (`sec-*`): where you are or where a link goes (a page's icon chip, the phone tab bar, a buyer's avatar tint). Never how things are going. Buyer avatars use four of the five tints (not orange, which sits next to the warning amber) so an avatar cannot read as a status.
- **deep** (`brand-900`): the Home hero and the Demo strip, nothing else. The block stays navy; the status is the pill on it.
- **ink**: text. `ink-3` is for captions, never for anything the owner must act on.

## 2. Shape

| Token | Value | For |
|---|---|---|
| `--radius-pill` (`rounded-pill`) | 9999px | buttons, chips, badges, pills, segmented controls and their thumb, inputs, selects, the chat composer, icon chips, avatars |
| `--radius-card` (`rounded-card`) | 16px | cards, the hero, disclosure cards, tables, dialogs, empty and error states |
| `--radius-tile` (`rounded-tile`) | 12px | what sits inside a card: fact tiles, list rows with a border, option rows, callouts |

A multi-line text area takes `rounded-card` (a pill clips the corners of a second line); the chat composer is a pill with a fixed two-line height.

Shadows: `--shadow-card` (a card at rest), `--shadow-lift` (a row, tile or option on hover), `--shadow-pop` (a sheet, menu, the chat panel, a floating button), `--shadow-up` (the Demo strip fixed to the bottom of a phone: the card shadow cast upward). No gradient on a button or a card, and no coloured rail on a card's edge: a status is a pill with a word, a tone is a 1 px line.

### Type, density and rhythm

One family, one role scale; body is 14 px (`text-sm`) and so is the data in a table or a row, captions and eyebrows are 12 px (`text-xs`, the floor: nothing is set below it, so there is no `text-2xs`), a figure is 20 px (`text-xl`, 24 px with `size="lg"` from `sm` up; 18 px on a phone), a card or page title 20 px. Every money column is `tabular-nums` and right-aligned, and a cell that holds an amount does not wrap (`whitespace-nowrap`).

Spacing is a 4 px base: 16 px (`p-4`) inside a Business card, 12 px (`gap-3`) between tiles, 24 px (`space-y-6`) between sections. The home hero keeps its own 20 px.

## 3. Components

All in `components/ui.tsx` unless noted.

- **Button** (`variant` primary, secondary, ghost, danger; `size` md, sm): a pill, 40 px tall (32 px compact), 16 px of horizontal padding, medium weight. Secondary has a `line-ui` border, ghost is text only, primary is the brand fill. **One primary per page.** A link that is the next step is a `ButtonLink` (same shape); `buttonClass()` is the class for a span that sits inside a link. `toggleClass(active)` is the pill that toggles (a preset, a demo scene): the selected one takes `brand-50` and a `brand-600` border.
- **Badge** (`tone`): a pill with its tint, line and (for a status) a solid dot. **Chip**: a Badge without the dot, for a tag that carries no status (a channel, a kind).
- **Segmented / SegmentedButtons**: a pill track (`line-ui` border on `subtle`) with a sliding pill thumb on `surface`. `Segmented` is a radio group (the Business/Demo switch, the language switch); `SegmentedButtons` is the same track made of `aria-pressed` buttons (the forecast horizon).
- **Inputs**: `inputClass` (pill, 40 px, `line-ui` border) and `textareaClass` (`rounded-card`).
- **Card**, **Callout**, **EmptyState**, **ErrorState**, **TableWrap**: radii from the scale above. `Card` reveals on mount. A card's `tone` is a 1 px tone line, never a rail.
- **Stat**: the one fact tile (hero tiles, Cash facts, Receivables summary, the Deals ceilings and recommendation facts, the Mandate limits, the next step's cost, landing and authority). An uppercase eyebrow (`text-xs`, tracking, `ink-3`), the figure (`tabular-nums`, `text-lg`/`text-xl`; its colour is a status only when `tone` names one), a caption (`text-xs`, `ink-3`: when, of what, against what; a second line is a second `block` span) and, only when the server sent a `delta_display`, a delta chip (neutral unless the server names its tone; the browser never subtracts). Two surfaces: `surface` (white, a `line` hairline) and `deep` (the home hero: `on-deep` at 10% over `brand-900`, eyebrow and caption in `on-deep-muted`, a status figure in its `-bright` tone). `tint` fills the tile with its status tint for the one tile that says who decides. A caption of a tile may carry a related figure (the headroom under the reserve and under the lowest point) with its own test id. A row of three is `grid-cols-2 sm:grid-cols-3` with the first tile `col-span-2` on a phone.
- **PageHeader** (`section`, optional `icon`): in the Business shell the title takes a 40 px round chip, a white 20 px icon on the section's `solid` (`components/section.tsx`, `PageIcon`). Every Business page and Approvals has one; the Demo shell keeps the flat look.
- **Disclosure** (`components/business/kit.tsx`): the one fold, with the one chevron (`FoldChevron`, right-pointing, a quarter turn when open; the same chevron opens a table row). A native `<details>` with a body that opens by height. Use it instead of a hand-rolled `<details>` (the Approvals card, the home's agent's answer, the inbox's earlier messages and the chat's details all use it now); `summaryClass` + `bare` let a row draw its own summary (a Cash option) and `flush` removes the body padding. Its label comes from one small set: **Details** (`biz.details.plan`), **Why** (`biz.hero.why`), **Show the calculation** (`biz.calculation`), **Audit details** (`biz.auditDetails`: ids, tiers, hashes, the executor's sentence). A fold that names its own subject ("Original message", "Debt readings", "Show 3 more", "Other plans considered") says so; two folds on one page never share a label.
- **Row disclosure** (`components/business/receivables-table.tsx`): in a table a row opens from a trailing chevron button (`aria-expanded`, `aria-controls`) into a second row spanning the table; on a phone the same facts are a stacked list whose row ends in a Disclosure.
- **Filters**: pills that toggle (`toggleClass`, `aria-pressed`) in a `role="group"`, above the list they filter; a filter that would repeat the whole list is not offered.
- **Ranking**: wherever the server ranks, the rank is a numeral (a column in a table, `#1` on a Cash plan, a number before a buyer on a phone) and the order is the server's. "Recommended" is the brand badge wherever the server marks a row; an alternative says why in a neutral chip (the server's `role_reason`).
- **Link tile** (`DoorTile` in `app/cash/page.tsx`): a quiet bordered tile with what the door is for and one text link stretched over the whole tile.
- **Avatar / toneFor / initials** (`kit.tsx`): a 36 px disc. A change row's icon sits on its status tint; a buyer's initials sit on a section tint (`toneFor(name)` is stable per name).
- **Icons**: from `components/icons.tsx` only, at 16 or 20 px, `currentColor`. The exception is a section chip, which sets a white icon on its solid.
- **Focus**: every focusable element gets the global ring (2 px, offset 2 px, `focus`; white inside `.on-deep`). Never remove an outline.
- **Status header**: Home says it in the navy hero; Cash says it once in a compact row (the status pill and the sentence, then the note) above the facts as `Stat` tiles. The same fact never has two voices.
- **Next-step band** (`NextStep`) only where the step is a navigation; the **Recommended-next-step card** where there is a priced action. A card's quiet links ("All receivables", "Open approvals") are text links; a pill is for a step.
- **Phone tab bar** (`app-shell.tsx`): the active tab's icon in its section solid, its label in ink; inactive in `ink-3`; a bar slides to the active tab. Its last 3 rem is Ask FLOW (below).
- **Ask FLOW** (`components/chat/chat-panel.tsx`, `.ask-trigger`): never floats over content. Below `sm` it is the last cell of the bottom bar (the tab bar, and the Demo stepper's last row), icon over "Ask"; from `sm` a brand pill 16 px above the bar (24 px from the corner from `lg`). The bar publishes its measured height as `--dock-h` (`useDock` in `app-shell.tsx`); `main` takes `.dock-pad` (the bar, the pill and 16 px of air) and `html` takes a matching `scroll-padding-bottom`, so the last row of a page and a focused control always clear both.
- **Touch** (the `touch:` variant: below `lg`, or a coarse pointer at any width): every control reaches 44 px. `Button` and `toggleClass` grow to `min-h-11` (the desktop 32 / 40 px look is unchanged); a small chip that must stay small (a segmented option, the account button, the copy-hash icon, the "Code" fold, a text link) keeps its look and takes `.hit`, a transparent 44 x 44 hit area. Inline links in a sentence are exempt.
- **Account sheet** (`AccountSheet` in `app-shell.tsx`): a native `<details>` under a small button; Escape closes it and returns focus to the button, a press outside closes it. Business: the identity, Limits, the tour, the language. Demo, below `lg`: mock or live data, who is signed in, the language (the header keeps the brand, the menu, the mode switch and this button).
- **Dialogs**: the chat and the walkthrough are native `<dialog>`s (`showModal`: the page behind is inert, Escape closes, focus returns). The walkthrough tracks its spotlight with a `ResizeObserver` and scroll, never a timer, and the spotlight jumps between steps.
- **Errors**: a failure the client recognises carries a code (`ApiError.code`) and is said through the dictionary (`err.<code>`, `errorText` in `lib/error-text.ts`); a failure the server explained shows the server's own words.
- **Backdrop** (`components/business/backdrop.tsx`): two blurred discs (Home blue, Cash teal) that drift once over 40 s and then rest, at a strength that keeps `ink-3` above 4.5:1 on their strongest point (the Cash disc is left out on a phone). Behind the Business pages only; cards stay solid.
- **Cash forecast labels** (`cash-forecast.tsx`): 12 px, placed in pixels against the measured drawing. Event labels alternate above and below the line, none within 24 px of another or of the first unsafe day and the lowest point; below `sm` there are none (the marks stay and the tooltip lists the day's events). The reserve is named in the legend, not on the line; the worst-point label is dropped when the worst point is the reserve. A label is pushed in from whichever edge it would cross.
- **Light only**: `color-scheme: light` on `html`. There is no dark theme; the scrollbars, form controls and dialog backdrop must not take a dark phone's.
- **First paint**: an inline script in `<head>` (`lib/pre-hydration.ts`) reads `tl-lang` and `tl-mode`, sets `lang` and `data-mode` at once, and keeps the body hidden (`data-pending`) while the server's Business/English markup would be the wrong shell or language; the shell clears it after hydration (a 2 s timer is the way out). The tab title of every route is server metadata (`lib/route-title.ts`, one `layout.tsx` per route); the shell puts the owner's language in.

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
