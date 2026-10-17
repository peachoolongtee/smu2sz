"""Mandate tools: what FLOW may do on its own, what needs the owner, and whether the signed mandate is valid."""

from __future__ import annotations

from typing import Any

from app.nl.answers import AnswerReply
from app.nl.answers import metrics as mx
from app.nl.answers.answers import a_autonomy, a_needs_approval
from app.nl.router.tools.common import Spec, obj, writer

RENEW_SOON_DAYS = 14  # "renew it soon": the mandate lapses within two weeks


def mandate_limits(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_autonomy(writer(ctx, lang), "")


def needs_approval(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    return a_needs_approval(writer(ctx, lang), "")


def mandate_validity(ctx: Any, lang: str, slots: dict[str, Any]) -> AnswerReply:
    w = writer(ctx, lang)
    r = w.r
    m = w.m(mx.mandate_limits_and_validity(r))
    d = m.detail
    version = r.mandate.version
    if m.value:
        w.fig("answer", "yes")
        left = d["expires_day"] - r.today
        w.fig("expires_day", str(d["expires_day"]))
        text = w.t(f"Yes: your signed mandate (version {version}) is valid until day {d['expires_day']}, {left} days from now, and has not "
                   f"been revoked.",
                   f"有效：您签署的授权（第 {version} 版）有效至第 {d['expires_day']} 天，还有 {left} 天，未被撤销。")
        if left <= RENEW_SOON_DAYS:
            text += w.t(" Renew it soon: once it lapses FLOW only proposes and you decide.",
                        "请尽快续签：授权失效后，FLOW 只提建议，由您决定。")
        return w.reply("MAN-03", text, w.basis("mandate"))
    w.fig("answer", "no")
    codes = d["problems"]
    if "MANDATE_REVOKED" in codes:
        why = w.t("it was revoked", "它已被撤销")
    elif "MANDATE_EXPIRED" in codes:
        why = w.t(f"it expired on day {d['expires_day']}", f"它已于第 {d['expires_day']} 天到期")
    else:
        why = w.t("its signature does not verify", "它的签名校验未通过")
    return w.reply("MAN-03", w.t(f"No: {why}, so FLOW only proposes and you decide until you sign a new one.",
                                 f"无效：{why}，因此在您签署新的授权之前，FLOW 只提建议，由您决定。"), w.basis("mandate"))


SPECS: tuple[Spec, ...] = (
    Spec("mandate_limits", "What FLOW may do on its own inside the owner's signed mandate, and its limits.", obj(), mandate_limits),
    Spec("needs_approval", "What needs the owner's approval, what FLOW declines on its own, and what it may never do.", obj(),
         needs_approval),
    Spec("mandate_validity", "Whether the owner's signed mandate is valid, until when, and whether it was revoked.", obj(),
         mandate_validity),
)
