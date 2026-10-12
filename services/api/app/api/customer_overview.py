"""GET /customers/{customer_id}/overview: what a buyer is worth to the owner and what it puts at risk (map #88, ticket #108, the server half).

    GET /customers/{customer_id}/overview?lang=en|zh&decision=<id>&path=<key>&invoice=<id>

One page's read, composed from reads the other pages already make; nothing is priced, projected or decided here:

    figures[4]      relationship value, outstanding, financing linked (with its state word), share of what you are owed
    decision        the one commercial decision waiting (the open offer's headline, the recommended path and its cost, the authority
                    sentence) with its actions, else null with `none_text`
    actions[2]      view the invoices; stress-test payment (the second only while the exposure flag is on)
    economics       the owner's inputs for the buyer (sales, margin, classification) and the two figures they give
    exposure        payment behaviour, financing, the 30-day late-payment stress, what the financing then costs, spare capacity:
                    the exposure layer's own block (`app.strategy.exposure`); null, with the top-level `note` (the field the page reads), while FEATURE_EXPOSURE is off
    history         the open offer, the buyer's entries in the log, the terms in force
    context.back    {label, href} built from the query: `decision` (+ `path`) back to /deals, `invoice` back to /receivables
    context.customer, .deal, .scenario   the selections the page was opened with (Home V2's URL state): this customer; the `decision` when it
                    names one of this buyer's offers, else null; the `scenario` when there is such a deal, else null

The sources are `inputs_from_store` (customer inputs and their provenance), `receivable_rows` (the net, the financing state, the
agreement, the pending counter), `deal_offers.open_offers` and the offer picture (the recommended path, its cost and authority), the
exposure layer (concentration, payments, stress, capacity) and the decision record's log. The only arithmetic is the owner's two
products of their own inputs: a year's contribution (sales times margin) and the open request's cost as a share of it, on a 12-month
basis. Annual sales are the owner's input when there is one, else projected from the books (the recurring schedule and the receivables
still to be issued over the next 12 months: "projected from your books"); the margin is the Demo's assumed default (`config.DEMO_GROSS_MARGIN_BP`, provenance DEMO, whatever the books are called) until the owner
enters one; one function reads it for this page and for the exposure routes' `customer_context`. A decision is `kind` counter, request or offer_received (a received offer not yet read: "Read the offer", no authority
sentence). Each history row with an `href` carries its `link_label`. The page reads the top-level `note` for the exposure panel.

Every sentence is written for `lang` through `t(lang, en, zh)` (INVARIANT 13); no id appears in a sentence (hrefs carry them). The
share of the buyer's sales is never stated unless the concentration holds it. Cached on the books, the mandate, the day, the
commitments, the buyer, the language, the inputs, the log and the flag (the query only builds `context`, outside the cache).
Context, not mandate: nothing here changes a verdict, a cap or what FLOW may do alone.

State (ticket #120): each figure, each exposure row and each history row carries `state` (lower case: planned | arranged | received |
repaid | current | due_soon | overdue | promise_missed, else `none`) and `state_text` (its word, "" for none), so the page can draw the one
state word (StateWord). Nothing is derived here: a financing state is `financing_words.state_of` (through `financing_state_words`; PLANNED
for an invoice of the buyer's that the plan FLOW has ready, and not run, would finance), a collection state is the receivable rows' own
`collection_state` and `collection_state_text` (the worst of the open invoices for the Outstanding figure). Where the states of several
invoices differ the figure says none, as its text says "more than one state".
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any, Literal, Protocol
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query

from app.alerts import alerts
from app.api.auth import require_owner
from app.api.deal_offers import open_offers
from app.api.decisions import Context, latest_verdict_for, load_context
from app.api.financing_words import State, state_of, state_word
from app.api.home import next_action
from app.api.offer_picture import FLOW_MAY, NEEDS_OWNER, OVER_LIMIT, cached_picture
from app.api.presentation import Lang, agreement_words, deal_back_label, event_words, party_name, t, when_text
from app.api.receivables import read_rows
from app.api.runtime import Runtime, get_runtime
from app.api.workspace import _months
from app.books import current_books
from app.config import DEMO_GROSS_MARGIN_BP, get_settings
from app.decisions.identity import deal_id, decision_id_for, offer_id_of
from app.decisions.state import DealState
from app.domain.models import CompiledOffer, FinancialState, OperationStatus, Verdict
from app.domain.money import (
    bp,
    fmt_pct,
    fmt_yuan_about,
    fmt_yuan_about_short,
    fmt_yuan_rounded,
    round_half_up,
)
from app.financial import EngineError, recurring_issue_days
from app.operations.log import LoggedEntry
from app.persistence.records import CustomerInputRecord, InputField
from app.strategy import exposure as assembly
from app.strategy.cache import AnswerCache, cache_key
from app.strategy.concentration import concentration
from app.strategy.inputs import DEMO_ENTERED_BY, CustomerInputs, inputs_from_store, provenance_words, value_of
from app.strategy.net import advance_lot
from app.strategy.words import buyer_short, financing_state_words, share_text, whole_yuan

router = APIRouter(tags=["customers"], dependencies=[Depends(require_owner)])
log = logging.getLogger("termsledger.decisions")

CACHE_SIZE = 32
LOG_ROWS = 3  # the entries of the log the history shows, newest first (beside the open offer and the terms in force)
_CACHE: AnswerCache[dict[str, Any]] = AnswerCache(CACHE_SIZE)
_SAFE = re.compile(r"[A-Za-z0-9_.:\-]{1,80}")
_CLASSES = {"NORMAL": ("Normal", "普通"), "IMPORTANT": ("Important", "重要"), "STRATEGIC": ("Strategic", "战略")}
_AGREEMENTS = ("ACCEPT_OFFER", "RECORD_COMMITMENT")
_SKIP_STATUS = (OperationStatus.DUPLICATE, OperationStatus.REFUSED)


def clear_cache() -> None:
    _CACHE.clear()


def _exposure_on() -> bool:
    return bool(get_settings().features.exposure)


def _economics_on() -> bool:
    return bool(get_settings().features.customer_economics)


def _quoted(value: str) -> str:
    return quote(value, safe="")


def _up(text: str) -> str:
    return text[:1].upper() + text[1:]


def _days(n: int, lang: Lang) -> str:
    return t(lang, f"{n} {'day' if n == 1 else 'days'}", f"{n} 天")


# ---------------------------------------------------------------- what has been read


@dataclass(frozen=True)
class _Read:
    """What the overview has read, once, under the runtime's lock."""

    rt: Runtime
    lang: Lang
    state: FinancialState
    today: int
    buyer_id: str
    name: str
    who: str  # the name an owner says aloud
    rows: list[dict[str, Any]]  # the buyer's receivables still to collect, due first
    inputs: CustomerInputs
    ctx: Context
    offer: dict[str, Any] | None  # the buyer's open offer (`deal_offers.open_offer`)
    offer_state: DealState | None  # the decision record's state of that offer
    verdict: Verdict | None
    picture: dict[str, Any] | None  # the offer picture, when it could be read
    conc: dict[str, Any] | None  # the concentration (strategy.types.Concentration as the exposure block carries it); None when unreadable
    exposure: dict[str, Any] | None  # the exposure block, when the flag is on and it could be read
    planned: dict[str, int] = field(default_factory=dict)  # invoice -> the advance the plan FLOW has ready (not run) would take on it

    @property
    def recommended(self) -> dict[str, Any] | None:
        return next((p for p in (self.picture or {}).get("paths", []) if p.get("recommended")), None)

    @property
    def lead(self) -> str:
        rec = self.recommended
        return rec["key"] if rec is not None else assembly.ASKED

    def decision_id(self) -> str | None:
        return deal_id(self.offer["offer_id"]) if self.offer is not None else None

    def input(self, f: InputField) -> CustomerInputRecord | None:
        return self.inputs.latest.get((self.buyer_id, f.value))


