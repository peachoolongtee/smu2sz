"""The deterministic intent parser (en + zh). It runs first on every owner request; the optional LLM
classifier is consulted only when these rules find nothing.

Order matters and is fixed ("why"/"为什么" makes a request EXPLAIN before any decline or approval cue):
  (borrower file, financing comparison, reconciliation, ratios and capex are read before the status questions)
  the question gate first: an information question that only names a Tier-3 subject, a subject the books do not hold, or a
  topic a read cue would answer wrongly is ASK_BOOKS (app/nl/ask.py), and every action rule below answers a question with
  ASK_BOOKS instead of acting; an otherwise unread question about the books is ASK_BOOKS too,
  correction / confirmation of the session's pending plan (a short whole-message affirmative only), Tier-3 requests,
  explicit approvals (a full-match approve or reject sentence only; see app/nl/consent.py), the closed command grammar
  (the only free text that executes a draw or a repay),
  EXPLAIN, WHAT_IF, fixture or quoted-offer references, alerts, the page questions (what changed, what we are waiting
  for, when money arrives, what is overdue), ACCELERATE_RECEIPT, NEGOTIATE, REPAY_FACILITY, FUND_GAP, SHOW_STATUS, bare approvals, capex, vague cash requests (AMBIGUOUS).
"""

from __future__ import annotations

import re

from app.domain.fixtures import load_offers
from app.domain.models import FinancialState
from app.nl import consent
from app.nl import lexicon as lx
from app.nl.models import Intent, Parsed, Slots


def fixture_id(text: str) -> str | None:
    """EX01 -> EX01_PACKAGE, ex 01b -> EX01B_REWORDED, SEC_DEMO -> SEC_DEMO_FASTCAPITAL."""
    m = lx.FIXTURE_RE.search(text)
    if not m:
        return None
    raw = m.group(0).upper().replace(" ", "")
    offers = load_offers()
    if raw in offers:
        return raw
    prefix = m.group(1).upper().replace(" ", "_")
    # a short name never reaches an example written for another scenario's books (it has its full id only)
    hits = [k for k, o in offers.items() if k.startswith(prefix + "_") and "scenario" not in o]
    return hits[0] if len(hits) == 1 else None


_QUOTE_PAIRS = {"'": "'", "‘": "’", '"': '"', "“": "”", "「": "」", "『": "』"}


def _pasted(body: str) -> str | None:
    """The buyer's words after "X sent this:": inside its quotes when quoted, without the owner's own
    trailing question ("What do you think?", 帮我看看能不能接)."""
    body = body.strip()
    close = _QUOTE_PAIRS.get(body[:1])
    if close and body.rfind(close) > 0:
        body = body[1:body.rfind(close)]
    parts = re.split(r"(?<=[!?。！？])\s*|(?<=\.)(?!\d)\s*", body)
    while len(parts) > 1 and (not parts[-1].strip() or lx.OWNER_TAIL.search(parts[-1])):
        parts.pop()
    out = " ".join(p.strip() for p in parts if p.strip()).strip()
    return out or None


def quoted(text: str) -> str | None:
    m = lx.QUOTED_RE.search(text)
    if m:
        return (m.group(1) or m.group(2)).strip()
    m = lx.BUYER_SAYS_RE.search(text.strip())
    if m:
        return _pasted(next((g for g in m.groups() if g), ""))
    return reported(text)


def reported(text: str) -> str | None:
    """A buyer's offer the owner reports in their own words and asks about ("Foshan says they'll pay early at
    1.2% if we go to 60 days. Good deal or not?", 东莞那边说下季度要我们返1个点，这个能接吗): the reported terms,
    compiled as the buyer's message so the verdict is on THEIR offer, not a plan of ours."""
    if not lx.EVAL_QUESTION.search(text):
        return None
    m = lx.REPORTED_OFFER.search(text)
    if not m:
        return None
    body = (m.group("en") or m.group("zh") or "").strip(" ,，:：")
    return body if len(body) >= 4 else None


