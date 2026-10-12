# Selection seams inventory (ticket #122, map #121)

Facts from source at dev `8b3d6761`, 13 October 2026. No servers were started; nothing here is a recommendation.

Keys in scope: `customer`, `decision`, `invoice`, `scenario`, `path`, `from` (the URL), plus `buyer`, `tab`, `stress`, `id`/`at`/`clause` and the `#` hashes where they decide a selection. Paths are relative to the repo root; `web:` is `apps/web/`, `api:` is `services/api/app/`.

## 1. The three context helpers (the client has two different key sets)

| Helper | Keys | Where |
|---|---|---|
| `readContext` / `contextQuery` / `customerHref` | `decision`, `path`, `invoice` — never `customer`, `from`, `scenario` | web:lib/customer-href.ts:16-32, :43-46 |
| `withContext` | `customer`, `decision`, `path`, `invoice` (+ `extra`) | web:lib/receivables-context.ts:7-22 |
| `contextQuery` (Deals queue) | `customer` (required), `decision`, `path` — never `invoice` | web:components/deals/queue/model.ts:50-55 |
| `fromCustomer` | appends `customer=<id>&from=customer` to a server href | web:lib/customer-href.ts:38-40 |
| `CustomerName` (every customer name in Deals, Receivables, Activity, legacy table) | `customerHref(id, readContext(useSearchParams()))`: the **current page URL's** `decision`, `path`, `invoice` | web:components/customer-link.tsx:12 |

`scenario`: no producer and no consumer anywhere in `apps/web` (grep over app, components, lib). `from`: one producer (`fromCustomer`, Customer → Cash) and one consumer (Cash, web:app/cash/page.tsx:118; validated to `deal|invoice|customer` at web:lib/cash-stress.ts:23).

## 2. Seams by surface

Columns: **Carried** = keys written on the link or read; **Dropped / replaced** = keys the source URL or row holds that the link does not carry, or carries with another row's value; **Source of selection** = URL, server, session cache (`tl-demo-v3` in sessionStorage, web:lib/demo-store.ts:94-96), page default, or module variable.

### Deals (`web:app/deals/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| D1 | Page mount | `GET /deals?lang&customer&invoice&path` | `customer`, `invoice`, `path`, read **once** at mount (`useState` initialiser, :81-82; web:lib/live/index.ts:229-233) | `decision` is not sent to the deals read; a later address change does not re-read | URL (frozen at mount) |
| D2 | Selected deal | `?decision=deal:<offer>` → `selectOffer` (:260-268); `useCurrentOffer` fetches the offer with `getOffer` when the store lacks it, but `verdict` and `negotiation` come **only** from the session store (web:lib/use-current.ts:23-29) | `decision` | a direct link to an evaluated deal shows no verdict unless this tab evaluated it | URL → session cache |
| D3 | Selected deal, no `decision` in URL | `demoStore.offerId` via `useCurrentOffer` (:61; web:lib/use-current.ts:19-22) | — | — | session cache (page default) |
| D4 | `?buyer=<id>` (chase thread, Home deal cards) | once after the books arrive: the buyer's most recently read offer in the session store, else the buyer's first `INBOX` fixture message is submitted (:119-135) | `buyer` | `decision`, `invoice`, `path` | session cache / client fixture list |
| D5 | `?path=` | picks the path when the picture has it (:246-256) | `path` | — | URL |
| D6 | `?tab=` | `openTab` (:454; queue/model.ts:36-39), else first non-empty tab | `tab` | — | URL, else page default |
| D7 | Address writes | `replaceState` writes `decision`, `path` (:272-287) and `tab` (:462-467); `customer` is never written by Deals (:275, :278, :285) | — | `customer` persists only if the page was opened with it | — |
| D8 | Selected deal → Customer (heading, detail, aside profile) | `/customers/{buyer}?customer&decision&path` (:458-459, :503, :532; `customer_context.profile_href` from api:api/customer_overview.py:507) | `customer`, `decision`, `path` | `invoice` (the one the page was opened with, D1) | selected offer + picked path |
| D9 | Queue list row → Customer | web:components/deals/queue/queue.tsx:54-57: `decision` = the row's own open offer, **else the selected offer's**; `path` = the picked path | `customer` (row's), `decision`, `path` | agreed / setup rows carry another row's `decision` and `path`; `invoice` never | row + selected deal |
| D10 | Read-only detail (agreed / setup line) → Customer | :503: `decision` = selected offer's, `path` = pick | `customer` (row's), `decision`, `path` | copies the selected deal's `decision`/`path` | row + selected deal |
| D11 | Aside → Cash stress | queue/model.ts:58-62: `/cash?stress=<buyer>:<days>&invoice=<first unpaid invoice of the deal>&customer&decision&path` (:532; `firstOpenInvoice` :65-67) | `stress`, `invoice`, `customer`, `decision`, `path` | `invoice` replaced by the deal's first unpaid; no `from` | server deal row |
| D12 | Back link | `open_offer.context.back` of the selected deal, **else the first deal in the read that has one** (:461, :541-544) | server href (see S1) | may show another deal's back | server |
| D13 | → Ask FLOW, Approvals, Documents, Verdict, Cash | `/chat` (:312, :584), `/approvals` (:185), `/documents` (queue-readonly.tsx:37, commitments.tsx:178), `/documents?id&at&clause` (deal-summary.tsx:56-61, :137), `/verdict` (workspace.tsx:329), `/decisions/{id}` (workspace.tsx:343), `/cash` (response.tsx:134), `/cash#cash-options` (decision.tsx:112) | `id`/`at`/`clause` on the clause link only | `customer`, `decision`, `invoice`, `path` on all | — |