# ---------------------------------------------------------------- economics (the owner's inputs and the two products of them)


PROJECTION_DAYS = 365  # annual sales projected from the books look this far ahead


class _Basis(Protocol):
    """What a year's contribution is worked out from: the books, the day, the buyer and the owner's inputs. `_Read` is one;
    `Held` (the exposure routes' customer context) is the other."""

    @property
    def state(self) -> FinancialState: ...
    @property
    def today(self) -> int: ...
    @property
    def buyer_id(self) -> str: ...
    def input(self, f: InputField) -> CustomerInputRecord | None: ...


@dataclass(frozen=True)
class Held:
    """The buyer's basis outside the overview's own read: just the books, the day, the buyer and the inputs in force."""

    state: FinancialState
    today: int
    buyer_id: str
    inputs: CustomerInputs

    def input(self, f: InputField) -> CustomerInputRecord | None:
        return self.inputs.latest.get((self.buyer_id, f.value))


def _projected_sales_fen(r: _Basis) -> int | None:
    """The buyer's sales over the next 12 months from the books, for when the owner has entered none: every invoice the buyer's recurring
    schedule issues in the window (`recurring_issue_days`) and every receivable of the buyer still to be issued in it. An invoice issued
    before today is past sales and not counted. None when the books schedule nothing for the buyer."""
    lo, hi = r.today, r.today + PROJECTION_DAYS
    total = sum(ri.face_fen * len(recurring_issue_days(ri, lo, hi)) for ri in r.state.recurring_invoices if ri.counterparty_id == r.buyer_id)
    total += sum(x.face_fen for x in r.state.receivables if x.counterparty_id == r.buyer_id and lo <= x.issue_day < hi and x.status != "FAILED")
    return total or None


def _sales(r: _Basis) -> tuple[int, CustomerInputRecord | None] | None:
    """(annual sales in fen, the owner's row when it is theirs): the owner's input overrides; else the books' projection (no row)."""
    rec = r.input(InputField.ANNUAL_SALES_FEN)
    if rec is not None and isinstance(v := value_of(rec), int) and not isinstance(v, bool):
        return v, rec
    projected = _projected_sales_fen(r)
    return (projected, None) if projected is not None else None


DEMO_PROVENANCE = "DEMO"  # the provenance of the default margin: never stored, never passed as the owner's


@dataclass(frozen=True)
class Margin:
    """The gross margin held for a buyer. `record` is the row in force (the owner's or the Demo seed's); None means no row exists and the
    Demo's default stands. The one predicate for "assumed for the Demo" is `assumed`: no row, or a row the Demo itself entered
    (provenance DEMO either way); every surface that shows the margin or a figure worked out from it says so by it."""

    bp: int
    record: CustomerInputRecord | None
    provenance: str

    @property
    def assumed(self) -> bool:
        return self.provenance == DEMO_PROVENANCE


def _margin(r: _Basis) -> Margin:
    """The one place the margin is read, for the overview, its economics rows and the exposure routes' customer context: the row in
    force when there is one, else the Demo's default margin (`config.DEMO_GROSS_MARGIN_BP`) whatever the books are called."""
    rec = r.input(InputField.MARGIN_BP)
    if rec is not None and isinstance(v := value_of(rec), int) and not isinstance(v, bool):
        return Margin(v, rec, DEMO_PROVENANCE if rec.entered_by == DEMO_ENTERED_BY else rec.provenance)
    return Margin(DEMO_GROSS_MARGIN_BP, None, DEMO_PROVENANCE)


def _demo_words(lang: Lang) -> str:
    return t(lang, "assumed for the Demo, not confirmed by you", "为演示而假设，尚未经您确认")


def _contribution_fen(r: _Basis) -> int | None:
    """A year's contribution: annual sales (the owner's, else the books' projection) times the margin (the owner's, else the Demo's
    default), half-up to the fen (ADR-0002). None unless sales are held."""
    sales = _sales(r)
    if sales is None:
        return None
    return round_half_up(Fraction(sales[0] * _margin(r).bp, 10_000))


def _about_big(fen: int, lang: Lang) -> str:
    """A year's figure at a glance: "about ¥1.09m" (one formatter, rounded once from the fen)."""
    return t(lang, f"about {fmt_yuan_about_short(fen)}", f"约 {fmt_yuan_about_short(fen, zh=True)}")


def _source(rec: CustomerInputRecord, lang: Lang) -> tuple[str, str]:
    """(the words for where a fact came from, their tone): the Demo's own assumption is said so and is never passed as the owner's."""
    if rec.entered_by == DEMO_ENTERED_BY:
        return _demo_words(lang), "warn"
    return provenance_words(rec.provenance, lang), "neutral"


def _percent(value: int) -> str:
    return f"{value // 100}%" if value % 100 == 0 else fmt_pct(bp(value))


def _ask(r: _Read) -> dict[str, Any] | None:
    """The open request on a 12-month basis, the offer picture's own: the verdict's forward concession over the mandate's horizon,
    scaled to twelve months, with the one-off discount (the picture's display) beside it and never added. None without a request."""
    if r.offer is None or r.verdict is None:
        return None
    forward = r.verdict.forward_concession_total_fen
    months = _months(r.ctx.mandate.forward_concession_horizon_days)
    year = round_half_up(Fraction(forward * 12, months)) if forward > 0 else 0
    asked = next((p for p in (r.picture or {}).get("paths", []) if p["key"] == assembly.ASKED), None)
    once = asked.get("cost_once_display") if asked is not None else None
    return {"year_fen": year, "once_display": once} if year > 0 or once else None


