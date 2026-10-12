# Session handoff 10 (12 Oct 2026, evening): Home hybrid shipped, #107 shipped, the three connected pages in build

Read docs/handover/08_session_handoff_2026-10-12.md first for the delegation protocol, the gate commands and the environment
quirks (zsh `=` expansion, no `timeout` on macOS, never port 3000, never a bare `git stash`, SKIP_PERF_BENCH on Windows).
New quirk today: agents must never run `pkill -f "playwright test"` or any unscoped pkill; kill only by their own ports or
PIDs (an unscoped kill ended the lead's gate runs three times).

## dev at 747fad6b (pushed)
- 59e9deb0 feat/exposure-api: map #88 Phase 1 server behind FEATURE_EXPOSURE (capacity, concentration, payment behaviour,
  the 30-day stress, customer inputs + routes); review's ten fixes in; design note docs/design/exposure-surface-2026-10-12.md.
- 3c310366 feat/net-collection (#107, closed): the stress moves a financed invoice through the engine's own repayment on the
  late day (lot and drawn balance kept until then); `net_at_collection`; new `GET /receivables?lang=` with governed_by /
  early_payment / pending_counter / collection_state / collection_action; one financing vocabulary (`state_of`: ARRANGED /
  RECEIVED / REPAID); zh engine words no longer say 预支 for an unlanded lot. Full suite 7233 passed.
- 747fad6b int/home-hybrid: the Home hybrid (owner's Home E). Server fields additive on GET /home (`cash.status_word`,
  `headline_conditional`, `facts`, `attention`, `funding_line`, `events_rail`, `counterfactual_series`, `stress` behind the
  exposure flag, `deals_card`, `receivables_card`, `changes_card`); web components/home/*; the attention card carries the
  run-the-plan control (`usePlanRun`); mocks re-recorded; both halves code- and design-reviewed. Gate API 872, mock 263, live 40.

## Owner decisions (12 Oct, on #89)
"Take your recommendations" on the lead's fifteen-item list: #107–#110 build now in order; the Phase 1 web half ships inside
the Deals queue; sales projected from the books with override; gross margin, 20% Demo, one firm-wide figure; classification
context only; recourse (shortfall owed by the owner); late receipt on a financed invoice keeps the financing running with
per-period charges from the facility record; an early-payment agreement lapses when paid late; due soon = 7 days, chase from
the day after due; the 15-day stress row waits for Phase 3; all five kill criteria hold; three packages on the card in Phase 4;
the closed-loop demo path (deal → customer → stress → back with the counter kept) beside the stepper until the pages exist.
Design direction: docs/design/mockups-connected-2026-10-12/README.md.

## In flight (branches, not merged)
- #108 Customer overview: read on feat/customer-overview-api (75c19029 + review fixes pending: the accept-branch authority
  text, the cache key on documents/offers, the share above 100% and the 12-month cost basis, sales projected from the books
  when no input exists, the unread-offer decision, no bank ids in history, link labels, edit_href null until Phase 2);
  page on feat/customer-overview-web 04177e7c (green; re-check and re-record after the read's fix).
- #109 Deals queue: feat/deals-queue 19fbe696 (+ a follow-up pending: no client build flag, phone primary in the first
  viewport, legacy deals specs remapped); its server words specced in docs/design/connected-views-2026-10-12/05 and not
  started (branch from feat/customer-overview-api after its fix).
- #110 Receivables: feat/receivables-layers in progress (from feat/net-collection, now in dev).
- Then: code + design review of each page, one integration branch from dev (Home + #107 in), mocks re-recorded with
  FEATURE_EXPOSURE=1, full gate (mock + live), merge, screenshots, the closed-loop demo path, memory + this doc updated.

## Still open elsewhere
#103 reskin debt, #106 pages-a2 flake, #104 money chart (owner's call), #66 / #59 owner items, map #88 Phases 2–5
(#97, #100, #98, #101, #102).
