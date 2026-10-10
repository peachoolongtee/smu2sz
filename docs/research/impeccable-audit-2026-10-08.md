# Impeccable audit: FLOW web (apps/web), 8 Oct 2026

Wave 8 of wayfinder map #47, branch `feat/strategy-mvp`, worktree `mvp-int`. Technical quality only (accessibility, performance, responsive, theming, robustness); the critique is a separate pass. Nothing in the repository was changed except this file.

## What was run and what was only read

**Ran** (all read-only; scripts in the session scratchpad `map47/audit/`, nothing added to the repo):
- `pnpm typecheck` (clean) and `pnpm exec eslint .` (clean).
- `node i18n-diff.mjs`: diffs the `en` and `zh` key sets of `lib/dictionary.ts`, checks placeholder parity, finds every static `t("…")` key used in `app/`, `components/`, `lib/` and the dynamic template keys.
- `node contrast.mjs`: WCAG 2.x ratios for every token pair in `app/globals.css` that a component actually uses (plus composited cases: `/80` white, `/40` tints, the backdrop disc at 12 % mix and 35 % opacity).
- A standalone Playwright walk (`walk.mjs`, `@playwright/test`'s Chromium, axe-core 4.13 injected from the pnpm store; no dependency added) against the existing `.next-e2e-mock-strategy` build served with `pnpm start -p 3121` (mock mode, `NEXT_PUBLIC_STRATEGY_MVP=1` inlined at build). Four viewports: desktop 1440×900, Pixel 7 (412×839), tablet 768×1024, tablet 1024×768. Routes: the 7 Business pages at day 0 and after the 15-step demo walk, in English and Chinese; the 14 Demo/engine routes after the walk; the chat slide-over open; the account sheet (Escape, outside click); a 40-stop Tab walk on `/` and `/mandate`; mid-page and end-of-page overlap of the Ask FLOW button. Per page: axe (wcag2a/aa, 2.1, 2.2 AA), landmarks, heading order, controls without an accessible name, targets under 44 px (phone) and 24 px (desktop), horizontal overflow, `document.title`, `html lang`, console errors. 246 page-views; 0 console errors or warnings.
- `title.mjs` (hard load vs client navigation vs reload) and `chart.mjs` (recharts focus and label sizes).
- Bundle composition from the served HTML of ten routes and the chunk files of the existing build (`pnpm build` was not rerun: the dist is newer than every source file).
- The Impeccable detector (`impeccable detect apps/web/app apps/web/components`): exit 0, no findings printed.

**Only read**: `DESIGN.md`, `globals.css`, `ui.tsx`, `app-shell.tsx`, every page under `app/**`, the business, deals, chat, home and tour components, `lib/{i18n,mode,auth,config,api,chat,use-async,create-store,when,live/http,mock/handlers}.ts`, the e2e specs, the 54 screenshots' manifest and four of the images. Live-mode behaviour (401/403 on reads, 503, 409) is inferred from `lib/live/http.ts` and `ui.tsx`: the mock handlers only raise 401 on `demoReset`/owner actions (`lib/mock/handlers.ts:516,668`), so the signed-out probes in mock mode rendered the normal pages.

## Audit health score

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 3 | the recharts SVG is a Tab stop with `outline: none` (globals.css:379); `document.title` lost on every hard load |
| 2 | Performance | 3 | route-level splitting works (recharts only on /cash, /trajectory, /whatif); the blurred backdrop animates a 64 px filter forever |
| 3 | Responsive | 2 | the floating Ask FLOW button sits on top of the fixed Demo stepper on phones and covers content rows on every small viewport |
| 4 | Theming | 3 | full token system, zero hard-coded colours in components; one text pair under 4.5:1; no dark scheme at all (by design, undeclared) |
| 5 | Implementation integrity | 4 | coherent, product-specific system; detector clean |
| **Total** | | **15/20** | **Good: address the weak dimensions** |

### Implementation integrity verdict: pass
Every colour, radius, shadow and duration in `components/**` and `app/**` resolves to a token in `globals.css` (`grep` for hex literals finds none outside `globals.css` and the documented `lib/annotation-style.ts`). The one-primary-per-page rule, the status/section/brand colour roles and the single `Disclosure` fold are followed on every page probed; axe found no missing names, every page has exactly one `h1` and no skipped heading level; the chat and sign-in dialogs are native `<dialog>`s with working focus trap, Escape and focus return (measured). The product reads as itself, not as a template.

## Executive summary
- Score **15/20** (Good). Issues: **P0 1 · P1 6 · P2 14 · P3 7**.
- Top five: (1) on phones the Ask FLOW button overlaps the fixed Demo stepper and partially hides the scene buttons (axe `target-size` on 13 page-views); (2) the browser-tab title is "FLOW" on every hard load and reload (Next's streamed metadata overwrites `useDocumentMeta`); only client-side navigation shows "Deals · FLOW 流"; (3) the cash chart's SVG is a keyboard stop with no visible focus (`.recharts-surface:focus-visible { outline: none }`); (4) the account sheet (`<details class="menu">`) ignores Escape and clicks outside; (5) in Chinese the Cash page is roughly a third English (server/mock strings: facility names, plan notes, worth sentences, "same day"/"3 days").
- Next: `/impeccable adapt` for the phone overlaps and the 32 px controls, `/impeccable harden` for the title, the sheet, the dl structure and the i18n gaps, `/impeccable optimize` for the backdrop and the chart chunk, then `/impeccable polish`.

## Detailed findings

### P0
**[P0] Ask FLOW covers the Demo stepper on phones.** `components/chat/chat-panel.tsx:38` (`fixed bottom-28 right-4`, 112 px) vs `components/app-shell.tsx:401-403` (stepper `fixed inset-x-0 bottom-0`, measured 117–133 px tall at 412 px because `demo-stepper.tsx:46` wraps to three rows). Measured on all 14 Demo routes on the phone: button box y 687–727, stepper top y 706. axe `target-size` (serious): the Scene 3 and Security buttons are "partially obscured (72.7 × 20 px)". Impact: a judge on a phone cannot reliably tap the scene jumps and the button hides the step text; no scroll clears it. Standard: WCAG 2.5.8, 2.4.11. Fix: on `< lg` move the chat trigger into the stepper row (or the Business tab bar) as a 44 px icon button, or compute `bottom` from the measured bar height (`env()` + a CSS variable set by the bar). Command: **adapt**.

### P1
**[P1] Tab title lost on hard load.** `components/app-shell.tsx:422-429` sets `document.title` in an effect; measured: "Deals · FLOW 流" right after load, then "FLOW" 300 ms later and still "FLOW" after 2 s, on `/deals`, `/cash`, `/mandate`, and after `page.reload()` on `/cash` (a second empty `<title>` appears). Client-side navigation keeps the right title, which is why `e2e/responsive.spec.ts:81` passes. Impact: bookmarks, history, tab switching and screen-reader page announcement all say "FLOW" (WCAG 2.4.2). Fix: per-route `metadata`/`generateMetadata` in a server `layout.tsx` per segment (static labels), or set the title from a `MutationObserver` on `<head>`; keep the effect for the language. Command: **harden**.

**[P1] Chart is a focus stop with no visible ring.** `app/globals.css:379-382` removes the outline on `.recharts-wrapper`/`.recharts-surface`; recharts 3's accessibility layer makes the `<svg>` `tabindex=0`. Measured on `/cash`: Tab from `forecast-horizon-120` lands on the SVG with `:focus-visible` true and `outline: none`. WCAG 2.4.7; contradicts DESIGN.md §3 "Never remove an outline". Same for `CashChart`/`DebtChart` on `/trajectory` and `/whatif`. Fix: give the surface the global ring (`outline: 2px solid var(--color-focus); outline-offset: 2px`) or set `accessibilityLayer={false}` and keep the table as the keyboard path. Command: **harden**.

**[P1] Ask FLOW covers content rows on phones and tablets.** Business pages, measured hits of the 124 × 40 button at the natural scroll positions: the hero's "Why" summary (`/` top), the "Details: what is on its way…" summary (`/` end, 412 and 768), "All receivables" (`/` after the walk, 768), "Debt readings (month 1)" (`/cash` end), two funding-option summaries (`/cash` mid), "Open the evidence export." (`/activity`), "Decline" (`/approvals`), the "Payment terms" slider (`/whatif`). `main` has `pb-28` (`app-shell.tsx:268`) which clears the tab bar but not the button, and nothing clears it mid-page. Fix: as P0 (tab-bar item or icon FAB), plus `scroll-padding-bottom`/`pb` equal to bar + button on `< lg`. Command: **adapt**.

**[P1] Chinese pages carry English server strings.** Measured Latin text in `main` with `tl-lang=zh`: `/cash` 25 distinct fragments ("Bank credit line", "Projected cash closes at ¥60,000.00 in 12 days…", "cost ¥3,938.81; within your limits but dearer than the selected plan", "not applied; cash in 21 days…", "NOT_APPLIED: counts as zero for hard constraints", "年化 6.40% · same day 到账"), `/` 16, `/receivables` 6 ("Saves ¥86.16 at the 0.85% limit…", "Ranked by what collecting each saves…"), `/deals` only the fixture messages and names (acceptable). Sources: `comparison[].note`, `menu[].reason`, `time_to_cash_display`, facility names, `worst`, `receivables/worth` sentences, `price-curve.sentence`. The dictionary itself is complete (see Positive). Fix: pass `lang` to `planFunding`, `getReconciliation`/worth and the home's option notes as `getHome(lang)` already does, add `_zh` recordings; translate `time_to_cash_display` via `te()` from a code. Command: **harden**.

**[P1] Account sheet has no dismissal.** `components/app-shell.tsx:150-170,175-209`: a native `<details>` sheet; measured on all four viewports: open after click, still open after Escape, still open after a click outside. Only `closeMenu` on a row closes it. Impact: keyboard users leave a 288 × 240 sheet floating over the header's content; pointer users must click the summary again. Fix: `onKeyDown` Escape and a document `pointerdown` listener while open (or a `<dialog>`/popover). Command: **harden**.

**[P1] Phone controls at 32 px.** `buttonClass` size `sm` is `min-h-8` (`ui.tsx:216`) and the `Segmented` options are `min-h-8` (`ui.tsx:352`): on the phone the demo stepper's Setup/Scene/Back/Next/Reset, Sign out, the account summary, the horizon toggles, "All receivables", the brand link are 32 px tall; `Hash` copy is 24 × 24 (`ui.tsx:453`); the "Code" summary is 43 × 16 (`badges.tsx:84`). 142 distinct controls under 44 px on the phone. WCAG 2.5.8 (24 px) is met except the 16 px summary and the 15–17 px inline links (exempt as inline). Fix: `sm` → `min-h-9` with `py` so the hit area is ≥ 40 px on `< lg`, 44 px for the stepper and tab-bar items (already 56). Command: **adapt**.

### P2
**[P2] `<dl>` structure invalid (axe `definition-list`, serious, 32 page-views).** `components/ui.tsx:190-195` `Stat` renders `<dt>`, `<dd>`, then `<p>` hint inside the `<div>` in a `<dl>` (`/receivables`, `/limits`, `/mandate`). Fix: hint as a second `<dd>`. Command: **harden**.

**[P2] Chat bubble label under 4.5:1.** `components/chat/chat-view.tsx:33` `text-white/80` on `bg-brand-600` composites to `#d1dff9` = **4.16:1** at 11.2 px bold. Fix: `text-white` or `text-brand-50`. Command: **polish**.

**[P2] Chart labels below 11 px and clipped on the phone.** `components/business/cash-forecast.tsx:136,140` annotation labels at `fontSize: 10/11`; measured on 412 px: "Receipt from Foshan Home Retail Co. ¥420…" ends at x = 410 of 412 (touching the edge), "Unsafe in 12 days" at 11 px. The text in the SVG has no DOM alternative except the table disclosure (good). Fix: minimum 12 px, `label_short` only on narrow, anchor labels inside the plot. Command: **adapt**.

**[P2] Floating button order and desktop overlap.** `ChatPanel` is rendered before `<header>` (`app-shell.tsx:229`), so Ask FLOW is the second Tab stop on every page (measured) while it sits bottom-right; at 1440 px it overlaps the card edge by ~18 px (`main` max 1180, button `right-6`). Fix: render after `main`, and `right` ≥ the gutter. Command: **layout**.

**[P2] First paint in the wrong shell and language.** `lib/create-store.ts:62` serves `initial` (`business`, `en`) as the server snapshot; a Demo-mode or Chinese owner sees the Business shell in English, then the swap after hydration, on every load (`<html lang="en">` is static in `app/layout.tsx:18`). Fix: a tiny inline script before hydration that reads `tl-mode`/`tl-lang` into `data-*`/`lang`, or a cookie read on the server. Command: **harden**.

**[P2] Backdrop: an unbounded blur animated forever.** `app/globals.css:334-355` two 38–40 rem discs with `filter: blur(64px)` on an infinite 40 s transform animation behind every Business page (also on phones). Fix: pre-blurred `radial-gradient` backgrounds (no filter), `will-change: transform` only while animating, pause when `document.hidden`. Command: **optimize**.

**[P2] Recharts in `/cash`'s initial JS.** Measured initial script payload: `/` 852 KB, `/cash` 1 244 KB (+372 KB recharts chunk, 106 KB gz, +52 KB), `/trajectory` 1 248 KB, `/whatif` 1 260 KB. `components/business/cash-forecast.tsx:4` imports recharts statically and the forecast card is below the fold. Fix: `next/dynamic` for `CashForecast`, `CashChart`, `DebtChart`, `ConcessionMeter` with the table as the loading state. Command: **optimize**.

**[P2] Tour overlay: no focus trap, polling, layout-property transition.** `components/business/tour.tsx:163-181` `role="dialog" aria-modal` on a non-`<dialog>` without trapping Tab; `:120` `setInterval(update, 120)` plus a capturing scroll listener while open; `:165` transitions `top,left,width,height` (DESIGN.md §4 forbids position/size animation; the 9999 px box-shadow repaints each frame); `CARD_H = 280` underestimates the card with the five-section list on the phone. Fix: `<dialog>` + `ResizeObserver`/`scroll` only. Command: **harden**.

**[P2] Error messages hard-coded in English.** `lib/live/http.ts:33-35,76` ("Owner sign-in required (401)…", "Cannot reach the API at …"), `lib/mock/handlers.ts:364-516` (404/409 messages) are shown verbatim by `ErrorState` (`ui.tsx:293`) in both languages. Fix: error codes mapped through `te("err", code)`. Command: **clarify**.

**[P2] Demo header stacks four rows on the phone.** `app-shell.tsx:371-393`: brand + hamburger, mode switch, mock badge, Owner badge + Sign out, language switch wrap to ~150 px on 412 px (screenshot `phone/21`), above a 133 px fixed stepper: ~45 % of the viewport is chrome. Fix: move language and sign-out into an account sheet as the Business shell does. Command: **adapt**.

**[P2] Annotation marks are focusable with tooltip-only labels.** `components/annotated-text.tsx:70-74` `<mark tabIndex=0 title=…>` activates on hover/focus only; the label ("1. Terms extension") is in `title`. Fix: `aria-describedby` to a visible footnote list, or make the `<sup>` a button. Command: **harden**.

**[P2] `CashChart`/`DebtChart` have no text alternative.** `components/charts.tsx:98,169` no `role="img"`/`aria-label` (unlike `CashForecast:117` and `ConcessionMeter:231`); the tooltip is hover-only. Fix: `role="img"` + summary sentence, and a figures table as on `/cash`. Command: **harden**.

**[P2] Status/alert plumbing.** `components/demo-stepper.tsx:72` an `aria-live="polite"` region re-announces step text on every step (fine) but `:115` reads `demoStore.get()` during render (dead code). The `LoadingBlock` announces "Loading" on every refetch because `useAsync` toggles `loading` on each `version` bump (`lib/use-async.ts:20-22`): pages that keep stale data still mount new skeletons where they test `!data` only. Fix: delete `:115`; keep `data` while revalidating. Command: **polish**.

**[P2] Reduced motion.** `globals.css:358-376` sets every duration to 0.001 ms: `Spinner` (`icons.tsx:66`) freezes at one frame, so a loading `Button` shows a static arc with only `aria-busy`; `Skeleton` stops pulsing with no other change. Acceptable per the checklist only if feedback survives: add a visible "…" or text for the spinner under reduced motion. Command: **animate**.

**[P2] No colour scheme declaration.** The app is light-only; there is no `color-scheme` or `prefers-color-scheme` handling, so form controls, scrollbars and the `<dialog>` backdrop take the OS theme on a dark phone while the page stays light. Fix: `color-scheme: light` on `html` (and record "light only" in DESIGN.md). Command: **colorize** (document the decision) or **polish**.

### P3
- **[P3] `dl` under `Stat`**: duplicate of the P2 for `FactTile` notes (`kit.tsx:35-38` are `<dd>`, correct).
- **[P3] `<th>` without `scope`** in the forecast table, `cash-forecast.tsx:188-191`. **harden**.
- **[P3] `"Inter"` named first in `--font-sans`** (`globals.css:11`) with no font file: the rule "no runtime web fonts" holds (none in the build, none from Google), but the UI renders Inter only where it is installed; screenshots differ between machines. Drop the name or self-host. **typeset**.
- **[P3] Both dictionaries ship on every page**: the 68 KB (18 KB gz) chunk holds `en` and `zh`. Acceptable; splitting saves 9 KB gz. **optimize**.
- **[P3] 110 MB of screenshots are committed** (559 files under `docs/screenshots`, 13 MB for this set); not served (no `public/`), so nothing ships, but the clone is heavy. Consider Git LFS or pruning. 
- **[P3] `ApprovalsBadge` refetches on every route change and every store write** (`app-shell.tsx:123`); harmless in mock, one request per navigation in live. **optimize**.
- **[P3] `aria-prohibited-attr` (axe incomplete)**: `offer-parts.tsx:13` `aria-label="#1"` on a `<span>` without a role; `app/evidence/page.tsx:98` `aria-*` on `<pre>`. Use `role="img"`/visible text. **harden**.

### Not findings (checked and fine)
Horizontal overflow: 0 px on every route at 412, 768, 1024, 1440 (tables scroll inside `TableWrap`). Landmarks: one `main`, one visible `header`, one labelled `nav` per shell, `aside` in Demo. Headings: one `h1` per page, no skips. Accessible names: none missing. Focus: a visible ring on all 38 Tab stops of `/`. Dialogs: focus inside, Escape closes, focus returns to the trigger (measured both viewports). `html lang` flips to `zh-CN` and persists across reload (measured). i18n keys: 1 582 `en` / 1 583 `zh`; zero keys missing either way (`apprstatus.PENDING` is defined twice in `en` on one line, `dictionary.ts:582`, so the diff shows it as zh-only: a formatting nit, not a gap); every static `t()` key exists; placeholders match; 9 dynamic template keys all resolve to existing families; 198 `en` keys are never referenced literally (dynamic families account for most; `home.*` and `alertkind.*` legacy keys may be dead). Dates/time zones: no `Date`, `Intl` or `toLocale*` in the UI; the only client arithmetic is day counting (`lib/when.ts`) and `toFixed(1)` seconds. Business/Demo and language persist in `localStorage`, the owner token in `sessionStorage` (`lib/auth.ts`). Strategy flag off: `useStrategyAsync` is a no-op hook (`use-async.ts:50-61`), `BeforeTheyAsk` is not mounted (`deals/page.tsx:215`). Mock JSON (1 552 KB, 141 KB gz) is a lazy chunk loaded on the first API call in mock builds only (`lib/api.ts:57`); the shared 188 KB chunk holds no live-client strings. Contrast of every documented token pair matches DESIGN.md (ink-3 on the backdrop disc 4.55; `ok/warn/bad/info-fg` on their tints 5.8–7.4; status words on bright pills 9.7–10.2; section `fg`/`solid` pairs as listed); the under-3:1 pairs are all hairlines and badge tint borders that the system declares decorative (`line`, `line-strong`, `*-line`, `brand-100`).

## Patterns and systemic issues
- **One fixed element, three fixed bars.** The chat trigger is positioned by a constant (`bottom-28`) while the Business tab bar, the Demo stepper and `main`'s padding each have their own heights; every overlap above comes from this.
- **Compact size = 32 px everywhere.** `sm` buttons and segmented options are shared by desktop and phone; the phone needs its own floor.
- **Client state hydrates late.** Mode, language and the tab title are all applied after hydration, which produces the shell/language flash and the title regression in one family.
- **Server prose is single-language.** Every page that shows `note`/`reason`/`*_display` strings inherits the recording's language; only `GET /home` and the opener have `_zh` recordings.

## Positive findings
Native `<dialog>` for chat and sign-in; native radios behind the segmented controls (arrow keys for free); `aria-current` on nav and steps, `aria-pressed` on the horizon, `aria-expanded`/`aria-controls` on the approval toggle, `role="log" aria-live` on the chat; a skip link that targets a focusable `main`; the forecast has a `role="img"` summary and a figures table; the Playwright config forces `reducedMotion: reduce`; recharts and the mock JSON are route-split and lazy; zero console noise; zero hard-coded colours; the dictionary is complete in both languages with real plural handling.

## Recommended actions
1. **[P0] `/impeccable adapt`**: the phone chat trigger (into the stepper/tab bar or a 44 px icon FAB) and `main`/scroll padding from measured bar heights; `sm` controls to ≥ 40 px on `< lg`; the Demo header rows; chart label sizes.
2. **[P1] `/impeccable harden`**: route metadata for the tab title; the chart focus ring; Escape/outside-click on the account sheet; `Stat` hint as `<dd>`; `lang` on the plan/worth/reconciliation reads and `_zh` recordings; error codes through the dictionary; the Tour as a `<dialog>`; `role="img"` on the engine charts; pre-hydration mode/lang.
3. **[P2] `/impeccable optimize`**: pre-blurred backdrop without `filter`; `next/dynamic` for the charts; stop the Tour's 120 ms poll.
4. **[P2] `/impeccable clarify`**: owner-facing error messages in both languages.
5. **[P2] `/impeccable polish`**: chat label contrast, `<th scope>`, `color-scheme: light`, the spinner under reduced motion, the duplicate `apprstatus.PENDING` line, the dead read in `demo-stepper.tsx:115`.

You can ask me to run these one at a time, all at once, or in any order you prefer. Re-run `/impeccable audit` after fixes to see your score improve.