def _economics(r: _Read) -> tuple[list[dict[str, Any]], str]:
    lang = r.lang
    rows: list[dict[str, Any]] = []
    missing = t(lang, "not entered yet", "尚未填写")

    def put(key: str, label: str, value: str, note: str | None, tone: str = "neutral", entered: bool = True) -> None:
        """`entered`: the row holds a value (the owner's input, the books' projection or the Demo's default), false for "not entered yet",
        so the page never matches the string."""
        rows.append({"key": key, "label": label, "value_display": value, "note": note, "tone": tone, "entered": entered})

    margin, klass = _margin(r), r.input(InputField.CLASSIFICATION)
    sales = _sales(r)
    if sales is not None and sales[1] is not None:
        note, tone = _source(sales[1], lang)
        put("annual_sales", t(lang, "Annual sales", "年销售额"), whole_yuan(sales[0]), note, tone)
    elif sales is not None:  # the owner entered none: the books' own schedule, said so
        put("annual_sales", t(lang, "Annual sales", "年销售额"), whole_yuan(sales[0]), t(lang, "projected from your books", "根据您的账目推算"))
    else:
        put("annual_sales", t(lang, "Annual sales", "年销售额"), missing, None, entered=False)
    note, tone = (_demo_words(lang), "warn") if margin.assumed or margin.record is None else _source(margin.record, lang)
    put("gross_margin", t(lang, "Gross margin", "毛利率"), _percent(margin.bp), note, tone)
    contribution = _contribution_fen(r)
    ask = _ask(r)
    if contribution is not None:
        put("contribution", t(lang, "Contribution a year", "每年贡献"), t(lang, f"about {fmt_yuan_rounded(contribution)}", f"约 {fmt_yuan_rounded(contribution)}"),
            t(lang, "under today's terms", "按现行条款"))
    if ask is not None:
        year, once = ask["year_fen"], ask["once_display"]
        label = t(lang, "The open request", "当前的请求")
        if year > 0 and contribution is not None and contribution > 0:
            ratio = Fraction(year, contribution)
            core = (t(lang, "more than the whole year's contribution", "超过其一整年的贡献") if ratio > 1
                    else t(lang, f"about {share_text(ratio, lang)} of it", f"约占其中的 {share_text(ratio, lang)}"))
            extra = t(lang, f", plus {once} once", f"，另加一次性 {once}") if once else ""
            put("open_request", label, t(lang, f"{core} as asked, over 12 months{extra}", f"按对方要求，12 个月内{core}{extra}"),
                t(lang, "the cost of keeping the same sales on softer terms, not profit gained",
                  "这是在更宽松的条款下保住同样销售额的成本，不是多赚的利润"))
        elif year <= 0 and once:  # a one-off cost has no yearly share
            put("open_request", label, t(lang, f"once, {once}", f"一次性 {once}"),
                t(lang, "a one-off cost, so it has no share of a year", "这是一次性成本，因此不按年计算占比"))
    if klass is not None and isinstance(v := value_of(klass), str):
        en, zh = _CLASSES.get(v.strip().upper(), (v, v))
        put("classification", t(lang, "Classed as", "客户分类"), t(lang, en, zh), t(lang, "context only", "仅供参考"))
    else:
        put("classification", t(lang, "Classed as", "客户分类"), missing, None, entered=False)
    never = t(lang, "None of this changes what FLOW may do on its own.", "这些都不会改变 FLOW 可以自行处理的范围。")
    if contribution is not None and ask is not None:
        year, once = ask["year_fen"], ask["once_display"]
        cost_en = f"a {fmt_yuan_about(year)} concession over 12 months" if year > 0 else f"a {once} one-off concession"
        cost_zh = f"12 个月内 {fmt_yuan_about(year)} 的让步" if year > 0 else f"一次性 {once} 的让步"
        worth = _about_big(contribution, lang)
        note = t(lang, f"A customer worth {worth.removeprefix('about ')} a year does not by itself justify {cost_en}; the question is how "
                       f"much of that is at risk if you counter. {never}",
                 f"一位每年价值{worth.removeprefix('约 ')}的客户，本身并不足以说明值得做{cost_zh}；"
                 f"关键是如果您还价，其中有多少会面临风险。{never}")
    else:
        note = never
    return rows, note


# ---------------------------------------------------------------- the state words (ticket #120)

NO_STATE: dict[str, str] = {"state": "none", "state_text": ""}
_COLLECTION_ORDER = ("PROMISE_MISSED", "OVERDUE", "DUE_SOON", "CURRENT")  # the worst first: an overdue invoice outranks one not yet due


def _financing_word(lang: Lang, state: State) -> dict[str, str]:
    """The financing state as the page draws it: `state` lower case, `state_text` the word the receivable rows say it with
    ("Arranged", "已安排"); none for no financing."""
    word = state_word(lang, state)
    return {"state": state.lower(), "state_text": _up(word)} if word else NO_STATE


def _collection(row: dict[str, Any]) -> dict[str, str]:
    """An invoice's collection state: the receivable row's own `collection_state` and `collection_state_text`."""
    return {"state": str(row["collection_state"]).lower(), "state_text": str(row["collection_state_text"])}


def _worst_collection(rows: list[dict[str, Any]]) -> dict[str, str]:
    """The collection state of the open invoices taken together: the worst of the rows' own, none without an open invoice."""
    if not rows:
        return NO_STATE
    return _collection(min(rows, key=lambda x: _COLLECTION_ORDER.index(x["collection_state"])))


def _financed(r: _Read) -> list[dict[str, Any]]:
    return [x for x in r.rows if x["financing_state"] in ("ARRANGED", "RECEIVED")]


def _financing_state(r: _Read) -> dict[str, str]:
    """The one state of the buyer's financing: the state of the advance lot behind the financed invoices (`state_of`, the function `financing_state_words` says it
    with) when they share one; PLANNED when none is financed yet and the ready plan would finance one of the buyer's invoices
    (`state_of(None, planned=True)`); none when nothing is financed, when the invoices are in more than one state (as the text says) or when
    an invoice is marked financed with no advance on record."""
    financed = _financed(r)
    if financed:
        if len({x["financing_state"] for x in financed}) > 1:
            return NO_STATE
        first = next(x for x in r.state.receivables if x.id == financed[0]["receivable_id"])
        return _financing_word(r.lang, state_of(advance_lot(r.state, first)))
    if any(x["net"].get("unrecorded_text") for x in r.rows):
        return NO_STATE
    if _planned_rows(r):
        return _financing_word(r.lang, state_of(None, planned=True))
    return NO_STATE


def _planned_rows(r: _Read) -> list[dict[str, Any]]:
    """The buyer's open invoices the ready plan would finance, when none is financed yet and none is marked financed without a record."""
    if _financed(r) or any(x["net"].get("unrecorded_text") for x in r.rows):
        return []
    return [x for x in r.rows if x["receivable_id"] in r.planned]


def _if_plan_runs(lang: Lang) -> str:
    return t(lang, "if you run the plan · not counted as cash", "执行方案后才会到账 · 不计入现金")


# ---------------------------------------------------------------- the four figures


def _figure(key: str, label: str, value: str, note: str, tone: str = "neutral", state: dict[str, str] | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "value_display": value, "note": note, "tone": tone, **(state or NO_STATE)}


def _outstanding(r: _Read) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Outstanding", "未收款")
    if not r.rows:
        return _figure("outstanding", label, whole_yuan(0), t(lang, "nothing is owed by them", "目前没有应收款"))
    total = sum(x["outstanding_fen"] for x in r.rows)
    late = [x for x in r.rows if x["past_due"]]
    waiting = [x for x in r.rows if not x["past_due"]]
    if late:
        note = t(lang, f"{whole_yuan(sum(x['outstanding_fen'] for x in late))} overdue", f"其中 {whole_yuan(sum(x['outstanding_fen'] for x in late))} 已逾期")
        if waiting:
            note += t(lang, f"; next due {waiting[0]['due_when']}", f"；下一笔{waiting[0]['due_when']}到期")
        return _figure("outstanding", label, whole_yuan(total), note, "bad", _worst_collection(r.rows))
    lead = "due" if len(r.rows) == 1 else "next due"
    return _figure("outstanding", label, whole_yuan(total),
                   t(lang, f"{lead} {r.rows[0]['due_when']}, nothing overdue", f"{r.rows[0]['due_when']}到期，没有逾期"),
                   state=_worst_collection(r.rows))


