"""GET /activity: the Activity page's record (Slice D, map #121, ticket #145; owner's decisions #135).

One read composed from the sources `GET /ledger` and `GET /audit` use: every operation (through `_op_view` with the `Causality`) and every
security event, each exactly once, newest first. A row is classified `business` (a deal, cash, a receivable or a document), `security`
(a real alert), `benign_auth` (a credential refused before it reached any module) or `system` (the clock and the like), and carries
the words the ledger read already computes (what changed, why it matters, what remains) plus Business words for security events
(`app.api.security_words`). A summary sentence sits BESIDE the rows; it never replaces, merges or hides one. A GET changes nothing.

The title of an operation row is the ledger's `event_text`; `what_changed` is the same sentence (the causality sets it from
`event_text`), so there is one source. Presentation only: no money arithmetic, every sentence in en and zh through `t`.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any
from urllib.parse import quote

from fastapi import APIRouter, Depends

from app.alerts import reconcile
from app.api.auth import require_owner
from app.api.causality import Causality, chain_fields, mark_changed
from app.api.decisions import Reconciled, load_context
from app.api.presentation import last_read, live_windows, party_name, t, when_text
from app.api.read import _forecast_now, _op_view
from app.api.runtime import get_runtime
from app.api.security_words import is_benign_auth, known_sender, security_words
from app.api.selection import Selection, build_context, selection
from app.persistence.records import ApprovalStatus

router = APIRouter(dependencies=[Depends(require_owner)])

# operation kind -> the filter category it belongs to; a kind not listed is read as the system's own
_CATEGORY = {
    "ACCEPT_OFFER": "deals", "RECORD_COMMITMENT": "deals", "COUNTER_OFFER": "deals", "REVOKE_COMMITMENT": "deals",
    "DRAW_FACILITY": "cash", "REPAY_FACILITY": "cash", "SUBMIT_INVOICE_FOR_FINANCING": "cash", "APPLY_FOR_FACILITY": "cash",
    "ADD_FACILITY": "cash",
    "RECEIVE_PAYMENT": "receivables",
    "CONFIRM_DOCUMENT": "documents", "REJECT_DOCUMENT": "documents",
}
_LABELS = {
    "all": ("All", "全部"), "deals": ("Deals", "交易"), "cash": ("Cash", "现金"), "receivables": ("Receivables", "应收款"),
    "documents": ("Documents", "文件"), "security": ("Security", "安全"), "system": ("System", "系统"),
}
_ORDER = ("all", "deals", "cash", "receivables", "documents", "security", "system")
_ACTORS = {"OWNER": ("you", "You", "您"), "AGENT": ("agent", "FLOW's agent", "FLOW 代理"), "SYSTEM": ("system", "The system", "系统"),
           "COUNTERPARTY": ("buyer", "The buyer", "买方")}


def _label(key: str, lang: str) -> str:
    return t(lang, *_LABELS[key])


def _actor(requested_by: Any, lang: str) -> tuple[str, str]:
    key, en, zh = _ACTORS.get(str(requested_by or "SYSTEM"), _ACTORS["SYSTEM"])
    return key, t(lang, en, zh)


def _status(status: str, decided: bool, lang: str) -> tuple[str | None, str]:
    """(the status word, the tone) of an operation's result."""
    if status == "REFUSED":
        return t(lang, "Refused", "已拒绝"), "warn"
    if status == "PENDING_APPROVAL":
        return (t(lang, "Decided", "已决定"), "neutral") if decided else (t(lang, "Waiting for your approval", "等待您批准"), "warn")
    if status == "EXECUTED":
        return t(lang, "Done", "已完成"), "ok"
    return None, "neutral"


