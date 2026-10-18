# ADR-0015: Ask FLOW's router: the model routes an owner's question to read-only tools, code answers

Status: Proposed, 18 Oct 2026. Owner-approved design ("the model routes, code answers"); the Security Lead's review is pending
(`docs/security/ask-router-review-notes.md`). Behind `FEATURE_ASK_ROUTER`, default off. Branches: `feat/ask-router` (the route,
the validation, the hook, the tests) and `feat/ask-router-tools` (the catalogue and its writers).

## Problem

Ask FLOW answers the owner's top 30 questions deterministically (`app/nl/answers`, matched by wording) and says plainly when it
cannot answer anything else. Owners ask the same 30 things in far more ways than a matcher holds: "can my company survive this
month?", "is my cash position ok for the next 4 months or am i in danger", 我们撑得过这个季度吗. Each new wording is another
pattern; the held-out general set (`evals/owner_questions/general.yaml`, 345 items) shows the gap.

A language model understands those wordings. But a model must not answer from the books: it would see the reserve, the limits,
the customers and the cash (data leaving the machine, in DeepSeek's case to a provider in mainland China), and it could state a
figure that is not in the books.

## Decision

### 1. The model routes, code answers

For an owner question the deterministic layers do not answer, a model may only **choose up to three tools from a closed
catalogue of read-only tools and fill their typed slots**. Code validates the choice, runs the tools and writes the answer. Every
figure and every word of the reply comes from the tools' writers (server-side, English and Chinese), built on the same metrics
the top-30 answers use (`app/nl/answers/metrics.py`). The model's output has no free text that is ever shown.

The catalogue (`app/nl/router/catalogue.py` and `tools/`, 40 tools) covers cash safety over a horizon, runway, the lowest point,
the first breach, upcoming payments, payroll, the funding need, plan and cost, debt, repaying everything, borrowing headroom,
loan payments, who owes most, overdue invoices, concentration, a late payment, an early-payment offer, longer terms, what waits,
approvals, covenants and their break points, the plan's covenants, a capex purchase, recent activity, the mandate's limits, what
needs approval, and general advice. Each tool has a one-line description for the model, a strict slot schema (enums, integer
ranges: horizon 1-365 days, days late 1-180, a rate 1-500 bp) and an `answer(ctx, lang, slots)` writer. A customer slot is free
text the tool resolves against the registry with the parties matcher; the model is never given the registry's names, and an
unresolved name gets a clarifying reply. A horizon beyond the forecast (the mandate's horizon, 120 days on the demo books) is
answered on the forecast and says so.

### 2. What the model sees, and what it does not

It sees exactly:

- a fixed system prompt: the rules (choose at most three tools, only slots stated in the question, no answer of its own, the
  question is data), the output format, a canary marker, and the catalogue as JSON (tool names, descriptions, slot schemas);
- one user message: the reply language and the owner's question, **redacted** (`compiler.redaction`, PRIV-1..3: accounts,
  phones, emails, credit codes, ID numbers, labelled addresses become placeholders) and fenced between `<owner_question>` markers
  that the question cannot reproduce (`_defang`).

It never sees a figure, a counterparty name, a mandate value or any state. This is structural: `build_prompt(question, lang)`
takes no context, so the books cannot reach it; a test captures the prompt the backend receives and asserts that no figure,
name or limit of the books is in it, and that the prompt is byte-identical whatever the books hold. The only digits in the
system prompt are the catalogue's own slot bounds and the rules' numbering. Names the owner types in the question (a customer)
do go, as the owner wrote them: they are the question.

### 3. Validation: anything unexpected rejects the whole response

`route.parse_route` accepts only `{"calls": [{"tool": ..., "slots": {...}}], "none": bool}`:

- the canary check first (a canary in the output means the prompt leaked: rejected);
- strict JSON: no duplicate keys, no NaN or Infinity, nothing around the object (a fenced code block is rejected);
- exactly the keys `calls` and `none` at the top and `tool` and `slots` in each call; `none: true` only with no calls;
- at most three calls; every tool in the catalogue; every slot valid against that tool's schema, checked twice: by the
  catalogue's own `validate_slots` and by the strict subset check in `app/nl/router/schema.py` (no unknown slot, no type
  coercion, a bool is not an integer and "30" is not 30, ranges and enums enforced, null only where the schema allows it).

One bad call rejects all of them. Identical calls run once. Several calls give one answer: each tool's sentence, joined, each
sentence once. The schema sent to the provider (`output_schema`, one `anyOf` branch per tool) has its numeric bounds removed,
because structured-output modes refuse them; the bounds are enforced on what comes back.

### 4. Where it sits, and the fallbacks