def _financing(r: _Read) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Financing linked", "已关联的融资")
    financed = _financed(r)
    state = _financing_state(r)
    unrecorded = next((x["net"]["unrecorded_text"] for x in r.rows if x["net"].get("unrecorded_text")), None)
    if not financed and unrecorded:  # marked financed, no advance on record: said so, never counted
        return _figure("financing", label, t(lang, "Not on record", "无记录"), unrecorded, "warn", state)
    planned = _planned_rows(r)
    if planned:  # the plan is ready and has not run: its advance, said as planned and never counted
        return _figure("financing", label, whole_yuan(sum(r.planned[x["receivable_id"]] for x in planned)), _if_plan_runs(lang), state=state)
    if not financed:
        return _figure("financing", label, t(lang, "None", "无"),
                       t(lang, f"nothing is financed against {r.who}'s invoices", f"没有以{r.who}的发票做融资"), state=state)
    total = sum(x["net"]["advance_fen"] for x in financed)
    states = {x["financing_state"] for x in financed}
    if len(states) > 1:
        return _figure("financing", label, whole_yuan(total), t(lang, "in more than one state; see the invoices", "处于不同阶段，详见发票"),
                       state=state)
    first = next(x for x in r.state.receivables if x.id == financed[0]["receivable_id"])
    return _figure("financing", label, whole_yuan(total), financing_state_words(lang, advance_lot(r.state, first), r.today)["text"], state=state)


def _share(r: _Read) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Share of what you are owed", "占您应收款的比例")
    c = r.conc
    if c is None:
        return _figure("share", label, "—", t(lang, "could not be read just now", "暂时无法读取"))
    if c["is_aggregate"]:
        return _figure("share", label, "—", c["aggregate_note"] or "")
    if c["ar_total_fen"] <= 0:
        return _figure("share", label, "—", t(lang, "nothing is owed to you", "目前没有应收款"))
    n = len(r.rows)
    count = t(lang, "no open invoice" if n == 0 else "one open invoice" if n == 1 else f"{n} open invoices",
              "没有未收发票" if n == 0 else f"{n} 张未收发票")
    if c.get("annual_sales_share_bp") is not None:  # only when the inputs hold it
        tail = t(lang, f"{share_text(Fraction(c['annual_sales_share_bp'], 10_000), lang)} of your sales",
                 f"占您销售额的 {share_text(Fraction(c['annual_sales_share_bp'], 10_000), lang)}")
    else:
        tail = t(lang, "not its share of your sales", "这不是其占您销售额的比例")
    share = c.get("ar_share_bp")
    tone = "warn" if share is not None and share >= assembly.MATERIAL_SHARE_BP else "neutral"
    return _figure("share", label, share_text(Fraction(c["ar_buyer_fen"], c["ar_total_fen"]), lang),
                   t(lang, f"{count}; {tail}", f"{count}；{tail}"), tone)


def _value_figure(r: _Read, contribution: int | None) -> dict[str, Any]:
    """The relationship value, with the Demo-margin qualifier while the margin behind it is the Demo's (as `customer_context` says it)."""
    lang = r.lang
    label = t(lang, "Relationship value", "客户关系价值")
    if contribution is None:
        return _figure("value", label, t(lang, "Not known yet", "暂不清楚"),
                       t(lang, "enter annual sales and gross margin to estimate it", "填写年销售额和毛利率后即可估算"))
    note = t(lang, "a year, estimated contribution", "每年，估算的贡献")
    if _margin(r).assumed:
        note += t(lang, f"; margin {_demo_words(lang)}", f"；毛利率{_demo_words(lang)}")
    return _figure("value", label, _about_big(contribution, lang), note)


def customer_context(state: FinancialState, inputs: CustomerInputs, buyer_id: str, today: int, conc: dict[str, Any] | None,
                     lang: Lang) -> dict[str, Any]:
    """Why this customer matters, in the words of the Customer page's own figures, for the exposure routes (`customer_context`): a year's
    contribution (`_contribution_fen`, the one function, with the Demo-margin qualifier while the margin is the Demo's default), what the
    buyer owes now, its share of what you are owed (from the concentration block `conc`; none for a name that stands for many small
    customers) and the way to its page. A word the books cannot support is None."""
    held = Held(state, today, buyer_id, inputs)
    contribution = _contribution_fen(held)
    note: str | None = None
    if contribution is not None:
        note = t(lang, "a year, estimated", "每年，估算")
        if _margin(held).assumed:
            note += t(lang, f"; margin {_demo_words(lang)}", f"；毛利率{_demo_words(lang)}")
    owed = conc is not None and not conc["is_aggregate"]
    return {
        "contribution_display": _about_big(contribution, lang) if contribution is not None else None,
        "contribution_note": note,
        "owes_display": whole_yuan(conc["ar_buyer_fen"]) if conc is not None and owed else None,
        "share_text": (share_text(Fraction(conc["ar_buyer_fen"], conc["ar_total_fen"]), lang)
                       if conc is not None and owed and conc["ar_total_fen"] > 0 else None),
        "profile_href": f"/customers/{_quoted(buyer_id)}",
    }


# ---------------------------------------------------------------- the decision and the actions


def _invoice_of(r: _Read) -> str | None:
    """The invoice the pages open on: the one an open counter would apply to, else the first still to collect."""
    pending = next((x for x in r.rows if x["pending_counter"] is not None), None)
    lead = pending or (r.rows[0] if r.rows else None)
    return lead["receivable_id"] if lead is not None else None


def _actions(r: _Read) -> list[dict[str, str]]:
    lang = r.lang
    invoice = _invoice_of(r)
    pages = f"customer={_quoted(r.buyer_id)}" + (f"&invoice={_quoted(invoice)}" if invoice else "")
    out = [{"key": "invoices", "label": t(lang, "View the invoices", "查看发票"), "href": f"/receivables?{pages}"}]
    if _exposure_on() and r.rows:  # a late-payment test needs an invoice still to collect
        stress = f"/cash?stress={_quoted(r.buyer_id)}:{assembly.STRESS_DELAY_DAYS}" + (f"&invoice={_quoted(invoice)}" if invoice else "")
        out.append({"key": "stress", "label": t(lang, "Stress-test payment", "测试晚付的影响"), "href": stress})
    return out