### Receivables (`web:app/receivables/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| R1 | Page read | `GET /receivables?lang` (api:api/receivables.py:148-149) | — | the server read takes no selection | — |
| R2 | Selected invoice | `?invoice=` (:81-85); **else the first visible row**; a filter change rewrites `invoice` to the first visible (:99-103) | `invoice` | — | URL, else page default |
| R3 | `#<receivable_id>` (Home remaining-task link) | converted once to `?invoice=` (:110-121) | `invoice` | — | URL hash |
| R4 | Deal read beside the invoice | `?decision=` → `GET /decisions/{id}/exposure?lang` with **no context** (:126-132; web:lib/live/index.ts:173); used only when its buyer is the selected row's | `decision` | `customer`, `invoice`, `path` not sent | URL |
| R5 | `customer`, `path`, `from` | never read by this page; only carried through `withContext` (:139-142, :173) | — | — | — |
| R6 | List row customer name (every row) | web:components/receivables/invoice-list.tsx:94 → `CustomerName` → URL context (web:components/customer-link.tsx:12; customer-href.ts:16-27) | `decision`, `path`, `invoice` **of the current URL** | `customer` never; every row's link carries the **selected** row's `invoice` | current URL, not the row |
| R7 | Selected row customer (strip, detail eyebrow, aside, "View payment terms") | `withContext('/customers/{buyer}', params, {customer: row, invoice: row})` (:139-140, :150, :164, :174; actions.tsx:23-28) | `customer`, `invoice` (row's), `decision`, `path` (URL) | — | row + URL |
| R8 | Pending counter → Deals | :141-142: `/deals?decision=<pending_counter.decision_id>&customer&invoice&path&buyer` (`pending_counter`: api:strategy/receivable_rows.py:125-139) | `decision`, `customer`, `invoice`, `path`, `buyer` | — | row + URL |
| R9 | "Explore the cash impact" → Cash | :173: `/cash?stress=<buyer>:<delay>&customer&invoice&decision&path` | `stress`, `customer`, `invoice`, `decision`, `path` | no `from` | row + URL |
| R10 | Financing → Decision record | `financing_href` = `/decisions/{id}` (invoice-detail.tsx:124-127; api:api/receivables.py:98-118) | — | all | server |
| R11 | Chase dialog → thread | `thread_href` = `/deals?buyer=<buyer>` (chase-payment.tsx:137; api:api/collections.py:146) | `buyer` | `invoice`, `decision`, `customer`, `path` | server |
| R12 | History sections | `CustomerName` (history.tsx:4) | as R6 | as R6 | current URL |
| R13 | Legacy page (only when the server has no `GET /receivables`, :57-58) | `CustomerName` (receivables-table.tsx:139, :221); `focusInvoice` on expand (receivables-table.tsx:80-82) | as R6 | — | current URL / module variable |

### Cash (`web:app/cash/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| C1 | Stress link | `?stress=<buyer>[:<days>]` (:117; web:lib/cash-stress.ts:14-20); **without it every other param is ignored** (:114-118) | `stress` | — | URL |
| C2 | Exposure read | `GET /buyers/{id}/exposure?lang&spare=0&customer&invoice&decision&path&from` (:118-121; web:lib/live/exposure-query.ts:4-8) | all five | — | URL |
| C3 | Invoice named | `GET /receivables` rows, matched to `ctx.invoice` (:124, :197) | `invoice` | — | URL |
| C4 | Back link | server `context.back` (:232; web:components/business/stress-context.tsx:12-23) | server href (see S3) | — | server |
| C5 | → Funding, What-if, Capex, options | `/funding` (:186), `/whatif` (:351), `/capex` (:358), `/cash#cash-options` (remaining-task links) | — | `customer`, `invoice`, `decision`, `path`, `stress` | — |

### Customer (`web:app/customers/[id]/page.tsx`, `web:components/customer/overview.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| U1 | Page read | id from the path (:36-37); `readContext` → `decision`, `path`, `invoice` (:38); `GET /customers/{id}/overview?lang&decision&path&invoice` (web:lib/live/index.ts:252-253) | `decision`, `path`, `invoice` | `customer`, `from` in the URL are ignored (customer-href.ts:16); the server also accepts `scenario` (api:api/customer_overview.py:989-992) but the client never sends it | URL |
| U2 | Back link | server `context.back` passed unchanged (overview.tsx:201-210; api:api/customer_overview.py:952-965): this buyer's `decision` → `/deals?decision&path`; else this buyer's `invoice` → `/receivables?customer&invoice`; else `/deals` | per branch | deal branch drops `customer` and `invoice`; invoice branch drops `decision`, `path` | server from the query |
| U3 | "View the invoices" | server `actions[invoices]` passed unchanged (overview.tsx:37; api:api/customer_overview.py:521-526): `/receivables?customer&invoice=<lead>` where lead = the row with a pending counter, else the first row (:514-519) | `customer`, `invoice` | `invoice` replaced by the server's lead (not the URL's); `decision`, `path` dropped | server |
| U4 | "Stress-test payment" | server `/cash?stress=<buyer>:30&invoice=<lead>` (api:api/customer_overview.py:527-528) + client `&customer=<id>&from=customer` (overview.tsx:37; customer-href.ts:38-40) | `stress`, `invoice`, `customer`, `from` | `invoice` is the lead's; `decision`, `path` dropped | server + client |
| U5 | Decision primary ("Read the offer" / reply) | server `decision.primary.href` passed unchanged (overview.tsx:64): `/deals?decision=<open offer>` (api:api/customer_overview.py:563) or `/deals?decision&path=<server's lead path>` (:586) | `decision`, (`path`) | `customer`, `invoice` dropped; `path` is the server's recommendation, not the URL's | server |
| U6 | Outstanding work "The deal" | `/deals?decision=` (overview.tsx:182-183; api:api/customer_overview.py:778) | `decision` | `customer`, `invoice`, `path` | server |
| U7 | Economics edit | `/inputs?customer=` (api:api/customer_overview.py:915; overview.tsx:136) | `customer` | the rest | server |

