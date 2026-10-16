"""GET /demo/story and POST /demo/restore: where the Demo's six-scene story stands (Slice D, map #121, ticket #145; owner's decisions #136).

The browser keeps running each step through the existing routes (`apps/web/lib/demo.ts`); this read only says where the story stands and
what the one next control is. Where it stands is DERIVED FROM THE BOOKS, never stored: the story's offer received (ask), its verdict
(decide), its agreement (agree), the synthetic bank receipt (bank), the clock at or past the late day (time), the cure queued (queue),
the approval answered (approve), the funding settled (settle). The three steps that change nothing (cash, outcome, proof) cannot be
derived: the optional `seen` parameter names the furthest of them the browser has shown, and the server accepts it only when every
book-changing step before it holds; a `seen` the books do not support is ignored, never an error.

The owner's step never carries an `action`: its `next` is a link to the approval, and the story never presses it. The restore
(`POST /demo/restore`) is the existing `rt.reset_demo("golden_sme")`; it cannot be logged as an operation (a reset wipes the operations
log, and the executor is in the stability set), so the swaps and restores are kept in `rt.demo_history` and read as `alternate.history`.

Presentation only: no money arithmetic; every sentence is written for `lang` through `t(lang, en, zh)` and carries no id or raw code.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_owner
from app.api.causality import chain_fields
from app.api.decisions import load_context
from app.api.presentation import party_name, t
from app.api.read import _op_view
from app.api.runtime import Runtime, get_runtime
from app.compiler.grounding import offer_id_for
from app.decisions.identity import deal_id
from app.domain.fixtures import offer_documents
from app.persistence.records import ApprovalStatus

router = APIRouter(dependencies=[Depends(require_owner)])
log = logging.getLogger("termsledger.demo")

MAIN = "golden_sme"
ALTERNATE = "busy"
STORY_FIXTURE = "EX01_PACKAGE"
LATE_DAY = 34  # the day the story lets time pass to (apps/web/lib/demo.ts LATE_DAY): a position on the clock, not a figure
BANK_PREFIX = "DEMO-RCPT"

# (step id, scene id, book-changing, owner's own click); the order of the story
STEPS = (("ask", "buyer", True, False), ("decide", "decision", True, False), ("agree", "agreement", True, False),
         ("cash", "agreement", False, False), ("bank", "reality", True, False), ("time", "reality", True, False),
         ("queue", "owner", True, False), ("approve", "owner", True, True), ("settle", "owner", True, False),
         ("outcome", "proof", False, False), ("proof", "proof", False, False))
SCENES = ("buyer", "decision", "agreement", "reality", "owner", "proof")

_SCENE = {  # id -> (en, zh): the dictionary's `scene.*` without its number
    "buyer": ("The buyer asks", "买方提出请求"), "decision": ("FLOW decides", "FLOW 作出决定"),
    "agreement": ("The agreement acts on the books", "协议改变账目"), "reality": ("Reality diverges", "现实与承诺出现偏差"),
    "owner": ("The owner stays in control", "老板掌控全局"), "proof": ("Outcome and proof", "结果与证明"),
}
_STEP = {  # id -> (label en, label zh, description en, description zh, the control's label en, zh): `demo.step.*` and `demo.desc.*`
    "ask": ("The buyer's message arrives", "买方的消息送达",
            "The books are reset and the buyer's message is read. Deals shows it beside the terms FLOW found in it.",
            "账目已重置，买方的消息已被读取。交易页面把它与 FLOW 读出的条款并排展示。", "Receive the buyer's message", "接收买方的消息"),
    "decide": ("FLOW checks the offer", "FLOW 检查报价",
               "FLOW works out what the offer costs, what it does to cash, and the one response it recommends.",
               "FLOW 算出这份报价的成本、对现金的影响，以及它推荐的唯一回复。", "Check the offer", "检查报价"),
    "agree": ("The recommended counter is sent and agreed", "发送并达成推荐的反报价",
              "The recommended counter goes to the simulated buyer, who accepts. The agreement and its funding are booked.",
              "推荐的反报价发给模拟买方，买方接受。协议及其融资已记入账目。", "Send the recommended counter", "发送推荐的反报价"),
    "cash": ("Cash now, and what is still arriving", "现在的现金，以及仍在途中的资金",
             "Cash shows what is in hand now, what is still on its way, and what the agreement did to the books.",
             "现金页面显示手头现金、仍在途中的资金，以及协议对账目做了什么。", "See the cash", "查看现金"),
    "bank": ("Bank: the agreed early payment arrives (synthetic)", "银行：约定的提前付款到账（模拟）",
             "A synthetic bank event posts the one receipt of the story, the early payment the buyer agreed to. The clock never records a receipt.",
             "一次模拟的银行事件登记故事中唯一的一笔收款，即买方约定的提前付款。时钟从不记录收款。", "Receive the bank payment", "接收银行付款"),
    "time": ("Time passes", "时间流逝",
             "The clock moves to the day the buyer's second payment is overdue. Nothing is recorded as received.",
             "时钟走到买方第二笔付款逾期的那一天。没有任何东西被记为已收到。", "Let time pass", "让时间流逝"),
    "queue": ("The cure is queued for the owner", "解决方案排队等待老板批准",
              "The cure costs more than the agent may approve alone, so it waits for the owner. Nothing has run.",
              "这项解决方案的成本超过代理可独自批准的上限，因此等待老板。尚未执行任何操作。", "Queue the cure for the owner", "把解决方案交给老板批准"),
    "approve": ("The owner approves", "老板批准",
                "FLOW prepared the funding plan. It is outside what FLOW may run alone, so it waits for the owner, who decides on the approval card.",
                "FLOW 已准备好融资方案。它超出了 FLOW 可独自执行的范围，因此等待老板，由老板在批准卡上作出决定。", "Review the approval", "查看批准事项"),
    "settle": ("Time passes: the funding settles", "时间流逝：资金到账",
               "The clock moves to the day after the funding lands, so the cash is in hand and no longer in transit.",
               "时钟走到资金到账的次日，于是这笔钱已在手头，不再在途中。", "Let the funding settle", "让资金到账"),
    "outcome": ("Where the books stand", "账目现在的状况", "Home shows today's cash and the risk that remains.",
                "首页显示今天的现金和剩余的风险。", "See where the books stand", "查看账目现状"),
    "proof": ("The record and the proof", "记录与证明",
              "Activity lists everything that happened, with what changed, why it matters and what remains. The evidence export can be checked on its own.",
              "动态页面列出发生的一切，包括变了什么、为什么重要以及还剩什么。证据导出可以单独核验。", "Open the record and the proof", "打开记录与证明"),
}
_STATE_TEXT = {"done": ("Done", "已完成"), "current": ("Now", "进行中"), "next": ("Next", "下一步"), "locked": ("Later", "稍后")}
_SCENARIO_TITLE = {"busy": ("Busy company", "繁忙的公司"), "golden_sme": ("The main books", "主账目"),
                   "short_facilities": ("Short facilities", "额度不足"), "public_sme": ("Public company", "上市公司"),
                   "blank": ("Blank books", "空白账目"), "own": ("Your own books", "您自己的账目")}
OWN = "own"  # the books the owner opened through the setup (`app.api.setup`): never a demo scenario, and never called one
_HINT = {  # id -> (en, zh): where the control takes you or what it does (never the step's own description)
    "ask": ("Opens Deals on the buyer's message.", "在交易页面打开买方的消息。"),
    "decide": ("Opens Deals with FLOW's reading of the offer.", "在交易页面打开 FLOW 对报价的解读。"),
    "agree": ("Sends the counter and opens the agreement.", "发送反报价并打开协议。"),
    "cash": ("Opens Cash. Nothing changes.", "打开现金页面。不会改变任何内容。"),
    "bank": ("One synthetic bank receipt, then the clock moves.", "登记一笔模拟银行收款，然后时钟前进。"),
    "time": ("Moves the clock to the overdue day and opens Home.", "把时钟推进到逾期当天并打开首页。"),
    "queue": ("Queues the cure and opens it in Approvals.", "把解决方案排入队列，并在批准事项中打开。"),
    "approve": ("Opens the approval. Approve there, then come back.", "打开批准事项。请在那里作出决定，然后回来。"),
    "settle": ("Moves the clock to when the funding lands and opens Cash.", "把时钟推进到资金到账之日，并打开现金页面。"),
    "outcome": ("Opens Home on where the books stand.", "在首页打开账目现状。"),
    "proof": ("Opens Activity, the record of everything that happened.", "打开动态页面，查看发生的一切记录。"),
}
_ENGINE = (("Signed mandate", "已签名授权书", "/mandate"), ("Cash line", "现金线", "/trajectory"), ("Debt Desk", "融资台", "/funding"),
           ("Verdict", "裁决", "/verdict"), ("Ledger", "账本", "/ledger"), ("Evidence export", "证据导出", "/evidence"),
           ("Alerts", "预警", "/alerts"), ("Reconciliation", "对账", "/reconciliation"), ("Security", "安全", "/security"))


def _plural(n: int, one_en: str, many_en: str) -> str:
    return f"{n} {one_en if n == 1 else many_en}"


@dataclass
class _Books:
    """What the books say about the story, read once under the runtime lock."""

    offer_id: str
    holds: dict[str, bool]
    cure: Any  # the approval of the cure the story queued, or None
    ops: list[tuple[Any, dict[str, Any], dict[str, Any]]]  # (record, payload, result)


def _json(raw: str) -> dict[str, Any]:
    try:
        v = json.loads(raw)
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _read_books(rt: Runtime) -> _Books:
    store = rt.store
    offer_id = offer_id_for(offer_documents(STORY_FIXTURE))
    ops = [(o, _json(o.payload_json), _json(o.result_json)) for o in store.operations()]
    approvals = store.approvals()
    cure = next((a for a in reversed(approvals) if str(a.op_id or "").startswith("alert:")), None)
    lots = store.get_state().lots
    holds = {
        "ask": store.get_offer(offer_id) is not None,
        "decide": any(v.offer_id == offer_id for v in store.verdicts()),
        "agree": any(c.offer_id == offer_id for c in store.commitments()),
        "bank": any(o.kind == "RECEIVE_PAYMENT" and res.get("status") == "EXECUTED" and str(p.get("bank_reference", "")).startswith(BANK_PREFIX)
                    for o, p, res in ops),
        "time": rt.day >= LATE_DAY,
        "queue": cure is not None,
        "approve": cure is not None and cure.status == ApprovalStatus.APPROVED,
        "settle": cure is not None and any(x.settled and (x.id == cure.op_id or x.id.startswith(f"{cure.op_id}#")) for x in lots),
    }
    return _Books(offer_id, holds, cure, ops)


def _with_views(holds: dict[str, bool], seen: str | None) -> dict[str, bool]:
    """Every step's `holds`: a view step holds once the browser has shown it (or one after it) and the book-changing steps before it hold."""
    out = dict(holds)
    view_ids = [s for s, _, books, _ in STEPS if not books]
    shown = -1
    if seen in view_ids:
        before = [s for s, _, books, _ in STEPS[:[x[0] for x in STEPS].index(seen)] if books]
        if all(holds[s] for s in before):
            shown = [x[0] for x in STEPS].index(seen)
    for i, (sid, _, books, _) in enumerate(STEPS):
        if not books:
            out[sid] = i <= shown
    return out


