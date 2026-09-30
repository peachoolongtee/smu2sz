# Invariants

These are architectural laws. Every module and every agent must respect them. A test in `evals/security/` or `services/api/tests/` guards each one. Breaking one is a release blocker.

1. **No LLM output directly creates or executes a financial operation.** Model output is a `CompiledOffer` or `CompiledTermSheet` proposal. Operations are built by deterministic code from a `Verdict` and executed only by `operations/`.
2. **The verifier never consumes arbitrary free text.** It reads typed contracts only. No `str` field of a `SourceDocument` is passed to `verifier/`, `funding/`, `covenants/`, `mandate/` or `financial/`.
3. **Unknown or unapproved lenders cannot enter the funding menu through messages.** Only an owner-originated `AddFacility` (Actor.OWNER) can add a facility. A term-sheet compilation yields a proposal that the owner must approve.
4. **Uncommitted facilities count as zero available liquidity for hard constraints.** PENDING, NOT_APPLIED and REFERENCE_ONLY are excluded from conservative trajectories and committed plans.
5. **Contingent concessions use conservative treatment for hard limits.** They are counted at maximum. Contingent gains count as zero. Only FIRM gains may offset concessions.
6. **Tier-3 actions can never be executed.** These are personal guarantees, pledging collateral, issuing equity, changing the mandate, and adding a facility by a non-owner. The executor refuses them regardless of the caller, text or claimed approval.
7. **Cross-counterparty information is private.** Buyer A can never retrieve Buyer B's terms, the reserve floor, facility limits, mandate values, reservation values, the funding menu or the system prompt. Outbound text is template-filled from an allow-list of fields; requests for protected data are refused and logged as `DATA_EXTRACTION_REFUSED`.
8. **All financial operations are typed, logged, attributable, replay-safe and checked against the current mandate version.** Each carries an idempotency key and, where relevant, a nonce. They are appended to a hash-chained log, refusals included.
9. **Money arithmetic is exact.** Money is integer fen. Rates are integer bp or exact fractions. Rounding happens only in `app/domain/money.py`, half-up, once per posting (ADR-0002). There is no float anywhere on a money path.
10. **When material semantics cannot be established from evidence, abstain rather than guess.** Every obligation needs a span that matches its source exactly. Conflicting spans give `CONFLICTING_SOURCES`, an unbounded or unspecified scope gives `UNRESOLVED_SCOPE`, and "as usual" books nothing.

Also:
- 11. **Conservative mode alone decides.** Expected-mode numbers are shown, never relied on.
- 12. **Tiers are enforced by code, not prompts.** The executor computes the tier itself; a caller or message cannot lower it.
- 13. **The UI never computes money.**
