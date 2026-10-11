# Pre-merge fixes, web side: the contract-ingestion branch (int/contracts → dev)

Worktree: /Users/ianpong/Hackathons/smu2sz/.claude/worktrees/contracts-web, branch `fix/contracts-web` (from `int/contracts`); `pnpm install` is done. Commit on this branch only, plain one-line messages, no merge; before every commit run `rm -f apps/web/AGENTS.md apps/web/CLAUDE.md; git checkout -- apps/web/tsconfig.json`. Never start anything on port 3000. The lead merges.

Rules: the browser computes no money and no date words (INVARIANT 13): every amount and every "when" is a server display string; Business mode shows no codes, day numbers, env names, ids, hashes or raw enums (they live behind the Technical fold, `Disclosure` with `biz.auditDetails`, as Activity does); every Business string has en and zh in `apps/web/lib/dictionary.ts`; DESIGN.md (apps/web/DESIGN.md) binds tokens, type floor 12 px, radius scale (pill, 16, 12), `Button` / `ButtonLink` with 44 px targets and `motion-press`, `textLinkClass` for links, `Badge` / `Chip` / `StatePill` for pills; reduced motion respected. Gate before you finish: `pnpm typecheck`, `pnpm lint`, `pnpm test:unit`, and `E2E_TARGET=mock pnpm exec playwright test` (the mocks under apps/web/mocks are re-recorded, never hand-edited: if the API's new `lang` fields change a response shape, record them with `node apps/web/scripts/record-mocks.mjs --api http://localhost:<port>` against the API from the sibling worktree /Users/ianpong/Hackathons/smu2sz/.claude/worktrees/contracts-api once its Task 6 is merged; the lead will tell you; until then type the new fields as optional and keep the mocks).

A parallel API implementer is adding `lang` to `GET /deals`, `GET /documents`, `GET /documents/{id}` and turning the server's sentences into words with zh twins, with relative-day "when" strings instead of day numbers, and separate id / seq fields for the Technical fold. Your side consumes that.

## Blocker 1: Business mode shows day numbers, codes, env names and raw enums
- Day numbers: `components/deals/deal-summary.tsx:174, 221, 224, 243`; `components/document-review.tsx:113`; `app/documents/page.tsx:113`; dictionary keys `docs.confirmedDay`, `docs.rejectedDay`, `deal.issued`, `deal.nextInvoice`. Fix: render the server's `*_when` strings (or the existing `whenText` helper that takes a server string) and never "day N".
- Codes and jargon: DOC ids (`document-review.tsx:113`, `documents/page.tsx:109`), "ledger entry #seq" (`docs.decided`), "hash-chained ledger" (`docs.decide.hint`). Fix: Business words ("Confirmed by you on …", "Recorded in your activity"); ids, seq and the compiler name go behind the Technical fold.
- Env names: "FEATURE_CONTRACTS" (`home.deals.off`), `NEXT_PUBLIC_API_MODE=live` (`docs.mockUpload`, `page.tsx:302`). Fix: owner words ("Document reading is switched off for this workspace."; "Uploading needs the live server; the Demo reads its three sample documents.").
- Raw enums: `reading_status` ("COMPILED" / "ABSTAINED", `document-review.tsx:120`) and flag `f.kind` (`:37`). Fix: map through the dictionary (`te()`), en and zh.

## Blocker 2: the three reads are not zh-aware
`lib/api.ts:312-324`: `getDeals()`, `getDocuments()`, `getDocument()` take no `lang`; `app/deals/page.tsx:62` has no `[lang]` dependency. Fix: pass `lang` like `getLedger(lang)` in both the live and the mock clients (`lib/live/*`, `lib/mock/handlers.ts`), re-fetch on language change, and stop `getDeals().catch(() => null)` from hiding a failed load (show the page's standard error state).

## Blocker 3: the confirm and reject controls are an irreversible, hash-bound action
`components/document-review.tsx:243-261`:
- Wording: "Confirm this reading" / "Reject this reading" (zh twins), with one line above the controls: "This cannot be undone. Confirming records the terms as read; rejecting records nothing from this document." (zh).
- Double submit: both buttons disabled while `busy`.
- Disabled confirm: the reason beside the button, bound with `aria-describedby`, not only at the top of the card.
- The facility-link checkbox defaults OFF and shows the facility's name (server string), not its id; 44 px target.
- Errors: never `e.message` raw; a hash mismatch (`TERMS_CHANGED` / 409) shows "The document changed since you opened it. Reload it and decide again." with a Reload action; an already-decided document (409 `ALREADY_DECIDED`) shows "You already decided this document." and refreshes.
- Placement on a phone: the controls stay reachable: sticky bottom bar at `touch:` widths, or the card moved directly under the terms list; measure with the e2e viewport at 390 px that the controls are inside two viewports from the top of the page.

## Also before merge (small)
- `deal-summary.tsx:61` hand-rolled `BUTTON`: use `Button` / `ButtonLink`.
- Type below 12 px (`documents.tsx:70, 108, 114`; `deal-summary.tsx:59, 123, 132`; `document-review.tsx:99, 101`) → 12 px tokens; `rounded-md` / `rounded-lg` / `rounded` → the scale; arbitrary values → tokens; `Pill` in `documents.tsx:62` → `Badge` / `Chip` / `StatePill`; `DocStatusBadge` must not pick a colour from a status it derives in the browser if the server gives a tone (use the server's `tone` field if present, else the dictionary's mapping of the status word).
- Stage state shown by colour only (`deal-summary.tsx:130`): show the word or a glyph.
- Links in running text (`documents.tsx:79`, `deal-summary.tsx:98`): `textLinkClass`.
- Collapse the deal summary: a headline, two to four facts and one action visible per buyer; stages, contract terms, changes, in force, invoices, owed and checks behind a `Disclosure`; the Next band's actions become text links (the page's `NextStep` already carries the action); the card must not duplicate "Your agreements" directly below it: fold the summary into that section or render one of them.

## Follow-up (do not do now; list in your report): the `/documents` route's scroll and focus after Read it / Upload; the page's several primaries; the `--color-new` token and `NewTag`; the purple quote rule; `annotation-style` raw palette classes; `tabIndex` doubles and `outline-none` in the terms list; `.hit` targets on the docs-list title and the Activity link; `aria-current` on the selected row; "Back to Deals" shown when the owner came from Activity; reading a contract before a deal is agreed; the `title` tooltip on the borrower file hash.

## Report
STATUS / FILES / TESTS (unit count, mock e2e count, typecheck, lint) / NOT CHECKED / FOLLOW-UPS, under 400 words.