def _states(holds: dict[str, bool], available: bool) -> tuple[dict[str, str], dict[str, str], int | None]:
    """(step states, scene states, the index of the current step or None when the story is complete or unavailable)."""
    ids = [s[0] for s in STEPS]
    if not available:
        return dict.fromkeys(ids, "locked"), dict.fromkeys(SCENES, "locked"), None
    cur = next((i for i, s in enumerate(ids) if not holds[s]), None)
    steps = {s: "done" if holds[s] else "current" if i == cur else "next" if cur is not None and i == cur + 1 else "locked"
             for i, s in enumerate(ids)}
    current_scene = STEPS[cur][1] if cur is not None else None
    scenes: dict[str, str] = {}
    for n, sc in enumerate(SCENES):
        mine = [s for s, scene, _, _ in STEPS if scene == sc]
        scenes[sc] = ("done" if all(holds[s] for s in mine) else "current" if sc == current_scene
                      else "next" if current_scene is not None and n == SCENES.index(current_scene) + 1 else "locked")
    return steps, scenes, cur


def _entry(books: _Books, kind: str, pick: Any = None) -> Any:
    """The first log record of `kind` (that `pick` accepts), as (record, payload, result), else None."""
    return next(((o, p, r) for o, p, r in books.ops if o.kind == kind and (pick is None or pick(o, p, r))), None)