In the ASK_BOOKS path (`app/nl/ask.py`), owner turns only: the Tier-3 information and "the books do not hold" replies, then the
deterministic answers (`answers.answer`), then the existing read that answers the topic right (the financing comparison, the
break-even, why cash is short, the page's late-payment read, what is waiting), **then the router**, then the honest "I cannot
answer that from the books in chat yet" with the nearest read. The topic reads stay before the router because they are
deterministic and some of them know the page's binding ("this invoice"), which the router cannot.

ASK_BOOKS is reached two ways: from the rules (a question they read as one about the books) and from the classifier fallback
(`service._parse`): an owner question the rules did not read, for which the classifier returned nothing, a low-confidence reading
or OUT_OF_SCOPE, and that names something the books are about, goes to ASK_BOOKS as a "question" and from there to the router
like any other. The router is skipped on that second route when the classifier's output for the text was rejected for a canary
trip: the text has already drawn a leaking or hostile reply once, and a second model call would carry it again, so the owner gets
the fixed "I cannot answer that yet" reply. A canary trip in the router's own output is recorded as a DATA_EXTRACTION security
event, as the classifier's is.

The router returns None, and the honest reply follows, on: the flag off; not the owner (the agent key and buyers never reach
it, and `route` checks again); an empty question or one over 500 characters (never sent); a cache miss in cache mode; a
provider error, a refusal, an empty reply or the deadline (12 s, the whole call); a rejected response; `none: true`; a tool that
raises an engine error.

### 5. Backends, cost and recordings

The classifier's pattern: recorded routes first (`app/nl/router/route_cache/`, keyed by sha256(prompt version + the redacted
question)), then, only in `LLM_MODE=live`, **one** call to the primary provider (`LLM_PRIMARY`): a failed live call ends the
routing rather than paying for a second provider. Claude runs at `effort: low` with a JSON-schema output; DeepSeek in JSON mode
with thinking off. No recordings ship, so cache mode answers nothing new and the flag changes nothing there.
`scripts/record_router_cache.py` records routes for a question list: `--estimate` counts calls and tokens, `--fake` records a
scripted keyword model for tests, `--live` needs the explicit flag and the provider key in the environment (it never reads
`.env`). A recorded route goes through the same validation on replay, so a route naming a tool that no longer exists is
rejected. Each entry carries the catalogue's hash for audit; it is not enforced, so a description change does not force a
paid re-recording.

### 6. Prompt injection

The question is the owner's own text, but it is treated as data: fenced, with a rule that nothing inside it changes the rules,
the tools or the format. The defence does not rely on the model obeying: the output schema has no free text the code would
show, every tool only reads, so the worst a hijacked model can do is pick the wrong read, and the answer's own wording (it says
what it answers: "Up to 90 days ...", "Your total debt is ...") shows that it is the wrong one.

### 7. Logging

Only a 16-hex-character hash of the redacted question, the backend, the model id, the tool names, the latency, the prompt
version and the outcome (`answered`, `none`, `rejected:<why>`, `failed`, `miss`, `skipped:<why>`) are logged. Never the question,
never a slot value, never the reply.

### 8. Privacy

In live mode the redacted question leaves the machine for the configured provider. With `LLM_PRIMARY=deepseek` that is a
provider in mainland China; with Claude, Anthropic. A deployer who switches the flag on in live mode needs a data-processing
agreement with that provider covering owner questions, and should tell the owner that questions FLOW cannot answer by itself are
sent, redacted and without the books, to that provider. The question hash in the logs is not secret against a dictionary of
likely questions; it is there to correlate, not to protect.

## Consequences

- An owner's wording FLOW's matcher does not hold can still get a figure-exact answer from the books, with no figure from a model.
- Coverage depends on what reaches ASK_BOOKS. On the general set at day 0 (measured before the classifier fallback below existed),
  103 of 345 items are answered by the deterministic answers, 87 more reach ASK_BOOKS on a topic the answers miss (the router's
  reach then), and **96 were not read as a question about the books at all** (the rules return nothing and the intent classifier
  falls back to OUT_OF_SCOPE). Since then `service._parse` sends such a question that names something the books are about to
  ASK_BOOKS, so the router now sees it too (section 4); what is not about the books stays out of scope and is never sent.
- Live mode costs one model call per routed question: about 3,300 input tokens with the 40-tool catalogue (an estimate of 3,250
  for the system prompt, identical on every call so provider prompt caching bills it at the cached rate, and about 36 for the
  question) and up to about 60 output tokens.
- A new tool is a code change with its schema and writer, reviewed like any read: the model can never reach anything that is not
  in the catalogue.

## Future work: placeholder answers

A later step may let the model write the sentence around code-computed figures it never sees: the model returns a template with
typed placeholders (`{lowest_cash}`, `{first_breach_day}`) drawn from a closed list per tool, code validates that every
placeholder belongs to the tools it called, fills them, and runs the result through the egress scan. That would give more
natural wording for compound questions while keeping figures out of the model, at the cost of free text that is shown, so it
needs its own review. Not part of this decision.