def _authority_sentence(path: dict[str, Any], subject: Literal["counter", "request"], lang: Lang) -> str | None:
    """Who decides, as a sentence that stands alone, from the deal picture's own authority class for the path (never a second rule). A path
    with no class (unpriced, not drawn) keeps the picture's words."""
    sentences = {
        ("counter", FLOW_MAY): ("FLOW can send this counter without your approval.", "FLOW 可以在无需您批准的情况下发送这份还价。"),
        ("counter", NEEDS_OWNER): ("This counter needs your approval before it is sent.", "这份还价需要您批准后才能发送。"),
        ("counter", OVER_LIMIT): ("This counter is over a limit you signed: only a new mandate changes that.",
                                  "这份还价超出您签署的上限：只有签署新的授权才能改变。"),
        ("request", FLOW_MAY): ("FLOW can accept this request without your approval.", "FLOW 可以在无需您批准的情况下接受这项请求。"),
        ("request", NEEDS_OWNER): ("This request needs your approval before FLOW accepts it.", "这项请求需要您批准后 FLOW 才能接受。"),
        ("request", OVER_LIMIT): ("This request is over a limit you signed: only a new mandate changes that.",
                                  "这项请求超出您签署的上限：只有签署新的授权才能改变。"),
    }
    pair = sentences.get((subject, str(path.get("authority"))))
    return t(lang, *pair) if pair is not None else path.get("authority_text")


def _decision(r: _Read, actions: list[dict[str, str]]) -> tuple[dict[str, Any] | None, str]:
    lang = r.lang
    none = t(lang, f"No commercial decision is waiting for you with {r.who}.", f"目前没有需要您对{r.who}作出的商务决定。")
    offer = r.offer
    if offer is None:
        return None, none
    asks = offer["asks_text"]
    wants = (t(lang, f"{r.who} wants {asks}.", f"{r.who}要求：{asks}。") if asks
             else t(lang, f"{r.who} has made a request.", f"{r.who}提出了一项请求。"))
    if r.offer_state == DealState.RECEIVED:  # received, not read yet: nothing to recommend and no authority to state
        return {
            "kind": "offer_received", "eyebrow": t(lang, "One offer waits to be read", "有一份报价等待阅读"),
            "text": f"{wants} {offer['action_text']}" if lang != "zh" else f"{wants}{offer['action_text']}",
            "headline_short": None, "authority_text": None,
            "primary": {"label": t(lang, "Read the offer", "阅读报价"), "href": f"/deals?decision={_quoted(r.decision_id() or '')}"},
            "secondary": actions}, none
    rec = r.recommended
    if rec is not None and rec["kind"] == "reply":
        cost = rec["cost_display"]
        if rec.get("cost_once_display") and not rec.get("cost_forward_display"):
            how = t(lang, f"{rec['label']}, {cost} once if accepted", f"{rec['label']}（如被接受，一次性成本 {cost}）")
        else:
            how = t(lang, f"{rec['label']} ({cost}; {rec['cost_note']})", f"{rec['label']}（{cost}；{rec['cost_note']}）")
        body = t(lang, f"{wants} FLOW recommends countering with {how}.", f"{wants}FLOW 建议以{how}还价。")
        label = t(lang, "Review the counter", "查看还价")
        authority = _authority_sentence(rec, "counter", r.lang)
    else:
        short = offer["headline_short"] or offer["action_text"]
        body = t(lang, f"{wants} {short}.", f"{wants}{short}。")
        label = t(lang, "Review the request", "查看请求")
        asked = next((p for p in (r.picture or {}).get("paths", []) if p["key"] == assembly.ASKED), None)
        authority = _authority_sentence(asked, "request", r.lang) if asked is not None else None
    path = f"&path={_quoted(r.lead)}" if rec is not None else ""
    return {
        "kind": "counter" if rec is not None and rec["kind"] == "reply" else "request",
        "eyebrow": t(lang, "One commercial decision waits for you", "有一项商务决定等待您处理"),
        "text": body, "headline_short": offer["headline_short"], "authority_text": authority,
        "primary": {"label": label, "href": f"/deals?decision={_quoted(r.decision_id() or '')}{path}"},
        "secondary": actions}, none


# ---------------------------------------------------------------- the exposure panel


def _row(key: str, label: str, value: str, note: str | None = None, tone: str = "neutral", state: dict[str, str] | None = None) -> dict[str, Any]:
    return {"key": key, "label": label, "value_display": value, "note": note, "tone": tone, **(state or NO_STATE)}


def _stress_value(row: dict[str, Any], lang: Lang) -> tuple[str, str]:
    if not row["available"]:
        return row["unavailable_text"], "neutral"
    if row["breach_days"] == 0:
        return t(lang, "cash stays above your minimum on every day", "现金每天都高于您的最低现金"), "ok"
    low = f"{'−' if row['lowest_fen'] < 0 else ''}{whole_yuan(abs(row['lowest_fen']))}"
    need = whole_yuan(row["need_fen"])
    if row["plan_admissible"]:
        tail = t(lang, f"{need} covered by FLOW's committed plan", f"{need} 的缺口由 FLOW 已承诺的方案覆盖")
        if row["needs_owner"]:
            tail += t(lang, ", with your approval", "，需要您批准")
        tone = "warn"
    else:
        tail = t(lang, f"{need} uncovered", f"{need} 缺口无法覆盖")
        tone = "bad"
    return t(lang, f"{low} {row['lowest_when']}; {_days(row['breach_days'], lang)} below your minimum; {tail}",
             f"{row['lowest_when']}降至 {low}；有 {_days(row['breach_days'], lang)}低于您的最低现金；{tail}"), tone


def _financing_row(r: _Read) -> dict[str, Any]:
    lang = r.lang
    financed = _financed(r)
    label = t(lang, "Financing", "融资")
    unrecorded = next((x["net"]["unrecorded_text"] for x in r.rows if x["net"].get("unrecorded_text")), None)
    state_words = _financing_state(r)
    if not financed and unrecorded:
        return _row("financing", label, unrecorded, None, "warn", state_words)
    planned = _planned_rows(r)
    if planned:
        advance = sum(r.planned[x["receivable_id"]] for x in planned)
        face = sum(x["outstanding_fen"] for x in planned)
        value = (t(lang, f"{whole_yuan(advance)} against the {whole_yuan(face)} invoice", f"{whole_yuan(advance)}，以 {whole_yuan(face)} 的发票做融资")
                 if len(planned) == 1 else
                 t(lang, f"{whole_yuan(advance)} against {len(planned)} invoices", f"{whole_yuan(advance)}，以 {len(planned)} 张发票做融资"))
        return _row("financing", label, value, _if_plan_runs(lang), state=state_words)
    if not financed:
        return _row("financing", label, t(lang, "none against this customer's invoices", "没有以该客户发票做的融资"), state=state_words)
    advance = sum(x["net"]["advance_fen"] for x in financed)
    face = sum(x["outstanding_fen"] for x in financed)
    net = sum(x["net"]["net_fen"] for x in financed)
    if len(financed) == 1:
        value = t(lang, f"{whole_yuan(advance)} against the {whole_yuan(face)} invoice", f"{whole_yuan(advance)}，以 {whole_yuan(face)} 的发票做融资")
    else:
        value = t(lang, f"{whole_yuan(advance)} against {len(financed)} invoices", f"{whole_yuan(advance)}，以 {len(financed)} 张发票做融资")
    state = next(x for x in r.state.receivables if x.id == financed[0]["receivable_id"])
    state_text = (financing_state_words(lang, advance_lot(r.state, state), r.today)["text"]
                  if len({x["financing_state"] for x in financed}) == 1 else None)
    parts = [state_text,
             t(lang, "repaid from the receipt", "由回款偿还"),
             t(lang, f"{_about_short(net, lang)} then becomes available cash", f"之后约有 {fmt_yuan_about(net)} 成为可用现金")]
    return _row("financing", label, value, t(lang, "; ", "；").join(p for p in parts if p), state=state_words)


