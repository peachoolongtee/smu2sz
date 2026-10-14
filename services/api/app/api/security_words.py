"""Security events in the owner's words (Slice D, ticket #145): what was attempted, what FLOW did, what remains.

One en/zh table for the ten `SecurityEventKind` values, plus the harmless failed sign-in (the events `log_refusal` writes, id prefix
`SEC-AUTH-`: a credential refused before it reached any module). Presentation only: no raw kind, route path, id or "Day N" appears in
these words; the raw `detail` stays on the event for the audit level. The counterparty is named with `party_name` when the books know
it, and never by its id.
"""

from __future__ import annotations

from typing import Any

from app.api.presentation import party_name, t, when_text
from app.domain.models import FinancialState, SecurityEvent

BENIGN_PREFIX = "SEC-AUTH-"

_NOTHING = ("Nothing remains for you to do.", "您无需再做任何事。")
_NOTHING_BOOKED = "Nothing was sent, booked or approved."

# kind -> (kind en, kind zh, title en, title zh, title-with-sender en, title-with-sender zh, action en, action zh, remaining en, remaining zh)
# `{who}` in the with-sender titles is the counterparty's name.
_TABLE: dict[str, tuple[str, ...]] = {
    "INJECTION": (
        "Instructions hidden in a message", "藏在消息里的指令",
        "A message tried to give FLOW instructions", "有一条消息试图向 FLOW 下达指令",
        "{who} sent a message that tried to give FLOW instructions", "{who}发来的消息试图向 FLOW 下达指令",
        "It was read as text, not as a command. " + _NOTHING_BOOKED, "它只被当作文字阅读，没有当作命令执行。没有发送、入账或批准任何内容。",
        *_NOTHING),
    "UNKNOWN_COUNTERPARTY": (
        "Unknown sender", "陌生发件人",
        "A message came from someone FLOW does not know", "有一条消息来自 FLOW 不认识的发件人",
        "A message came from someone FLOW does not know", "有一条消息来自 FLOW 不认识的发件人",
        "It was set aside. " + _NOTHING_BOOKED, "该消息已被搁置。没有发送、入账或批准任何内容。",
        "Nothing remains for you to do unless you recognise the sender.", "除非您认识这位发件人，否则无需再做任何事。"),
    "DATA_EXTRACTION": (
        "Request for private figures", "索取内部数据的请求",
        "A message asked FLOW for figures that are yours alone", "有一条消息向 FLOW 索取只属于您的数据",
        "{who} asked FLOW for figures that are yours alone", "{who}向 FLOW 索取只属于您的数据",
        "FLOW did not share them. Nothing was disclosed, booked or approved.", "FLOW 没有透露这些数据。没有披露、入账或批准任何内容。",
        *_NOTHING),
    "PRIVILEGE_ESCALATION": (
        "Attempt beyond permission", "越权尝试",
        "Someone tried to do something they are not allowed to do", "有人试图做他们无权做的事",
        "{who} tried to do something they are not allowed to do", "{who}试图做其无权做的事",
        "FLOW refused it. Nothing was changed.", "FLOW 拒绝了该请求。没有任何内容被更改。",
        *_NOTHING),
    "UNEVIDENCED_CLAIM": (
        "Claim without evidence", "没有依据的说法",
        "A message made a claim with nothing to back it up", "有一条消息提出了没有任何依据的说法",
        "{who} made a claim with nothing to back it up", "{who}提出了没有任何依据的说法",
        "FLOW did not rely on it. Nothing was booked or approved.", "FLOW 没有采信它。没有入账或批准任何内容。",
        *_NOTHING),
    "REPLAY": (
        "Repeated request", "重复的请求",
        "A request that had already been used was sent again", "一个已经用过的请求被再次发送",
        "{who} sent a request again that had already been used", "{who}再次发送了一个已经用过的请求",
        "FLOW refused the repeat. It was not run a second time.", "FLOW 拒绝了重复请求，没有再执行一次。",
        *_NOTHING),
    "EXPIRED": (
        "Expired permission", "已过期的授权",
        "Something tried to use a permission that has run out", "有人试图使用已经过期的授权",
        "{who} tried to use a permission that has run out", "{who}试图使用已经过期的授权",
        "FLOW refused it. Nothing was changed.", "FLOW 拒绝了该请求。没有任何内容被更改。",
        "Renew the permission only if you still want it.", "只有在您仍然需要时，才需要续期该授权。"),
    "REVOKED": (
        "Withdrawn permission", "已撤回的授权",
        "Something tried to use a permission you had withdrawn", "有人试图使用您已撤回的授权",
        "{who} tried to use a permission you had withdrawn", "{who}试图使用您已撤回的授权",
        "FLOW refused it. Nothing was changed.", "FLOW 拒绝了该请求。没有任何内容被更改。",
        *_NOTHING),
    "TERMS_CHANGED": (
        "Terms changed after they were shown", "条款在展示后发生了变化",
        "The terms changed after they were shown to you", "条款在展示给您之后发生了变化",
        "{who} changed the terms after they were shown to you", "{who}在条款展示给您之后更改了条款",
        "FLOW held the change back. Nothing was booked on the new terms.", "FLOW 拦下了这项改动。没有按新条款入账。",
        "Nothing is booked until you decide on the changed terms.", "在您对更改后的条款作出决定之前，不会入账。"),
    "TIER3": (
        "Needs you alone", "只能由您决定",
        "Someone else attempted something only you may decide", "有人试图做只能由您决定的事",
        "{who} attempted something only you may decide", "{who}试图做只能由您决定的事",
        "FLOW did not run it. It stays with you.", "FLOW 没有执行它，这件事仍由您决定。",
        "Nothing runs unless you decide.", "除非您作出决定，否则不会执行。"),
}

