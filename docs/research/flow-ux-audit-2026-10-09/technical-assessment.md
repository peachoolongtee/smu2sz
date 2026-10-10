# FLOW Assessment B — technical evidence, 9 October 2026

STATUS: Complete independent technical assessment; no UI implementation changes. Findings were held until the Assessment A completion gate. Target: apps/web plus relevant backend failure tests. No prior UX audit or Assessment A findings were used to form this assessment.

FILES CHANGED: /tmp/flow-assessment-b.md; raw detector output /tmp/flow-detect-b.json; temporary existing-test wrapper /tmp/flow-responsive-b.config.ts; test artifacts /tmp/flow-pw-live-b and /tmp/flow-pw-responsive-b. Next builds generate .next-e2e-* and may format tsconfig.json. The observed .next-ux-audit includes and globals.css correction belong to the parent's concurrent setup, not this agent. No deliberate source edits, no existing server reset.

## Evidence boundaries

- CUA inventory exposed no browser surfaces. A Chrome fresh-tab request failed; parent owned native Safari. No DOM injection API was available and no on-screen audit overlay was injected. Concrete fallback: exact source locations, compiled CSS, existing Playwright tests using isolated disposable servers, and a written evidence report. Do not claim a browser overlay or independent visual review from Assessment B.
- Live tests used web :3002 / API :8012, in-memory database, LLM_MODE=cache, TERMSLEDGER_NO_DOTENV=1. They never reset localhost:3000 or its API. The responsive wrapper changes only test configuration in /tmp; no app files.
- An original live build succeeded but emitted malformed touch-selector warnings. Later phone tests ran after the parent's temporary globals.css correction. This means the five phone passes certify that patched runtime, not the original malformed variant. Assessment B independently verified the original source syntax and warning; it did not independently establish the parent's original HTTP500 observation.
- No WCAG conformance certification, screen-reader session, 200%/400% zoom assessment, tablet Safari, performance profile, complete contrast sweep or live-model timeout session was performed.

## Detector

Command: /Users/ianpong/.agents/skills/impeccable/scripts/impeccable detect --json apps/web
Result: exit 0; JSON [] (0 findings). Rule names: none. Locations: none. False positives: none returned. This is a detector result only, not proof that the app is accessible or free of technical defects. The manual CSS and failure-state findings below were not reported by this scan.

## Findings

### B1 [P1] Refused owner approvals leave an obsolete pending decision card

Category: failure recovery / implementation integrity. Evidence: services/api/app/operations/executor.py:371 persists the owner's decision before the operation is revalidated at :396; tests/operations/test_approvals_and_circuit.py:52 and :63 confirm revocation and commitment expiry can refuse the rerun. apps/web/lib/live/approvals.ts:67 throws ApiError(403) for an APPROVE whose result is REFUSED before getApprovals() at :70. apps/web/app/approvals/page.tsx:31 only refreshes the queue for 404 / 409; the 403 branch at :37 stores a string error, and :40 re-enables the original controls. ApprovalCard at components/approval-card.tsx:162 displays Approve/Decline whenever the old row remains PENDING.

Impact: after a legitimate owner's approval is refused because books or authority changed, the page can still show it as pending and invite another decision even though the backend recorded it as decided. The next click yields already-decided 409 rather than a coherent terminal result. Backend remains fail-closed; this is user-visible state disagreement, not evidence of unsafe execution.

Recommendation: reload the queue after any completed server decision, retain its refusal/result on the card, and separate successful authorization from failed execution. Preserve the executor's explanation and remove decision controls when the queue is no longer pending. Suggested command: $impeccable harden. Confidence: high source evidence and executed backend tests; this exact browser refusal-after-valid-owner scenario was not exercised.

### B2 [P2] Reduced-motion users lose all visual button busy indicators

Category: accessibility / feedback. Original apps/web/app/globals.css:486 hides .spinner in reduce mode, :489 enables .spinner-dots, then the equal-specificity later .spinner-dots rule at :494 sets display:none again. With the temporary four-line touch fix present, these locations are :490, :493, :498 respectively. components/icons.tsx:68 and :71 supply the spinner and ellipsis; components/ui.tsx:279 marks loading buttons aria-busy.

Compiled original live CSS independently confirmed: `.spinner{display:none}.spinner-dots{order:1;display:inline}}.spinner-dots{display:none}`. Under reduce both indicators disappear. aria-busy remains useful for assistive technology; a sighted reduced-motion user sees a disabled action with unchanged text and no intended waiting indicator. All existing Playwright projects set reducedMotion:'reduce' at playwright.config.ts:42 but do not assert visible busy feedback.

Recommendation: place the base hidden rule before the reduced-motion override or explicitly make the reduced rule win. Preserve a stationary ellipsis or a loading label. Suggested command: $impeccable animate. Confidence: high source + compiled cascade; computed DOM state was not separately probed.

### B3 [P2] Original touch variant drops the large-screen coarse-pointer branch