def _view(rt: Runtime, rec: Any, lang: str, commitments: Any, agreements: Any) -> dict[str, Any]:
    state = rt.store.get_state()
    decided = frozenset(a.id for a in rt.store.approvals() if a.status != ApprovalStatus.PENDING)
    return _op_view(rec, state, rt.day, commitments, decided, agreements, None, lang)


def _results_and_proof(rt: Runtime, books: _Books, scenes: dict[str, str], lang: str) -> tuple[dict[str, str | None], dict[str, list[dict[str, str]]]]:
    """For each done scene, what happened in the books' own words and the links to the records it wrote (never a link to something absent)."""
    result: dict[str, str | None] = {}
    proof: dict[str, list[dict[str, str]]] = {}
    state = rt.store.get_state()
    commitments = rt.store.commitments()
    agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
    try:
        ctx_states = load_context(rt).states()
    except Exception:
        log.exception("the decision record could not be read for the demo story")
        ctx_states = {}
    offer = rt.store.get_offer(books.offer_id)
    who = party_name(state, offer.counterparty_id) if offer is not None else ""
    deal = deal_id(books.offer_id)

    def entry(rec: Any, label: str | None = None) -> dict[str, str]:
        from app.api.presentation import kind_text

        return {"label": label or kind_text(rec.kind, lang), "href": f"/trust?view=evidence&entry={rec.seq}&from=demo"}

    def sentence(found: Any) -> str | None:
        return _view(rt, found[0], lang, commitments, agreements).get("event_text") if found else None

    record = {"label": t(lang, "The deal's decision record", "这笔交易的决定记录"), "href": f"/decisions/{quote(deal, safe=':')}"}
    from app.api.lifecycle import AGREED_STATES, deal_href

    found_deal = ctx_states.get(deal)
    tracked = found_deal is not None and found_deal[0].state in AGREED_STATES and offer is not None
    track = ({"label": t(lang, "Track the deal", "跟踪这笔交易"), "href": deal_href(offer.counterparty_id, deal, "demo")} if tracked else None)
    for sc in SCENES:
        if scenes[sc] != "done":
            continue
        links: list[dict[str, str]] = []
        if sc == "buyer":
            result[sc] = t(lang, f"{who} asked for better terms and FLOW read the message.", f"{who}要求更好的条件，FLOW 已读取该消息。")
            links = [record] if deal in ctx_states else []
        elif sc == "decision":
            result[sc] = t(lang, "FLOW priced the offer and worked out the one response it recommends.", "FLOW 为报价定价，并算出它推荐的唯一回复。")
            links = [record] if deal in ctx_states else []
        elif sc == "agreement":
            found = _entry(books, "ACCEPT_OFFER") or _entry(books, "RECORD_COMMITMENT")
            result[sc] = sentence(found)
            draw = _entry(books, "DRAW_FACILITY")
            links = [entry(x[0]) for x in (found, draw) if x]
            links += [record] if deal in ctx_states else []
            links += [track] if track else []
        elif sc == "reality":
            bank = _entry(books, "RECEIVE_PAYMENT", lambda o, p, r: str(p.get("bank_reference", "")).startswith(BANK_PREFIX))
            late = _entry(books, "ADVANCE_CLOCK", lambda o, p, r: (r.get("effective_day") or p.get("to_day") or 0) >= LATE_DAY)
            result[sc] = " ".join(x for x in (sentence(bank), t(lang, "Time then passed and the second payment did not arrive.",
                                                               "随后时间流逝，第二笔付款没有到账。")) if x)
            links = [entry(x[0]) for x in (bank, late) if x]
        elif sc == "owner":
            cure = books.cure
            done = _entry(books, "SUBMIT_INVOICE_FOR_FINANCING", lambda o, p, r, c=cure: r.get("status") == "EXECUTED" and r.get("approval_id") == c.id)
            result[sc] = sentence(done) or t(lang, "The cure was queued and the owner decided.", "解决方案已排队，老板已作出决定。")
            links = [{"label": t(lang, "The approval", "批准事项"), "href": f"/approvals#approval-{quote(cure.id, safe='')}"}]
            cure_decision = next((d for d in ctx_states if d.startswith("alert:")), None)
            if cure_decision:
                links.append({"label": t(lang, "The cure's decision record", "这项解决方案的决定记录"), "href": f"/decisions/{quote(cure_decision, safe=':')}"})
            links += [entry(done[0])] if done else []
        else:
            n = len(books.ops)
            result[sc] = t(lang, f"The record holds {n} entries and every one is kept.", f"记录中共有 {n} 条，且每一条都已保留。")
            links = [{"label": t(lang, "The full record", "完整记录"), "href": "/trust?view=evidence&from=demo"},
                     {"label": t(lang, "Security", "安全"), "href": "/trust?view=security&from=demo"}]
            links += [track] if track else []
        proof[sc] = links
    return result, proof