_BENIGN = ("Sign-in refused", "登录被拒绝",
           "A sign-in attempt was refused", "有一次登录尝试被拒绝",
           "The credential was refused before it reached anything. Nothing was read, changed or sent.",
           "凭证在到达任何功能之前就被拒绝了。没有读取、更改或发送任何内容。")


def is_benign_auth(event: SecurityEvent) -> bool:
    """A credential refused before it reached any module (what `log_refusal` writes): harmless, summarised apart from real alerts."""
    return event.id.startswith(BENIGN_PREFIX)


def known_sender(state: FinancialState, party_id: str | None) -> str | None:
    """The counterparty's name when the books know it, else None (an unknown id is never shown)."""
    if not party_id or not any(c.id == party_id for c in state.counterparties):
        return None
    return party_name(state, party_id) or None


def security_words(state: FinancialState, event: SecurityEvent, lang: str) -> dict[str, Any]:
    """The Business words of one security event: `kind_text`, `title_text` (what was attempted), `action_text` (what FLOW did, which is
    also why it is safe), `remaining_text`, and `who` (the counterparty's name or None)."""
    who = known_sender(state, event.counterparty_id)
    if is_benign_auth(event):
        kind_en, kind_zh, title_en, title_zh, action_en, action_zh = _BENIGN
        remaining = _NOTHING
        return {"kind_text": t(lang, kind_en, kind_zh), "title_text": t(lang, title_en, title_zh),
                "action_text": t(lang, action_en, action_zh), "remaining_text": t(lang, *remaining), "who": who}
    row = _TABLE[event.kind.value]
    kind_en, kind_zh, plain_en, plain_zh, with_en, with_zh, action_en, action_zh, rem_en, rem_zh = row
    title = t(lang, with_en, with_zh).format(who=who) if who and "{who}" in with_en else t(lang, plain_en, plain_zh)
    return {"kind_text": t(lang, kind_en, kind_zh), "title_text": title, "action_text": t(lang, action_en, action_zh),
            "remaining_text": t(lang, rem_en, rem_zh), "who": who}


def audit_fields(state: FinancialState, event: SecurityEvent, today: int, lang: str) -> dict[str, Any]:
    """The additive words `GET /audit` carries on each event, so the security view can drop its raw codes."""
    w = security_words(state, event, lang)
    return {"kind_text": w["kind_text"], "day_when": when_text(event.day, today, lang), "title_text": w["title_text"],
            "action_text": w["action_text"]}
