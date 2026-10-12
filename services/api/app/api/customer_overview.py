"""GET /customers/{customer_id}/overview: what a buyer is worth to the owner and what it puts at risk (map #88, ticket #108, the server half).

    GET /customers/{customer_id}/overview?lang=en|zh&decision=<id>&path=<key>&invoice=<id>

One page's read, composed from reads the other pages already make; nothing is priced, projected or decided here:

    figures[4]      relationship value, outstanding, financing linked (with its state word), share of what you are owed
    decision        the one commercial decision waiting (the open offer's headline, the recommended path and its cost, the authority
                    sentence) with its actions, else null with `none_text`
    actions[2]      view the invoices; stress-test payment (the second only while the exposure flag is on)
    economics       the owner's inputs for the buyer (sales, margin, classification) and the two figures they give
    exposure        payment behaviour, financing, the 30-day late-payment stress, what the financing then costs, spare capacity:
                    the exposure layer's own block (`app.strategy.exposure`); null, with `note`, while FEATURE_EXPOSURE is off
    history         the open offer, the buyer's entries in the log, the terms in force
    context.back    {label, href} built from the query: `decision` (+ `path`) back to /deals, `invoice` back to /receivables

The sources are `inputs_from_store` (customer inputs and their provenance), `receivable_rows` (the net, the financing state, the
agreement, the pending counter), `deal_offers.open_offers` and the offer picture (the recommended path, its cost and authority), the
exposure layer (concentration, payments, stress, capacity) and the decision record's log. The only arithmetic is the owner's two
products of their own inputs: a year's contribution (sales times margin) and the open request's cost as a share of it.

Every sentence is written for `lang` through `t(lang, en, zh)` (INVARIANT 13); no id appears in a sentence (hrefs carry them). The
share of the buyer's sales is never stated unless the concentration holds it. Cached on the books, the mandate, the day, the
commitments, the buyer, the language, the inputs, the log and the flag (the query only builds `context`, outside the cache).
Context, not mandate: nothing here changes a verdict, a cap or what FLOW may do alone.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_owner
from app.api.deal_offers import open_offers
from app.api.decisions import Context, latest_verdict_for, load_context
from app.api.offer_picture import cached_picture
from app.api.presentation import Lang, event_words, party_name, t, when_text
from app.api.receivables import read_rows
from app.api.runtime import Runtime, get_runtime
from app.books import current_books
from app.config import get_settings
from app.decisions.identity import deal_id, decision_id_for, offer_id_of
from app.domain.models import CompiledOffer, FinancialState, OperationStatus, Verdict
from app.domain.money import bp, fmt_pct, fmt_yuan_about, round_half_up
from app.financial import EngineError
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
_SKIP_STATUS = (OperationStatus.DUPLICATE, OperationStatus.REFUSED)


def clear_cache() -> None:
    _CACHE.clear()


def _exposure_on() -> bool:
    return bool(get_settings().features.exposure)


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
    verdict: Verdict | None
    picture: dict[str, Any] | None  # the offer picture, when it could be read
    conc: Any  # strategy.types.Concentration
    exposure: dict[str, Any] | None  # the exposure block, when the flag is on and it could be read

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


def _contribution_fen(r: _Read) -> int | None:
    """A year's contribution: the owner's annual sales times the owner's margin, half-up to the fen (ADR-0002). None unless both are held."""
    sales, margin = r.input(InputField.ANNUAL_SALES_FEN), r.input(InputField.MARGIN_BP)
    if sales is None or margin is None:
        return None
    s, m = value_of(sales), value_of(margin)
    if not isinstance(s, int) or not isinstance(m, int) or isinstance(s, bool) or isinstance(m, bool):
        return None
    return round_half_up(Fraction(s * m, 10_000))


def _about_big(fen: int, lang: Lang) -> str:
    """A year's figure at a glance: "about ¥1.09m" from a million, else the house's "about" rounding."""
    yuan = round_half_up(Fraction(abs(fen), 100))
    sign = "−" if fen < 0 else ""
    if yuan >= 1_000_000:
        return t(lang, f"about {sign}¥{round_half_up(Fraction(yuan, 10_000)) / 100:.2f}m", f"约 {sign}¥{round_half_up(Fraction(yuan, 10_000))} 万")
    return t(lang, f"about {fmt_yuan_about(fen)}", f"约 {fmt_yuan_about(fen)}")