def _next(lang: str, available: bool, cur: int | None, books: _Books, rejected: bool, scenario: str | None = None) -> dict[str, Any]:
    if not available and scenario == "blank":
        return {"label": t(lang, "Set up your books", "设置您的账目"), "action": None, "href": "/setup",
                "hint_text": t(lang, "Blank books hold nothing yet. The setup takes you through your business and opens them as your own.",
                               "空白账目里还没有任何内容。设置向导会带您录入您的业务，并把它们开立为您自己的账目。"), "owner": False}
    if not available and scenario == OWN:
        return {"label": t(lang, "Open Home on your books", "在您的账目上打开首页"), "action": None, "href": "/",
                "hint_text": t(lang, "These are your own books. The story runs on the demo's main books; restoring them replaces yours.",
                               "这些是您自己的账目。故事在演示的主账目上进行；恢复主账目会替换您的账目。"), "owner": False}
    if not available:
        return {"label": t(lang, "Open Home on these books", "在这些账目上打开首页"), "action": None, "href": "/",
                "hint_text": t(lang, "The story runs on the main books. These alternate books are for looking around; restore the main books to run the story.",
                               "故事在主账目上进行。这些备用账目用于随意查看；要运行故事，请先恢复主账目。"), "owner": False}
    if rejected:
        return {"label": t(lang, "Start the story again", "重新开始故事"), "action": "restart", "href": None, "owner": False,
                "hint_text": t(lang, "The cure was declined, so the story cannot go on. Start again from fresh books.",
                               "这项解决方案已被拒绝，故事无法继续。请从全新的账目重新开始。")}
    if cur is None:
        return {"label": t(lang, "Start the story again", "重新开始故事"), "action": "restart", "href": None, "owner": False,
                "hint_text": t(lang, "All six scenes are done. Starting again resets the books to the start of the story.",
                               "六个场景都已完成。重新开始会把账目重置到故事的起点。")}
    sid, _, _, owner = STEPS[cur]
    label, hint = t(lang, _STEP[sid][4], _STEP[sid][5]), t(lang, *_HINT[sid])
    if owner:
        return {"label": label, "action": None, "owner": True, "hint_text": hint,
                "href": f"/approvals#approval-{quote(books.cure.id, safe='')}" if books.cure else "/approvals"}
    return {"label": label, "action": sid, "href": None, "hint_text": hint, "owner": False}


def _status(r: Any) -> str:
    return str(getattr(r.status, "value", r.status))


def _counts(rt: Runtime, books: _Books) -> dict[str, int]:
    """What the loaded books hold that a reset discards, counted from the stores (offers FLOW has read and priced, agreements, approvals,
    the approvals still waiting, record entries other than document decisions, documents read, confirmed and rejected, customer inputs,
    security events, all record entries, the clock)."""
    store = rt.store
    verdict_offers = {v.offer_id for v in store.verdicts()} | {c.offer_id for c in store.commitments() if c.offer_id}
    approvals = store.approvals()
    docs = store.contract_records()
    return {"offers": len(verdict_offers | ({books.offer_id} if books.holds["ask"] else set())), "agreements": len(store.commitments()),
            "approvals": len(approvals), "waiting": sum(1 for a in approvals if a.status == ApprovalStatus.PENDING),
            "entries": sum(1 for o, _, _ in books.ops if o.kind not in ("CONFIRM_DOCUMENT", "REJECT_DOCUMENT")), "ops": len(books.ops),
            "docs": len(docs), "docs_confirmed": sum(1 for r in docs if _status(r) == "CONFIRMED"),
            "docs_rejected": sum(1 for r in docs if _status(r) == "REJECTED"), "inputs": len(store.all_customer_inputs()),
            "security": len(store.security_events()), "day": rt.day}


def _dump(x: Any) -> Any:
    return x.model_dump_json() if hasattr(x, "model_dump_json") else repr(x)


def fingerprint(rt: Runtime) -> str:
    """A short hash of everything a reset of the loaded books would discard: the scenario and the day, the record (entry count and head
    hash), the books and the mandate, the security events, the documents and their states, the customer inputs, the approvals, the
    commitments, the verdicts and the messages read. It is the loss token: it changes with any of them and with nothing else."""
    store = rt.store
    ops = store.operations()
    parts = [rt.scenario, rt.day, len(ops), ops[-1].entry_hash if ops else "", store.get_state().model_dump_json(), store.get_mandate().model_dump_json(),
             sorted(e.id for e in store.security_events()), [_dump(r) for r in store.contract_records()],
             [_dump(r) for r in store.all_customer_inputs()], [(a.id, _status(a), a.decided_by, a.decided_day) for a in store.approvals()],
             [_dump(c) for c in store.commitments()], sorted(v.id for v in store.verdicts()), sorted(rt.documents)]
    return hashlib.sha256(json.dumps(parts, default=str, sort_keys=True).encode()).hexdigest()[:16]


