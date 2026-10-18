# Ask FLOW router: notes for the Security Lead's review

Prepared 18 Oct 2026 for the Security Lead, who owns `docs/SECURITY_SELF_ASSESSMENT.md`; nothing there was changed. The design is
ADR-0015 (Proposed). Code: `services/api/app/nl/router/` (route.py, schema.py, catalogue.py, fake.py), the hook in
`app/nl/ask.py`, the flag `FEATURE_ASK_ROUTER` (default off) in `app/config.py`. Tests: `tests/nl/test_ask_router.py`,
`tests/certification/test_ask_router_boundary.py`.

## What is new on the attack surface

A new model call on the owner channel: an owner question that the deterministic layers do not answer may be sent, in
`LLM_MODE=live` with the flag on, to the primary provider. The model's output selects read-only tools; code writes the reply.

| Property | How it holds | Evidence |
| --- | --- | --- |
| The model sees no books | `build_prompt(question, lang)` takes no context; the catalogue is static text | `test_the_model_receives_no_figure_name_or_limit_from_the_books`, `test_the_prompt_does_not_change_with_the_books` |
| Identifiers in the question are redacted (PRIV-1..3) | `redact_text` before the prompt is built (LLM_REDACT, default on); the cache key is on the redacted text | `test_the_question_is_redacted_before_it_leaves` |
| The model's output cannot reach the reply | the output is tool names and typed slots only; the reply is the tools' own sentences | `test_a_single_call_is_answered_by_the_tool_writer`, the injection tests |
| Only catalogue tools run, only with valid slots | strict parse: exact keys, at most 3 calls, known tool, slots checked by the catalogue's `validate_slots` and the strict subset check (no coercion, ranges, enums), canary check; one bad call rejects all | `test_an_invalid_response_is_rejected_whole` (24 cases), `test_a_canary_in_the_output_is_rejected` |
| Every tool only reads | catalogue writers call the read-only metrics (`answers/metrics.py`); hypotheticals run on model copies | `test_routing_changes_nothing_in_the_store`; certification run below |
| Owner only | `ask_books` returns before the router for the agent key; `route` checks `owner_authenticated` and actor OWNER again | `test_not_the_owner_never_reaches_a_model`, `test_through_nl_the_owner_is_routed_and_the_agent_key_is_not` |
| Off unless switched on; no paid call in cache mode | flag default off; cache mode has no live backend and no recordings ship | `test_the_flag_off_never_calls_the_router`, `test_cache_mode_has_no_live_backend` |
| One paid call at most per question | the chain is cache then the primary only; a failed live call ends the routing | `test_a_provider_error_returns_none_and_no_second_paid_call` |
| A slow provider cannot hold the chat | a 12 s deadline over the whole call (thread pool, `max_retries=0`) | `test_a_timeout_returns_none_without_waiting_for_the_model` |
| Logs hold no question text | log line: question hash, backend, model, tool names, latency, outcome | `test_the_log_holds_a_hash_and_the_tools_never_the_question` |

## Prompt injection

The question is fenced between `<owner_question>` markers that it cannot reproduce (stripped from the question before it is
placed) under a rule that nothing inside changes the rules. The control that matters is not the instruction but the output
contract: a model that follows an injected instruction can only return a different valid route (a wrong read, which the answer's
wording shows) or an invalid one (rejected). Tested with five injections (English, Chinese, a marker-closing attempt, a JSON
payload in the question, a "print the reserve" request), each against a model that obeys (slot smuggling: rejected), names an
action tool (rejected) and routes the genuine read (the code's sentence, unchanged).

## Language-boundary certification

`tests/certification/test_ask_router_boundary.py` runs the whole adversarial set through the real POST /nl in the harness's
cache mode twice: as shipped, and with the flag on and a hostile routing model that routes every question it sees to two reads.
The harness's judge and criteria are unchanged. Result: WRONG_MATERIAL stays at the known findings (none open), WRONG_HARMLESS
stays within the known three, and every item keeps its class, operations (kind and status), decided approvals, commitments and
books; the router is reached and changes some owner replies (the honest "cannot yet" becomes a read). The harness itself was not
modified.

## Open points for the reviewer

1. **Provider location.** With `LLM_PRIMARY=deepseek` the redacted question goes to a provider in mainland China. A deployer
   needs a data-processing agreement covering owner questions; the owner should be told that questions FLOW cannot answer by
   itself are sent, redacted and without the books. Customer names the owner types are part of the question and are sent.
2. **A canary trip is on the security log (closed, RT-L2).** The router itself writes nothing to the store (that is what makes
   the store-unchanged property simple to test): `route_outcome` returns the rejection code, and `ask.router_reply` records one
   DATA_EXTRACTION event for the owner when it is `canary`, as the classifier path does. Log lines carry the fixed rejection
   code only (RT-L1), never the model's keys or values.
3. **The question hash** (sha256 of the redacted question, 16 hex characters) correlates log lines; it does not protect a short
   question against a dictionary of likely questions. Consider a keyed hash if the logs leave the deployment.
4. **Thread on timeout.** A live call past the deadline is abandoned, not killed; with `max_retries=0` and the client's own 12 s
   timeout it ends shortly after. The pool has four workers.
5. **The tools are on another branch** (`feat/ask-router-tools`). Each tool's writer must stay read-only and must resolve a
   customer slot by itself (never echo the slot text into the reply unresolved). `test_every_catalogue_schema_is_in_the_checked_subset`
   refuses a slot schema keyword the validator does not enforce.
6. **Reach.** Only questions that reach ASK_BOOKS are routed, and ASK_BOOKS is reached two ways: from the rules, and from the
   classifier fallback in `service._parse` (a question about the business that the rules did not read and the classifier returned
   nothing, a low-confidence reading or OUT_OF_SCOPE for). So an owner text can go to the classifier and then, if that did not
   settle it, to the router: two model calls in live mode, each with the redacted text. When the classifier's output for the text
   was rejected for a canary trip, the router is skipped and the owner gets the fixed "cannot answer yet" reply (RT-L3). A text
   that is not about the books at all stays out of scope and goes to no router.
