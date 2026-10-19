# Wave 0: port inventory, dictionary merge plan and baseline (6 Oct 2026)

Ticket: [Wave 0: integration baseline](https://github.com/peachoolongtee/smu2sz/issues/17) on the map
[Wayfinder: Business + Demo UX integration](https://github.com/peachoolongtee/smu2sz/issues/13). Branch
`feat/ux-integration` at `origin/dev` `53cd1cc`; source `origin/test/ui-ux` `f59149b`. The decisions behind each row are in
`docs/UX_INTEGRATION_BRIEF.md` section B.

## 1. Port inventory (from `test/ui-ux`)

Rule: transplant by file, never by commit (every `test/ui-ux` commit also edits the old single-shell home or the sidebar).
Read the source with `git show origin/test/ui-ux:apps/web/<path>`.

| Source on `test/ui-ux` | Target on `feat/ux-integration` | Depends on | Adapt | Wave |
| --- | --- | --- | --- | --- |
| `components/simple/cash-card.tsx` (`CashForecast`, `ForecastTooltip`, `ForecastTable`, `Box`, `Swatch`) | `components/business/cash-forecast.tsx` | `lib/chart-helpers.ts` (present), `components/in-transit.tsx` (present), `SectionLink` from `home/today-card` (replace with a plain link) | Feed it `GET /home` `cash.series` / `cash.plan_series` instead of `GET /trajectory`; series names "If you do nothing" / "With the recommended plan"; reserve label "Minimum cash reserve"; add the event annotations and the 30 / 60 / 120 horizon filter; keep `yMin = min(0, min_cash)`; `simple.cash.*` strings become `biz.forecast.*` | 1 (axis and data), 4 (the rest) |
| `components/verdict-glance.tsx` | `components/deals/verdict-glance.tsx` | `glance.*` strings (13 keys, both languages) | Used as Deals level 2 under the recommendation; drop nothing | 7 |
| `components/next-step.tsx` | `components/next-step.tsx` | `next.*` strings (8) | As is; Deals and Approvals use it | 7 |
| `components/deal-steps.tsx` | `components/deals/deal-steps.tsx` | `steps.*` (9), `lib/use-current.ts` (present) | Hrefs change: `/deals` for read and check, `/deals#counters` for respond, `/deals#commitments` for agreed | 7 |
| `lib/inbox.ts` (`INBOX`, `SOURCE_CHANNEL`, `inboxMessageForDoc`) | `lib/inbox.ts` | `lib/samples.ts` (present) | As is; the Deals list renders it labelled "Simulated inbox"; FastCapital stays "Not in your contacts" | 7 |
| `app/inbox/page.tsx` `InboxList` and `PasteMessage` | `components/deals/inbox-list.tsx`, `components/deals/paste-message.tsx` | `inbox.*` additions (19 keys) | Opening a message reads it (no separate button); the Demo engine view `/inbox` keeps its page | 7 |
| `components/verdict-parts.tsx` `ViolationCard` folding, `CounterCard` "Show the calculation", `OperationsList` without the tier badge | same file | `verdict.details`, `verdict.showCalc` strings | Take the whole diff; it is used by Deals and the Demo verdict view | 7 |
| `components/home/agreements-card.tsx` `obligationSentence`, `basePhrase`, `durationPhrase`, `AgreementItem` | `components/deals/commitments.tsx` | `deal.*` strings (48) | Renders "Active commitments" on Deals and the agreements list on Activity; the economic effect shown is the server's `forward_value_display` and the promised payments; no new arithmetic | 7 |
| `components/capex-form.tsx` (`CapexForm`, `yuanToFen`, `useLenders`, `lenderOf`) and the `CapexRequest` fields in `lib/types.ts` | `components/capex-form.tsx`, `lib/types.ts` | `capexForm.*` (8), `lib/demo.ts` `runCapex(req)` signature and exported `CAPEX_REQUEST` | Goes on `/capex` and the Cash & funding equipment section, never on the home; the mock refusal for other figures (`lib/mock/handlers.ts` `capexEvaluate`) comes with it | 4 |
| `app/capex/page.tsx` "Who lends" column | same file | `useLenders` | Take | 4 |
| `components/simple/borrowing-card.tsx` `Option` ("what / good for / watch out" per facility kind) | `components/business/facility-explainer.tsx` | `simple.kind.*.{what,good,watch}`, `simple.borrow.*` | A disclosure under Other options on Cash & funding; availability sort stays | 4 |
| `components/home/glossary.tsx` | `components/glossary.tsx` | `gloss.*` (21) | Opens from the account menu and the Limits page; "safety minimum" becomes "minimum cash reserve" | 6 |
| `components/ui.tsx` `Segmented` wraps (`max-w-full flex-wrap`) | same | none | Take now | 0 (done in Wave 2's first commit) |
| `components/badges.tsx` `TierBadge` removal and its callers (`lists.tsx`, `verdict-parts.tsx`, `chat/assistant-turn.tsx`, `whatif-results.tsx`, `ledger/page.tsx`, `approval-card.tsx`, `capex/page.tsx`) | same files | the `tier.*` strings stay for the autonomy panel | On `dev` the tier is already under "Audit details" on the approval card and Activity; keep it there as text (`te("tier.short")`), drop the badge everywhere else | 7 |
| `components/home/lists.tsx` "Waiting for you" one-line empty state | principle only | | The Business home hides empty blocks (Wave 3); the Demo engine views are unchanged | 3 |
| `components/home/fix-alert.tsx` `openerOfferStore` / `openerAlertId` ("one cure, one button") | not ported | | The Business home has one action already; the mirror of the server's opener rule would be a second source of truth | — |
| `app/simple/page.tsx`, `components/simple/buyers-card.tsx`, `components/simple/agreements-card.tsx` | not ported | | A fourth home; the buyers card's logic lives on in the Deals inbox list | — |
| `app/documents/page.tsx`, `lib/demo-store.ts` `OwnerDocument`, `e2e/documents.spec.ts` | not ported now | | Fog on the map ("Your documents") | — |
| `components/home/capex-card.tsx`, `TodayCard` on the home, `Glossary` on the home | not ported | | Not on a calm home | — |
| `app/verdict/page.tsx` restructure (answer card, `VerdictNextStep`, autonomy panel, rules, counters, "Send our response") | partly | | The Demo engine view keeps `dev`'s page; the glance and the folding reach it through the shared components | 7 |
| `docs/UI_UX_CHANGES.md` | not ported | | Its label map is folded into section 2 below; the living record for this work is the map and `docs/UX_AUDIT.md` section 17 | — |
| `e2e/inbox.spec.ts` | `e2e/deals.spec.ts` (rewritten for the Deals list) | | | 7 |
| `e2e/approvals.spec.ts`, `demo.spec.ts`, `chat.spec.ts`, `home.spec.ts` changes | not taken | | They test the old home and the single shell; the final specs are rewritten per wave | — |

## 2. Dictionary merge plan

The `dev` dictionary (1,136 keys per language) and the `test/ui-ux` dictionary (1,300) share the engine-view namespaces;
`dev` adds `biz.*` (132 keys), `mode.*`, `story.*`; `test/ui-ux` adds `simple.*` (116), `deal.*` (48), `docs.*` (37), `gloss.*`
(21), `glance.*` (13), `steps.*` (9), `next.*` (8), `capexForm.*` (8), `verdict.plain.*` (6). Every `test/ui-ux` key has both
languages except `apprstatus.PENDING` (one value: check it when touched).

**Take the `test/ui-ux` values (English and Chinese) for:**

- `violation.*`: the 11 changed and the 8 new keys (`CONFLICTING_COMMITMENT`, `DISCOUNT_ABOVE_BREAK_EVEN`,
  `EARLY_PAY_DEARER_THAN_PLAN`, `EARLY_PAY_NOT_NEEDED`, `NEW_BORROWING_NOT_ALLOWED`, `PRECONDITION_FAILED`, `STALE_OPERATION`,
  `STALE_VERDICT`), with three edits for the map's terminology: `RESERVE_BREACH` → "Cash drops below your minimum cash reserve";
  "Tier 3" in the four `TIER3_*` labels → "(never allowed)" as on `test/ui-ux`.
- `alertkind.*`: all 8 changed, with `RESERVE_BREACH_AHEAD` → "Cash will drop below your minimum cash reserve" and
  `RESERVE_HEADROOM_LOW` → "Cash is getting close to your minimum cash reserve".
- `opkind.*`: all 10 changed, with `REQUEST_OWNER_APPROVAL` → "Ask for your approval" (mandate language, not "your OK").
- `glance.*`, `steps.*`, `next.*`, `deal.*`, `capexForm.*`, `gloss.*`, `verdict.plain.*`, `verdict.details`, `verdict.showCalc`,
  `inbox.from`, `inbox.source.*`, `inbox.role.*`, the `simple.kind.*` and `simple.cash.*` strings under new `biz.*` names.

**Leave on `dev`'s wording:**

- `nav.*` for the engine views (`Mandate`, `Inbox`, `Trajectory`, `Funding`, `Verdict`, `What-if`, `Capex`, `Ledger`, `Alerts`,
  `Reconciliation`, `Security`, `Evidence`): the Demo navigation names the engine by module on purpose, and `demo.spec.ts`,
  `alerts.spec.ts`, `catchup.spec.ts`, `responsive.spec.ts` and `chat.spec.ts` click those names. The 22 `nav.hint.*` and
  `nav.group.*` keys are not needed (the top bar has six entries).
- `tier.*`: the labels only appear under audit details after the badge removal; keep "Tier 1 / 2 / 3" there as the audit word
  (the approval and chat specs assert it), and keep `dev`'s `tier.title.*` for the Limits page.
- `home.position.*`, `home.waiting.*`, `home.risk.*`, `home.done.*`: the old home's cards; only `TodayCard` survives (on the
  story page). Delete the unused keys in Wave 3 rather than merge them.
- `brand.tagline`, `common.tagline`, `common.synthetic`, `common.simulation`: rewritten in Wave 6, not taken from either.
- `mode.*`, `story.*`, `biz.*`: `dev` only.

**Specs that quote a value this plan changes** (rewrite in the wave that lands it): `demo.spec.ts:72` "Draw facility" and `:84`
"Submit invoice for financing" (operation names), `approvals.spec.ts:61` "Apply for facility". `chat.spec.ts:55`,
`approvals.spec.ts:20` and `home.spec.ts:134` assert "Tier 1 / Tier 2" and stay true (audit details).

**Mechanics:** the dictionary is one file with an `en` block and a `zh` block of the same keys (typecheck fails on a
missing pair). Apply changes as targeted key edits in both blocks, in the wave that needs them, never a wholesale paste of
the `test/ui-ux` file.

## 3. Baseline on `feat/ux-integration` (this worktree, 6 Oct)

| Check | Result |
| --- | --- |
| `pnpm install --frozen-lockfile` | clean |
| `uv sync` (services/api) | clean; `app.main` imports |
| `pnpm typecheck` | clean |
| `pnpm lint` | clean |
| `pnpm mocks:record` against the API on :8011 (memory store, cached model, `DEMO_MODE=1`) | 52 files recorded, `git status apps/web/mocks` empty: the committed mocks are the engine's current figures |
| `E2E_TARGET=mock pnpm exec playwright test` | 34 passed, 1 skipped, 2 failed: both are `responsive.spec.ts` "the slide-over chat fits the viewport with a long reply" (the chat dialog measures about 431 px against a 413 px bound), the macOS Chromium loose end listed in the handover's section 6 (an internal note, in the git history), now seen on the desktop project as well as the phone project; application code is `origin/dev` unchanged. Everything else, including every home, approval, demo, alert, what-if and chat spec, passes |

Facts for later waves, read from the recorder: the trajectory mocks are recorded with the EX01 verdict applied (line 170), the
day-0 fix is asserted to run alone with two legs (`home_act_day0.json`, `executed === 2`), and the day-34 cure is asserted to
wait for approval; both assertions will move with the Wave 1 plan change.