def snapshot_fresh(rt: Runtime) -> dict[str, Any]:
    """The fingerprint and the counts of the books right after a reset (`Runtime.mark_fresh`)."""
    return {"fp": fingerprint(rt), "counts": _counts(rt, _read_books(rt))}


def is_fresh(rt: Runtime, fp: str | None = None) -> bool:
    """True only when the loaded books are exactly what a fresh reset of the scenario produced."""
    return rt.fresh is not None and rt.fresh["fp"] == (fp or fingerprint(rt))


def _beyond(rt: Runtime, books: _Books) -> dict[str, int]:
    """The counts beyond a fresh reset of the loaded scenario (its own seed's work is not counted)."""
    base = rt.fresh["counts"] if rt.fresh is not None else {}
    return {k: max(0, v - base.get(k, 0)) for k, v in _counts(rt, books).items()}


def _lost(rt: Runtime, books: _Books, steps: dict[str, str], lang: str) -> list[str]:
    """What a reset or swap of the loaded books would lose, in words, each with its count. Never empty while anything would be lost: a
    catch-all line says so when the named lines do not account for every difference; empty only when the books are exactly fresh."""
    c = _beyond(rt, books)
    items: list[str] = []
    scenes_run = sum(1 for sc in SCENES if any(steps[s] == "done" for s, scene, *_ in STEPS if scene == sc))
    if scenes_run:
        items.append(t(lang, f"Your place in the story: {scenes_run} of {len(SCENES)} scenes have run.", f"您在故事中的进度：已运行 {scenes_run} / {len(SCENES)} 个场景。"))
    if c["offers"]:
        items.append(t(lang, f"{_plural(c['offers'], 'offer', 'offers')} FLOW has read and priced.", f"FLOW 已读取并定价的 {c['offers']} 份报价。"))
    if c["agreements"]:
        items.append(t(lang, f"{_plural(c['agreements'], 'agreement', 'agreements')} on the books.", f"账目中的 {c['agreements']} 项协议。"))
    if c["approvals"]:
        extra = t(lang, f", {c['waiting']} still waiting for you", f"，其中 {c['waiting']} 项仍在等您") if c["waiting"] else ""
        items.append(t(lang, f"{_plural(c['approvals'], 'approval', 'approvals')}{extra}.", f"{c['approvals']} 项批准事项{extra}。"))
    if c["docs"]:
        items.append(t(lang, f"{_plural(c['docs'], 'document', 'documents')} read.", f"已读取 {c['docs']} 份文件。"))
    if c["docs_confirmed"]:
        items.append(t(lang, f"{_plural(c['docs_confirmed'], 'document', 'documents')} confirmed.", f"已确认 {c['docs_confirmed']} 份文件。"))
    if c["docs_rejected"]:
        items.append(t(lang, f"{_plural(c['docs_rejected'], 'document', 'documents')} rejected.", f"已驳回 {c['docs_rejected']} 份文件。"))
    if c["inputs"]:
        items.append(t(lang, f"{_plural(c['inputs'], 'customer input', 'customer inputs')} entered.", f"已录入 {c['inputs']} 项客户信息。"))
    if c["entries"]:
        items.append(t(lang, f"{_plural(c['entries'], 'entry', 'entries')} in the record.", f"记录中的 {c['entries']} 条记录。"))
    other = c["ops"] - c["entries"] - c["docs_confirmed"] - c["docs_rejected"]
    if other > 0:
        items.append(t(lang, f"{_plural(other, 'other entry', 'other entries')} in the record.", f"记录中另有 {other} 条记录。"))
    if c["security"]:
        items.append(t(lang, f"{_plural(c['security'], 'security event', 'security events')} in the record.", f"记录中的 {c['security']} 条安全事件。"))
    if c["day"]:
        items.append(t(lang, f"The clock goes back to the start: {c['day']} days of simulated time are undone.", f"时钟回到起点：模拟的 {c['day']} 天被撤销。"))
    if not items and not is_fresh(rt):
        items.append(t(lang, "Other changes made to these books since they were reset.", "自这些账目重置以来所做的其他更改。"))
    return items


def lost_anything(rt: Runtime) -> bool:
    """True when a reset of the loaded books would discard anything beyond what a fresh reset produces."""
    with rt.lock:
        return not is_fresh(rt)


def _declined_current(lang: str, step: tuple[str, str, bool, bool]) -> dict[str, Any]:
    """`current` once the owner declined the cure: the plan does not wait any more, and the story cannot go on."""
    return {"scene_id": step[1], "step_id": step[0], "title_text": t(lang, "The cure was declined", "解决方案已被拒绝"),
            "text": t(lang, "You declined the funding plan, so it did not run and nothing was financed. The story cannot go on from here; start it again from fresh books.",
                      "您拒绝了融资方案，因此它没有执行，也没有任何融资。故事无法从这里继续；请从全新的账目重新开始。"),
            "owner": False, "owner_text": None}


def _guard_error(code: str, en: str, zh: str, lang: str, **extra: Any) -> HTTPException:
    return HTTPException(409, {"code": code, "message": en, "message_when": t(lang, en, zh), **extra})