Category: responsive / implementation integrity. Original globals.css:5 uses `@custom-variant touch (@media (max-width: 63.999rem), (pointer: coarse));`. Original live Next build emitted three `Invalid dangling combinator in selector` warnings for `.touch\\:size-11 (pointer: coarse)`, `.touch\\:h-11 (pointer: coarse)`, `.touch\\:min-h-11 (pointer: coarse)`. The compiled original CSS retained valid touch rules under `(max-width:63.999rem)` but dropped the malformed coarse-pointer selectors. The parent subsequently replaced this with a block @media containing @slot.

Impact: a phone under 1024px can still get touch sizing from the valid narrow branch; this is not evidence that all phone targets fail. A touch laptop/tablet at >=1024px can keep 32/40px buttons or 40px close controls despite the intended 44px policy. .hit's separate correctly-written coarse-pointer media rule at original :335 still works, so not every compact target is affected. Small targets are a usability/design-policy concern; <44px alone is not automatically a WCAG 2.2 AA failure (AA minimum is not the same as the 44px design floor).

Recommendation: ship the corrected explicit media block and verify both narrow and wide coarse-pointer modes. Suggested command: $impeccable adapt. Confidence: high original build/source evidence; exact wide coarse-pointer hit boxes untested. Parent's patched phone checks do not settle this original branch.

### B4 [P2] Slow or hung model requests have no bounded client recovery

Category: error handling / performance. lib/live/http.ts:67 calls fetch without AbortSignal or client timeout. lib/chat.ts:79 keeps the conversation busy until response/rejection; :114 prevents a second send in that role while busy. The composer at components/chat/chat-view.tsx:84 disables Send while busy. There is no timed waiting message, request cancel or timeout-specific recovery in these paths. Server adapters may take multiple timed attempts: compiler/backends.py:59 uses 60s; :72 configures two SDK retries, compiler/service.py:38 chains both providers then rules. Classifier clients at nl/classifier.py:141 and :157 use 30s and a retry.

Impact: an unusually slow connection can leave the action blocked with little explanation; a model failure can return only an out-of-scope interpretation when every classifier fails (nl/service.py:181–188) rather than distinguishing temporary service failure from unsupported user intent. Do not imply that financial execution proceeds unsafely: the tested classifier proposes only and compiler output is grounded.

Recommendation: show a bounded slow-request status, let the user recover while preserving the exact request id, distinguish model unavailability from unsupported intent, and ensure cancel/retry cannot duplicate an operation. Suggested command: $impeccable harden. Confidence: high source; no real-time live-model failure UX test. Existing transport retry/error checks pass, but they abort promptly and do not cover a hanging request.

## Failure-state coverage

| Case | Evidence / behavior | Execution status |
|---|---|---|
| Stale alert / books | components/home/fix-alert.tsx:41 detects ALERT_CHANGED; :48 refetches; e2e/live.spec.ts:208 asserts current warning, Nothing was run, no success box, no queued cure | Passed live |
| Unknown or already-decided approval | app/approvals/page.tsx:32 plain 404/409 copy + reload; e2e/contract.spec.ts:109 tests second decision 409 / unknown 404 | Passed adapter + backend; page exact branch not separately exercised |
| Approval no longer admissible | Revalidation tests for revoked mandate and expired commitment; B1 frontend refresh gap | Backend passed; exact UI scenario untested |
| API offline | e2e/chat.spec.ts:246 aborts first /nl request, asserts Cannot reach API, retries same conversation successfully | Passed live |
| Missing server credentials | Same test injects 503 OWNER_TOKEN_NOT_CONFIGURED; error explains configuration | Passed live |
| Concurrent-write API error | e2e/live.spec.ts:270 retries once; :284 second conflict returns books-busy error; retry.test.mjs proves other 409 codes are not retried | Passed live + unit |
| Model timeout | compiler/test_backends.py:142 mocks ConnectionError then TimeoutError then success; fallback tests at :107, :133; classifier backend error at test_classifier.py:85 falls through | Backend passed; no visible timeout-specific UI test |
| Duplicate execution | tests/api/test_operations.py:46 asserts DUPLICATE and valid evidence; operations/test_idempotency_and_log.py checks no double effect. UI operation-result.tsx:9 names Duplicate in neutral tone and glyph | Backend passed; duplicate UI source checked, no browser duplicate test |
| Permissions | chat 401 opens sign-in and resends once; wrong token remains rejected; buyer turns carry no owner token; e2e/live.spec.ts:230 wrong-owner approval refuses | Passed live |
| Expired mandate | components/home/fix-alert.tsx:19 information-only mapping; e2e/catchup.spec.ts:64 asserts warning / critical / offline renewal / no button. test_mandate_gate.py:76 and test_signing.py:103 test expiry boundaries | Backend passed; mock UI test could not run |
| Unavailable facility | components/business/funding-options.tsx:103 neutral Not possible badge, :115 reason in disclosure; test_truth_fields.py:92,:204 unavailable vs insufficient semantics | Backend + unit passed; specific unavailable row browser state untested |

## Positive practices verified

