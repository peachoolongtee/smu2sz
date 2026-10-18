# Decision log

item | class P0/P1/P2 | acceptance condition | outcome | commit

Owner stop switch (R-14 write switch) | P0 | owner-only pause/resume; while paused an AGENT or COUNTERPARTY operation is not executed, queued or booked and is logged; OWNER and bank-feed operations run; survives restart; no engine change | done: /agent/pause, /agent/resume, PausableExecutor, state on the hash-chained log; refusal chosen over queueing; API only | 0af4a6bc
Mandate revoke/renew route | P1 | owner can revoke and renew the signed mandate through FLOW | not done: needs the owner's offline signing key (an unsigned revocation also blocks bank-feed receipts) and a signed-mandate upload; R-14 narrowed, stays open | none
Second approver | P2 | documented single-operator model, residual risk, where a second approver adds value | documented only (no second approver, per the owner's brief) | docs
External checkpoint file | P0 | save count, head and day to a file kept outside the database; verify later exports against it; rewrite before it, rollback and mismatched head detected; appends accepted | done: verify_evidence.py --checkpoint-save and --checkpoint FILE; manual checkpoint, no anchoring claim | 464617b3
Live-mode privacy trace test | P1 | each model path in live mode with the default chain sends redacted text only and logs no identifier, failures included | done: tests/security/test_model_privacy_paths.py, five paths plus the LLM_REDACT=0 opt-out | ab8bac83
Live script flags force redaction | P2 | the live evaluation flags force LLM_REDACT=1 | not done: no --live-llm flag exists; live flags honour LLM_REDACT (default on); forcing it changes what the harnesses measure; disclosed | none
Redaction gaps found (personal names, handles, filename attribute, trailing group of an unlabelled card number) | P2 | disclosed in the technical document and security assessment wording | disclosed in control_audit_privacy.md; no pattern change (redaction tests and recorded caches would need re-certification) | docs
