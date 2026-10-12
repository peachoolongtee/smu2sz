# Lifecycle state inventory: the stage, state and tier words across the Deals read, /decisions, the worklist and Approvals (13 Oct 2026)

Ticket #123 of map #121. Facts only; the queue model is decided on #127. Read against dev `8b3d6761`. Every sentence and line number below is the
repo's own; the observed cells come from running the API in-process (FastAPI `TestClient`, `FEATURE_HOME_V2=1 FEATURE_EXPOSURE=1
FEATURE_CONTRACTS=1`, owner header `X-Owner-Token: demo-owner-token`, agent header `X-Agent-Key: demo-agent-key`) through these walks on the
demo books, day 0:

| Walk | How the state was reached |
| --- | --- |
| RECEIVED | `POST /offers {fixture_id: EX01_PACKAGE}` |
| RESPONSE_READY | then `POST /offers/{id}/evaluate` |
| AUTHORIZATION_REQUIRED | then `executor.propose_commitment(verdict, expires_day=14, counter B)` + agent `POST /operations RECORD_COMMITMENT` (the `_queue_counter` helper, `services/api/tests/api/test_time_semantics.py:397-412`) |
| AGREED (via approval) | then owner `POST /approvals/APR-000001 {decision: APPROVE}` |
| DECLINED | the same queue, then `{decision: REJECT}` |
| NEEDS_CLARIFICATION | `POST /offers {fixture_id: EX07_CONFLICT}` + evaluate (compile status CONFLICTING_SOURCES) |
| AGREED (via buyer) / NO_DEAL | EX01 evaluated, then `POST /negotiate/{id}` with `cooperative` / `hard_line` |

Not walked (vocabulary taken from code): FAILED, EXPIRED, MISSED, FULFILLED, REVOKED, and the FUNDING family.

## 1. The vocabularies, read by read

### 1.1 The decision record (`GET /decisions`, `GET /decisions/{id}`)

- States: `DealState` and `FundingState`, `services/api/app/decisions/state.py:41-63`; the deal rule table `_deal_state` `:477-513` (first match wins, 13 rules, ADR-0011 §5 `docs/adr/0011-durable-decision-record.md:143-167`). Terminal set `_DEAL_TERMINAL` `:467-470` (REVOKED, FULFILLED, MISSED, EXPIRED, DECLINED, FAILED, NO_DEAL; MISSED is non-terminal while the commitment is still live `:452-454`).
- Who is awaited: `waiting_for` `:693-721` returns `WaitCode` × `Party` (`:66-82`): RECEIVED and RESPONSE_READY → OWNER_RESPONSE/owner; NEEDS_CLARIFICATION → BUYER_CLARIFICATION/buyer; AUTHORIZATION_REQUIRED → OWNER_APPROVAL/owner with the commitment's expiry day; AGREED → BANK_RECEIPT/buyer or INVOICE_ISSUE/books; MISSED → BANK_RECEIPT/buyer; SETTLEMENT_PENDING (and a DEAL in AGREED or NO_DEAL with unsettled lots) → FUNDING_SETTLEMENT/lender; PARTIALLY_EXECUTED or residual → OWNER_DECISION/owner; else NOTHING/none.
- Words: `_DEAL_STATE_WORDS` `services/api/app/api/presentation.py:1748-1760`; RESPONSE_READY takes `_RESPONSE_WORDS` by `business_action` (`:1761-1767`, `:1785-1797`, `:1327-1340`): accept → "Acceptable, awaiting agreement", counter → "Counter recommended", decline → "Decline recommended", needs_owner → "Needs your approval", cannot → "Cannot be decided yet". `_FUNDING_STATE_WORDS` `:1768-1776`.
- Tone: `decision_state_tone` `:1800-1812`: FAILED/MISSED → bad; owner awaited or residual → warn; FULFILLED/SETTLED → ok; DECLINED/NO_DEAL/EXPIRED/REVOKED → neutral; anything else (AGREED included) → info.
- Waiting sentence: `waiting_text` `:1815-1841`. Summary row: `decision_summary` `services/api/app/api/decisions.py:329-343` (reused by the Home's open decisions `home.py:1075-1096` and the approvals queue). List: `list_decisions` `:606-626`.
- Coverage: a decision is a candidate only if it has a run, an approval, a verdict, a commitment or a stored fact (`Context.candidate_ids` `decisions.py:160-171`). A submitted, unevaluated offer (RECEIVED) is therefore **absent from `GET /decisions`** (observed: `decisions: []` at RECEIVED) and is 404-safe only on `GET /decisions/{id}` (`:629-642` derives it on request).
- Tier on the record: `authorization.required_tier` is the executor's logged tier for the queued operation (`decisions.py:482-490`), null when no entry names the approval.

### 1.2 The Deals read (`GET /deals`, `GET /deals/{counterparty_id}`): `open_offer`, `needs_you`

`services/api/app/api/deal_offers.py`, composed onto `app.deals.deals()` rows by `with_offers` `:188-200` (route `services/api/app/api/deals.py:37-44`).

- Which decisions are "open": `OPEN = (RECEIVED, NEEDS_CLARIFICATION, RESPONSE_READY, AUTHORIZATION_REQUIRED)` `:25-26`. A terminal or AGREED deal has no `open_offer`.
- Stages: five keys `received, analysed, reply_ready, sent, agreed` with server labels en/zh `:23-24`; the current index per state `_NOW` `:25`: RECEIVED → `received`, NEEDS_CLARIFICATION → `analysed`, RESPONSE_READY → `reply_ready`, **AUTHORIZATION_REQUIRED → `sent`** (`:31-34`: earlier stages `done`, the index `now`, later `todo`). Submitted-but-unevaluated offers are found through the session documents (`_submitted` `:87-109`).
- `action_text` `:70-84`: RECEIVED "FLOW has not read it yet."; NEEDS_CLARIFICATION "The buyer needs to clarify first."; AUTHORIZATION_REQUIRED **or** `business_action == needs_owner` "Needs your approval." `:75-76`; accept "FLOW can accept it within your limits."; counter "{N} replies are ready to send."; decline "FLOW recommends declining."; else "FLOW cannot decide on this yet.".
- `headline_short` `:47-55` (NEEDS_CLARIFICATION → "Clarify before deciding", otherwise by `business_action`); `read_text` `:37-44`.
- `tone` `:164`: `warn` when the state is in `OWNER_WAITS = (RECEIVED, RESPONSE_READY, AUTHORIZATION_REQUIRED)` `:27`, else `info`.
- `needs_you` / `needs_you_text` `:168-185`, first match: offer state in `OWNER_WAITS` → "An offer is waiting for your reply"; a PROPOSED contract → "A document is waiting for your review"; a PENDING approval on this buyer's invoices → "An approval is waiting for you"; a late invoice → "An invoice is late and needs chasing".
- One offer per customer: `open_offers` `:112-121` keeps the greatest `updated_seq`; the comparison is strict `>` `:119`, so an equal sequence keeps the first found, and the iteration is `ctx.states()` then `_submitted` `:115`. `open_deals` `:124-132` lists every open offer (the worklist's source). The Customer overview (`customer_overview.py:818-824`) and the Home deals card (`home_hybrid.py:835`) also take `open_offers` (one per buyer).

The deal row's own five contract stages (`read, negotiated, early_payment, collecting, fulfilled`, states `done/skipped/pending/missed/now/todo`) are a different track, `services/api/app/deals/__init__.py:453-468`; its pills "Payment overdue" / "{n} approval(s) waiting" / "On track" `:559-583`; `has_contract` is a CONFIRMED buyer-contract document, not a commitment (`:120-125`, `:539`).

### 1.3 The web queue model (`apps/web/components/deals/queue/model.ts`) and the Deals page

- Tabs `needs | wait | agreed | setup` `:4-5`; labels (dictionary) "Needs your response" / "Awaiting the buyer" / "Agreed, in force" / "Customer setup" (`apps/web/lib/dictionary.ts:2279-2282`, zh `:4710-4713`).
- Filing `queueRows` `:21-33`: an open offer whose stage `sent` is `now` → `wait`, any other open offer → `needs` `:26-27`; `has_contract` → `agreed` `:29`; neither → `setup` `:30`. A customer whose only deal is terminal (DECLINED, NO_DEAL, FAILED, EXPIRED) or AGREED-without-a-confirmed-contract has no open offer and files under `setup`.
- Row words `queue.tsx:62-76`: tone by tab `STATUS_TONE = {needs: warn, wait: info, agreed: ok, setup: neutral}` `:20`; the status word is the record's `state_text` on the selected line, else on `needs` `needs_you_text ?? action_text`, on `wait` the `now` stage's label (`:64-66`), i.e. "Sent".
- Page subtitle `apps/web/app/deals/page.tsx:539`: "One decision is yours today…" when any `needs` row exists, else "Nothing needs your reply today…".
- Step line: an open offer renders the server's `StageTrack` (`apps/web/components/deals/workspace.tsx:78-80`); a deal with no open offer renders the browser's `DealStage` from `dealProgress(record.state)` (`workspace.tsx:81-82`, `apps/web/lib/decision.ts:41-61`, `apps/web/components/deals/deal-steps.tsx:18-29`). `dealProgress` is a second state→step table in the browser: RECEIVED done 1, NEEDS_CLARIFICATION done 1 stalled, RESPONSE_READY done 3, AUTHORIZATION_REQUIRED done 4 reached (so "Sent" done, the outcome chip current), AGREED/FULFILLED good, MISSED/FAILED bad, the rest closed. Its open-state branches are not reachable from the Deals page while the Deals read supplies stages; no unit test covers `dealProgress` or `queueRows`.
- Stage labels: `StageTrack` prefers the browser dictionary `te("dealstage", key)` over the server label (`stage-track.tsx:48`): `dictionary.ts:2218-2222` / `:4649-4653` for the offer track, `:1988-1992` / `:4419-4423` for the contract track; stage-state words "done / in progress / not yet / skipped / waiting / missed" `:2147-2152`. `DealStage` uses `steps.*` `:1677-1678, 1823-1827` ("Response ready"), not `dealstage.*` ("Reply ready").
- The inbox row's state word is looked up in `records.data.decisions` (`page.tsx:138-141`), so a RECEIVED offer (absent from `/decisions`, §1.1) has no word there.

### 1.4 The worklist (`GET /worklist`, `FEATURE_HOME_V2`)

`services/api/app/api/worklist.py`. `owner` is `NEEDS_YOU` or `WAITING` `:104`; severity `CRITICAL | CAUTION | NORMAL` `:105`; tiers `CASH_SAFETY=0, DEADLINE=1, MISSED_RECEIPT=2, MATERIAL=3, ORDINARY=4` `:106`, `tier_of` `:147-158` (breach day → 0; COLLECTION → 2; deadline → 1; non-NORMAL severity → 3; else 4), `rank`/`order` `:161-177`. The tier is not a field of the row: only `why_first_text` on the first row names it (`:180-185`, `:108-114`).

Needs you kinds and status words:

| kind | source | status_text (en) | severity | deadline_day |
| --- | --- | --- | --- | --- |
| DECISION | each open deal (`open_deals`) except NEEDS_CLARIFICATION (→ waiting) and AUTHORIZATION_REQUIRED (**skipped**, `:238-239`) | RECEIVED "Offer received · Your review needed"; recommended reply sendable "Counter ready · Reply needed"; recommended as-asked "Recommendation ready · Reply needed"; else "Read by FLOW · Reply needed" (`_deal_status` `:256-265`, from the offer picture's recommended path, not from `business_action`) | by the picture: CRITICAL if the recommended path breaches, CAUTION if as-asked breaches or needs the owner / over limit, else NORMAL (`_deal_effect` `:273-309`) | the recommended path's breach day |
| APPROVAL | every PENDING approval the Home words, less the company plan's legs (`_approval_rows` `:312-344`) | "Approval requested · Your approval needed" `:340` | CAUTION if the card states what it protects, else NORMAL | the agreement's `expires_day` for a commercial kind |
| COLLECTION | receivable rows OVERDUE / PROMISE_MISSED, one per buyer `:347-369` | "Payment overdue · Your follow-up needed" / "Promised payment missed · Your follow-up needed" `:365-366` | CRITICAL if missed or reserve unsafe, else CAUTION | the earliest due day |
| SETUP | a PROPOSED buyer contract `:372-384` | "Terms read · Your review needed" `:381` | NORMAL | none |

Waiting kinds: BUYER_REPLY (NEEDS_CLARIFICATION, "Waiting for the buyer's clarification · asked {when}", NORMAL, `:231-236`), SETTLEMENT (a lot `state_of` ARRANGED, `:397-410`), PROMISE (an AWAITED early payment, CAUTION, `:413-427`); ordered by severity then expected day `:430-431`. The company cash alert is counted nowhere `:437-461`.

### 1.5 Approvals (`GET /approvals/queue`, `POST /approvals/{id}`)

`services/api/app/api/operations.py:174-283`. Row `status` is `ApprovalStatus` PENDING | APPROVED | REJECTED (`services/api/app/persistence/records.py:42-45`); `tier` is the constant string `"TIER_2"` on every row `:227`; `decision_state` is the record's state `:138-141`; `presentation.execution_status` is PENDING | EXECUTED | REFUSED | DUPLICATE | DECLINED (`_execution_status` `:119-124`); `execution.summary_text` while pending "Waiting for your approval. Nothing has run." `:166`.

`result_state_text` / `result_tone` (`approval_result_state`, `presentation.py:1166-1189`): PENDING "Waiting for your approval"/warn; REJECTED or DECLINED "Declined, nothing ran"/neutral; REFUSED "Approved, did not run. No money moved."/bad; DUPLICATE "Approved, already done"/info; not yet EXECUTED "Approved, waiting to run"/info; EXECUTED commercial "Approved, agreement recorded"/ok; money kinds "Approved, cash arrives {when}"/info or "Approved, cash received"/ok; else "Approved, done"/ok. Decided headline `decided_headline` `:1146-1163`.

Web: `apps/web/app/approvals/page.tsx:70-71` splits the list by `status === "PENDING"` (waiting) vs the rest ("Already decided", `dictionary.ts:2184`); the card shows the server's `result_state_text`/`result_tone` and falls back to the dictionary badge `apprstatus.PENDING` "Needs your approval" / APPROVED "Approved" / REJECTED "Declined" (`approval-card.tsx:26, 233`; `dictionary.ts:656-659`); the tier sits under Audit details `:315`.

### 1.6 Two more reads that word the same states

- The Home deals card (`GET /home` → `deals_card`), `services/api/app/api/home_hybrid.py:845-849, 869-891`: `_STATUS` RECEIVED and RESPONSE_READY "Your response needed", AUTHORIZATION_REQUIRED "Needs your approval", NEEDS_CLARIFICATION "Awaiting the buyer", AGREED "Agreed"; order RECEIVED/RESPONSE_READY, then AUTHORIZATION_REQUIRED, then NEEDS_CLARIFICATION `:845`. One row per buyer (`open_offers`).
- The Customer overview (`GET /customers/{id}/overview` → `decision`), `services/api/app/api/customer_overview.py:549-591`: the buyer's one open offer (`_find_offer` `:818-824`, via `open_offers`); RECEIVED → kind `offer_received`, eyebrow "One offer waits to be read", link "Read the offer" `:558-565`; every other open state → eyebrow "One commercial decision waits for you", kind `counter` ("Review the counter", `/deals?decision=…&path=…`) when the picture recommends a reply, else kind `request` ("Review the request") `:566-591`; no open offer → "No commercial decision is waiting for you with {buyer}." `:551`.

## 2. The matrix: read × state → word, tier or tone, next actor

Observed cells are marked (obs.); the rest are read from the code cited in §1. "Next actor" is what the read itself says or implies.

### 2.1 DEAL states

| State | `/decisions` (word · tone · waiting party) | `/deals` open_offer (now stage · action_text · tone · needs_you_text) | Web queue (tab · row word · tab tone) | `/worklist` (kind · owner · status · severity · tier) | `/approvals/queue` | Home deals card | Customer overview |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RECEIVED | **not listed** (obs.) · (detail on request: "Received; not evaluated yet" · warn · owner) | `received` · "FLOW has not read it yet." · warn · "An offer is waiting for your reply" (obs.) | needs · "An offer is waiting for your reply" · warn | DECISION · NEEDS_YOU · "Offer received · Your review needed" · NORMAL · 4 ORDINARY (obs.) | no row | "Your response needed" (obs.) | "One offer waits to be read" → owner (obs.) |
| NEEDS_CLARIFICATION | "Needs clarification from the buyer" · info · **buyer** (obs.) | `analysed` · "The buyer needs to clarify first." · info · needs_you **false** (obs.) | **needs** (stage `sent` not now) · "The buyer needs to clarify first." · warn | BUYER_REPLY · **WAITING** · "Waiting for the buyer's clarification · asked today" · NORMAL · (waiting rows have no tier) (obs.) | no row | "Awaiting the buyer" (obs.) | **"One commercial decision waits for you"**, kind `request`, "Review the request" → owner (obs.) |
| RESPONSE_READY | by verdict: "Counter recommended" (obs.) / "Acceptable, awaiting agreement" / "Decline recommended" / "Needs your approval" / "Cannot be decided yet" · warn · owner | `reply_ready` · "Two replies are ready to send." (obs.; by `business_action`) · warn · "An offer is waiting for your reply" | needs · "An offer is waiting for your reply" (selected: "Counter recommended") · warn | DECISION · NEEDS_YOU · "Counter ready · Reply needed" (obs.; by the picture's recommended path) · CAUTION · 3 MATERIAL (obs.; 0 CASH_SAFETY when the recommended reply breaches) | no row | "Your response needed" (obs.) | "One commercial decision waits for you", kind `counter` (obs.) |
| AUTHORIZATION_REQUIRED | "Waiting for your approval" · warn · owner, "…the offer expires in 14 days." (obs.) | **`sent`** · "Needs your approval." · warn · **"An offer is waiting for your reply"** (obs.) | **wait** ("Awaiting the buyer") · **"Sent"** (selected: "Waiting for your approval") · **info**; page subtitle "Nothing needs your reply today…" | **no DECISION row**; APPROVAL · NEEDS_YOU · "Approval requested · Your approval needed" · NORMAL · 1 DEADLINE (day 14) (obs.) | PENDING · TIER_2 · decision_state AUTHORIZATION_REQUIRED · "Waiting for your approval" · warn · execution PENDING (obs.); web fallback badge "Needs your approval" | "Needs your approval" (obs.) | "One commercial decision waits for you", kind `counter`, **"Review the counter"** → `/deals?decision=…&path=…` (obs.) |
| AGREED | "Agreed" · **info** · books (INVOICE_ISSUE, obs. after approval) or buyer (BANK_RECEIPT, obs. after negotiate) | no open_offer; needs_you false (obs.) | agreed ("Agreed, in force") if a confirmed contract document exists, else **setup** · ok / neutral | no row (obs.); PROMISE waiting row when an early payment is awaited (obs.) | APPROVED · "Approved, agreement recorded" · ok · EXECUTED (obs.) | "Agreed" (obs.) | none: "No commercial decision is waiting…" (obs.) |
| DECLINED | "You declined it" · neutral · none; terminal (obs.) | no open_offer (obs.) | agreed or setup | no row (obs.) | REJECTED · "Declined, nothing ran" · neutral · DECLINED (obs.) | no row (obs.) | none (obs.) |
| NO_DEAL | "No deal: the buyer did not accept" · neutral · lender when the negotiation funded a gap (obs.); terminal | no open_offer (obs.) | agreed or setup | no row; SETTLEMENT waiting row for the arranged lot (obs.) | no row | no row (obs.) | none (obs.) |
| FAILED | "Could not run; nothing changed" · bad · none; terminal | no open_offer | agreed or setup | no row | APPROVED · "Approved, did not run. No money moved." · bad · REFUSED | no row | none |
| EXPIRED | "Expired before it was agreed" · neutral · none; terminal | no open_offer | agreed or setup | no row | — | no row | none |
| MISSED | "Early payment did not arrive" · bad · buyer (the invoice's due day) | no open_offer | agreed or setup | COLLECTION row (PROMISE_MISSED) · "Promised payment missed · Your follow-up needed" · CRITICAL · 2 MISSED_RECEIPT | — | no row | none |
| FULFILLED | "Fulfilled" · ok · none; terminal | no open_offer | agreed or setup | no row | — | no row | none |
| REVOKED | "Revoked" · neutral · none; terminal | no open_offer | agreed or setup | no row | — | no row | none |

### 2.2 Approval status × execution

| `status` | `execution_status` | queue `result_state_text` · tone | record `decision_state` (DEAL) | worklist | web Approvals |
| --- | --- | --- | --- | --- | --- |
| PENDING | PENDING | "Waiting for your approval" · warn | AUTHORIZATION_REQUIRED | APPROVAL row, NEEDS_YOU, tier 1 when the agreement has an expiry (else 3/4 by severity) | waiting list; fallback badge "Needs your approval" |
| APPROVED | EXECUTED | commercial "Approved, agreement recorded" · ok; money "Approved, cash arrives {when}" · info / "Approved, cash received" · ok | AGREED | none | "Already decided" |
| APPROVED | REFUSED | "Approved, did not run. No money moved." · bad | FAILED | none | "Already decided" |
| APPROVED | DUPLICATE | "Approved, already done" · info | — | none | "Already decided" |
| APPROVED | PENDING (no run logged) | "Approved, waiting to run" · info | — | none | "Already decided" |
| REJECTED | DECLINED | "Declined, nothing ran" · neutral | DECLINED | none | "Already decided" |

### 2.3 FUNDING states (code only)

`_FUNDING_STATE_WORDS` `presentation.py:1768-1776`: AUTHORIZATION_REQUIRED "Waiting for your approval", DECLINED "You declined it", FAILED "Could not run. No money moved", PARTIALLY_EXECUTED "Partly done", SETTLEMENT_PENDING "Requested; the cash is on its way", SETTLED "Done; the cash has landed", EXECUTED "Done"; SETTLED/EXECUTED with a residual "Funded, reserve still short" `:1795-1796`. The worklist shows a pending funding approval as an APPROVAL row unless it is a leg of the company plan while the alert is up (then it is the alert's, `worklist.py:320-322, 437-461`), and an ARRANGED lot as a SETTLEMENT waiting row; the Deals read and the queue model carry no funding state.

## 3. Contradictions, with file lines

1. **AUTHORIZATION_REQUIRED is "sent / awaiting the buyer" on Deals and "waiting for your approval" everywhere else** (UX02). `_NOW` maps it to the `sent` stage (`deal_offers.py:25`) while `action_text` says "Needs your approval." (`:75-76`); the web files a `sent`-now offer under "Awaiting the buyer" with the row word "Sent" and tone info (`model.ts:26-27`, `queue.tsx:20, 64-66`, `dictionary.ts:2280`) and the page says "Nothing needs your reply today" (`page.tsx:539`); the record says OWNER_APPROVAL/owner (`state.py:703-706`, `presentation.py:1751`), the worklist files the approval under Needs you (`worklist.py:238-239, 312-344, 523`), the queue says PENDING "Waiting for your approval" (`presentation.py:1170-1171`), the Home deals card "Needs your approval" (`home_hybrid.py:847`). No test pins the Deals stage or action text in this state (§4).
2. **Deals `needs_you_text` calls the approval "an offer waiting for your reply".** `OWNER_WAITS` includes AUTHORIZATION_REQUIRED (`deal_offers.py:27, 173-174`), so the row says "An offer is waiting for your reply" (observed) while the only action is the approval; the Home web renders that text as a warn pill beside a track whose "Sent" step is "in progress" (`apps/web/components/home/deals.tsx:55-63`). The approval phrase "An approval is waiting for you" (`:177-182`) is reached only for approvals on the buyer's invoices and only after the offer check.
3. **Deals' open-offer tone (warn) vs the queue's wait tab tone (info)** for the same AUTHORIZATION_REQUIRED row: `deal_offers.py:164` vs `queue.tsx:20`; the record says warn (`presentation.py:1806-1807`).
4. **NEEDS_CLARIFICATION: the Customer overview says the owner has a decision; every other read says the buyer is awaited.** `customer_overview.py:549-591` words any open offer except RECEIVED as "One commercial decision waits for you" with "Review the request" (observed kind `request`); the record says BUYER_CLARIFICATION/buyer (`state.py:700-702`), the worklist files it under WAITING as BUYER_REPLY (`worklist.py:231-236`), the Deals read sets `needs_you` false and tone info (`deal_offers.py:27, 164, 173`), the Home deals card says "Awaiting the buyer" (`home_hybrid.py:848`).
5. **NEEDS_CLARIFICATION lands in the queue's "Needs your response" tab.** `queueRows` sends every open offer whose `sent` stage is not `now` to `needs` (`model.ts:26-27`); the server's current stage is `analysed` (`deal_offers.py:25`) and the row word is "The buyer needs to clarify first." under a tab named "Needs your response" with tone warn.
6. **AUTHORIZATION_REQUIRED on the Customer overview links to the counter, not the approval.** `customer_overview.py:566-575, 585` builds "Review the counter" → `/deals?decision=…&path=…` from the picture's recommended path whenever one exists; the record's waiting is the approval and the worklist's href is `/approvals#approval-{id}` (`worklist.py:342`).
7. **RECEIVED exists for Deals, the worklist, the Home card and the Customer overview but not for `GET /decisions`.** `candidate_ids` needs a verdict, commitment, run, approval or fact (`decisions.py:160-171`); the Deals read derives submitted offers from the session documents (`deal_offers.py:87-109`). The web inbox row therefore has no state word for a RECEIVED offer (`page.tsx:138-141`), and the Home's "open decisions" (`home.py:1075-1096`) do not count it.
8. **One row per customer on Deals, one per decision on the worklist; ties keep the earlier offer** (UX04). `open_offers` keeps the greatest `updated_seq` with a strict `>` (`deal_offers.py:112-121`, `:119`), iterating recorded decisions before submitted ones (`:115`); `open_deals` lists all (`:124-132`) and the worklist counts "2 open negotiations · 2 need you" (`tests/api/test_worklist.py:171-178`). The Customer overview (`customer_overview.py:818-824`) and the Home deals card (`home_hybrid.py:835`) take the one offer, so a buyer with two open offers has one decision on Customer (UX12) and two on the worklist.
9. **Two rules word RESPONSE_READY.** The record and the Deals read word it by the verdict's `business_action` (`presentation.py:1327-1340, 1785-1788`; `deal_offers.py:70-84, 142`); the worklist words it by the offer picture's recommended path (`kind`, `sendable`; `worklist.py:256-265`) and its severity by the picture's breach days (`:273-309`). Observed together: "Counter recommended" / "Two replies are ready to send." / "Counter ready · Reply needed" / "Your response needed" for one state.
10. **AGREED is "info" on the record, "ok" on the queue's agreed tab and on the approval row.** `presentation.py:1800-1812` (only FULFILLED/SETTLED → ok) vs `queue.tsx:20` and `presentation.py:1180-1181`.
11. **The agreed tab is keyed on a confirmed contract document, not on the commitment.** `model.ts:29-30` reads `has_contract` (`deals/__init__.py:120-125, 539`): an AGREED or terminal deal for a buyer without a confirmed contract files under "Customer setup".
12. **Approvals tier.** `GET /approvals/queue` stamps every row `tier: "TIER_2"` as a constant (`operations.py:227`); the record's `authorization.required_tier` is the logged tier (`decisions.py:482-490`); the web shows the queue's constant under Audit details (`approval-card.tsx:315`).
13. **Two words for a pending approval on the web.** The server's `result_state_text` "Waiting for your approval" (`presentation.py:1170-1171`) and the dictionary fallback `apprstatus.PENDING` "Needs your approval" (`dictionary.ts:656`, used at `approval-card.tsx:233` when the server sends no state text); the Deals read says "Needs your approval." (`deal_offers.py:76`), the worklist "Approval requested · Your approval needed" (`worklist.py:340`), the queue's execution line "Waiting for your approval. Nothing has run." (`operations.py:166`).
14. **Two browser step tables and two label sets for the offer track.** `dealProgress` (`decision.ts:41-61`) puts NEEDS_CLARIFICATION on `received` and AUTHORIZATION_REQUIRED past `sent`; the server puts them on `analysed` and `sent` (`deal_offers.py:25`). `DealStage` labels the third step "Response ready" (`dictionary.ts:1823`), `StageTrack` and the server "Reply ready" (`dictionary.ts:2220`, `deal_offers.py:23`). `StageTrack` prefers the browser dictionary to the server label (`stage-track.tsx:48`): zh "回复已备好" vs the server's "回复已就绪" (`deal_offers.py:23`), and for the contract track "条款已谈妥 / 回款中 / 已履行" vs the server's "条款已谈判 / 催收中 / 已履行完毕" (`dictionary.ts:4420-4423` vs `deals/__init__.py:456-467`). The `dealProgress` open-state branches are not rendered on dev's Deals page (`workspace.tsx:78-83`).
15. **The worklist's tier is not readable from the row.** `_needs_item` (`worklist.py:180-185`) emits severity and `deadline_day` but not the tier; a DECISION's `deadline_day` is its breach day (`:250-252`) while an APPROVAL's is the agreement's expiry (`:341`), the same field meaning two things.

