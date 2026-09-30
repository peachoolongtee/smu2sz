"""The deterministic intent parser (en + zh). It runs first on every owner request; the optional LLM
classifier is consulted only when these rules find nothing.

Order matters and is fixed ("why"/"为什么" makes a request EXPLAIN before any decline or approval cue):
  correction / confirmation of the session's pending plan, Tier-3 requests, explicit approvals,
  EXPLAIN, WHAT_IF, fixture or quoted-offer references, ACCELERATE_RECEIPT, NEGOTIATE, REPAY_FACILITY,
  FUND_GAP, SHOW_STATUS, bare approvals, capex, vague cash requests (AMBIGUOUS).
"""

from __future__ import annotations

import re

from app.domain.fixtures import load_offers
from app.domain.models import FinancialState
from app.nl import lexicon as lx
from app.nl.models import Intent, Parsed, Slots


def fixture_id(text: str) -> str | None:
    """EX01 -> EX01_PACKAGE, ex 01b -> EX01B_REWORDED, SEC_DEMO -> SEC_DEMO_FASTCAPITAL."""
    m = lx.FIXTURE_RE.search(text)
    if not m:
        return None
    raw = m.group(0).upper().replace(" ", "")
    keys = list(load_offers())
    if raw in keys:
        return raw
    prefix = m.group(1).upper().replace(" ", "_")
    hits = [k for k in keys if k.startswith(prefix + "_")]
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
        return m.group(1).strip()
    m = lx.BUYER_SAYS_RE.search(text.strip())
    if m:
        return _pasted(next((g for g in m.groups() if g), ""))
    return None


def _facility(text: str, state: FinancialState) -> str | None:
    for kind, pat in lx.FACILITY_WORDS:
        if pat.search(text):
            found = [f.id for f in state.facilities if f.kind.value == kind]
            if len(found) == 1:
                return found[0]
    return None


def slots_from(text: str, state: FinancialState) -> Slots:
    rates = lx.rates(text)
    amounts = lx.amounts(text)
    low = lx.norm(text)
    rebate = next((r.value for r in rates if lx.REBATE_WORD.search(low[max(0, r.start - 25):r.end + 25])), None)
    days = lx.days(text)
    cps = lx.find_counterparty(text, state)
    tier3 = next((kind for kind, pat in lx.TIER3 if pat.search(text)), None)
    appr = lx.APPROVAL_ID_RE.search(text)
    return Slots(
        fixture_id=fixture_id(text),
        counterparty_id=cps[0] if len(cps) == 1 else None,
        facility_id=_facility(text, state),
        amount_fen=amounts[0].value if amounts else None,
        rate_bp=rates[0].value if rates else None,
        rebate_bp=rebate,
        terms_days=days[0].value if days else None,
        invoices=lx.invoices(text),
        approval_id=appr.group(0).upper() if appr else None,
        buyer_profile="BUYER-1-HARDLINE" if lx.HARDLINE.search(text) else None,
        quoted_text=quoted(text),
        zero_forward=bool(lx.ZERO_FORWARD.search(text)),
        use_financing=bool(lx.USE_FINANCING.search(text)),
        execute_now=bool(lx.EXECUTE_NOW.search(text)),
        tier3=tier3,  # type: ignore[arg-type]
        capex=bool(lx.CAPEX.search(text)),
    )


def parse(text: str, state: FinancialState, *, pending_plan: bool = False) -> Parsed | None:
    """Owner request -> intent + typed slots, or None when no rule applies."""
    s = slots_from(text, state)
    asks_why = bool(lx.EXPLAIN.search(text))  # "why was it rejected?" / "为什么被拒绝?" asks; it declines nothing

    def hit(intent: Intent, cue: str, **kw: bool) -> Parsed:
        return Parsed(intent=intent, slots=s, matched=[cue], **kw)

    if pending_plan and not asks_why and lx.CORRECTION.search(text) and (s.rate_bp is not None or s.use_financing or s.counterparty_id
                                                        or s.amount_fen is not None or s.buyer_profile):
        return hit(Intent.AMBIGUOUS, "correction", correction=True)  # the service keeps the plan's intent
    if pending_plan and not s.tier3 and not s.approval_id and not asks_why:
        if lx.CONFIRM.search(text) and not lx.DECLINE.search(text):
            return hit(Intent.APPROVE, "confirm_plan", confirm_plan=True)
        if lx.DECLINE.search(text):
            return hit(Intent.REJECT, "decline_plan", confirm_plan=True)
    if s.tier3:
        return hit(Intent.OUT_OF_SCOPE, f"tier3:{s.tier3}")
    if not asks_why and (s.approval_id or (lx.APPROVAL_REF.search(text) and (lx.CONFIRM.search(text)
                                                                            or lx.DECLINE.search(text)))):
        return hit(Intent.REJECT if lx.DECLINE.search(text) and not lx.CONFIRM.search(text) else Intent.APPROVE,
                   "approval")
    if lx.EXPLAIN.search(text):
        return hit(Intent.EXPLAIN, "explain")
    if lx.WHAT_IF.search(text):
        return hit(Intent.WHAT_IF, "what_if")
    if s.fixture_id == "EX12_GOAL":
        return hit(Intent.ACCELERATE_RECEIPT, "fixture:EX12")
    if s.fixture_id == "EX11_CAPEX":
        return hit(Intent.OUT_OF_SCOPE, "capex")
    if (s.fixture_id or s.quoted_text) and lx.NEGOTIATE.search(text):
        return hit(Intent.NEGOTIATE, "negotiate+offer")
    if s.fixture_id or s.quoted_text:
        return hit(Intent.EVALUATE_OFFER, "offer_reference")
    if lx.STATUS_QUESTION.search(text) and not lx.ACCELERATE.search(text):
        return hit(Intent.SHOW_STATUS, "status_question")
    if lx.NEGOTIATE_VERB.search(text):
        return hit(Intent.NEGOTIATE, "negotiate")
    if lx.ACCELERATE.search(text):
        return hit(Intent.ACCELERATE_RECEIPT, "accelerate")
    if lx.NEGOTIATE.search(text):
        return hit(Intent.NEGOTIATE, "negotiate")
    if lx.REPAY.search(text):
        return hit(Intent.REPAY_FACILITY, "repay")
    if lx.FUND.search(text):
        # an explicit instruction executes; a request to find or suggest a way proposes (en and zh alike)
        explore = bool(lx.FUND_EXPLORE.search(text))
        return hit(Intent.FUND_GAP, "fund_explore" if explore else "fund", tentative=explore)
    if lx.FUND_SOFT.search(text):
        return hit(Intent.FUND_GAP, "fund_need", tentative=True)
    if lx.STATUS.search(text):
        return hit(Intent.SHOW_STATUS, "status")
    if lx.EVALUATE.search(text):
        return hit(Intent.EVALUATE_OFFER, "evaluate")
    if lx.CONFIRM.search(text) and not lx.DECLINE.search(text):
        return hit(Intent.APPROVE, "approval")
    if lx.DECLINE.search(text):
        return hit(Intent.REJECT, "approval")
    if s.capex:
        return hit(Intent.OUT_OF_SCOPE, "capex")
    if lx.AMBIGUOUS.search(text):
        return hit(Intent.AMBIGUOUS, "vague")
    return None