def _about_whole(fen: int, lang: Lang) -> str:
    return t(lang, f"about ¥{round_half_up(Fraction(fen, 100)):,}", f"约 ¥{round_half_up(Fraction(fen, 100)):,}")


def _source(rec: CustomerInputRecord, lang: Lang) -> tuple[str, str]:
    """(the words for where a fact came from, their tone): the Demo's own assumption is said so and is never passed as the owner's."""
    if rec.entered_by == DEMO_ENTERED_BY:
        return t(lang, "assumed for the Demo, not confirmed by you", "为演示而假设，尚未经您确认"), "warn"
    return provenance_words(rec.provenance, lang), "neutral"


def _percent(value: int) -> str:
    return f"{value // 100}%" if value % 100 == 0 else fmt_pct(bp(value))


def _cost_fen(r: _Read) -> int | None:
    return r.verdict.forward_concession_total_fen if r.offer is not None and r.verdict is not None else None


def _economics(r: _Read) -> tuple[list[dict[str, Any]], str]:
    lang = r.lang
    rows: list[dict[str, Any]] = []
    missing = t(lang, "not entered yet", "尚未填写")

    def put(key: str, label: str, value: str, note: str | None, tone: str = "neutral") -> None:
        rows.append({"key": key, "label": label, "value_display": value, "note": note, "tone": tone})

    sales, margin, klass = (r.input(InputField.ANNUAL_SALES_FEN), r.input(InputField.MARGIN_BP), r.input(InputField.CLASSIFICATION))
    if sales is not None and isinstance(v := value_of(sales), int):
        note, tone = _source(sales, lang)
        put("annual_sales", t(lang, "Annual sales", "年销售额"), whole_yuan(v), note, tone)
    else:
        put("annual_sales", t(lang, "Annual sales", "年销售额"), missing, None)
    if margin is not None and isinstance(v := value_of(margin), int):
        note, tone = _source(margin, lang)
        put("gross_margin", t(lang, "Gross margin", "毛利率"), _percent(v), note, tone)
    else:
        put("gross_margin", t(lang, "Gross margin", "毛利率"), missing, None)
    contribution = _contribution_fen(r)
    cost = _cost_fen(r)
    if contribution is not None:
        put("contribution", t(lang, "Contribution a year", "每年贡献"), _about_whole(contribution, lang),
            t(lang, "under today's terms", "按现行条款"))
        if cost is not None and contribution > 0:
            put("open_request", t(lang, "The open request", "当前的请求"),
                t(lang, f"about {share_text(Fraction(cost, contribution), lang)} of it as asked",
                  f"按对方要求约占其中的 {share_text(Fraction(cost, contribution), lang)}"),
                t(lang, "the cost of keeping the same sales on softer terms, not profit gained",
                  "这是在更宽松的条款下保住同样销售额的成本，不是多赚的利润"))
    if klass is not None and isinstance(v := value_of(klass), str):
        en, zh = _CLASSES.get(v.strip().upper(), (v, v))
        put("classification", t(lang, "Classed as", "客户分类"), t(lang, en, zh), t(lang, "context only", "仅供参考"))
    else:
        put("classification", t(lang, "Classed as", "客户分类"), missing, None)
    never = t(lang, "None of this changes what FLOW may do on its own.", "这些都不会改变 FLOW 可以自行处理的范围。")
    if contribution is not None and cost is not None:
        note = t(lang, f"A customer worth {_about_big(contribution, lang).removeprefix('about ')} a year does not by itself justify "
                       f"a {fmt_yuan_about(cost)} concession; the question is how much of that is at risk if you counter. {never}",
                 f"一位每年价值{_about_big(contribution, lang).removeprefix('约 ')}的客户，本身并不足以说明值得做 {fmt_yuan_about(cost)} 的让步；"
                 f"关键是如果您还价，其中有多少会面临风险。{never}")
    else:
        note = never
    return rows, note


# ---------------------------------------------------------------- the four figures