def check_books_unchanged(rt: Runtime, from_scenario: str | None, confirm_loss: str | None, lang: str) -> None:
    """The optional guard of `POST /demo/reset` and `POST /demo/restore` (call under `rt.lock`): a caller that names the scenario it
    believes is loaded (`from_scenario`) is refused when the books are another. When something would be lost it also needs
    `confirm_loss=<the loss token it was shown>`: none is `LOSS_NOT_CONFIRMED`, one that is not the current token (the books changed since
    the list was shown, or the old literal "1") is `LOSS_CHANGED`. With nothing to lose no token is needed. Without `from_scenario`
    nothing is checked (every existing caller)."""
    if from_scenario is None:
        return
    if from_scenario != rt.scenario:
        raise _guard_error("BOOKS_CHANGED", "The books changed since this page was read; nothing was reset.",
                           "自您查看此页面以来，账目已发生变化；未重置任何内容。", lang, scenario=rt.scenario)
    fp = fingerprint(rt)
    if is_fresh(rt, fp):
        return
    books = _read_books(rt)
    items = _lost(rt, books, _states(_with_views(books.holds, None), rt.scenario == MAIN)[0], lang)
    if not confirm_loss:
        raise _guard_error("LOSS_NOT_CONFIRMED", "Resetting would discard work on these books and it was not confirmed; nothing was reset.",
                           "重置会丢弃这些账目上的工作，而这一点尚未确认；未重置任何内容。", lang, loss_items=items, loss_token=fp)
    if confirm_loss != fp:
        raise _guard_error("LOSS_CHANGED", "The books changed since this list was shown; nothing was reset.",
                           "自显示此清单以来，账目已发生变化；未重置任何内容。", lang, loss_items=items, loss_token=fp)


def _books_block(rt: Runtime, books: _Books, steps: dict[str, str], lang: str) -> dict[str, Any]:
    main = rt.scenario == MAIN
    items = _lost(rt, books, steps, lang)
    fp = fingerprint(rt)
    nothing = is_fresh(rt, fp)
    if nothing:
        items = []
    if nothing:
        items = [t(lang, "Nothing has been done yet, so nothing is lost." if main else "Nothing has been done on these books yet, so nothing is lost.",
                   "目前还没有做任何事，所以不会损失任何内容。" if main else "这些账目上还没有做任何事，所以不会损失任何内容。")]
    return {
        "scenario": rt.scenario, "main": main, "nothing_to_lose": nothing, "loss_token": fp,
        "loss_title_text": t(lang, "What the main books lose" if main else "What these books lose", "主账目会失去什么" if main else "这些账目会失去什么"),
        "loss_items": items,
        "reset_confirm_title_text": t(lang, "Reset the books?" if main else "Reset these books?", "重置账目？" if main else "重置这些账目？"),
        "reset_confirm_label": t(lang, "Reset the books" if main else "Reset these books", "重置账目" if main else "重置这些账目"),
        "reset_cancel_label": t(lang, "Keep the books", "保留账目"),
        "reset_keeps_text": t(lang, "A reset puts the books back at their start; it does not bring back what is listed above.",
                              "重置会让账目回到起点，上面列出的内容不会恢复。")}


def _scope(rt: Runtime, lang: str) -> str:
    """The books on the screen described from their own counts: the worklist, the Deals queue and the Receivables read."""
    from app.api import worklist
    from app.api.receivables import read_rows

    queue = worklist.queue(rt, lang)
    customers = queue["counts"]["customers"]
    decisions = sum(1 for r in queue["needs_you"] if r["kind"] == "DECISION")
    replies = sum(1 for r in queue["waiting"] if r["kind"] == "BUYER_REPLY")
    agreements = queue["counts"]["agreements"]
    approvals = sum(1 for a in rt.store.approvals() if a.status == ApprovalStatus.PENDING)
    overdue = int(read_rows(rt, lang)[2]["summary"]["overdue_count"])
    en = [_plural(customers, "customer", "customers")]
    zh = [f"{customers} 位客户"]
    for n, e, z in ((decisions, "negotiation{s} waiting for your decision", "项谈判等您决定"), (replies, "negotiation{s} waiting for the buyer's reply", "项谈判等买方回复"),
                    (agreements, "agreement{s} in force", "项协议已生效"), (approvals, "approval{s} waiting for you", "项批准事项等您处理"),
                    (overdue, "overdue invoice{s}", "张发票已逾期")):
        if n:
            en.append(f"{n} " + e.format(s="" if n == 1 else "s"))
            zh.append(f"{n} {z}")
    return t(lang, ", ".join(en[:-1]) + (" and " if len(en) > 1 else "") + en[-1] + ".", "、".join(zh) + "。")


def _ago(at: float, lang: str) -> str:
    secs = max(0, int(time.time() - at))
    if secs < 60:
        return t(lang, "just now", "刚刚")
    if secs < 3600:
        n = secs // 60
        return t(lang, f"{_plural(n, 'minute', 'minutes')} ago", f"{n} 分钟前")
    if secs < 86400:
        n = secs // 3600
        return t(lang, f"{_plural(n, 'hour', 'hours')} ago", f"{n} 小时前")
    n = secs // 86400
    return t(lang, f"{_plural(n, 'day', 'days')} ago", f"{n} 天前")


def note_scenario_change(rt: Runtime, before: str, after: str) -> None:
    """Remember that the books were swapped to another scenario, or the main ones restored (a reset wipes the operations log, so the
    note lives on the runtime). Re-running the main story on the main books is not a swap."""
    with rt.lock:
        if before == after:
            return
        rt.demo_history.append({"kind": "restore" if after == MAIN else "swap", "scenario": after, "at": time.time()})
        del rt.demo_history[:-20]


