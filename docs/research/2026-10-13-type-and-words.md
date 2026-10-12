# Bilingual and type inventory: 12 px financial qualifiers, English words in Chinese, day numbers in Business (13 Oct 2026)

Ticket: [#125](https://github.com/peachoolongtee/smu2sz/issues/125) on map [#121](https://github.com/peachoolongtee/smu2sz/issues/121).
Read from source at `dev` `8b3d6761`, no server run; line numbers are that commit's. The audit's citations moved: `offer_picture.py:488` is
`offer_picture.py:584` on dev; `cash/page.tsx:38–43` and `invoice-list.tsx:51–59` are unchanged. Facts only; each item names the server
field or dictionary key that should carry the word (the fix is #138's).

## 1. The type scale as declared

- `apps/web/app/globals.css:137` `--text-meta: 0.75rem` (12 px); `:139` `--text-supporting: 0.8125rem` (13 px, the floor the comment at
  `:131–136` sets for "any financial qualification: a figure, a rate, a limit, the words that say what a number is against").
- No other sub-13 px size exists: `text-xs` is not redefined (no `--text-xs` in globals.css), and the only explicit `font-size:` lines
  (`:224, :462, :468, :476, :482, :580`) are 14 px or a token. The app has no `text-[10px]`/`text-[11px]`/`text-[12px]` class anywhere.
- `text-meta` appears 307 times in `apps/web` (components 192, app 115). Most are eyebrows, column headers, `<dt>` labels, ids in
  monospace, hints: the role the token is for. Section 2 lists only the uses that carry a figure, a rate, a limit or a timing qualifier.

## 2. Financial qualifiers at 12 px (`text-meta`), by surface

### Business pages and Approvals (the map's surfaces)

| File:line | What is 12 px | The word's source |
| --- | --- | --- |
| `components/approval-card.tsx:68` | `quote.rate_basis` (the quote's rate and basis) | `quote_view` field `rate_basis` (`presentation.py:1893`) |
| `components/approval-card.tsx:69` | `quote.cost_note` | `quote_view` field `cost_note` |
| `components/approval-card.tsx:70` | "Cash arrives {when}." with `quote.lands_when` | `quote.lands_when` + key `appr.quote.lands` |
| `components/approval-card.tsx:73` | the "Actual" caption over landed amounts | key `appr.quote.actual` (label; the amounts under it are `text-ink`) |
| `components/approval-card.tsx:179` | "({rate} a year)" beside `p.cost_display` when `priced` (`block text-meta`) | `p.rate_text` + key `biz.costRateOnly` |
| `components/approval-card.tsx:315` | `te("tier.short", a.tier)` (the authority tier's words) | key `tier.short.*` |
| `app/decisions/[id]/page.tsx:122–125` | "Net cost {net_display} · {basis_facility_name}" | `sent.economics.net_display`, `basis_facility_name` |
| `app/decisions/[id]/page.tsx:127` | `sent.funding_blocked` (why funding did not run) | `sent.funding_blocked` |
| `app/decisions/[id]/page.tsx:175` | `o.when` beside each operation | `operations[].when` |
| `app/decisions/[id]/page.tsx:190` | "Cash received {when}" / "Cash arrives {when}" beside `principal_display` | `settlement[].arrival_when` + keys `deal.cashReceived`/`deal.cashArrives` |
| `components/business/next-action.tsx:134` | the "Cost in total" eyebrow over the cost breakdown (label only; the terms line at `:146` is `text-supporting`) | key `biz.costTotal` |
| `components/home/attention.tsx:122, :165` | `f.label` of each fact (the lands-when fact's label; its value at `:123` is `text-sm`) | `attention.facts[].label` |
| `components/ui.tsx:289` | every `Stat` tile's `<dt>` label (the value is `type-value`/`text-section`, the caption `text-supporting`) | the tile's `label` prop |
| `components/receivables/invoice-list.tsx:69` | the desktop column headers (Customer, Outstanding, Due, Financing, Net to you, Status) | keys `recv3.col.*` |
| `components/receivables/invoice-list.tsx:156` | the phone column caption over each cell (`Label`) | keys `recv3.col.*` |
| `app/receivables/legacy.tsx:25` | the caption under each fact figure (legacy page, mounted only when the v3 read is off, `receivables/page.tsx:58`) | the fact's `caption` prop |
| `components/business/receivables-table.tsx:285, :291` | `o.receivable_id` in mono (legacy only) | id, not a word |
| `app/activity/page.tsx:219–224` | a time-passing row: the sentence and its kind word | `event_text`/`kind_text` |
| `app/activity/page.tsx:234` | `o.event_detail` (amounts and landing words of an operation) | `operations[].event_detail` (`executed_words`, `presentation.py:540`) |
| `app/activity/page.tsx:244` | "What remains: {what_remains}" (a residual shortfall sentence) | `operations[].what_remains` |
| `app/activity/page.tsx:302, :361` | the audit-detail `<dl>` under a row (ids, hashes, days) | audit level, raw fields |
| `components/chat/assistant-turn.tsx:107` | "Curable for {cost}" | `violations[].cure_cost_display` + key `chat.verdict.curable` |
| `components/chat/assistant-turn.tsx:67, :174` | a plan step's condition; an operation's sequence | `plan.steps[].condition`, `ops[].seq` |
| `components/annualised.tsx:58–62` (`AnnualisedCompact`, chat) | "{discount} on {rcv} = {rate} a year for {days} days" as a whole list | `annualised[].discount_display`, `annual_rate_display`, `days_early` + keys `annualised.leg`/`annualised.line` |
| `components/annualised.tsx:26–30` | "against {label} at {rate}" comparison lines | `compare_to[].annual_rate_display` + key `annualised.against` |
| `components/deals/decision.tsx:121, :133` | the "Money" and "What is left" `<dt>` labels (values are `text-sm`) | keys `deal.money`, `common.left` |
| `components/business/facility-explainer.tsx:55–63` | the what/good/watch `<dt>` labels (values `text-ink`) | keys `biz.facility.*` |
| `components/deals/deal-summary.tsx:35` | the terms table headers | keys |

### What-if, Capex, the engine views (reachable from Business doors)

| File:line | What is 12 px | Source |
| --- | --- | --- |
| `components/whatif-results.tsx:108` | the sub-line under a summary figure (`sub`) | the figure's `sub` prop |
| `components/whatif-results.tsx:255` | "{x} still available under your limit" | `headroom_display` + key `whatif.meter.headroom` |
| `components/whatif-results.tsx:264` | each concession item's formula (mono) | `items[].formula` |
| `components/whatif-results.tsx:286` | `c.limit` under a covenant's observed value (observed is `text-lg`) | `covenants[].limit` |
| `components/whatif-results.tsx:309` | "Need {x}" under the plan cost | `need_display` + key `whatif.plan.need` |
| `components/whatif-controls.tsx:171` | "the whole face, {face}" | `receivable_face_display` + key `whatif.face.whole` |
| `components/charts.tsx:45–58` | the whole chart tooltip (day and each series' figure) for `CashChart`/`DebtChart`, mounted by `app/trajectory/page.tsx:144, :198` and `components/whatif-results.tsx:208` | series `display` strings |
| `app/capex/page.tsx:90, :92` | `estimate_note`; "as of {when}" | `capex.estimate_note`, `as_of_day` |
| `app/capex/page.tsx:189, :289` | a structure's warning; the assumptions list | `structures[].note`, `assumptions[]` |
| `app/capex/page.tsx:306, :341` | the file's as-of and provenance lines | `file.as_of`, provenance |
| `components/verdict-parts.tsx:36, :40` | the Observed/Limit `<dt>` labels (values `text-lg`) | keys `verdict.observed`/`verdict.limit` |
| `components/verdict-parts.tsx:70` | `cure_note_when`/`cure_note` under the cure cost | `violations[].cure_note_when` |
| `components/verdict-parts.tsx:90` | the "Cost to supplier" label over `supplier_cost_display` (`text-lg`) | key `verdict.counter.cost` |
| `components/in-transit.tsx:22` (mandate page only) | "requested on day {from}, {facility}" | `lots[].request_day`, `facility_id` + key `transit.hint` |
| `app/funding/page.tsx:109, :129, :150, :176` | a menu row's covenant effect, reason, excluded note, a candidate's note | `menu[].covenant_effect`, `menu[].reason`, `excluded_note`, `note` |
| `app/trajectory/page.tsx:150, :268` | the chart legend; a covenant's formula | legend keys; `formula` |
| `app/alerts/page.tsx:47, :90` | "basis: {mode}, day {day}"; a suggested cure's detail | `basis`, `day`, `suggested[].detail` |
| `app/reconciliation/page.tsx:32, :78, :127` | "as of day {day}"; a row's detail; a promise's detail | `as_of_day`, `detail` |
| `components/plan-card.tsx:85` | a plan table cell in mono | plan fields |

Everything else at `text-meta` is a label, an eyebrow, an id, a hint or a nav item (the `apps/web` grep `text-meta|text-xs` lists all 307).

## 3. English timing and event words that reach a Chinese page

### 3a. "same day" and "N days" on the Cash page (UX31)

- `services/api/app/api/decide.py:592` builds `menu[].time_to_cash_display` as `"same day"` / `f"{r.time_to_cash_days} days"` with no
  `lang`, inside `router_plan(lang)` (`:570–573` already normalises `lang`). The recorded live read shows the strings: `apps/web/mocks/funding.json`
  and `funding_day34.json` carry `"same day"`, `"1 days"` (the plural is wrong too), `"2 days"` … `"60 days"`.
- Rendered on Chinese Cash twice: `apps/web/app/cash/page.tsx:38` (`ttc = menu…time_to_cash_display`) and `:43` through key
  `biz.facility.speed`, whose zh value is `"{ttc} 到账"` (`dictionary.ts:3652`) → "same day 到账"; and
  `components/business/facility-explainer.tsx:45` (same key, same field), mounted at `cash/page.tsx:303`.
- The neighbours at `decide.py:593–596` are English-only too: `covenant_effect` (`"counts in leverage"`/`"no debt"`), `reason`
  (`"; ".join(r.notes)`) and `rate_basis`. `reason` is shown on Chinese Cash at `facility-explainer.tsx:73`; the notes come from
  `services/api/app/funding/menu.py:36–70` and include `f"cash on day {f.lead_time_days}, needed by day {need_day}"` (`:56`), a day number.
- Field that should carry the word: `menu[].time_to_cash_display` (and `reason`, `covenant_effect`), written with `lang`. The server
  already has the Chinese forms: `nl/capabilities.py:112–114` ("当天到账" / "{n} 天到账") and `strategy/words.py:192` ("当天").

### 3b. "Payroll" and the other flow labels (UX31)

- The flow labels are fixture book names: `fixtures/scenarios/public_sme.json` flows `Payroll (the 15th)`, `Material suppliers (the 10th and 25th)`,
  `Rent, utilities, freight (the 28th)`, `VAT and surcharges (the 15th)`; `golden_sme.json` flows `Payroll`, `Operating bill`, `Supplier payment`.
- `services/api/app/api/home.py:381` sets each series event's `label` = `in_language(label, lang, state)` and `label_short` =
  `_label_short(...)` (`:354–367`), which for a FLOW falls to `in_language(...)`. `in_language` (`presentation.py:526–531`) calls
  `translate(text, book_names(state))`, and `book_names` (`:508–512`) lists `x.label for x in state.flows`: flow labels are, by that
  docstring, "carried over exactly in a Chinese sentence, never translated". So the Chinese home read keeps `"label_short": "Payroll"`
  (`apps/web/mocks/home_summary_day34_zh.json:134–135, :1347–1348, :2976–2977`).
- The driver sentence does the same: `home.py:261–262` `f"{label} {fmt_short(…)} 将于{when}到期。"` with `label` from `in_words`, giving
  `"Payroll ¥200k 将于8 天后到期。"` (`home_summary_day34_zh.json:30`, field `cash.drivers[]`).
- Where it shows: `components/business/cash-forecast.tsx:184` (receipt-basis rows use `e.label_short ?? e.label`), the forecast table
  `:265` (`e.label`), and the Home drivers (`cash.drivers[]`, `home.py:1243`). The event picture's rail is not affected: it reads
  `cash.events_rail` (`event-picture.tsx:84`), built by `home_hybrid.py:531` with the kind words of `:389–433` ("发放工资").
- The server already has the Chinese words for the kinds: `home_hybrid.py:358–365` (`_flow_kind`: payroll / debt / supplier),
  `:389–390` ("发放工资"), `:433` (`_noun`: 工资 / 供应商付款 / 债务还款). Fields that should carry them: `cash.series[].events[].label_short`
  (and `label`) and `cash.drivers[]`, from `_flow_kind` rather than the verbatim book name.

### 3c. Facility names

- `HomeView.facilities[].name` and `menu[].facility.name` are the fixture's English names (`public_sme.json`: "Bank credit lines, undrawn room",
  "Invoice financing (supply-chain platform)", …; the `Facility` model has one `name: str`, `domain/models.py:260`, no Chinese name).
  Shown on Chinese Cash at `cash/page.tsx:42` and `facility-explainer.tsx:43`, and inside every server sentence that names a source.
  `book_names` keeps them verbatim by design; a Chinese name would need a fixture field or a name map, not a words-layer change.

### 3d. Engine formulas

- `cash/page.tsx:180` renders each plan cost's `c.formula` (`Formula`, `text-supporting`) in the "Calculation" disclosure; `plan_when`
  (`presentation.py:617–638`) adds `*_when` beside `label`, `approval_reason`, `note` but leaves `formula` as the engine's English.
  Same at `whatif-results.tsx:264`, `verdict-parts.tsx:48`. Field: `costs[].formula` (no Chinese form exists today).

### 3e. The dictionary

- `apps/web/lib/dictionary.ts`: 2,375 keys in `en` and 2,375 in `zh`; no en-only key (`i18n.ts:36, :53` fall back to `en[key]`, so a
  missing zh key would show English; none is missing).
- 15 zh values equal their English: brand and format names only (`brand.name`, `chat.agent`, `deal.actor.AGENT` "FLOW", `traj.ebitda`,
  `traj.dscr`, `sample.SEC`, `capex.file.*`, `docformat.*`, and three `{a} · {b}` templates).
- The words layers (`api/financing_words.py`, `api/exposure_words.py`, `strategy/words.py`, `api/receipt_basis.py`, `nl/*`) have no
  untranslated English timing literal; every sentence goes through `t(lang, en, zh)` or `say(lang, …)`. The one English-only timing
  builder on a Business read is `decide.py:592` (3a).

### 3f. Day words computed in the browser

`lib/when.ts:4–6` allows day counting in the browser ("the one arithmetic the browser may do"), and the Business pictures use it instead of
a server word: `cash-forecast.tsx:184, :262`, `components/business/cash-picture.tsx:419, :527, :583`, `components/home/event-picture.tsx:412`,
`components/deals/paths-picture.tsx:197, :325`, `app/activity/page.tsx:211` (fallback), `components/deals/deal-summary.tsx:97` (fallback),
`deals/commitments.tsx:63, :74, :121`, `deals/workspace.tsx:227, :235`, `deals/queue/why-facts.tsx:29, :37`, `deals/inbox-list.tsx:134`,
`app/deals/page.tsx:369`, `receivables/history.tsx:80, :86`, and the legacy Receivables tables. Keys: `biz.when.today`, `biz.when.tomorrow`,
`biz.when.yesterday`, `biz.when.inDays` ("{n} 天后"), `biz.when.daysAgo`, `biz.picture.today`. The zh strings are correct; the words are
the browser's, not the server's.

## 4. Day numbers in Business (UX33)

| File:line | What shows | Field or key that should carry it |
| --- | --- | --- |
| `services/api/app/api/offer_picture.py:584` | `_word()` returns `say(lang, f"Day {n}", f"第 {n} 天")` for any moment kind without a branch; `_KINDS` (`:562`) includes `"end"`, which has no branch, so the picture's last moment is "Day 66" / "第 66 天" | `moments[].word` for kind `end` (a distance word from `_distance`/`when_text`, `presentation.py:316`) |
| `components/deals/paths-picture.tsx:201, :197, :436` | that `word` as the chip label, the tooltip word and the caption | same field |
| `funding/menu.py:56` → `decide.py:596` → `facility-explainer.tsx:73` | "cash on day 3, needed by day 12" in a facility's reason on Cash | `menu[].reason`, through `business_text` |
| `components/approval-card.tsx:200` | `t("common.dayN", { n: p.lands_day })` when `lands_when` is absent | `lands_when` (already sent on current reads; the fallback remains) |
| `components/approval-card.tsx:313` | `appr.requestedValue` "第 {day} 天，由{who}提出" when `created_when` is absent | `created_when` (same) |
| `components/approval-card.tsx:454` | `appr.decidedOn` "第 {day} 天已决定。" when `decided_when` is absent | `decided_when` (same) |
| `components/verdict-parts.tsx:25` | `common.dayN` when `today` is null (mounted by `deals/reasons.tsx`, `verdict`, `capex`) | the caller's `today` |
| `components/charts.tsx:47, :103, :173` | "{Day} {row.day}" in the tooltip and day-number x ticks, for What-if (`whatif-results.tsx:208`) and Trajectory | series `when` |
| `components/in-transit.tsx:21–22` | "{amount} 将于第 {n} 天到账" / "第 {from} 天申请" (mandate page only) | `lots[].arrival_when` (none exists on that read) |
| `components/home/today-card.tsx:47` | `common.dayN` (Demo page only) | Demo keeps day numbers by rule |
| `lib/dictionary.ts:3088, :3368, :3787, :3789` | zh strings with `第 {day} 天` on Business keys: `appr.decidedOn`, `appr.requestedValue`, `biz.deals.breach`, `biz.deals.lowest` (the last two are referenced by no component) | the `*_when` fields above; the two unused keys are dead |

No Business component renders `day_index`; the identifier does not occur in `apps/web`. The engine views (`app/alerts/page.tsx:47, :59`, `app/reconciliation/page.tsx:32,
:129, :169`, `app/ledger/page.tsx:62`, `app/mandate/page.tsx:70`, `app/trajectory/page.tsx:105–142`, `app/security/page.tsx:189`,
`app/inbox/page.tsx:130`, `app/verdict/page.tsx:318`, `components/offer-parts.tsx:59`) keep "Day N" by the standing rule (`when_text` docstring, `presentation.py:317–318`).

## 5. Labels likely to wrap at 390 in Chinese (UX28)

- Receivables filters, `components/receivables/invoice-list.tsx:40–45` (labels) and `:51–59` (`SegmentedTabs` with no `scroll`, no `stretch`).
  Four pills, each with a 16 px icon, `gap-2`, `px-3` and a count badge (`segmented-tabs.tsx:152–170`); the label span is `max-h-9 overflow-hidden`,
  so a label that does not fit wraps to two lines and is then cut (`:33–35` in the component's comment). Labels: en "All / Due soon / Overdue /
  Payment promises" (keys `biz.recv.filter.all`, `biz.recv.filter.soon`, `recv3.filter.overdue`, `recv3.filter.promises`), zh "全部 / 即将到期 /
  逾期 / 付款承诺" (`dictionary.ts:4241, :4243, :4795, :4796`). At 390 − 32 px gutters the track is 358 px for four pills whose natural widths sum
  to roughly 470 px (icon + gap + text + gap + badge + padding); the two four-character pills wrap first.
- The Deals queue's four tabs use the same control with `stretch` and `scroll` (`components/deals/queue/queue-list.tsx:48–49`), which keeps
  every label on one line and scrolls the track; the other `SegmentedTabs` mounts (`event-picture.tsx:275, :286`, `cash-picture.tsx:426`,
  `cash-forecast.tsx:158`, `activity/page.tsx:192`) carry two or three short labels.
- The Receivables column headers (`recv3.col.*`) are hidden under `lg` (`invoice-list.tsx:69` `hidden … lg:grid`) and replaced by per-cell captions
  (`:156`), so they do not wrap on a phone.

## 6. Does the series `when` (dev be9bbfa2+) already cover Cash's timing words?

- What be9bbfa2 added: `presentation.py:307–313` `point_words(rows, today, lang)` sets `when` (`when_text`, "in 30 days" / "30 天后") and
  `display` (`whole`) on every point; called from `home.py:1153–1154` on `GET /home`'s `cash.series` and `next_action.plan_series` only.
- Not on: the router comparison rows' series (`decide.py:565`, `_series` without `point_words`; drawn as the chosen alternative on Cash,
  `cash/page.tsx:150–153`), the offer picture's path series (`offer_picture.py:72–76` `_line` → `_series`; `:776–777`), the pending receipt
  series (`cash.pending.series`, `home_hybrid.py:772`; its `receipt_rows[].when` is sent, `types.ts:2472`, and read at `cash-forecast.tsx:190`).
- Not read by the web: `HomeSeriesPoint` (`apps/web/lib/types.ts`, the `interface` with `closing_display`) declares no `when` or `display`,
  and the pictures compute the words from `day − today` (section 3f: `cash-forecast.tsx:184, :262`, `cash-picture.tsx:419, :527`,
  `event-picture.tsx:412`, `paths-picture.tsx:325`). The x-axis ticks are browser-chosen days (`paths-picture.tsx:176–177`,
  `event-picture.tsx:218–219`) with no server word; only `moments[].word` names a day on the offer picture.
- Cash's "same day" (3a) is a menu field, not a series point: `when` does not touch it.

So: `when` covers the Home chart's points on the server side and nothing on the browser side yet; Cash's timing words (`time_to_cash_display`,
the menu `reason`, the flow labels) are outside it.