def _figure(key: str, label: str, value: str, note: str, tone: str = "neutral") -> dict[str, Any]:
    return {"key": key, "label": label, "value_display": value, "note": note, "tone": tone}


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
        return _figure("outstanding", label, whole_yuan(total), note, "bad")
    lead = "due" if len(r.rows) == 1 else "next due"
    return _figure("outstanding", label, whole_yuan(total),
                   t(lang, f"{lead} {r.rows[0]['due_when']}, nothing overdue", f"{r.rows[0]['due_when']}到期，没有逾期"))


def _financing(r: _Read) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Financing linked", "已关联的融资")
    financed = [x for x in r.rows if x["financing_state"] in ("ARRANGED", "RECEIVED")]
    if not financed:
        return _figure("financing", label, t(lang, "None", "无"),
                       t(lang, f"nothing is financed against {r.who}'s invoices", f"没有以{r.who}的发票做融资"))
    total = sum(x["net"]["advance_fen"] for x in financed)
    states = {x["financing_state"] for x in financed}
    if len(states) > 1:
        return _figure("financing", label, whole_yuan(total), t(lang, "in more than one state; see the invoices", "处于不同阶段，详见发票"))
    first = next(x for x in r.state.receivables if x.id == financed[0]["receivable_id"])
    return _figure("financing", label, whole_yuan(total), financing_state_words(lang, advance_lot(r.state, first), r.today)["text"])


def _share(r: _Read) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Share of what you are owed", "占您应收款的比例")
    c = r.conc
    if c.is_aggregate:
        return _figure("share", label, "—", c.aggregate_note or "")
    if c.ar_total_fen <= 0:
        return _figure("share", label, "—", t(lang, "nothing is owed to you", "目前没有应收款"))
    n = len(r.rows)
    count = t(lang, "no open invoice" if n == 0 else "one open invoice" if n == 1 else f"{n} open invoices",
              "没有未收发票" if n == 0 else f"{n} 张未收发票")
    if c.annual_sales_share_bp is not None:  # only when the inputs hold it
        tail = t(lang, f"{share_text(Fraction(c.annual_sales_share_bp, 10_000), lang)} of your sales",
                 f"占您销售额的 {share_text(Fraction(c.annual_sales_share_bp, 10_000), lang)}")
    else:
        tail = t(lang, "not its share of your sales", "这不是其占您销售额的比例")
    tone = "warn" if c.ar_share_bp is not None and c.ar_share_bp >= assembly.MATERIAL_SHARE_BP else "neutral"
    return _figure("share", label, share_text(Fraction(c.ar_buyer_fen, c.ar_total_fen), lang), t(lang, f"{count}; {tail}", f"{count}；{tail}"), tone)


def _value_figure(r: _Read, contribution: int | None) -> dict[str, Any]:
    lang = r.lang
    label = t(lang, "Relationship value", "客户关系价值")
    if contribution is None:
        return _figure("value", label, t(lang, "Not known yet", "暂不清楚"),
                       t(lang, "enter annual sales and gross margin to estimate it", "填写年销售额和毛利率后即可估算"))
    return _figure("value", label, _about_big(contribution, lang), t(lang, "a year, estimated contribution", "每年，估算的贡献"))


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


def _decision(r: _Read, actions: list[dict[str, str]]) -> tuple[dict[str, Any] | None, str]:
    lang = r.lang
    none = t(lang, f"No commercial decision is waiting for you with {r.who}.", f"目前没有需要您对{r.who}作出的商务决定。")
    offer = r.offer
    if offer is None:
        return None, none
    asks = offer["asks_text"]
    wants = (t(lang, f"{r.who} wants {asks}.", f"{r.who}要求：{asks}。") if asks
             else t(lang, f"{r.who} has made a request.", f"{r.who}提出了一项请求。"))
    rec = r.recommended
    if rec is not None and rec["kind"] == "reply":
        cost = rec["cost_display"]
        if rec.get("cost_once_display") and not rec.get("cost_forward_display"):
            how = t(lang, f"{rec['label']}, {cost} once if accepted", f"{rec['label']}（如被接受，一次性成本 {cost}）")
        else:
            how = t(lang, f"{rec['label']} ({cost}; {rec['cost_note']})", f"{rec['label']}（{cost}；{rec['cost_note']}）")
        body = t(lang, f"{wants} FLOW recommends countering with {how}.", f"{wants}FLOW 建议以{how}还价。")
        label = t(lang, "Review the counter", "查看还价")
        authority = rec["authority_text"]
    else:
        short = offer["headline_short"] or offer["action_text"]
        body = t(lang, f"{wants} {short}.", f"{wants}{short}。")
        label = t(lang, "Review the request", "查看请求")
        authority = (r.picture or {}).get("asked", {}).get("authority_text") if r.picture else None
    path = f"&path={_quoted(r.lead)}" if rec is not None else ""
    return {
        "eyebrow": t(lang, "One commercial decision waits for you", "有一项商务决定等待您处理"),
        "text": body, "headline_short": offer["headline_short"], "authority_text": authority,
        "primary": {"label": label, "href": f"/deals?decision={_quoted(r.decision_id() or '')}{path}"},
        "secondary": actions}, none