def _op_rows(rt: Any, lang: str, today: int) -> list[dict[str, Any]]:
    """Every operation as an Activity row (oldest first; the caller orders). Set up exactly as `GET /ledger` sets up its views."""
    ops = rt.store.operations()
    state = rt.store.get_state()
    mandate = rt.store.get_mandate()
    commitments = rt.store.commitments()
    decided = frozenset(a.id for a in rt.store.approvals() if str(getattr(a.status, "value", a.status)) != "PENDING")
    agreements = {c.id: party_name(state, c.counterparty_id) for c in commitments}
    reconciled = Reconciled(rt.store, lambda st, day: reconcile(st, day=day))
    live = (live_windows(reconciled.report(rt.day), commitments, state) if any(o.kind == "RECEIVE_PAYMENT" for o in ops) else None)
    try:
        ctx = load_context(rt, reconciled=reconciled) if ops else None
    except Exception:
        logging.getLogger("termsledger.decisions").exception("the decision record could not be read for activity")
        ctx = None
    causality = Causality(ctx, _forecast_now(rt, state, mandate, commitments, today) if ops else None, today, lang)
    documents = {r.id: r for r in rt.store.contract_records()} if any(o.kind.endswith("_DOCUMENT") for o in ops) else {}
    views = [_op_view(o, state, rt.day, commitments, decided, agreements, live, lang, causality, documents) for o in ops]
    mark_changed(list(reversed(views)))  # "why" is new when it differs from the row above it: this page reads newest first
    rows: list[dict[str, Any]] = []
    last_day = 0
    for o, v in zip(ops, views, strict=True):
        payload = _payload(o)
        raw_day = v.get("day")
        day: int = raw_day if isinstance(raw_day, int) else last_day
        last_day = day
        category = _CATEGORY.get(o.kind, "system")
        status = str(json.loads(o.result_json).get("status") or "")
        title = v.get("event_text") or v.get("message_when") or v["kind_text"]
        actor, actor_text = _actor(v.get("requested_by"), lang)
        word, tone = _status(status, json.loads(o.result_json).get("approval_id") in decided, lang)
        buyer = _buyer_of(state, payload, commitments, v)
        link = v.get("decision_link")
        href, href_label = (link["href"], t(lang, "Open this decision", "查看这项决定")) if link else _own_link(payload, buyer, category, lang)
        why = v.get("why_it_matters")
        rows.append({
            "id": f"op:{o.seq}", "kind": "system" if category == "system" else "business", "category": category,
            "category_label": _label(category, lang), "day": day, "order": (day, 1, o.seq),
            "when": when_text(day, today, lang), "title_text": title, "detail_text": v.get("event_detail") or None,
            "why_text": why, "why_as_of_text": v.get("why_it_matters_as_of") if why else None,
            "why_changed": bool(v.get("why_it_matters_changed")), "remaining_text": v.get("what_remains"),
            "actor": actor, "actor_text": actor_text, "status_word": word, "tone": "neutral" if category == "system" and tone == "ok" else tone,
            "customer_id": buyer, "customer_name": party_name(state, buyer) if buyer else None,
            "decision_id": v.get("decision_id") if link else None, "href": href, "href_label": href_label,
            "evidence_href": f"/trust?view=evidence&entry={o.seq}&from=activity", "evidence_label": t(lang, "Evidence", "证据"),
            "record": {"seq": o.seq, "entry_hash": o.entry_hash, "prev_hash": o.prev_hash, "kind_text": v["kind_text"],
                       "message": v["summary"]},
        })
    return rows


def _payload(o: Any) -> dict[str, Any]:
    try:
        p = json.loads(o.payload_json)
    except ValueError:
        return {}
    return p if isinstance(p, dict) else {}


def _buyer_of(state: Any, payload: dict[str, Any], commitments: Any, view: dict[str, Any]) -> str | None:
    """The customer an operation concerns, when the books say so (a receivable's buyer, an agreement's counterparty)."""
    rid = payload.get("receivable_id")
    if rid:
        found = next((r.counterparty_id for r in state.receivables if r.id == rid), None)
        if found:
            return str(found)
    cid = payload.get("commitment_id") or payload.get("offer_id")
    for c in commitments:
        if cid and cid in (c.id, c.offer_id):
            return str(c.counterparty_id)
    link = view.get("decision_link")
    if link:
        for c in commitments:
            if c.offer_id and str(link["decision_id"]).endswith(str(c.offer_id)):
                return str(c.counterparty_id)
    return None


