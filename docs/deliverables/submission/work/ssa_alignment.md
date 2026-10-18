# Security Self-Assessment vs technical document: alignment check

Prepared on 18 Oct 2026 for the integration lead, on branch `docs/sub-ssa` from `origin/docs/submission` `1cb0d2e2`. I compared
`docs/SECURITY_SELF_ASSESSMENT.md` (v3, assessed build `70f23ac5`, plus the submission addendum) with
`docs/deliverables/technical_document.md` (TD) as it stands on `1cb0d2e2`, with `docs/deliverables/execution_evidence.md`, and with
the certification records (`docs/security/CERTIFICATIONS.md`, `08c8dac0`). I did not edit the technical document, because another
editor is restructuring it. Line numbers refer to TD at `1cb0d2e2`.

## Figures that agree (checked)

| Figure | Self-assessment | TD |
| --- | --- | --- |
| Attack catalogue | 279 = 128 API + 151 chat; 0 harm; 279 of 279 reached their path; 120 of 128 stopped by the named control (E1, 2.4) | lines 61, 1186-1199, 1348 |
| Full suite on `70f23ac5` | 10,674 passed, 0 failed, 47 skipped (E5) | lines 1229, 1331, 1345 |
| Certifications | `29fa0ea2`, `85309b63`, `6d2b6941` conditional (contract terms off), `70f23ac5` the final assessed build (2.7) | lines 1226-1231 |
| Mock browser, CSP, PostgreSQL | 479 passed / 77 skipped; 0 CSP violations; 3 of 3 (Appendix C) | lines 1229-1230, 1332, 1358 |
| Readiness | local GO; live mode not certified; network demo NO-GO; production NO-GO (executive summary, 4.6) | Table 16, lines 1247-1250 |
| Audit chain | tamper-evident against parties without database write access; R-13 (1.10) | lines 1058-1070 |
| APR 15% | an approval threshold for the agent, not a hard rule (1.3, corrected in this branch) | lines 993-995, 1526 |
| Review | internal and AI-assisted; the Security Lead is an AI agent that also wrote the fixes it certified (2.6) | lines 61, 1217-1225 |
| Audit and red-team findings | A01 to A13 plus 3 + 7 + 3 + 7 + 6 = 39 (Appendix B) | line 1218 |
| Routes | 106 API routes (1.5, 2.9; the executive summary corrected from 100 in this branch) | lines 389, 1209, 1359 |
| Submission build | not certified; the same list of additions (addendum) | lines 1232-1239 |

## Inconsistencies in the technical document (for the lead; TD not edited)

1. **Refusals before the executor (line 1061).** TD: "Requests refused before the executor are kept as append-only security
   events". Self-assessment 1.9: a refused credential is recorded only within a budget (300 an hour per process, 30 per client
   address; the excess is counted, not stored). Validation refusals (422, 413, 409) are not recorded in the store at all, only in the
   access log. Rate-limit refusals give a warning line, not an event. Suggested: "Refused credentials are kept as append-only security
   events within a budget (300 an hour, 30 per address; the excess is counted); requests refused by validation are only in the access
   log. Security events are not chained."
2. **Language boundary (line 910, Table "Does language stay safe at the boundary?").** TD gives "231 adversarial inputs (3 Oct,
   build `979defb`)". The self-assessment (E6, Appendix A) and TD's own line 1335 give the re-run on `70f23ac5`: cache 0
   wrong-and-material (1 wrong-harmless), scripted 0 wrong-and-material (3 wrong-harmless), 231 items each. Suggested: "231
   adversarial inputs, last run on `70f23ac5`: 0 wrong-and-material on the cache and scripted backends; not run against a live model".
3. **Documentation routes (line 1359).** TD says "plus three documentation routes in demo mode". Self-assessment 1.5: the route
   policy test enumerates 110 routes in demo mode, 106 API routes and 4 documentation routes (FastAPI also serves
   `/docs/oauth2-redirect` when `/docs` is on). The sweep names three (`/docs`, `/redoc`, `/openapi.json`). Suggested: "plus four
   documentation routes in demo mode (`/docs`, `/docs/oauth2-redirect`, `/redoc`, `/openapi.json`)".
4. **What was disclosed with `70f23ac5` (lines 1230-1231).** TD lists REG-8, REG-9, CT-2b, SEC-27 and SEC-28. The self-assessment's
   certification table (2.7) and `CERTIFICATIONS.md` say "with REG-8 disclosed". Section 4.4 of the self-assessment covers all
   five, so nothing is contradicted, but a reader who compares the two tables sees different lists. No change needed if TD keeps
   pointing to section 4.4.
5. **Model answers in the attack runs (lines 61, 1207-1208).** TD: "rules path and a scripted hostile model; no real model, recorded
   or live, read an attack" (78 rules readings, 4 scripted). Self-assessment executive summary: "offline, with recorded or scripted
   model answers", which describes cache mode, not what was actually read. The two are compatible. TD is more precise, and the
   Security Lead could adopt its wording at re-certification. I left the self-assessment's text unchanged.
6. **External red-team run (lines 1220-1222).** TD: "who ran it is not recorded there, so we do not call it independent". The
   self-assessment now carries `{TEAM_REDTEAM_WHO}` and `{TEAM_REDTEAM_REPORT}`. When the owner answers, update TD line 1220-1222 to
   the same answer, so the two documents do not disagree on who ran it or where its report is.
7. **SEC-28 reporting fix not in TD.** TD's list of submission-build additions (lines 1232-1238) does not include the SEC-28
   reporting fix (`fix/sec28-funding-status`: the negotiation reply states each funding leg's actual outcome). Add it once it is merged.
   Also check TD's description of `/negotiate`, if it has one. Table 16's production blocker "resumable or reversible plans (SEC-28)"
   stays correct, because atomicity is still per operation only.
8. **Principal audit (line 1218).** TD: "An audit and five red-team rounds by AI subagents (1 to 3 Oct)". The self-assessment
   (2.6) leaves open whether the 3 Oct principal audit was done by people, AI agents or both (`{TEAM_AUDIT_WHO}`). If the owner's
   answer includes people, TD line 1218 must change too.

## Changes made to the self-assessment in this branch (listed in its addendum)

- Executive summary: 100 API routes changed to 106; live model mode named as not certified in the verdict.
- Document control: the 18 Oct manifest update is dated.
- 1.3: the rate ceiling (15%) described as an approval threshold for the agent (`app/operations/executor.py`: the admission's
  approval reason raises a leg to Tier 2 only when the requester is not the owner).
- 2.6: Security Lead dates 14 to 18 Oct.
- New section: Appendix E, Submission build addendum (integration lead, not certified), with tokens `{SUBMISSION_COMMIT}`, `{SEC28_COMMIT}` and
  `{VERIFICATION_ROWS}`.
- `[TEAM]` placeholders replaced with the tokens `{TEAM_AUDIT_WHO}`, `{TEAM_REDTEAM_WHO}`, `{TEAM_REDTEAM_REPORT}`,
  `{TEAM_BRACES_OWNER}` and `{TEAM_LICENCE}`.