def _about_short(fen: int, lang: Lang) -> str:
    return t(lang, f"about {fmt_yuan_about(fen)}", f"约 {fmt_yuan_about(fen)}")


def _financing_then(r: _Read, delay: int) -> dict[str, Any] | None:
    """What the financing costs when the buyer pays late: the rows' own per-period charges (`net_words`), said for the standing delay."""
    lang = r.lang
    financed = [x["net"] for x in r.rows if x["financing_state"] in ("ARRANGED", "RECEIVED") and x["net"]["per_period_more_fen"] > 0]
    if not financed:
        return None
    label = t(lang, "The financing then", "届时的融资")
    if all(n["period_days"] == delay for n in financed):
        more = sum(n["per_period_more_fen"] for n in financed)
        value = t(lang, f"runs {delay} days longer; {_about_short(more, lang)} more in charges",
                  f"多持续 {delay} 天；费用约增加 {fmt_yuan_about(more)}")
    else:
        value = t(lang, f"runs {delay} days longer; ", f"多持续 {delay} 天；") + financed[0]["per_period_text"]
    return _row("financing_then", label, value)


def _capacity_row(r: _Read, ex: dict[str, Any]) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Spare capacity", "可用余量")
    view = ex["capacity"].get(r.lead)
    spare = view.get("spare") if view and view.get("available") else None
    if spare is None:
        return _row("capacity", label, t(lang, "not available", "暂无法计算"))

    def amount(fen: int | None) -> str:
        return t(lang, "none", "无") if fen is None else whole_yuan(fen)

    today = t(lang, f"{amount(spare['today_fen'])} today", f"今天 {amount(spare['today_fen'])}")
    if r.offer is None:
        return _row("capacity", label, today)
    rec = r.recommended
    after = (t(lang, f"if {r.who} accepts {rec['label']}", f"如果{r.who}接受{rec['label']}") if rec is not None
             else t(lang, "if you accept as asked", "如果您按对方要求接受"))
    value = t(lang, f"{today}; {amount(spare['x_star_fen'])} {after}", f"{today}；{after}，{amount(spare['x_star_fen'])}")
    return _row("capacity", label, value, ex["band"]["by_path"][r.lead]["capacity"])


def _exposure(r: _Read) -> dict[str, Any] | None:
    ex = r.exposure
    if ex is None:
        return None
    lang = r.lang
    rows: list[dict[str, Any]] = []
    paid = ex["payments"]
    label = t(lang, "Payment behaviour", "付款表现")
    if paid is None:
        rows.append(_row("payments", label, ex["payments_note"] or ""))
    elif paid["insufficient"]:
        rows.append(_row("payments", label, t(lang, "not enough history yet", "付款记录还不够"), paid["insufficient_text"]))
    else:
        rows.append(_row("payments", label, paid["sentence"]))
    rows.append(_financing_row(r))
    stress = ex["stress"]["paths"].get(r.lead) or ex["stress"]["now"]
    value, tone = _stress_value(stress, lang)
    rows.append(_row("stress", t(lang, f"Paid {assembly.STRESS_DELAY_DAYS} days late", f"晚付 {assembly.STRESS_DELAY_DAYS} 天"), value, None, tone))
    if stress["available"]:
        then = _financing_then(r, stress["delay_days"])
        if then is not None:
            rows.append(then)
    rows.append(_capacity_row(r, ex))
    return {"rows": rows, "same_figures_note": t(
        lang, "The same figures as on the deal, on Receivables and on Cash: one comparison, read once.",
        "与交易、应收款和现金页面上的数字相同：同一项比较，只读取一次。")}


# ---------------------------------------------------------------- the history


def _mine(e: LoggedEntry, rids: set[str], buyer_id: str, agreements: set[str]) -> bool:
    p = e.payload or {}
    if p.get("receivable_id") in rids or p.get("counterparty_id") == buyer_id or p.get("buyer_id") == buyer_id:
        return True
    message = e.result.message or ""
    return any(cid in message for cid in agreements)


def _financing_event(r: _Read, e: LoggedEntry) -> tuple[str, dict[str, str]] | None:
    """(the sentence, the state) of an invoice-financing entry in the financing words' own state (arranged, received, repaid), never
    "drawn" for a lot whose cash has not landed; a request with no lot yet has no state. None when the entry names no invoice the books know."""
    lang = r.lang
    rcv = next((x for x in r.state.receivables if x.id == (e.payload or {}).get("receivable_id")), None)
    advance = (e.payload or {}).get("advance_fen")
    if rcv is None or not isinstance(advance, int):
        return None
    lot = advance_lot(r.state, rcv)
    repaid = lot is None and rcv.status != "FINANCED"
    words = financing_state_words(lang, lot, r.today, repaid=repaid)
    state = _financing_word(lang, state_of(lot, repaid=repaid))
    amount, face = whole_yuan(advance), whole_yuan(rcv.face_fen)
    if words["state"] == "NONE":
        return (t(lang, f"Invoice financing of {amount} was requested against the {face} invoice.",
                  f"已就 {face} 的发票申请 {amount} 的融资。"), state)
    tail = words["text"].removeprefix(t(lang, "financing ", "融资"))
    return t(lang, f"Invoice financing of {amount} against the {face} invoice: {tail}.", f"以 {face} 的发票做 {amount} 的融资：{tail}。"), state


def _receipt_event(r: _Read, e: LoggedEntry) -> tuple[str, dict[str, str]] | None:
    """(the sentence, the state) of a receipt as the receipt: its amount and the invoice, never the bank's reference (an id has no place
    in a Business sentence). The state is the collection state of the invoice if it is still to collect (the rows' own), else none."""
    lang = r.lang
    p = e.payload or {}
    rcv = next((x for x in r.state.receivables if x.id == p.get("receivable_id")), None)
    amount = p.get("amount_fen")
    if not isinstance(amount, int) or rcv is None:
        return None
    open_row = next((x for x in r.rows if x["receivable_id"] == rcv.id), None)
    return (t(lang, f"The receipt of {whole_yuan(amount)} against the {whole_yuan(rcv.face_fen)} invoice came in.",
              f"已收到 {whole_yuan(amount)}，对应 {whole_yuan(rcv.face_fen)} 的发票。"),
            _collection(open_row) if open_row is not None else NO_STATE)


def _agreement_event(r: _Read, e: LoggedEntry) -> str | None:
    """An accepted offer as the agreement it booked (the Activity page's own words), found by the commitment its message names."""
    cmt = next((c for c in r.ctx.commitments if c.id in (e.result.message or "") and c.counterparty_id == r.buyer_id), None)
    return agreement_words(r.state, cmt.counterparty_id, cmt.forward_value_fen, r.lang) if cmt is not None else None