## 4. Which tests pin which mapping

| Mapping | Pinned by |
| --- | --- |
| Deals stages RECEIVED → `received` now; `needs_you_text` "An offer is waiting for your reply" | `services/api/tests/deals/test_open_offer.py:43-50` |
| Deals stages RESPONSE_READY → `reply_ready` now; `action_text`, `headline_short`, tone warn; record state RESPONSE_READY | `test_open_offer.py:53-68` |
| After a counter is sent (AGREED, NO_DEAL) no open offer | `test_open_offer.py:95-98` |
| `_headline_short` per outcome incl. NEEDS_CLARIFICATION "Clarify before deciding" | `test_open_offer.py:79-92` (unit) |
| Deals `needs_you_text` for a late invoice and a document | `test_open_offer.py:114-124` |
| Deals stages / `action_text` / `needs_you` at **AUTHORIZATION_REQUIRED** | **none** ("Needs your approval." appears in no test) |
| Deals stages / tone at **NEEDS_CLARIFICATION** | **none** on the read |
| Contract-track stages | `services/api/tests/api/test_deals.py:77, 90-92`, `tests/deals/test_lang.py:85`, `tests/api/test_demo_documents.py:42` |
| Web `queueRows`, `dealProgress`, `DealStage` for open states | **none** (no unit test); e2e `apps/web/e2e/deals-queue.spec.ts:41-58` pins counts `["1","0","1","1"]`, the needs row's chip "Counter recommended" and the empty wait tab on the recorded mock; `apps/web/e2e/record.spec.ts:40-61` pins the RECEIVED → RESPONSE_READY → AGREED chip and `DealStage` done steps for AGREED |
| Record words: RESPONSE_READY "Counter recommended" / "Acceptable, awaiting agreement" (zh), AGREED "Agreed" non-terminal, NO_DEAL, MISSED, AUTHORIZATION_REQUIRED zh "等待您批准" | `services/api/tests/api/test_decisions_flow.py:40, 56, 59, 69, 89, 101, 130` |
| Record FAILED after a refused approval, `decision_state` on the queue row | `tests/api/test_w2_review.py:199, 208`; `tests/api/test_approval_refused_terminal.py:18, 23` |
| Activity's `current_decision_state` equals the record's `state_text` | `tests/api/test_activity_causality.py:75-101` |
| Worklist DECISION row "Counter ready · Reply needed" | `tests/api/test_worklist.py:117-125` |
| Worklist APPROVAL row for a queued agreement: words, deadline 14, href, **no DECISION row**, tier DEADLINE first; zh | `test_worklist.py:426-443` |
| Worklist BUYER_REPLY under WAITING for EX07_CONFLICT; zh | `test_worklist.py:479-488` |
| Worklist order and `tier_of` | `test_worklist.py:304-367` |
| Worklist COLLECTION, PROMISE, SETUP rows; the plan's approvals are the alert's | `test_worklist.py:193-215, 218-237, 445-476` |
| Home deals card "Your response needed" | `tests/api/test_home_hybrid.py:563-573` ("Needs your approval" / "Awaiting the buyer" rows: **unpinned**) |
| Customer overview RECEIVED "One offer waits to be read"; RESPONSE_READY "One commercial decision waits for you" | `tests/api/test_customer_overview.py:585-592, 134` (NEEDS_CLARIFICATION and AUTHORIZATION_REQUIRED: **unpinned**) |
| Approvals `result_state_text`/tone per status × execution | `tests/api/test_w7_addendum.py:118-149` |
| Queue row PENDING_APPROVAL after RECORD_COMMITMENT | `tests/api/test_time_semantics.py:415-417` |

## 5. Notes

- `FLOW-dev-audit.md` is not in the repository at dev `8b3d6761`; UX02, UX04 and UX12 are quoted from the ticket.
- The Home V2 worklist page is not on dev (no web file reads `owner`/`kind` of `/worklist`); its server read is.
- Nothing in the app was changed; the probe script lived in the session scratchpad.