### Activity (`web:app/activity/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| A1 | Page | reads no query or hash | — | — | — |
| A2 | Record links | `decision_link.href` = `/decisions/{id}` (:50, :297; api:api/causality.py:159); `/documents?id=` (:277); `/evidence` (:431) | `id` on the document link | — (the page holds no selection) | server |
| A3 | Customer names | `CustomerName` (:352) → `/customers/{id}` with no query (the Activity URL holds no context) | — | — | — |

### Approvals (`web:app/approvals/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| P1 | Page | `#approval-<id>` scrolls the card into view (:81-82); no query key is read | hash | — | URL hash |
| P2 | Arrivals | `/approvals#approval-<id>` from the decision record (decisions/[id]/page.tsx:47, :150), `approvalHref` (web:components/operation-result.tsx:20-21; next-action.tsx:61), Home V2 attention (api:api/home_v2.py:260-270); `/approvals` bare from Deals (:185) | hash only | `customer`, `decision`, `invoice` never | — |
| P3 | Links out | `/decisions/{decision_id}` (web:components/approval-card.tsx:289-291); `next_step_href` = `/limits` after a refused run (approval-card.tsx:445-447; api:api/presentation.py:1162) | — | — | server |

### Decision record (`web:app/decisions/[id]/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| E1 | Page | id from the path (:226-228); no query | — | — | URL path |
| E2 | Back | `history.back()`, else `/activity` (:239) | — | — | browser history |
| E3 | "Open Deals" / "Open Approvals" | `dealHome` = `/deals` or `/approvals`, bare (:29, :211) | — | the record's own `decision` id is not carried to Deals | — |
| E4 | Review the plan | `/approvals#approval-<id>` (:47, :150) | hash | — | server |
| E5 | Remaining-task links | server `remaining_task.links` (:60-72; api:api/decisions.py:544-556): `/cash#cash-options`, `/receivables#<rid>`, `/limits` | `#<rid>` hash | — | server |