def _own_link(payload: dict[str, Any], buyer: str | None, category: str, lang: str) -> tuple[str | None, str | None]:
    """Where an entry without a decision continues: its invoice in Receivables, or the Documents page."""
    rid = payload.get("receivable_id")
    if rid and category in ("receivables", "cash"):
        tail = f"&customer={quote(buyer, safe='')}" if buyer else ""
        return f"/receivables?invoice={quote(str(rid), safe='')}{tail}", t(lang, "Open in Receivables", "在应收款中打开")
    if category == "documents":
        return "/documents", t(lang, "Open in Documents", "在文件中打开")
    return None, None


def _event_rows(rt: Any, lang: str, today: int) -> list[dict[str, Any]]:
    state = rt.store.get_state()
    rows: list[dict[str, Any]] = []
    for i, e in enumerate(rt.store.security_events()):
        w = security_words(state, e, lang)
        benign = is_benign_auth(e)
        who = known_sender(state, e.counterparty_id)
        rows.append({
            "id": f"sec:{e.id}", "kind": "benign_auth" if benign else "security", "category": "security",
            "category_label": _label("security", lang), "day": e.day, "order": (e.day, 0, i),
            "when": when_text(e.day, today, lang), "title_text": w["title_text"], "detail_text": None,
            "why_text": w["action_text"], "why_as_of_text": None, "why_changed": True, "remaining_text": w["remaining_text"],
            "actor": "system" if benign else "buyer", "actor_text": _actor("SYSTEM" if benign else "COUNTERPARTY", lang)[1],
            "status_word": t(lang, "Refused", "已拒绝") if benign else t(lang, "Set aside", "已搁置"), "tone": "neutral" if benign else "bad",
            "customer_id": e.counterparty_id if who else None, "customer_name": who, "decision_id": None, "href": None, "href_label": None,
            "evidence_href": f"/trust?view=security&event={quote(e.id, safe='')}&from=activity", "evidence_label": t(lang, "Evidence", "证据"),
            "record": {"event_id": e.id, "kind_text": w["kind_text"], "action_text": w["action_text"], "detail": e.detail},
        })
    return rows


def _search_text(row: dict[str, Any]) -> str:
    parts = [row["title_text"], row["detail_text"], row["why_text"], row["remaining_text"], row["customer_name"], row["category_label"]]
    return " ".join(str(p) for p in parts if p).lower()


def _benign_text(today_n: int, earlier_n: int, lang: str) -> str | None:
    if not today_n and not earlier_n:
        return None
    if today_n:
        text = t(lang, f"{today_n} failed sign-in attempt{'' if today_n == 1 else 's'} today, "
                       f"{'refused' if today_n == 1 else 'all refused'}; nothing was reached.",
                 f"今天有 {today_n} 次登录尝试失败，均已被拒绝；没有触及任何内容。")
        if earlier_n:
            text += t(lang, f" {earlier_n} more earlier, also refused.", f"此前还有 {earlier_n} 次，同样已被拒绝。")
        return text
    return t(lang, f"{earlier_n} failed sign-in attempt{'' if earlier_n == 1 else 's'} earlier, "
                   f"{'refused' if earlier_n == 1 else 'all refused'}; nothing was reached.",
             f"此前有 {earlier_n} 次登录尝试失败，均已被拒绝；没有触及任何内容。")


def _alerts_text(rows: list[dict[str, Any]], lang: str) -> str | None:
    alerts = [r for r in rows if r["kind"] == "security"]
    if not alerts:
        return None
    n = len(alerts)
    when = alerts[0]["when"]  # the newest first
    return t(lang, f"{n} security alert{' is' if n == 1 else 's are'} in the record, the latest {when}. Open one to see what was "
                   "attempted and what FLOW did about it.",
             f"记录中有 {n} 条安全警示，最近一条发生在{when}。打开即可查看有人尝试了什么，以及 FLOW 如何处理。")