def _history(r: _Read) -> list[dict[str, Any]]:
    lang = r.lang
    out: list[dict[str, Any]] = []
    if r.offer is not None:
        o = r.offer
        asked = (t(lang, f"Asked for {o['asks_text']}. ", f"对方提出：{o['asks_text']}。") if o["asks_text"] else "")
        out.append({"when_text": _up(o["received_when"] or when_text(r.today, r.today, lang)), "text": asked + o["action_text"],
                    "href": f"/deals?decision={_quoted(r.decision_id() or '')}", "link_label": t(lang, "The deal", "该交易"), **NO_STATE})
    state, ctx = r.state, r.ctx
    rids = {x.id for x in state.receivables if x.counterparty_id == r.buyer_id}
    agreements = {c.id for c in ctx.commitments if c.counterparty_id == r.buyer_id}
    names = {c.id: party_name(state, c.counterparty_id) for c in ctx.commitments}
    decided = {a.id for a in ctx.approvals if str(getattr(a.status, "value", a.status)) != "PENDING"}
    known = ctx.states()
    entries = sorted((e for e in ctx.entries if e.day is not None and e.result.status not in _SKIP_STATUS and "CLOCK" not in e.kind.upper()
                      and not (e.result.status == OperationStatus.PENDING_APPROVAL and e.result.approval_id in decided)
                      and _mine(e, rids, r.buyer_id, agreements)), key=lambda e: (-(e.day or 0), -e.seq))
    for e in entries[:LOG_ROWS]:
        words = event_words(state, kind=e.kind, status=e.result.status.value, payload=e.payload, message=e.result.message,
                            approval_id=e.result.approval_id, day=e.day, today=r.today, lang=lang,
                            decided=e.result.approval_id in decided, agreements=names, window_live=False)
        said = (_financing_event(r, e) if e.kind == "SUBMIT_INVOICE_FOR_FINANCING"
                else _receipt_event(r, e) if e.kind == "RECEIVE_PAYMENT" else None)
        text, words_of = said if said is not None else (
            _agreement_event(r, e) if e.kind in _AGREEMENTS and e.result.status == OperationStatus.EXECUTED else None, NO_STATE)
        text = text or t(lang, " ", "").join(x.strip() for x in (words["event_text"], words["event_detail"]) if x)
        if not text:
            continue
        did = decision_id_for(e.payload, e.idempotency_key, ctx.commitments, approval_id=e.result.approval_id)
        href = f"/decisions/{_quoted(did)}" if did is not None and did in known else None
        agreement = e.kind in _AGREEMENTS
        label = t(lang, "The agreement", "协议") if agreement else t(lang, "The record", "记录")
        out.append({"when_text": _up(when_text(e.day, r.today, lang)), "text": text, "href": href,
                    "link_label": label if href else None, **words_of})
    if r.rows:
        g = r.rows[0]["governed_by"]
        out.append({"when_text": t(lang, "In force", "现行"),
                    "text": t(lang, f"{g['terms_text']}; early payment: {r.rows[0]['early_payment']['text']}",
                              f"{g['terms_text']}；提前付款：{r.rows[0]['early_payment']['text']}"),
                    "href": "/documents" if g["contract_ref"] else None,
                    "link_label": t(lang, "The terms", "条款") if g["contract_ref"] else None, **NO_STATE})
    return out


# ---------------------------------------------------------------- reading


def _find_offer(rt: Runtime, ctx: Context, buyer_id: str, lang: Lang
                ) -> tuple[dict[str, Any] | None, DealState | None, CompiledOffer | None, Verdict | None]:
    found = open_offers(ctx, lang).get(buyer_id)
    if found is None:
        return None, None, None, None
    offer = found[0]
    return offer, found[1], rt.store.get_offer(offer["offer_id"]), latest_verdict_for(rt, offer["offer_id"])


def _read_exposure(rt: Runtime, state: FinancialState, buyer_id: str, offer_id: str, verdict: Verdict | None, today: int,
                   lang: Lang, inputs: CustomerInputs) -> dict[str, Any] | None:
    """The exposure block for the buyer, on the books without the open offer's own commitments (the offer as asked); None when the books
    cannot be projected (the panel then says nothing rather than something wrong)."""
    try:
        mandate = rt.store.get_mandate()
        held = tuple(c for c in rt.store.commitments() if c.offer_id != offer_id)
        books = current_books(state, held)
        return assembly.buyer_exposure(rt, books, mandate, rt.day, buyer_id, offer_id, verdict, lang, held, inputs)
    except EngineError:
        log.exception("the exposure could not be read for the customer overview")
        return None


def _planned_financing(rt: Runtime, state: FinancialState, rows: list[dict[str, Any]], today: int, lang: Lang) -> tuple[dict[str, int], bool]:
    """(the buyer's invoices the ready plan would finance, each with its advance, whether it could be read): the invoice-financing legs of the plan the Home shows
    as its next action (`home.next_action`, the same reading), for the buyer's invoices still to collect that are not financed yet. A plan
    that has run is not a plan (its alert is gone and its lots are the books'). Nothing is read when no such invoice is open."""
    if not any(x["financing_state"] not in ("ARRANGED", "RECEIVED") for x in rows):
        return {}, True
    try:
        mandate = rt.store.get_mandate()
        found = alerts(state, mandate, rt.store, rt.day)
        books = current_books(state, rt.store.commitments())
        action = next_action(books.state, books.with_([]), mandate, found, rt.store.approvals(), today, state.state_version, lang,
                             use_router=rt.settings.features.debt_desk)
    except EngineError:
        log.exception("the plan could not be read for the customer overview")
        return {}, False
    if action is None or action["kind"] != "RESERVE_BREACH_AHEAD":
        return {}, True
    mine = {x["receivable_id"] for x in rows}
    out: dict[str, int] = {}
    for leg in action["legs"]:
        rid = leg.get("receivable_id")
        if leg["operation_kind"] == "SUBMIT_INVOICE_FOR_FINANCING" and rid in mine and isinstance(leg.get("amount_fen"), int):
            out[rid] = out.get(rid, 0) + leg["amount_fen"]
    return out, True