def _history(rt: Runtime, lang: str) -> list[dict[str, str]]:
    out = []
    for h in reversed(rt.demo_history):
        title = t(lang, *_SCENARIO_TITLE.get(h["scenario"], ("another scenario", "另一个场景")))
        title = title.lower() if lang == "en" else title
        text = (t(lang, "The main books were restored.", "主账目已恢复。") if h["kind"] == "restore"
                else t(lang, f"The main books were replaced by the {title}.", f"主账目被{title}替换。"))
        out.append({"when": _ago(h["at"], lang), "text": text})
    return out


def build_story(rt: Runtime, lang: str, seen: str | None = None) -> dict[str, Any]:
    with rt.lock:
        main = rt.scenario == MAIN
        books = _read_books(rt)
        holds = _with_views(books.holds, seen)
        steps, scenes, cur = _states(holds, main)
        rejected = bool(main and books.cure is not None and books.cure.status == ApprovalStatus.REJECTED)
        complete = main and cur is None
        results, proof = _results_and_proof(rt, books, scenes, lang) if main else ({}, {})
        block = _books_block(rt, books, steps, lang)
        loss_items = block["loss_items"]
        if main:
            loss_text = (t(lang, "Nothing has been done on the main books yet, so loading the alternate scenario loses nothing.",
                           "主账目上还没有做任何事，所以加载备用场景不会损失任何内容。") if block["nothing_to_lose"]
                         else t(lang, f"Loading it replaces the main books. You would lose: {' '.join(loss_items)} Restoring puts the main books back at the start of the story, not where you left them.",
                                f"加载它会替换主账目。您将失去：{' '.join(loss_items)}恢复主账目会回到故事的起点，而不是您离开时的状态。"))
        elif rt.scenario == OWN:
            loss_text = t(lang, "Restoring replaces your own books with the main books at the start of the story. Your books are not kept.",
                          "恢复会用故事起点的主账目替换您自己的账目。您的账目不会保留。")
        else:
            loss_text = t(lang, "Restoring replaces these books with the main books at the start of the story. What you did here is not kept.",
                          "恢复会用故事起点的主账目替换这些账目。您在这里做过的事不会保留。")
        valid = rt.store.verify_chain()
        # The same block as GET /activity: the page reads `chain_valid` for the badge's tone, never infers it from the words.
        chain = {"chain_valid": valid, "chain_length": len(books.ops), "head_hash": books.ops[-1][0].entry_hash if books.ops else None,
                 **chain_fields(valid, len(books.ops), lang)}
        scope = _scope(rt, lang) if not main else t(lang, "A company with several customers, open negotiations, an approval waiting for you and overdue invoices.",
                                                    "一家有多位客户、多项进行中的谈判、待您批准的事项和逾期发票的公司。")
        current_scene = STEPS[cur][1] if cur is not None else None
        n_scene = SCENES.index(current_scene) + 1 if current_scene else len(SCENES)
        alt_title = t(lang, *_SCENARIO_TITLE[ALTERNATE])
        history = _history(rt, lang)
        scenario = rt.scenario
        # The banner over books that are not the main ones. The owner's own books and the blank books are never called "the alternate books" or a demo scenario.
        if main:
            loaded_text = None
        elif scenario == OWN:
            loaded_text = t(lang, f"You are on your own books. {scope} The story runs on the demo's main books; restoring them replaces yours.",
                            f"您正在使用您自己的账目。{scope}故事在演示的主账目上进行；恢复主账目会替换您的账目。")
        elif scenario == "blank":
            loaded_text = t(lang, "You are on blank books, ready to set up as your own. The story runs on the demo's main books; restore them to run it.",
                            "您正在使用空白账目，可以设置为您自己的账目。故事在演示的主账目上进行；恢复主账目才能运行故事。")
        else:
            loaded_text = t(lang, f"You are on the alternate books ({alt_title if scenario == ALTERNATE else t(lang, *_SCENARIO_TITLE.get(scenario, ('another scenario', '另一个场景')))}). {scope} The main books are not here; restore them to run the story.",
                            f"您正在备用账目上。{scope}主账目不在这里；恢复它才能运行故事。")
        restore_text = (t(lang, "Puts the main books back at the start of the story. Your own books are not kept.", "让主账目回到故事的起点。您自己的账目不会保留。")
                        if scenario == OWN else
                        t(lang, "Puts the main books back at the start of the story. What you did on the alternate books is not kept.",
                          "让主账目回到故事的起点。您在备用账目上做过的事不会保留。"))
    cur_step = STEPS[cur] if cur is not None else None
    return {
        "lang": lang, "scenario": scenario, "main": main,
        "title_text": t(lang, "The story", "故事线"),
        "subtitle_text": t(lang, "A buyer asks for better terms. FLOW prices the offer and the agreement changes the books. The bank then pays only part of what was promised, and the owner stays in control of the cure. Six scenes, about five minutes.",
                          "买方要求更好的条件。FLOW 为报价定价，协议随之改变账目。随后银行只付了承诺的一部分，而老板始终掌控解决方案。六个场景，约五分钟。"),
        "story_available": main, "complete": complete,
        "progress_text": (t(lang, "The story runs on the main books", "故事在主账目上进行") if not main
                          else t(lang, f"All {len(SCENES)} scenes are done", f"{len(SCENES)} 个场景已全部完成") if complete
                          else t(lang, f"Scene {n_scene} of {len(SCENES)}", f"第 {n_scene} / {len(SCENES)} 个场景")),
        "scenes": [{"id": sc, "n": i + 1, "label": t(lang, *_SCENE[sc]), "state": scenes[sc], "state_text": t(lang, *_STATE_TEXT[scenes[sc]]),
                    "result_text": results.get(sc),
                    "steps": [{"id": sid, "label": t(lang, _STEP[sid][0], _STEP[sid][1]), "state": steps[sid], "owner": owner}
                              for sid, scene, _, owner in STEPS if scene == sc],
                    "proof": proof.get(sc, [])} for i, sc in enumerate(SCENES)],
        "current": (_declined_current(lang, cur_step) if rejected and cur_step is not None else
                    {"scene_id": cur_step[1], "step_id": cur_step[0], "title_text": t(lang, *_SCENE[cur_step[1]]),
                     "text": t(lang, _STEP[cur_step[0]][2], _STEP[cur_step[0]][3]), "owner": cur_step[3],
                     "owner_text": (t(lang, "The approval is your own click. This story never presses it for you; open the approval and decide.",
                                      "批准是您自己的一次点击。这个故事绝不会代您点击；请打开批准事项并作出决定。") if cur_step[3] else None)}
                    if cur_step is not None and main else None),
        "next": _next(lang, main, cur, books, rejected, scenario),
        "alternate": {
            "label": t(lang, "Load alternate scenario", "加载备用场景"), "scenario": ALTERNATE, "title_text": alt_title, "scope_text": scope,
            "loss_title_text": t(lang, "What the main books lose", "主账目会失去什么"), "loss_items": loss_items, "nothing_to_lose": block["nothing_to_lose"], "loss_token": block["loss_token"], "loss_preview_text": loss_text,
            "keeps_text": t(lang, "Restoring puts the main books back at the start: the starting day, the sample documents confirmed, and no offers, agreements or approvals.",
                            "恢复会让主账目回到起点：起始日期、已确认的示例文件，没有报价、协议或批准事项。"),
            "confirm_title_text": t(lang, f"Load the {alt_title.lower()}?", f"加载“{alt_title}”？"),
            "confirm_label": t(lang, f"Load the {alt_title.lower()}", f"加载“{alt_title}”"),
            "cancel_label": t(lang, "Keep the main books", "保留主账目"), "loaded": not main,
            "loaded_text": loaded_text,
            "restore_label": t(lang, "Restore the main books", "恢复主账目"),
            "restore_text": restore_text,
            "history": history},
        "books": block,
        "operator_tools": {
            "label": t(lang, "Operator tools", "操作工具"), "hint_text": t(lang, "Clock, reset, engine views", "时钟、重置、引擎页面"),
            "groups": [
                {"key": "clock", "label": t(lang, "The clock", "时钟"),
                 "items": []},
                {"key": "books", "label": t(lang, "The books", "账目"), "items": [{"label": t(lang, "Reset the books", "重置账目"), "action": "reset", "replaces_books": True}],
                 "note_text": t(lang, "Clears every deal, operation and approval of this session.", "清除本次会话的所有交易、操作和批准事项。")},
                {"key": "engine", "label": t(lang, "Engine views", "引擎页面"), "items": [{"label": t(lang, en, zh), "href": href} for en, zh, href in _ENGINE]}]},
        "proof": {"title_text": t(lang, "Proof", "证明"),
                  "text": t(lang, "The engine under the story, opened as it is: the full record, the security view and the ledger each read the books as they stand.",
                            "故事之下的引擎页面，按其现状打开：完整记录、安全视图和账本都按账目当前的样子读取。"),
                  "links": [{"label": t(lang, "The full record", "完整记录"), "href": "/trust?view=evidence&from=demo"},
                            {"label": t(lang, "Security", "安全"), "href": "/trust?view=security&from=demo"},
                            {"label": t(lang, "The ledger", "账本"), "href": "/ledger"}], "chain": chain},
        "simulation_text": t(lang, "Simulation. Every company, bank and figure here is synthetic.", "模拟。这里的每家公司、银行和数字都是合成的。"),
    }