### Ask FLOW (`web:lib/chat-context.ts`, `web:lib/chat.ts`, `web:components/chat/`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| F1 | What an owner turn sends | `context` on `POST /nl` (chat.ts:138; chat-context.ts:52-61): `page` = pathname; `offer_id` = `demoStore.offerId` **only if its verdict is in the session store** (:57); `invoice_id` only when `page === "/receivables"` **and** `focusInvoice` was called (:58); `since_day` | `page`, `offer_id`, `invoice_id`, `since_day` | **no URL key is read**; `decision_id` exists in `NlPageContext` (web:lib/types.ts:2121-2127) but the client never sets it; `focusInvoice` is called only by the legacy table (web:components/business/receivables-table.tsx:80-82), never by the new Receivables page (web:app/receivables/page.tsx:71-143), so the selected invoice never reaches chat from it | session cache + module variable |
| F2 | Server binding | api:nl/binding.py:69-95 validates `offer_id`/`decision_id`/`invoice_id` against the stores; a deal binds only with its verdict (:86-87) | — | ids not found are dropped silently | server |
| F3 | Displayed scope ("Discussing: …") | the **last assistant response's** `context_echo` (chat-view.tsx:153-154, :279; `Discussing` :125-134) | `counterparty_name`, else `invoice_id` | shown after an answer, not before the question; nothing shown until the first answer | last response |
| F4 | Clearing | the owner conversation is emptied only by `newConversation` (no callers in apps/web), `setCounterparty` (buyer role) and sign-out (chat.ts:202-230); **not on route change** | — | — | — |
| F5 | Suggested prompts | `promptsFor(role, lang, pathname, facts)` with `dealFacts()` from the session store (chat-view.tsx:149-151; use-chat-facts.ts:23) | pathname | — | session cache |
| F6 | Entry | `/chat` bare from Deals (deals/page.tsx:312, :584); the dock button opens the panel in place (chat-panel.tsx:29-40) | — | — | — |

### Documents (`web:app/documents/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| O1 | Page | `?id`, `?at`, `?clause` (:39-42) | `id`, `at`, `clause` | — | URL |
| O2 | Selecting a document | `router.replace('/documents?id=…')` (:53) | `id` | `at`, `clause` dropped on the next selection | URL |
| O3 | Arrivals | `/documents?id&at&clause` (deal-summary.tsx:56-61); `/documents?id=` (deal-summary.tsx:137; activity :277); `/documents` bare (home/deals.tsx:38, queue-readonly.tsx:37, commitments.tsx:178) | per link | `customer`, `decision`, `invoice`, `path` never | — |
| O4 | Shell back | `OWNER_DETAIL_ROUTES['/documents'] = '/deals'` (web:lib/mode.ts:30; app-shell.tsx:368, :427-430) | — | the deal | — |

### What-if (`web:app/whatif/page.tsx`)

| # | Surface element | Link or read | Carried | Dropped / replaced | Source of selection |
|---|---|---|---|---|---|
| W1 | Page | reads no query; `START` = EX01's terms (60 days, 120 bp, 100 bp; :23-24) | — | — | hard-coded page default |
| W2 | Read | `POST /whatif` body = slider params only (web:lib/types.ts:2248-2256; api:api/whatif.py:66); the server builds `context(state, day)` with no buyer (api:whatif/simulate.py:285, :305) → the buyer with a recurring invoice and an open receivable, golden `BUYER-1` / `RCV-A` (api:whatif/offer.py:99-103) | — | `customer`, `decision`, `invoice` have no route to this page or read | server default |
| W3 | Arrival / back | `/whatif` bare from Cash (:351); shell back `/cash` bare (web:lib/mode.ts:30) | — | all | — |

### Home (arrivals into the surfaces above; `web:app/page.tsx`)

| # | Surface element | Link | Carried | Dropped / replaced |
|---|---|---|---|---|
| H1 | Deal cards | `/deals?buyer=<id>` (web:components/home/deals.tsx:46; api:api/home_hybrid.py:876, :889, :1060; api:api/worklist.py:383) | `buyer` | `decision`, `invoice`, `path` (resolved on Deals by D4) |
| H2 | Section cards | `/deals`, `/receivables`, `/activity` (api:api/home_hybrid.py:890, :1204, :1210; web:components/home/cards.tsx:33, :58, :95) | — | — |
| H3 | Remaining task | `/receivables#<rid>` (api:api/decisions.py:553; web:app/page.tsx:146; open-decisions.tsx:18-30), `/decisions/{id}` (open-decisions.tsx:11, :21) | hash / path id | — |
| H4 | Attention | `/approvals#approval-<id>`, `/cash#cash-options` (api:api/home_v2.py:260-275; home_hybrid.py:1008; web:components/home/attention.tsx:136-255) | hash | — |