def _build(rt: Runtime, buyer_id: str, lang: Lang) -> tuple[dict[str, Any], bool]:
    """(the page, whether it is whole): a read that fell back (a supporting read that failed, `partial`) is returned but never cached."""
    state, today, body, partial = read_rows(rt, lang)
    name = party_name(state, buyer_id)
    rows = [x for x in body["rows"] if x["buyer_id"] == buyer_id]
    inputs = inputs_from_store(rt.store)
    ctx = load_context(rt, found=[])
    offer, offer_state, compiled, verdict = _find_offer(rt, ctx, buyer_id, lang)
    offer_id = offer["offer_id"] if offer is not None and compiled is not None else ""
    whole = partial.view(lang) is None
    picture: dict[str, Any] | None = None
    if offer is not None and verdict is not None:
        try:
            pic = cached_picture(rt, offer["offer_id"], lang)
            picture = pic if pic.get("available") else None
        except Exception:  # a supporting read: the decision then reads from the Deals read's own words
            log.exception("the offer picture could not be read for the customer overview")
            whole = False
    exposure_block: dict[str, Any] | None = None
    if _exposure_on():
        exposure_block = _read_exposure(rt, state, buyer_id, offer_id, verdict if offer_id else None, today, lang, inputs)
        whole = whole and exposure_block is not None
    shares: dict[str, Any] | None
    if exposure_block is not None:
        shares = exposure_block["concentration"]
    else:
        try:
            held = tuple(c for c in rt.store.commitments() if c.offer_id != offer_id)
            shares = concentration(current_books(state, held), buyer_id, rt.day, inputs, lang=lang).model_dump(mode="json")
        except EngineError:
            log.exception("the concentration could not be read for the customer overview")
            shares, whole = None, False
    planned, planned_read = _planned_financing(rt, state, rows, today, lang)
    whole = whole and planned_read
    r = _Read(rt=rt, lang=lang, state=state, today=today, buyer_id=buyer_id, name=name, who=buyer_short(name), rows=rows, inputs=inputs,
              ctx=ctx, offer=offer, offer_state=offer_state, verdict=verdict if offer is not None else None, picture=picture, conc=shares, exposure=exposure_block, planned=planned)
    econ_rows, econ_note = _economics(r)
    actions = _actions(r)
    decision, none_text = _decision(r, actions)
    figures = [_value_figure(r, _contribution_fen(r)), _outstanding(r), _financing(r), _share(r)]
    return {
        "customer_id": buyer_id, "name": name, "lang": lang, "day": today, "state_version": state.state_version,
        "summary_text": t(lang, "What this relationship is worth, and what it puts at risk.", "这段客户关系的价值，以及它带来的风险。"),
        "figures": figures,
        "decision": decision, "none_text": none_text if decision is None else None, "actions": actions,
        "economics": econ_rows, "economics_note": econ_note,
        # the inputs sheet is Phase 2 (FEATURE_CUSTOMER_ECONOMICS): until it is on there is nowhere to send the owner, and the label stays
        "edit_label": t(lang, "Edit these facts", "修改这些信息"),
        "edit_href": f"/inputs?customer={_quoted(buyer_id)}" if _economics_on() else None,
        "exposure": _exposure(r),
        "note": _exposure_note(lang, exposure_block, shares is not None),
        "history": _history(r),
        "partial": partial.view(lang),
    }, whole


def _exposure_note(lang: Lang, block: dict[str, Any] | None, shares_read: bool = True) -> str | None:
    """Why `exposure` is null: the flag is off, or the books could not be read for it (or for the share beside it)."""
    if block is not None and shares_read:
        return None
    if shares_read and not _exposure_on():
        return t(lang, "Financial exposure is not switched on for this account, so payment behaviour, the late-payment test and spare "
                       "capacity are not shown.", "此账户未开启财务风险敞口功能，因此不显示付款表现、晚付测试和可用余量。")
    return t(lang, "The financial exposure could not be read just now.", "暂时无法读取财务风险敞口。")


def _cached(rt: Runtime, buyer_id: str, lang: Lang) -> dict[str, Any]:
    """The page for the buyer, cached on what it reads: the books, the mandate, the day, the commitments, the inputs, the flags, the
    store's change marker (counts of log entries, verdicts, approvals, decisions and contract records) and the session's inbound
    documents (an offer received and not yet evaluated surfaces through them). Nothing is loaded in full for the key."""
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    key = cache_key(state, mandate, max(rt.day, state.as_of_day), tuple(rt.store.commitments()), "customer-overview", buyer_id, lang,
                    inputs_from_store(rt.store).digest(), _exposure_on(), _economics_on(), rt.store.change_marker(), tuple(rt.documents))
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    body, whole = _build(rt, buyer_id, lang)
    if whole:
        _CACHE.put(key, body)
    return body


# ---------------------------------------------------------------- the back link (built from the query, never cached)


def _back(rt: Runtime, state: FinancialState, buyer_id: str, who: str, lang: Lang, decision: str | None, path: str | None,
          invoice: str | None) -> dict[str, str]:
    """Where the page was opened from: the deal (with the path that was selected), else the invoices (with the invoice), else Deals.
    A query that names nothing of this buyer's is ignored, never echoed."""
    offer_id = offer_id_of(decision) if decision and _SAFE.fullmatch(decision) else None
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is not None and offer.counterparty_id == buyer_id:
        tail = f"&path={_quoted(path)}" if path and _SAFE.fullmatch(path) else ""
        return {"label": deal_back_label(lang, who), "href": f"/deals?decision={_quoted(decision or '')}{tail}"}
    if invoice and any(x.id == invoice and x.counterparty_id == buyer_id for x in state.receivables):
        return {"label": t(lang, "Back to the invoices", "返回发票"),
                "href": f"/receivables?customer={_quoted(buyer_id)}&invoice={_quoted(invoice)}"}
    return {"label": t(lang, "Back to Deals", "返回交易"), "href": "/deals"}


def _selected_deal(rt: Runtime, buyer_id: str, decision: str | None) -> str | None:
    """The deal the page was opened on, when the query names one of this buyer's offers (else None, never echoed)."""
    offer_id = offer_id_of(decision) if decision and _SAFE.fullmatch(decision) else None
    offer = rt.store.get_offer(offer_id) if offer_id else None
    return decision if offer is not None and offer.counterparty_id == buyer_id else None


_SCENARIO = re.compile(r"asked|counter:[0-9]{1,3}")


def _selected_scenario(rt: Runtime, deal: str | None, scenario: str | None) -> str | None:
    """The scenario the page was opened on, validated as the exposure reads validate `response`: `asked`, or `counter:<k>` when the deal's
    verdict has a k-th counter-offer; none without a deal (a scenario is of a deal), and never an echo of anything else."""
    if deal is None or not scenario or not _SCENARIO.fullmatch(scenario):
        return None
    if scenario == "asked":
        return scenario
    offer_id = offer_id_of(deal)
    verdict = latest_verdict_for(rt, offer_id) if offer_id else None
    return scenario if verdict is not None and int(scenario.split(":")[1]) < len(verdict.counters) else None


@router.get("/customers/{customer_id}/overview")
def get_overview(customer_id: str, lang: Literal["en", "zh"] = Query("en"), decision: str | None = Query(None, max_length=120),
                 path: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120),
                 scenario: str | None = Query(None, max_length=120)) -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        buyer = next((c for c in state.counterparties if c.id == customer_id and c.role == "BUYER"), None)
        if buyer is None:
            raise HTTPException(404, detail={"code": "CUSTOMER_NOT_FOUND", "message": f"There is no customer {customer_id} on the books."})
        body = _cached(rt, customer_id, lang)
        back = _back(rt, state, customer_id, buyer_short(buyer.name), lang, decision, path, invoice)
        deal = _selected_deal(rt, customer_id, decision)
    # the three selections (Home V2's URL state), echoed when they name this buyer's: a `scenario` needs a deal to be a scenario of
    return {**body, "context": {"back": back, "customer": customer_id, "deal": deal, "scenario": _selected_scenario(rt, deal, scenario)}}