@router.get("/demo/story")
def get_demo_story(lang: str = "en", seen: str | None = None) -> dict[str, Any]:
    """Where the story stands, from the books. `seen` (a step id) is the furthest step that changes nothing the browser has shown;
    one the books do not support is ignored."""
    return build_story(get_runtime(), "zh" if lang == "zh" else "en", seen)


@router.post("/demo/restore")
def demo_restore(lang: str = "en", from_scenario: str | None = None, confirm_loss: str | None = None) -> dict[str, Any]:
    """Put the main books back through the existing `rt.reset_demo("golden_sme")`, and say where the story stands. `from_scenario` and
    `confirm_loss` are the optional stale-page guard (`check_books_unchanged`). The history notes a restore only when the scenario really
    changed or the reset discarded something (a restore of untouched main books is not an event)."""
    from app.api.demo_seed import DemoSeedError
    from app.api.runtime import ResetRefused

    lang = "zh" if lang == "zh" else "en"
    rt = get_runtime()
    try:
        with rt.lock:
            check_books_unchanged(rt, from_scenario, confirm_loss, lang)
            before, discarded = rt.scenario, lost_anything(rt)
            rt.reset_demo(MAIN)
            if before != MAIN or discarded:
                rt.demo_history.append({"kind": "restore", "scenario": MAIN, "at": time.time()})
                del rt.demo_history[:-20]
    except ResetRefused as e:
        raise HTTPException(403, {"code": "RESET_REFUSED", "message": str(e)}) from e
    except DemoSeedError as e:
        raise HTTPException(500, {"code": "DEMO_SEED_FAILED", "step": e.step, "message": str(e)}) from e
    return {"ok": True, "scenario": MAIN, "day": rt.day,
            "restored_text": t(lang, "The main books are back at the start of the story.", "主账目已回到故事的起点。"),
            "story": build_story(rt, lang)}