# ---------------------------------------------------------------- the exposure panel


def _row(key: str, label: str, value: str, note: str | None = None, tone: str = "neutral") -> dict[str, Any]:
    return {"key": key, "label": label, "value_display": value, "note": note, "tone": tone}


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
    financed = [x for x in r.rows if x["financing_state"] in ("ARRANGED", "RECEIVED")]
    label = t(lang, "Financing", "融资")
    if not financed:
        return _row("financing", label, t(lang, "none against this customer's invoices", "没有以该客户发票做的融资"))
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
    return _row("financing", label, value, t(lang, "; ", "；").join(p for p in parts if p))


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


def _history(r: _Read) -> list[dict[str, Any]]:
    lang = r.lang
    out: list[dict[str, Any]] = []
    if r.offer is not None:
        o = r.offer
        asked = (t(lang, f"Asked for {o['asks_text']}. ", f"对方提出：{o['asks_text']}。") if o["asks_text"] else "")
        out.append({"when_text": _up(o["received_when"] or when_text(r.today, r.today, lang)), "text": asked + o["action_text"],
                    "href": f"/deals?decision={_quoted(r.decision_id() or '')}"})
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
        text = t(lang, " ", "").join(x.strip() for x in (words["event_text"], words["event_detail"]) if x)
        if not text:
            continue
        did = decision_id_for(e.payload, e.idempotency_key, ctx.commitments, approval_id=e.result.approval_id)
        out.append({"when_text": _up(when_text(e.day, r.today, lang)), "text": text,
                    "href": f"/decisions/{_quoted(did)}" if did is not None and did in known else None})
    if r.rows:
        g = r.rows[0]["governed_by"]
        out.append({"when_text": t(lang, "In force", "现行"),
                    "text": t(lang, f"{g['terms_text']}; early payment: {r.rows[0]['early_payment']['text']}",
                              f"{g['terms_text']}；提前付款：{r.rows[0]['early_payment']['text']}"),
                    "href": "/documents" if g["contract_ref"] else None})
    return out


# ---------------------------------------------------------------- reading


def _find_offer(rt: Runtime, ctx: Context, buyer_id: str, lang: Lang) -> tuple[dict[str, Any] | None, CompiledOffer | None, Verdict | None]:
    found = open_offers(ctx, lang).get(buyer_id)
    if found is None:
        return None, None, None
    offer = found[0]
    return offer, rt.store.get_offer(offer["offer_id"]), latest_verdict_for(rt, offer["offer_id"])


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


def _build(rt: Runtime, buyer_id: str, lang: Lang) -> dict[str, Any]:
    state, today, body = read_rows(rt, lang)
    name = party_name(state, buyer_id)
    rows = [x for x in body["rows"] if x["buyer_id"] == buyer_id]
    inputs = inputs_from_store(rt.store)
    ctx = load_context(rt, found=[])
    offer, compiled, verdict = _find_offer(rt, ctx, buyer_id, lang)
    offer_id = offer["offer_id"] if offer is not None and compiled is not None else ""
    picture: dict[str, Any] | None = None
    if offer is not None and verdict is not None:
        try:
            pic = cached_picture(rt, offer["offer_id"], lang)
            picture = pic if pic.get("available") else None
        except Exception:  # a supporting read: the decision then reads from the Deals read's own words
            log.exception("the offer picture could not be read for the customer overview")
    exposure_block: dict[str, Any] | None = None
    if _exposure_on():
        exposure_block = _read_exposure(rt, state, buyer_id, offer_id, verdict if offer_id else None, today, lang, inputs)
    held = tuple(c for c in rt.store.commitments() if c.offer_id != offer_id)
    shares = concentration(current_books(state, held), buyer_id, rt.day, inputs, lang=lang)
    r = _Read(rt=rt, lang=lang, state=state, today=today, buyer_id=buyer_id, name=name, who=buyer_short(name), rows=rows, inputs=inputs,
              ctx=ctx, offer=offer, verdict=verdict if offer is not None else None, picture=picture, conc=shares, exposure=exposure_block)
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
        "edit_label": t(lang, "Edit these facts", "修改这些信息"), "edit_href": f"/inputs?customer={_quoted(buyer_id)}",
        "exposure": _exposure(r),
        "note": _exposure_note(lang, exposure_block),
        "history": _history(r),
    }


