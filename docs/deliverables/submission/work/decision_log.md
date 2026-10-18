# Decision log (append-only; one line per decision)

item | class | acceptance condition | outcome | commit
1 chat confirmation per-leg outcomes | P0 | reply names each leg done/queued/refused, the funding still to arrange, cash in now vs landing day; retry repeats no executed leg | per-leg lines and cash-landing already existed; added "Still to arrange" line for a part-run plan; retry test added (no pending plan after go-ahead, same request_id replays as DUPLICATE) | 386775ca
1b retried go-ahead approved the queued above-ceiling leg | P0 | a plain yes/go ahead never decides a waiting approval | fixed: approvals need the word approve (or the id); Business wording now says Approve it | 386775ca
2 bare acknowledgements as consent | P0 | ok / ok thanks / thanks / 好的谢谢 run nothing; go ahead / yes, run it / do it / 执行 / 确认执行 run the plan shown | fixed in consent.py and lexicon.BARE_CONFIRM; plan stays waiting | 386775ca
2b pay-everyone offer replaced a waiting fund-gap plan | P1 | an answer that offers a plan never replaces a waiting plan | fixed (any waiting plan is kept) | 386775ca
2c "approve the pending one" bound to an unshown queue | P1 | id-less approval binds only to the one approval named in the previous reply | fixed | 386775ca
3 approved but re-run refused: visible status | P1 | decision response, queue row and chat all say approved-did-not-run | queue row already did (F14); added approval{decision,execution_status,ran,text} to POST /approvals/{id} and the chat sentence; row stays APPROVED (engine, SEC-27 unchanged) | d9923e92
3b re-check at execution | P1 | stale books/mandate/offer refused at decision time | verified by tests (expired mandate, receipt booked after queueing, changed state on buyer yes); no change needed | d9923e92
4 owner-reported buyer acceptance | P1 | bound to verdict, message hash, terms hash, expiry, books; evidence unverified; funding stated either way | binding already complete (tests added); added "none is needed" statement when no reserve gap is ahead | 7404f798
5 thresholds wording | P1 | hard limits vs approval thresholds worded consistently | NOT DONE: Business card wording already says "limit you signed for funding without your approval"; chat plan sentence still says "yearly ceiling for what I may borrow alone" (app/nl/plans.py approval_sentences); hard-vs-threshold classification not pinned by tests | -
6 bypass via actor/lower-level routes | P1 | agent key, counterparty key, no token cannot skip a gate | partly covered: chat approval by agent refused (existing), POST /approvals by agent refused, bank-feed receipt vs queued receipt; routes /documents/{id}/confirm, /negotiate, /alerts/{id}/act, /nl not re-swept; NOT DONE | -

## Owner control, checkpoint and privacy (fix/control-audit-privacy)

# Decision log

item | class P0/P1/P2 | acceptance condition | outcome | commit

Owner stop switch (R-14 write switch) | P0 | owner-only pause/resume; while paused an AGENT or COUNTERPARTY operation is not executed, queued or booked and is logged; OWNER and bank-feed operations run; survives restart; no engine change | done: /agent/pause, /agent/resume, PausableExecutor, state on the hash-chained log; refusal chosen over queueing; API only | 0af4a6bc
Mandate revoke/renew route | P1 | owner can revoke and renew the signed mandate through FLOW | not done: needs the owner's offline signing key (an unsigned revocation also blocks bank-feed receipts) and a signed-mandate upload; R-14 narrowed, stays open | none
Second approver | P2 | documented single-operator model, residual risk, where a second approver adds value | documented only (no second approver, per the owner's brief) | docs
External checkpoint file | P0 | save count, head and day to a file kept outside the database; verify later exports against it; rewrite before it, rollback and mismatched head detected; appends accepted | done: verify_evidence.py --checkpoint-save and --checkpoint FILE; manual checkpoint, no anchoring claim | 464617b3
Live-mode privacy trace test | P1 | each model path in live mode with the default chain sends redacted text only and logs no identifier, failures included | done: tests/security/test_model_privacy_paths.py, five paths plus the LLM_REDACT=0 opt-out | ab8bac83
Live script flags force redaction | P2 | the live evaluation flags force LLM_REDACT=1 | not done: no --live-llm flag exists; live flags honour LLM_REDACT (default on); forcing it changes what the harnesses measure; disclosed | none
Redaction gaps found (personal names, handles, filename attribute, trailing group of an unlabelled card number) | P2 | disclosed in the technical document and security assessment wording | disclosed in control_audit_privacy.md; no pattern change (redaction tests and recorded caches would need re-certification) | docs