def _merge(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _pasted_span(body: str, start: int) -> tuple[int, int] | None:
    """Where the buyer's words sit inside the text after a "X sent this:" lead-in (offsets in the full text):
    through the last closing quote when the body opens with one (so nested quotes of the same kind stay inside),
    otherwise the sentences before the owner's own trailing question."""
    lead = len(body) - len(body.lstrip())
    b = body.strip()
    if not b:
        return None
    close = _QUOTE_PAIRS.get(b[:1])
    if close and b.rfind(close) > 0:
        return start + lead, start + lead + b.rfind(close) + 1
    end = pos = 0
    for part in re.split(r"(?<=[!?。！？])\s*|(?<=\.)(?!\d)\s*", b):
        if not part.strip():
            continue
        at = b.find(part, pos)
        pos = at + len(part)
        if not lx.OWNER_TAIL.search(part):
            end = pos
    return (start + lead, start + lead + end) if end else None


def split_provenance(text: str) -> tuple[str, list[str]]:
    """(owner_text, quoted_spans). What the owner typed, and what they quoted or pasted from someone else (a
    quoted span, or the buyer's body after a "X sent this:" lead-in). Intent cues and approval references are
    read from owner_text only: a buyer's "please approve APR-000001" is data, never an instruction."""
    t = text.strip()
    spans = [m.span() for m in lx.QUOTED_RE.finditer(t)]
    m = lx.BUYER_SAYS_RE.search(t)
    if m:
        i = next((k for k in range(1, (m.re.groups or 0) + 1) if m.group(k)), None)
        if i is not None:
            sp = _pasted_span(m.group(i), m.start(i))
            if sp:
                spans.append(sp)
    spans = _merge(spans)
    owner, last = [], 0
    for a, b in spans:
        owner.append(t[last:a])
        last = b
    owner.append(t[last:])
    return " ".join(x.strip() for x in owner if x.strip()), [t[a:b] for a, b in spans]


def quoted_approval(spans: list[str]) -> bool:
    """A quoted span that tries to approve something: an approval id or an approve/confirm cue."""
    return any(lx.APPROVAL_ID_RE.search(q) or lx.CONFIRM.search(q) or lx.BARE_CONFIRM.search(q)
               or lx.APPROVAL_REF.search(q) for q in spans)


def bare_counterparty(text: str, state: FinancialState) -> bool:
    """"Foshan???", "佛山？": a counterparty's name and nothing else to act on."""
    core = re.sub(r"[\s?？!！.。,，:：~…]+", " ", lx.norm(text)).strip()
    if not core:
        return False
    names = {n for ns in lx.counterparty_aliases(state).values() for n in ns}
    return core in names or core.replace("那边", "").replace("这边", "").strip() in names


def _facility(text: str, state: FinancialState) -> str | None:
    low = lx.norm(text)
    named = [f.id for f in state.facilities if re.search(rf"(?<![a-z0-9-]){re.escape(f.id.lower())}(?![a-z0-9-])", low)]
    if len(named) == 1:
        return named[0]
    for kind, pat in lx.FACILITY_WORDS:
        if pat.search(text):
            found = [f.id for f in state.facilities if f.kind.value == kind]
            if len(found) == 1:
                return found[0]
    return None


def slots_from(text: str, state: FinancialState) -> Slots:
    ot, spans = split_provenance(text)
    rates = lx.rates(ot) or lx.rates(text)
    amounts = lx.amounts(ot) or lx.amounts(text)
    days = lx.days(ot) or lx.days(text)
    low = lx.norm(ot if lx.rates(ot) else text)
    rebate = next((r.value for r in rates if lx.REBATE_WORD.search(low[max(0, r.start - 25):r.end + 25])), None)
    cps = lx.find_counterparty(text, state)
    tier3 = next((kind for kind, pat in lx.TIER3 if pat.search(ot)), None)
    appr = lx.APPROVAL_ID_RE.search(ot)
    return Slots(
        fixture_id=fixture_id(text),
        counterparty_id=cps[0] if len(cps) == 1 else None,
        facility_id=_facility(ot, state),
        amount_fen=amounts[0].value if amounts else None,
        rate_bp=rates[0].value if rates else None,
        rebate_bp=rebate,
        terms_days=days[0].value if days else None,
        invoices=lx.invoices(text),
        approval_id=appr.group(0).upper() if appr else None,
        buyer_profile="BUYER-1-HARDLINE" if lx.HARDLINE.search(text) else None,
        quoted_text=quoted(text),
        zero_forward=bool(lx.ZERO_FORWARD.search(text) or lx.ZERO_FORWARD_EXTRA.search(text)
                          or consent.NO_CONCEDE.search(consent.normalise(ot))),
        use_financing=bool(lx.USE_FINANCING.search(ot)),
        execute_now=False,  # only the closed command grammar (consent.parse_command) or a confirmed plan sets this
        tier3=tier3,  # type: ignore[arg-type]
        capex=bool(lx.CAPEX.search(ot)),
        quoted_approval=quoted_approval(spans),
    )


def _top_question(text: str) -> str | None:
    """The id of the top owner question this text asks, when the answer module is installed (app/nl/answers)."""
    try:
        from app.nl.answers import match
    except ImportError:  # the routing works without the answer module; ask.py then falls back to the nearest read
        return None
    found = match(text)
    return found[0] if found else None


def parse(text: str, state: FinancialState, *, pending_plan: bool = False) -> Parsed | None:
    """Owner request -> intent + typed slots, or None when no rule applies."""
    s = slots_from(text, state)
    text = split_provenance(text)[0]  # every cue below is read from what the owner typed, never from quoted text
    asks_why = bool(lx.EXPLAIN.search(text))  # "why was it rejected?" / "为什么被拒绝?" asks; it declines nothing

    def hit(intent: Intent, cue: str, **kw: bool) -> Parsed:
        return Parsed(intent=intent, slots=s, matched=[cue], **kw)

    def _act(intent: Intent, cue: str) -> Parsed:
        """A negotiation or an early-pay request: "do not negotiate", "don't send the counters", 不要谈判 and "do not get
        paid early" negate the action itself (nothing is done, no plan stays pending); a phrase that only constrains it
        ("don't give anything away") does not."""
        kind = "NEGOTIATE" if intent == Intent.NEGOTIATE else "ACCELERATE"
        if consent.action_negated(kind, text):  # type: ignore[arg-type]
            return Parsed(intent=intent, slots=s, matched=[cue, "consent:negated"])
        return hit(intent, cue)

    def _money(intent: Intent, cue: str) -> Parsed:
        gate = consent.money_gate(text)
        if gate in ("negated", "bad_amount", "deferred"):
            return Parsed(intent=intent, slots=s, matched=[cue, f"consent:{gate}"])
        return hit(intent, cue, tentative=True)  # a proposal that waits for the owner's confirmation

    # ---- the question gate (app/nl/ask.py): a question about the books is answered, never acted on. It comes before every
    # action rule: no plan is proposed, no offer compiled, nothing queued or run, and no refused operation is written to the
    # log for a question that only names a Tier-3 subject ("Did anyone try to change our limits?", "Is equity an option?").
    # A buyer's offer the owner asks about (a fixture, a quote, a reported offer) still gets its verdict; a request phrased
    # as a question ("can you draw ...?", 能不能让他们早点打款) keeps its action reading, and consent.py is unchanged.
    asks = (lx.is_question(text) and not s.fixture_id and not s.quoted_text and not s.approval_id
            and not (pending_plan and (lx.CORRECTION.search(text) or consent.confirmation(text) is not None)))

    def ask_books(topic: str) -> Parsed:
        slots = s.model_copy(update={"tier3": None, "execute_now": False, "question": text})
        return Parsed(intent=Intent.ASK_BOOKS, slots=slots, matched=["ask", f"ask:{topic}"])

    # One of the top owner questions (app/nl/answers) is answered from the books before any older read claims it: the
    # answer leads with the yes/no or the figure. "show me / tell me / list ..." asks too. Never for a fixture, quoted text,
    # an approval or a reply to a pending plan.
    plain = not s.fixture_id and not s.quoted_text and not s.approval_id and not s.tier3
    if plain and not (pending_plan and (lx.CORRECTION.search(text) or consent.confirmation(text) is not None)):
        if lx.not_held(text) is None and (top := _top_question(text)) is not None:
            return ask_books(f"answer:{top}")

    if asks:
        if s.tier3:
            return ask_books(f"tier3:{s.tier3}")
        if (held := lx.not_held(text)) is not None:
            return ask_books(f"not_held:{held}")
        topic = next((name for name, pat in lx.ASK_TOPICS if pat.search(text)), None)
        if topic is not None:
            return ask_books(topic)
    elif (not s.fixture_id and not s.quoted_text and not s.tier3 and lx.DATA_REQUEST.search(text)
          and (held := lx.not_held(text)) is not None):
        return ask_books(f"not_held:{held}")  # "Balance by account, please", 按账户列一下余额: asked for as a list

    declines_plan = pending_plan and not s.counterparty_id and consent.confirmation(text) == "no"  # "先不要发送": a decline
    if not asks and not asks_why and not s.approval_id and not s.tier3 and not declines_plan:
        # "do not negotiate", "don't send the counters", 不要谈判, "do not get paid early": nothing is done and no plan
        # stays pending, whether or not a plan is waiting (a decline that names a buyer would otherwise be held back)
        for intent, kind in ((Intent.NEGOTIATE, "NEGOTIATE"), (Intent.ACCELERATE_RECEIPT, "ACCELERATE")):
            if consent.action_negated(kind, text):  # type: ignore[arg-type]
                return Parsed(intent=intent, slots=s, matched=["negated_action", "consent:negated"])
    if pending_plan and not asks_why and not s.tier3 and not s.approval_id and consent.is_constraint(text):
        # "don't give anything away" with a plan waiting: a constraint on it, not a refusal. The plan is proposed again
        # with the constraint applied and waits for its own go-ahead; nothing is sent and nothing is cancelled.
        return hit(Intent.AMBIGUOUS, "constraint", correction=True)
    if pending_plan and not asks_why and lx.CORRECTION.search(text) and (s.rate_bp is not None or s.use_financing or s.counterparty_id
                                                        or s.amount_fen is not None or s.buyer_profile):
        return hit(Intent.AMBIGUOUS, "correction", correction=True)  # the service keeps the plan's intent
    if pending_plan and not s.tier3 and not s.approval_id and not asks_why:
        # a short, whole-message affirmative confirms the plan; "should I go ahead?" or "do not go ahead" never does
        verdict = consent.confirmation(text)
        if verdict == "yes":
            return hit(Intent.APPROVE, "confirm_plan", confirm_plan=True)
        if verdict == "no":
            return hit(Intent.REJECT, "decline_plan", confirm_plan=True)
        if lx.CONFIRM.search(text) and not lx.DECLINE.search(text):
            # confirm words inside something that is not a short affirmative: it confirms nothing (the service
            # logs it when it sat in a forwarded message, otherwise asks for a plain go-ahead)
            return hit(Intent.APPROVE, "confirm_unclear", confirm_plan=True)
    if not pending_plan and lx.BARE_CONFIRM.search(text) and not lx.DECLINE.search(text):
        # "yes do it" with no plan in this session: it names nothing, so it may only bind to an approval the
        # session has just shown (the service checks); never to whatever happens to be in the queue
        return hit(Intent.APPROVE, "bare_confirm")
    if s.tier3:
        return hit(Intent.OUT_OF_SCOPE, f"tier3:{s.tier3}")
    if not asks_why and (s.approval_id or (lx.APPROVAL_REF.search(text) and (lx.CONFIRM.search(text)
                                                                            or lx.DECLINE.search(text)))):
        # an approval is decided only by a full-match approve or reject sentence; anything else clarifies
        decision = consent.approval_verdict(text) if s.approval_id or consent.approval_ids(text) else consent.bare_verdict(text)
        if decision is None:
            return hit(Intent.AMBIGUOUS, "consent:approval_unclear")
        return hit(Intent.REJECT if decision == "reject" else Intent.APPROVE, "approval")
    cmd = consent.parse_command(text, state)
    if cmd is not None:  # the whole message is one affirmative command: the only free text that executes
        s = s.model_copy(update={"amount_fen": cmd.amount_fen, "facility_id": cmd.facility_id, "execute_now": True})
        return hit(Intent.FUND_GAP if cmd.kind == "DRAW" else Intent.REPAY_FACILITY, f"command:{cmd.kind.lower()}")
    if lx.EXPLAIN.search(text):
        return hit(Intent.EXPLAIN, "explain")
    if lx.WHAT_IF.search(text):
        return hit(Intent.WHAT_IF, "what_if")
    if s.fixture_id == "EX12_GOAL":
        return _act(Intent.ACCELERATE_RECEIPT, "fixture:EX12")
    if s.fixture_id == "EX11_CAPEX":
        return hit(Intent.CAPEX, "fixture:EX11")
    if (s.fixture_id or s.quoted_text) and lx.NEGOTIATE.search(text):
        return _act(Intent.NEGOTIATE, "negotiate+offer")
    if s.fixture_id or s.quoted_text:
        return hit(Intent.EVALUATE_OFFER, "offer_reference")
    if lx.ALERTS.search(text) and not lx.ACCELERATE.search(text):
        return hit(Intent.SHOW_ALERTS, "alerts")
    # the questions the Business pages suggest (app/nl/reads.py): read-only, answered from the Home read
    if lx.CHANGES_ASK.search(text):
        return hit(Intent.CHANGES, "changes")
    if lx.WAITING_ASK.search(text):
        return hit(Intent.SHOW_STATUS, "waiting")
    if lx.ARRIVAL_ASK.search(text):
        return hit(Intent.SHOW_STATUS, "arrival")
    if lx.OVERDUE_ASK.search(text):
        return hit(Intent.RECONCILE, "overdue")
    if lx.OWED_ASK.search(text):
        return hit(Intent.SHOW_STATUS, "owed")
    if lx.BORROWER_FILE.search(text):
        return hit(Intent.BORROWER_FILE, "borrower_file")
    if lx.COMPARE_FINANCING.search(text) and not lx.ACCELERATE.search(text):
        return hit(Intent.COMPARE_FINANCING, "compare_financing")
    if lx.RECONCILE.search(text):
        return hit(Intent.RECONCILE, "reconcile")
    if lx.RATIOS.search(text):
        return hit(Intent.SHOW_RATIOS, "ratios")
    if lx.CAPEX_ASK.search(text):
        return hit(Intent.CAPEX, "capex")
    if lx.DEAL.search(text) and not (lx.NEGOTIATE_VERB.search(text) or lx.NEGOTIATE.search(text)
                                     or lx.ACCELERATE.search(text) or lx.FUND.search(text) or lx.REPAY.search(text)):
        return hit(Intent.SHOW_DEAL, "deal")  # read-only: the confirmed contract beside the live books
    if lx.STATUS_QUESTION.search(text) and not lx.ACCELERATE.search(text):
        return hit(Intent.SHOW_STATUS, "status_question")
    # the action rules: a question that names an action is asked about it, so it is answered (ASK_BOOKS), never proposed
    # "can we pay off all our loans?", 我们能把债务还清吗 (a question about the term debt, not "could you repay the loan")
    debt_ask = bool(lx.DEBT_ASK.search(text)) and (asks or (lx.is_asking(text) and not lx.ASK_YOU.search(text)))
    if lx.RECORD_FACT.search(text) and not (lx.ACCELERATE.search(text) or lx.NEGOTIATE_VERB.search(text)
                                            or lx.NEGOTIATE.search(text) or lx.REPAY.search(text)
                                            or lx.FUND.search(text) or lx.FUND_SOFT.search(text)):
        if asks:
            return ask_books("record")
        return hit(Intent.RECORD_FACT, "record_fact")  # read-only: it says the agent cannot book this from chat
    if lx.NEGOTIATE_VERB.search(text):
        return ask_books("negotiate") if asks else _act(Intent.NEGOTIATE, "negotiate")
    if lx.ACCELERATE.search(text):
        return ask_books("accelerate") if asks else _act(Intent.ACCELERATE_RECEIPT, "accelerate")
    if lx.NEGOTIATE.search(text):
        return ask_books("negotiate") if asks else _act(Intent.NEGOTIATE, "negotiate")
    if lx.REPAY.search(text):
        if debt_ask:
            return ask_books("debt")  # the term loan is repaid on its schedule; REPAY_FACILITY repays a drawn line
        return ask_books("repay") if asks else _money(Intent.REPAY_FACILITY, "repay")
    if lx.FUND.search(text):
        if asks:
            return ask_books("fund")
        # nothing here executes: a clear negation, a bad amount or a condition is answered, anything else proposes
        return _money(Intent.FUND_GAP, "fund_explore" if lx.FUND_EXPLORE.search(text) else "fund")
    if lx.FUND_SOFT.search(text):
        return ask_books("fund") if asks else hit(Intent.FUND_GAP, "fund_need", tentative=True)
    if lx.STATUS.search(text):
        return hit(Intent.SHOW_STATUS, "status")
    if lx.EVALUATE.search(text):
        return hit(Intent.EVALUATE_OFFER, "evaluate")
    if lx.CONFIRM.search(text) or lx.DECLINE.search(text):
        decision = consent.bare_verdict(text)  # "approve it" / 驳回这个 only; a longer sentence decides nothing
        if decision is not None:
            return hit(Intent.REJECT if decision == "reject" else Intent.APPROVE, "approval")
    if s.capex:
        return hit(Intent.CAPEX, "capex")
    if lx.AMBIGUOUS.search(text) or bare_counterparty(text, state):
        return hit(Intent.AMBIGUOUS, "vague")
    if debt_ask:
        return ask_books("debt")  # "Can we clear our debts?", "How much debt do we have?"
    if asks and lx.ASK_WORD.search(text) and lx.BOOKS_TOPIC.search(text) and s.amount_fen is None and s.rate_bp is None:
        return ask_books("books")  # a question about the books no rule reads: the answer layer, else the nearest capability
    return None