## 3. The server reads: query accepted, `context.back`, echo fields

| # | Read | Query keys accepted | `context.back` | Echo beside `back` | Pointer |
|---|---|---|---|---|---|
| S1 | `GET /deals`, `GET /deals/{cp}` | `lang`, `customer`, `invoice`, `path` (no `decision`) | on `open_offer.context.back` of the buyer named by `customer` or by `invoice`'s owner only; `customer_back`: `/customers/{buyer}?decision=<the open offer's deal id>&path&invoice` (parts naming another buyer are dropped) | none | api:api/deals.py:20-45; api:api/exposure_words.py:235-252 |
| S2 | `GET /customers/{id}/overview` | `lang`, `decision`, `path`, `invoice`, `scenario` | always: this buyer's deal → `/deals?decision&path`; else this buyer's invoice → `/receivables?customer&invoice`; else `/deals` | `context.customer` (the id), `context.deal` (only when `decision` is this buyer's offer), `context.scenario` (only with a deal and `asked` or `counter:<k>` under the verdict's counters) — **no client reads these three** | api:api/customer_overview.py:952-1003 |
| S3 | `GET /buyers/{id}/exposure` | `lang`, `spare`, `customer`, `invoice`, `decision`, `path`, `from` | `origin_back`: `from=deal` → `/deals?decision&path&customer`; `from=invoice` → `/receivables?invoice&customer`; `from=customer` → `/customers/{id}` (no query); without `from`: deal, else invoice, else customer; parts naming another buyer dropped; `context` absent when nothing names this buyer | none (`{"back": back}` only) | api:api/strategy_exposure.py:216-246; api:api/exposure_words.py:254-275 |
| S4 | `GET /decisions/{id}/exposure` | `lang`, `spare`, `customer`, `invoice`, `path` | `customer_back` with the read's own deal, **only when the query carries `customer` or `invoice`**; a bare read has no `context` | `customer` (the offer's buyer), `deal`, `scenario: "asked"` — only when `back` is present | api:api/strategy_exposure.py:131-153, :170-186 |
| S5 | `GET /offers/{id}/exposure` | `response`, `lang`, `spare`, `customer`, `invoice`, `path` | as S4 | `customer`, `deal`, `scenario` = `response` — only when `back` is present; the Deals page calls it with no context (web:lib/api.ts:267; live/index.ts) so no `context` is returned | api:api/strategy_exposure.py:156-168 |
| S6 | `GET /receivables` | `lang` | none | none; rows carry `financing_href` (`/decisions/{id}`) and `pending_counter.decision_id` | api:api/receivables.py:98-118, :148-149 |
| S7 | `POST /nl` | body `context` = `page`, `offer_id`, `decision_id`, `invoice_id`, `since_day` | — | `context_echo` = `{offer_id, counterparty_name, decision_id (the verdict id), invoice_id}`, null when none bound | api:nl/models.py:103-125; api:nl/binding.py:40-56, :69-95; api:nl/service.py:738 |
| S8 | `POST /whatif` | slider params only | — | — | api:api/whatif.py:66 |
| S9 | Chase (`collections`) | — | — | `thread_href` = `/deals?buyer=` | api:api/collections.py:146 |

## 4. Counts

- Link seams inventoried: 37 (D8–D13, R6–R13, C5, U2–U7, A2–A3, P2–P3, E3–E5, F6, O2–O4, W3, H1–H4).
- Link seams that **drop** a key the source page holds, or **replace** it with another row's or the server's choice: 25 (D8–D13, R6, R10–R13, C5, U2–U7, E3, F6, O2–O4, W3, H1). The three that carry everything the page holds: R7, R8, R9 (R9 without `from`). The other nine are bare links from pages that hold no selection in their URL (A2, A3, P2, P3, E4, E5, H2, H3, H4).
- Seams that **copy another row's** value: D9, D10 (the selected deal's `decision`/`path` on agreed and setup rows), D12 (another deal's back), R6 and R12 (the selected row's `invoice` on every customer name), U3 and U4 (the server's lead invoice in place of the page's), U5 (the server's lead path in place of the URL's).
- Reads whose selection comes from a session cache or a page default instead of the URL: D3 (session cache), D2 (verdict and negotiation from the cache only), D4 (session cache, else the client fixture list), R2 (first visible row), W1/W2 (hard-coded EX01, golden buyer), F1 (session cache plus a module variable; never the URL), F3 (the last response).
- Echo fields no client reads: S2's `context.customer/deal/scenario`; S4/S5's `customer/deal/scenario` (and the Deals page never asks for them). `scenario` has no producer in `apps/web`.