def _state(rt: Any, rows: list[dict[str, Any]], valid: bool, today: int, lang: str) -> tuple[str, str, str]:
    """(word, tone, text) for the status pill and the subheading: what changed most recently and whether anything waits on the owner."""
    waiting = sum(1 for a in rt.store.approvals() if a.status == ApprovalStatus.PENDING)
    newest = next((r for r in rows if r["kind"] == "business"), None)
    if newest:
        title = str(newest["title_text"]).rstrip()
        title += "" if title[-1] in ".!?。！？" else t(lang, ".", "。")
        recent = t(lang, f"Latest, {newest['when']}: {title}", f"最新，{newest['when']}：{title}")
    else:
        recent = t(lang, "Nothing has changed in the books yet.", "账目中还没有任何变化。")
    if not valid:
        return (t(lang, "Record check failed", "记录核验未通过"), "bad",
                recent + " " + t(lang, "The record chain did not pass its check.", "记录链没有通过核验。"))
    if waiting:
        text = t(lang, f"{waiting} approval{' waits' if waiting == 1 else 's wait'} for you.", f"有 {waiting} 项批准事项在等您。")
        return t(lang, "Waiting on you", "等待您处理"), "warn", f"{recent} {text}"
    fresh = any(r["kind"] == "security" and r["day"] == today for r in rows)
    if fresh:  # the pill says it; the sentence does not say it again
        return t(lang, "Security alert today", "今天有安全警示"), "warn", recent
    return t(lang, "Nothing waits on you", "没有事项在等您"), "ok", recent


@router.get("/activity")
def get_activity(lang: str = "en", *, sel: Annotated[Selection, Depends(selection)]) -> dict[str, Any]:
    rt = get_runtime()
    lang = "zh" if lang == "zh" else "en"
    with rt.lock:
        state = rt.store.get_state()
        today = max(rt.day, state.as_of_day)
        rows = _op_rows(rt, lang, today) + _event_rows(rt, lang, today)
        rows.sort(key=lambda r: r["order"], reverse=True)  # newest first: the day, then events after operations of the same day
        n_ops = len(rt.store.operations())
        valid = rt.store.verify_chain()
        head_hash = rt.store.operations()[-1].entry_hash if n_ops else None
        benign_today = sum(1 for r in rows if r["kind"] == "benign_auth" and r["day"] == today)
        word, tone, text = _state(rt, rows, valid, today, lang)
        for r in rows:
            r["search_text"] = _search_text(r)
            r.pop("order")
            r.pop("day")
        benign = [r for r in rows if r["kind"] == "benign_auth"]
        counts = {k: sum(1 for r in rows if r["kind"] == k) for k in ("business", "security", "benign_auth", "system")}
        keys = ["all", *[k for k in _ORDER[1:] if any(r["category"] == k for r in rows)]]
        context = build_context(rt, lang, sel, page="activity")
    return {
        "lang": lang, "title_text": t(lang, "Activity", "动态"), "state_word": word, "state_tone": tone, "state_text": text,
        "summary": {
            "business_count": counts["business"], "security_alert_count": counts["security"], "benign_auth_count": counts["benign_auth"],
            "system_count": counts["system"],
            "benign_auth_text": _benign_text(benign_today, len(benign) - benign_today, lang),
            "benign_auth_word": t(lang, "Refused", "已拒绝") if benign else None,
            "security_alerts_text": _alerts_text(rows, lang),
            "kept_text": t(lang, "Every entry stays in the record whatever the filter.", "无论如何筛选，每一条记录都会保留。"),
        },
        "categories": [{"key": k, "label": _label(k, lang), "count": len(rows) if k == "all" else sum(1 for r in rows if r["category"] == k)}
                       for k in keys],
        "rows": rows,
        "chain": {"chain_valid": valid, "chain_length": n_ops, "head_hash": head_hash, **chain_fields(valid, n_ops, lang)},
        "context": context,
        **last_read(today, lang),
    }