def _exposure_note(lang: Lang, block: dict[str, Any] | None) -> str | None:
    """Why `exposure` is null: the flag is off, or the books could not be read for it."""
    if block is not None:
        return None
    if not _exposure_on():
        return t(lang, "Financial exposure is not switched on for this account, so payment behaviour, the late-payment test and spare "
                       "capacity are not shown.", "此账户未开启财务风险敞口功能，因此不显示付款表现、晚付测试和可用余量。")
    return t(lang, "The financial exposure could not be read just now.", "暂时无法读取财务风险敞口。")


def _cached(rt: Runtime, buyer_id: str, lang: Lang) -> dict[str, Any]:
    state, mandate = rt.store.get_state(), rt.store.get_mandate()
    commitments = tuple(rt.store.commitments())
    inputs = inputs_from_store(rt.store)
    verdict_ids = "|".join(f"{v.id}" for v in rt.store.verdicts())
    key = cache_key(state, mandate, max(rt.day, state.as_of_day), commitments, "customer-overview", buyer_id, lang, inputs.digest(),
                    _exposure_on(), verdict_ids, len(rt.store.operations()), len(rt.store.approvals()), len(rt.store.contract_records()))
    return _CACHE.get_or_compute(key, lambda: _build(rt, buyer_id, lang))


# ---------------------------------------------------------------- the back link (built from the query, never cached)


def _back(rt: Runtime, state: FinancialState, buyer_id: str, who: str, lang: Lang, decision: str | None, path: str | None,
          invoice: str | None) -> dict[str, str]:
    """Where the page was opened from: the deal (with the path that was selected), else the invoices (with the invoice), else Deals.
    A query that names nothing of this buyer's is ignored, never echoed."""
    offer_id = offer_id_of(decision) if decision and _SAFE.fullmatch(decision) else None
    offer = rt.store.get_offer(offer_id) if offer_id else None
    if offer is not None and offer.counterparty_id == buyer_id:
        tail = f"&path={_quoted(path)}" if path and _SAFE.fullmatch(path) else ""
        return {"label": t(lang, f"Back to the {who} deal", f"返回与{who}的交易"), "href": f"/deals?decision={_quoted(decision or '')}{tail}"}
    if invoice and any(x.id == invoice and x.counterparty_id == buyer_id for x in state.receivables):
        return {"label": t(lang, "Back to the invoices", "返回发票"),
                "href": f"/receivables?customer={_quoted(buyer_id)}&invoice={_quoted(invoice)}"}
    return {"label": t(lang, "Back to Deals", "返回交易"), "href": "/deals"}


@router.get("/customers/{customer_id}/overview")
def get_overview(customer_id: str, lang: Literal["en", "zh"] = Query("en"), decision: str | None = Query(None, max_length=120),
                 path: str | None = Query(None, max_length=120), invoice: str | None = Query(None, max_length=120)) -> dict[str, Any]:
    rt = get_runtime()
    with rt.lock:
        state = rt.store.get_state()
        buyer = next((c for c in state.counterparties if c.id == customer_id and c.role == "BUYER"), None)
        if buyer is None:
            raise HTTPException(404, detail={"code": "CUSTOMER_NOT_FOUND", "message": f"There is no customer {customer_id} on the books."})
        body = _cached(rt, customer_id, lang)
        back = _back(rt, state, customer_id, buyer_short(buyer.name), lang, decision, path, invoice)
    return {**body, "context": {"back": back}}