- Native <dialog> for owner auth and chat; chat focus returns to trigger on Escape. e2e/chat.spec.ts:201 passed live. Account sheet escape/focus/outside dismissal passed at a phone viewport.
- Business five-tab navigation, accessible names and aria-current, Ask FLOW reachability, language/title semantics are checked by responsive.spec.ts:57. Phone execution passed.
- Shared buttons use native buttons, disabled and aria-busy; ErrorState uses role=alert and loading uses role=status (components/ui.tsx:279,:312,:337). Source verified.
- Skip link to focusable main, semantic sections/headings, labeled owner-token input, native radio groups and a forecast table with column scope are present (app-shell.tsx:102,:348; owner-auth.tsx:61; ui.tsx:400; business/cash-forecast.tsx:346). Source verified; not a screen-reader certification.
- Status words and glyphs accompany colors. Executed / waiting / refused / duplicate have separate treatments; no success styling on stale alerts. Source + passing live stale-alert test.
- Token colors and focus rings are centralized. color.spec.ts has targeted computed contrast checks for hero, caption, pill and breach figure, but it was not executed in this pass because mock build failed. No claim of full AA contrast.
- Native responsive geometry at 412×915 passed for navigation, reload titles, account focus, selected phone touch targets and chat long-reply bounding box in the temporarily patched runtime.

## Scores (provisional technical-only; original code + explicitly scoped patched checks)

Accessibility 3/4; performance 2/4; responsive 3/4; theming 3/4; implementation integrity 2/4. Total 13/20, acceptable with significant work needed. Scores are implementation judgments, not WCAG certification or production performance measurement. The original startup blocker independently observed by Assessment A should take precedence over this conditional health score.

P0 confirmed independently by B: 0. P1: 1. P2: 3. P3: 0. Integrity verdict: coherent product-specific semantic system, but refusal-state refresh and CSS feedback defects prevent a clean technical pass.

## Test commands and results

1. `pnpm test:unit` from apps/web: 30 passed, exit 0.
2. `UV_CACHE_DIR=/tmp/flow-uv-cache UV_NO_SYNC=1 uv run pytest -o addopts= -q -p no:cacheprovider tests/compiler/test_backends.py tests/nl/test_classifier.py tests/api/test_operations.py tests/api/test_decide.py tests/api/test_write_conflict_409.py tests/api/test_truth_fields.py` from services/api: 75 passed in 6.48s.
3. Same uv prefix with `tests/operations/test_approvals_and_circuit.py tests/operations/test_mandate_gate.py tests/operations/test_idempotency_and_log.py tests/mandate/test_signing.py`: 63 passed in 1.38s.
4. `UV_CACHE_DIR=/tmp/flow-uv-cache UV_NO_SYNC=1 E2E_TARGET=live E2E_LIVE_PORT=3002 E2E_API_PORT=8012 pnpm exec playwright test e2e/chat.spec.ts e2e/live.spec.ts e2e/contract.spec.ts`: 27 passed / 1 infrastructure artifact failure. The failed landing-day test reported ENOENT while browserContext closed because another runner removed shared test-results trace files; it reported no assertion failure.
5. Follow-up same env, `pnpm exec playwright test e2e/live.spec.ts -g 'plan card shows the landing day' --output=/tmp/flow-pw-live-b`: 1 passed. Combined unique live checks: 28 passed; do not conceal original artifact failure.
6. Same isolated live env, `pnpm exec playwright test --config=/tmp/flow-responsive-b.config.ts -g 'Business navigation|controls reach 44|slide-over chat fits|account sheet closes|hard load names'`: 5 passed at 412×915 in 14.8s. Temporary config imports repo config, uses live project name so demo-owner-token is correct, changes viewport and output only. Runtime had parent's temporary touch correction.
7. `E2E_TARGET=mock E2E_PORT=3102 pnpm exec playwright test e2e/responsive.spec.ts e2e/colour.spec.ts e2e/catchup.spec.ts e2e/approvals.spec.ts`: failed before any test executed, Turbopack CSS processing attempted a local port and received Operation not permitted. Two escalated follow-ups failed with same build restriction; stopped retrying. No failed UX assertions from these runs.
8. Initial backend batch included nonexistent tests/mandate/test_signed.py: no tests ran. Corrected subsequent batches above passed.

REGRESSIONS: No code changes by B. Original touch-selector warnings independently present. Parent temporarily patched source during assessment. Incomplete checks are explicitly listed; browser trace artifact race was isolated and the affected test passed.

INTERFACE CHANGE REQUESTS: None for financial engine or API contract. B1 can refresh and render existing queue/result fields. B4 client recovery must preserve existing request-id/idempotency contract.

ASSUMPTIONS: Read-only assessment includes disposable existing E2E tests that mutate only their own in-memory API. Live tests are cached-model tests, not external-model certification. Existing user servers and financial engine source remain untouched.

Recommended order: $impeccable harden for B1 and B4, $impeccable adapt for B3, $impeccable animate for B2, then $impeccable polish after functional verification. Re-run the technical audit after fixes; preserve the independent unpatched startup evidence in the parent report.
