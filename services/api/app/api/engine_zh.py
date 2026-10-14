"""Chinese for the engine's English sentences, as a Business page reads them (wayfinder #65 Wave 7, F28).

The engine writes English: the alert engine's titles and details, the executor's result messages, the router's labels and notes, the
verifier's violation messages, the reconciliation details. Those sentences are hash-chained or are the audit level, so they stay exactly
as written (stability mode). The Business presentation fields are another matter: `presentation.business_text` first says the engine
sentence in the owner's English (names for ids, distances from today, the owner's words for the ceiling and the terms), and then, for
`lang == "zh"`, `translate` below says that same sentence in Chinese.

`translate` works on that normalized English, so the day phrases are a closed set ("today", "tomorrow", "yesterday", "in N days",
"N days ago") and an id has already become a name. Each template is a whole sentence or clause with its figures as groups; amounts,
rates, names and ids are carried over exactly, never recomputed (INVARIANT 13). A name the books give (a buyer, a facility) is lifted
out of the sentence before matching and put back afterwards, so a name that contains a full stop or a comma cannot confuse a template.
A sentence that no template knows passes through unchanged, never guessed at; `MISSES` lists those for the tests.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from app.api.financing_words import state_word

Rule = tuple["re.Pattern[str]", Callable[["re.Match[str]"], str]]

MISSES: set[str] = set()  # sentences with Latin words that no template knew (the tests and the report read it)
_MISS_LIMIT = 500

M = r"¥[\d,]+(?:\.\d+)?"  # an amount
SM = r"[−-]?¥[\d,]+(?:\.\d+)?"  # a signed amount
PCT = r"\d+(?:\.\d+)?%"
WHEN = r"(?:today|tomorrow|yesterday|in \d+ days|\d+ days ago)"  # what `presentation.when_text` writes in English
UNTIL = r"(?:today|tomorrow|yesterday|\d+ days from now|\d+ days ago)"  # what `relative_days` writes after "to day N"
DAYS = r"(?:days?|day\(s\))"
DEADLINE = r"(?:by today|by tomorrow|within \d+ days|by a deadline that passed yesterday|by a deadline that passed \d+ days ago)"
N = r"⟦\d+⟧"  # a name the books give (lifted out of the sentence)
_LATIN = re.compile(r"[A-Za-z]{3,}")
_TOKEN = re.compile(r"⟦(\d+)⟧")


def when_zh(phrase: str) -> str:
    """`presentation.when_text`'s English phrase in Chinese ("in 12 days" -> "12 天后")."""
    fixed = {"today": "今天", "tomorrow": "明天", "yesterday": "昨天"}
    if phrase in fixed:
        return fixed[phrase]
    m = re.fullmatch(r"in (\d+) days", phrase)
    if m:
        return f"{m.group(1)} 天后"
    m = re.fullmatch(r"(\d+) days ago", phrase)
    return f"{m.group(1)} 天前" if m else phrase


def until_zh(phrase: str) -> str:
    m = re.fullmatch(r"(\d+) days from now", phrase)
    return f"{m.group(1)} 天后" if m else when_zh(phrase)


def deadline_zh(phrase: str) -> str:
    """`presentation.deadline_text`'s English ("by today", "within 5 days") as a phrase of time."""
    if phrase == "by today":
        return "今天之前"
    if phrase == "by tomorrow":
        return "明天之前"
    m = re.fullmatch(r"within (\d+) days", phrase)
    if m:
        return f"{m.group(1)} 天内"
    m = re.fullmatch(r"by a deadline that passed (yesterday|\d+ days ago)", phrase)
    return f"已于{when_zh(m.group(1))}截止" if m else phrase


_RULES: list[Rule] = []


def rule(pattern: str) -> Callable[[Callable[[re.Match[str]], str]], Callable[[re.Match[str]], str]]:
    """Register a template: `pattern` must match the whole sentence (a trailing full stop is not part of it)."""
    compiled = re.compile(pattern, re.DOTALL)

    def add(fn: Callable[[re.Match[str]], str]) -> Callable[[re.Match[str]], str]:
        _RULES.append((compiled, fn))
        return fn

    return add


def tr(text: str | None) -> str:
    """One sentence or clause in Chinese when a template knows it, else unchanged."""
    if text is None:
        return ""
    out = _match(text.strip())
    if out is not None:
        return out
    clauses = re.split(r";\s+", text.strip())
    if len(clauses) > 1:  # several clauses (a plan with several legs): each by its own template
        got = [_match(c) for c in clauses]
        if any(g is not None for g in got):
            return "；".join(g if g is not None else c for g, c in zip(got, clauses, strict=True))
    return text


def _match(text: str) -> str | None:
    core = text.removesuffix(".")
    for pattern, build in _RULES:
        m = pattern.fullmatch(core)
        if m is not None:
            return build(m)
    return None


def _each(text: str, sep: str, joiner: str) -> str:
    return joiner.join(tr(part) for part in text.split(sep))


# ---------------------------------------------------------------- noun phrases

_INVOICE = re.compile(rf"[Tt]he (?:(?P<face>{M}) )?invoice to (?P<buyer>{N})(?: due (?P<due>{WHEN}))?")


def inv(text: str) -> str:
    """The invoice phrase `presentation.invoice_words` writes ("the ¥420,000.00 invoice to X due in 32 days") in Chinese."""
    def say(m: re.Match[str]) -> str:
        face = f" {m['face']}" if m["face"] else ""
        due = f"（{when_zh(m['due'])}到期）" if m["due"] else ""
        return f"{m['buyer']} 的{face} 发票{due}"

    return re.sub(r"(?<![\w-])((?:RCV-|RI:)[\w:-]+)", r"发票 \1", _INVOICE.sub(say, text))


INV = rf"(?:[Tt]he (?:{M} )?invoice to {N}(?: due {WHEN})?|invoice [\w:-]+|(?:RCV-|RI:)[\w:-]+)"
AGR = rf"(?:[Tt]he (?:[a-z]+ )*agreement(?: with {N})?)"
_ADJ = {"earlier": "较早的", "other": "另一项", "first": "最初的", "later": "较晚的", "accepted": "已接受的", "active": "生效中的",
        "revoked": "已撤销的", "proposed": "待定的", "expired": "已到期的"}


def agr(text: str) -> str:
    """"the agreement with X" / "the earlier active agreement" in Chinese."""
    def say(m: re.Match[str]) -> str:
        who = f"与{m['buyer']}的" if m["buyer"] else ""
        adjectives = "".join(_ADJ.get(a, "") for a in (m["adj"] or "").split())
        return f"{who}{adjectives}协议"

    return re.sub(rf"[Tt]he (?:(?P<adj>(?:[a-z]+ )*[a-z]+) )?agreement(?: with (?P<buyer>{N}))?", say, text)


# ---------------------------------------------------------------- funding legs (alerts, the router)

_LEG = re.compile(rf"(?P<verb>draw on|finance an invoice on|repay|apply for) (?P<fac>{N}) (?:for )?(?P<amt>{M})"
                  rf"(?:, cost (?P<cost>{M})(?: \((?P<rate>{PCT}) a year for (?P<days>\d+) days\))?)?")
_LEG_VERB = {"draw on": "从{fac}提款 {amt}", "finance an invoice on": "以发票在{fac}融资 {amt}", "repay": "向{fac}还款 {amt}",
             "apply for": "申请{fac} {amt}"}


def _leg(text: str) -> str:
    m = _LEG.fullmatch(text.strip())
    if m is None:
        return text
    out = _LEG_VERB[m["verb"]].format(fac=m["fac"], amt=m["amt"])
    if m["cost"]:
        out += f"，成本 {m['cost']}"
        if m["rate"]:
            out += f"（年化 {m['rate']}，{m['days']} 天）"
    return out


def legs(text: str) -> str:
    """"draw on X ¥150,000.00, cost ¥1.00 (6.4% a year for 29 days) + finance an invoice on Y ¥336,000.00" in Chinese."""
    return "；".join(_leg(part) for part in text.split(" + "))


_CAP_TAIL = (rf"; that is above the (?P<cap>{PCT}) limit you signed for funding without your approval, "
             r"so it needs your approval before it runs")


def _cap_zh(cap: str | None) -> str:
    return f"；该方案的年化成本高于您签署的无需批准融资上限 {cap}，因此执行前需要您批准" if cap else ""


# ---------------------------------------------------------------- the owner's approval queue and the executor's results


@rule(r"Queued for owner approval \((?P<id>APR-[\w-]+)\): (?P<why>.+)")
def _queued(m: re.Match[str]) -> str:
    return f"已排入待批准队列（{m['id']}）：{tr(m['why'])}"


@rule(rf"the yearly cost of (?P<r>{PCT}) is above the (?P<cap>{PCT}) limit you signed for funding without your approval"
      r"(?: \((?P<tail>[^;]+)\))?")
def _ceiling(m: re.Match[str]) -> str:
    out = f"年化成本 {m['r']} 高于您签署的无需批准融资上限 {m['cap']}"
    return out + (f"（{tr(m['tail'])}）" if m["tail"] else "")


@rule(rf"(?P<r>{PCT}) simple")
def _simple(m: re.Match[str]) -> str:
    return f"单利 {m['r']}"


@rule(rf"all charges on (?P<amt>{M}) held (?P<n>\d+) days \(from (?P<a>{WHEN}) to (?P<b>{WHEN})\), annualised = (?P<r>{PCT})")
def _charges(m: re.Match[str]) -> str:
    return f"{m['amt']} 计息 {m['n']} 天（从{when_zh(m['a'])}到{when_zh(m['b'])}），年化 {m['r']}"


@rule(r"Declined by the owner \((?P<id>APR-[\w-]+)\); nothing executed")
def _declined(m: re.Match[str]) -> str:
    return f"您已拒绝（{m['id']}）；未执行任何操作"


_LANDS = rf"(?:, upfront fee (?P<fee>{M}))?(?:; the cash(?: \((?P<net>{M}) after the upfront fee\))? lands (?P<lw>{WHEN}), not today)?"


def _landing(m: re.Match[str]) -> str:
    out = f"，预收费用 {m['fee']}" if m["fee"] else ""
    if m["lw"]:
        net = f"（扣除预收费用后 {m['net']}）" if m["net"] else ""
        out += f"；资金{net}将于{when_zh(m['lw'])}到账，不是今天"
    return out


@rule(rf"Drew (?P<amt>{M}) on (?P<fac>{N}) (?P<w>{WHEN}){_LANDS}")
def _drew(m: re.Match[str]) -> str:
    return f"已于{when_zh(m['w'])}从{m['fac']}提取 {m['amt']}" + _landing(m)


@rule(rf"Advance (?P<amt>{M}) on (?P<inv>{INV}) from (?P<fac>{N}) (?P<w>{WHEN}){_LANDS}")
def _advance(m: re.Match[str]) -> str:
    # one vocabulary for the financing (app.api.financing_words): an advance whose cash lands later is ARRANGED, not "advanced"
    word = state_word("zh", "ARRANGED" if m["lw"] else "RECEIVED")
    return f"已于{when_zh(m['w'])}以{inv(m['inv'])}从{m['fac']}申请融资 {m['amt']}（融资{word}）" + _landing(m)


@rule(rf"Repaid (?P<amt>{M}) on (?P<fac>{N}) with interest (?P<int>{M}) \((?P<parts>.+)\)")
def _repaid(m: re.Match[str]) -> str:
    return f"已向{m['fac']}还款 {m['amt']}，利息 {m['int']}（{m['parts']}）"


@rule(rf"Applied for (?P<amt>{M}) on (?P<fac>{N}); it is PENDING and counts as zero until committed")
def _applied(m: re.Match[str]) -> str:
    return f"已向{m['fac']}申请 {m['amt']}；申请已提交，在银行承诺之前按零现金计算"


@rule(r"Refused: (?P<why>.+)")
def _refused(m: re.Match[str]) -> str:
    whole = _match(m["why"])
    return "已拒绝：" + (whole if whole is not None else _each(m["why"], "; ", "；"))


@rule(rf"Draw (?P<amt>{M}) exceeds (?P<fac>{N})'s available (?P<avail>{M})")
def _draw_exceeds(m: re.Match[str]) -> str:
    return f"提款 {m['amt']} 超过{m['fac']}的可用额度 {m['avail']}"


@rule(rf"Repayment (?P<amt>{M}) exceeds (?P<fac>{N})'s drawn (?P<drawn>{M})")
def _repay_exceeds(m: re.Match[str]) -> str:
    return f"还款 {m['amt']} 超过{m['fac']}已提取的 {m['drawn']}"


@rule(rf"Advance (?P<amt>{M}) exceeds (?P<bp>\d+)bp of (?P<inv>{INV})'s outstanding (?P<out>{M})")
def _advance_exceeds(m: re.Match[str]) -> str:
    return f"融资 {m['amt']} 超过{inv(m['inv'])}未收金额 {m['out']} 的 {m['bp']} 个基点"


@rule(rf"(?P<a>{AGR}) and (?P<b>{AGR}) both cover receivable (?P<inv>{INV}); the owner must revoke (?P<c>{AGR}) first")
def _overlap(m: re.Match[str]) -> str:
    return f"{agr(m['a'])}与{agr(m['b'])}都涉及{inv(m['inv'])}；您须先撤销{agr(m['c'])}"


@rule(rf"(?P<c>{AGR}) is (?P<status>[A-Z]+); forward concession (?P<fc>{M}) booked(?:; accepted terms written on (?P<on>.+))?")
def _agreement_active(m: re.Match[str]) -> str:
    state = {"ACTIVE": "已生效", "ACCEPTED": "已接受", "PROPOSED": "待定"}.get(m["status"], m["status"])
    out = f"{agr(m['c'])}{state}；已计入远期让步 {m['fc']}"
    return out + (f"；已将接受的条款写入 {inv(m['on'])}" if m["on"] else "")


@rule(rf"(?P<c>{AGR}) revoked by the owner \((?P<a>[A-Z]+) -> REVOKED\); forward concession (?P<fc>{M}) removed"
      r"(?:; (?P<n>\d+) invoice adjustment\(s\) removed)?")
def _agreement_revoked(m: re.Match[str]) -> str:
    out = f"{agr(m['c'])}已由您撤销（{m['a']} → REVOKED）；已移除远期让步 {m['fc']}"
    return out + (f"；已移除 {m['n']} 处发票调整" if m["n"] else "")


@rule(rf"Received (?P<amt>{M}) on (?P<inv>{INV})(?: \((?P<detail>.+?)\))?(?P<lender>; (?:repaid advance|all) .+)?")
def _received(m: re.Match[str]) -> str:
    out = f"已收到{inv(m['inv'])}的回款 {m['amt']}"
    if m["detail"]:
        out += f"（{_each(m['detail'], '; ', '；')}）"
    if m["lender"]:
        out += "；" + tr(m["lender"][2:])
    return out


@rule(rf"settles (?P<face>{M}) at the agreed (?P<d>[\d.]+%|{M}) early-payment discount")
def _settles(m: re.Match[str]) -> str:
    return f"按约定的 {m['d']} 提前付款折扣结清 {m['face']}"


@rule(rf"(?P<amt>{M}) (?:was )?still due (?P<w>{WHEN})")
def _still_due(m: re.Match[str]) -> str:
    return f"另有 {m['amt']} 原定{when_zh(m['w'])}到期"


@rule(rf"up to (?P<amt>{M}) more may still be settled early (?P<d>{DEADLINE})")
def _more_may(m: re.Match[str]) -> str:
    return f"另有最多 {m['amt']} 仍可在{deadline_zh(m['d'])}提前结算"


@rule(rf"up to (?P<amt>{M}) more could be settled early until (?P<u>{UNTIL})")
def _more_could(m: re.Match[str]) -> str:
    return f"另有最多 {m['amt']} 可提前结算，直到{until_zh(m['u'])}"


@rule(rf"the early-payment window for the other (?P<amt>{M}) ended (?P<w>{WHEN})")
def _window_ended(m: re.Match[str]) -> str:
    return f"另外 {m['amt']} 的提前付款期限已于{when_zh(m['w'])}结束"


@rule(rf"repaid advance (?P<p>{M}) \+ interest (?P<i>{M}) \+ fee (?P<f>{M}) \((?P<d>\d+) days billed as (?P<n>\d+) whole period\(s\)\) to (?P<fac>{N})")
def _repaid_advance(m: re.Match[str]) -> str:
    return f"已偿还融资本金 {m['p']}、利息 {m['i']}、费用 {m['f']}（{m['d']} 天按 {m['n']} 个整期计费），付给{m['fac']}"


@rule(rf"Clock moved from (?P<a>{WHEN}) to (?P<b>{WHEN}): (?P<items>.+)")
def _clock(m: re.Match[str]) -> str:
    items = "，".join(tr(part) for part in re.split(r", (?=\d)", m["items"]))
    return f"时间从{when_zh(m['a'])}推进到{when_zh(m['b'])}：{items}"


@rule(r"(?P<n>\d+) scheduled flow\(s\) posted \(net (?P<net>[^)]+)\)")
def _clock_flows(m: re.Match[str]) -> str:
    return f"已入账 {m['n']} 笔计划收支（净额 {m['net']}）"


@rule(r"(?P<n>\d+) invoice\(s\) issued")
def _clock_invoices(m: re.Match[str]) -> str:
    return f"已开出 {m['n']} 张发票"


@rule(r"(?P<n>\d+) commitment\(s\) expired")
def _clock_expired(m: re.Match[str]) -> str:
    return f"{m['n']} 项协议已到期"


@rule(rf"(?P<n>\d+) funding request\(s\) landed \(funding net (?P<net>{SM})\)")
def _clock_funding(m: re.Match[str]) -> str:
    return f"{m['n']} 笔融资已到账（融资净额 {m['net']}）"


@rule(rf"(?P<n>\d+) existing-debt payment\(s\) posted \((?P<net>{SM})\)")
def _clock_debt(m: re.Match[str]) -> str:
    return f"已入账 {m['n']} 笔既有债务还款（{m['net']}）"


@rule(r"(?P<n>\d+) funding request\(s\) landed")
def _clock_landed(m: re.Match[str]) -> str:
    return f"{m['n']} 笔融资已到账"


@rule(rf"(?P<n>\d+) loan payment\(s\) posted(?: \(funding net (?P<net>{SM})\))?")
def _clock_loans(m: re.Match[str]) -> str:
    return f"已入账 {m['n']} 笔贷款还款" + (f"（融资净额 {m['net']}）" if m["net"] else "")


@rule(r"(?P<n>\d+) commitment\(s\) fulfilled \(every invoice carrying the accepted terms is settled\)")
def _clock_fulfilled(m: re.Match[str]) -> str:
    return f"{m['n']} 项协议已履行（带有已接受条款的发票均已结清）"


@rule(r"(?P<n>\d+) early-payment commitment\(s\) ended: the promised payment did not arrive \((?P<who>.+), now EXPIRED\)")
def _clock_lapsed(m: re.Match[str]) -> str:
    return f"{m['n']} 项提前付款协议已终止：约定的付款没有到账（{agr(m['who'])}，现已到期）"


@rule(r"(?P<n>\d+) new scheduled flow\(s\) recorded")
def _clock_new_flows(m: re.Match[str]) -> str:
    return f"已记录 {m['n']} 笔新的计划收支"


@rule(r"Duplicate of seq (?P<seq>\d+) \(status (?P<status>[A-Z_]+)\); nothing re-executed\. (?P<msg>.+)")
def _duplicate(m: re.Match[str]) -> str:
    return f"与第 {m['seq']} 条记录重复（状态 {m['status']}）；未重复执行。{tr(m['msg'])}"


@rule(rf"(?P<label>{N}: (?:draw|advance|early payment|discount) [^:]+): (?P<why>(?:(?!; {N}: ).)+)")
def _leg_with_reason(m: re.Match[str]) -> str:
    return f"{tr(m['label'])}：{tr(m['why'])}"


@rule(rf"Advance on (?P<inv>{INV}), (?P<fac>{N})")
def _label_advance(m: re.Match[str]) -> str:
    return f"{m['fac']}以{inv(m['inv'])}融资"


# approval reasons the executor writes for what is not a rate above the ceiling


@rule(rf"apply for facility (?P<fac>{N}) \((?P<amt>{M})\)")
def _reason_apply(m: re.Match[str]) -> str:
    return f"申请融资工具{m['fac']}（{m['amt']}）"


@rule(rf"facility (?P<fac>{N}) is not COMMITTED and owner-approved")
def _reason_uncommitted(m: re.Match[str]) -> str:
    return f"融资工具{m['fac']}尚未获得承诺和您的批准"


@rule(rf"receipt of (?P<amt>{M}) on (?P<inv>{INV}) reported by (?P<who>[A-Z_]+); "
      r"only the bank feed or the owner records a receipt without confirmation")
def _reason_receipt(m: re.Match[str]) -> str:
    return f"{m['who']}报告了 {inv(m['inv'])} 的 {m['amt']} 回款；只有银行流水或您本人才能在无确认的情况下登记回款"


@rule(rf"(?P<c>{AGR}) lengthens payment terms")
def _reason_terms(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}延长了付款账期"


@rule(rf"(?P<c>{AGR}) of (?P<fv>{M}) is above the (?P<limit>{M}) you allow without your approval")
def _reason_commitment_limit(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}的 {m['fv']} 高于您无需批准即可允许的 {m['limit']}"


@rule(rf"(?P<c>{AGR}) of (?P<fv>{M}) is above the limit you set for what needs your approval")
def _reason_commitment_limit_plain(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}的 {m['fv']} 高于您设定的无需批准额度"


# ---------------------------------------------------------------- the alert engine


@rule(rf"A funding plan is available: (?P<legs>.+?)(?:{_CAP_TAIL})?")
def _cure(m: re.Match[str]) -> str:
    return f"有可用的融资方案：{legs(m['legs'])}{_cap_zh(m['cap'])}"


@rule(rf"[Nn]o funding plan restores your minimum cash reserve; the plan that keeps cash at or above zero is: (?P<legs>.+?)(?:{_CAP_TAIL})?")
def _zero_cure(m: re.Match[str]) -> str:
    return f"没有融资方案能恢复您的最低现金储备；能让现金保持在零以上的方案是：{legs(m['legs'])}{_cap_zh(m['cap'])}"


@rule(rf"A fallback also exists: (?P<legs>.+?), at (?P<cost>{M}) \((?P<rate>{PCT}) a year for (?P<days>\d+) days\)"
      rf"(?:{_CAP_TAIL})?; FLOW recommends the plan above")
def _fallback(m: re.Match[str]) -> str:
    parts = "；".join(_leg(p.strip()) for p in re.split(r" and (?=draw on|finance an invoice on|repay|apply for)", m["legs"]))
    return f"另有备选方案：{parts}，费用 {m['cost']}（年化 {m['rate']}，{m['days']} 天）；FLOW 推荐上面的方案"


@rule(rf"Projected cash closes at (?P<close>{SM}) (?P<w1>{WHEN}), (?P<short>{M}) below your minimum cash reserve; the gap peaks at "
      rf"(?P<peak>{M}) (?P<w2>{WHEN}) and lasts until (?P<u>{UNTIL})")
def _breach_detail(m: re.Match[str]) -> str:
    return (f"预计现金将在{when_zh(m['w1'])}降至 {m['close']}，比最低现金储备低 {m['short']}；"
            f"缺口在{when_zh(m['w2'])}最大，为 {m['peak']}，持续到{until_zh(m['u'])}")


@rule(rf"Reserve breach ahead (?P<w>{WHEN})")
def _breach_title(m: re.Match[str]) -> str:
    return f"{when_zh(m['w'])}现金将低于最低现金储备"


@rule(rf"cash goes below zero (?P<w>{WHEN}) without action")
def _zero_title(m: re.Match[str]) -> str:
    return f"若不采取行动，现金将在{when_zh(m['w'])}跌破零"


@rule(rf"Cash is close to your minimum (?P<w>{WHEN})")
def _thin_title(m: re.Match[str]) -> str:
    return f"{when_zh(m['w'])}现金仅略高于最低现金储备"


@rule(rf"Cash stays above your minimum cash reserve by only (?P<amt>{M}) (?P<w>{WHEN}) "
      r"\((?P<n>\d+) days? with less than 10% of your minimum cash reserve to spare\)")
def _thin_detail(m: re.Match[str]) -> str:
    return f"{when_zh(m['w'])}现金仅高出最低现金储备 {m['amt']}（共 {m['n']} 天高出的部分不足最低现金储备的 10%）"


@rule(rf"It does not restore the reserve: cash stays at or above zero, but the reserve is still (?P<amt>{M}) short at the worst day, "
      r"which needs the owner's decision")
def _no_restore(m: re.Match[str]) -> str:
    return f"这不能恢复现金储备：现金可保持在零以上，但最差一天储备仍差 {m['amt']}，需要您决定"


@rule(r"The projection lets cash run below zero only as a simulation limit; the bank does not allow an overdraft, so a negative "
      r"figure is a day the books cannot pay what falls due")
def _overdraft(m: re.Match[str]) -> str:
    return "预测只是为了模拟才允许现金低于零；银行不允许透支，因此出现负数就表示那一天账上无法支付到期款项"


@rule(r"[Tt]he mandate does not allow new borrowing, so no facility can be drawn or applied for")
def _no_borrowing(m: re.Match[str]) -> str:
    return "您的授权不允许新增借款，因此无法提款或申请任何融资工具"


@rule(r"[Nn]o committed facility can cure it; uncommitted facilities count as zero")
def _no_facility(m: re.Match[str]) -> str:
    return "没有已承诺的融资工具能解决这个缺口；未承诺的融资工具按零计算"


@rule(r"(?P<kind>DSCR|Leverage) (?P<what>breach|is within 0\.10× of its limit) in month (?P<month>\d+)")
def _covenant_title(m: re.Match[str]) -> str:
    what = "已低于限值" if m["what"] == "breach" else "距限值不足 0.10×"
    return f"第 {m['month']} 个月 {m['kind']} {what}"


@rule(r"(?P<kind>DSCR|Leverage) (?P<value>[\d.×]+|undefined) against your signed limit (?P<limit>[\d.×]+) \(version (?P<v>\d+)\) "
      r"\((?P<head>[\d.×]+|undefined) (?P<dir>above|below) the limit\); months affected: (?P<months>[\d, ]+)")
def _covenant_detail_signed(m: re.Match[str]) -> str:
    return (f"{m['kind']} {m['value']}，对照您签署的授权（第 {m['v']} 版）限值 {m['limit']}（{'高于' if m['dir'] == 'above' else '低于'}限值 "
            f"{m['head']}）；涉及的月份：{m['months']}")


@rule(r"(?P<kind>DSCR|Leverage) (?P<value>[\d.×]+|undefined) against (?P<src>.+?) limit (?P<limit>[\d.×]+) "
      r"\((?P<head>[\d.×]+|undefined) (?P<dir>above|below) the limit\); months affected: (?P<months>[\d, ]+)")
def _covenant_detail(m: re.Match[str]) -> str:
    src = m["src"]
    return f"{m['kind']} {m['value']}，对照{src}限值 {m['limit']}（{'高于' if m['dir'] == 'above' else '低于'}限值 {m['head']}）；涉及的月份：{m['months']}"


@rule(rf"Clean-down at risk on (?P<fac>{N})")
def _cleandown_title(m: re.Match[str]) -> str:
    return f"{m['fac']}的清零要求面临风险"


@rule(rf"The longest projected run at zero balance is (?P<n>\d+) {DAYS} starting (?P<w>{WHEN}); the covenant needs (?P<need>\d+) "
      rf"consecutive days\. Drawn now: (?P<drawn>{M})")
def _cleandown_detail(m: re.Match[str]) -> str:
    return f"预计余额为零的最长连续时间是 {m['n']} 天（从{when_zh(m['w'])}起）；契约要求连续 {m['need']} 天。目前已提取：{m['drawn']}"


@rule(r"The line must be at zero for its clean-down")
def _line_zero(m: re.Match[str]) -> str:
    return "该额度须为零才能满足清零要求"


@rule(rf"(?P<c>{AGR}) expires in (?P<n>\d+) {DAYS}")
def _expiry_title(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}将在 {m['n']} 天后到期"


@rule(rf"(?P<status>[A-Z]+) commitment on offer (?P<offer>\S+) v(?P<v>\d+) expires (?P<w>{WHEN}); "
      r"after that its nonce is refused \(COMMITMENT_EXPIRED\)")
def _expiry_detail(m: re.Match[str]) -> str:
    state = {"PROPOSED": "待定", "ACCEPTED": "已接受"}.get(m["status"], m["status"])
    return f"{state}的协议（报价 {m['offer']} v{m['v']}）将在{when_zh(m['w'])}到期；到期后其一次性凭据将被拒绝（COMMITMENT_EXPIRED）"


@rule(r"mandate expired: the agent can no longer act")
def _mandate_expired_title(m: re.Match[str]) -> str:
    return "授权已过期：代理不能再操作"


@rule(rf"Your signed limits \(version (?P<v>\d+)\) expire in (?P<n>\d+) {DAYS}")
def _mandate_title(m: re.Match[str]) -> str:
    return f"您签署的授权（第 {m['v']} 版）将在 {m['n']} 天后到期"


@rule(rf"Your signed limits \(version (?P<v>\d+)\) expired (?P<w>{WHEN}), (?P<n>\d+) {DAYS} ago")
def _mandate_expired_detail(m: re.Match[str]) -> str:
    return f"您签署的授权（第 {m['v']} 版）已于{when_zh(m['w'])}到期（{m['n']} 天前）"


@rule(rf"Your signed limits \(version (?P<v>\d+)\) expired (?P<w>{WHEN})")
def _limits_expired(m: re.Match[str]) -> str:
    return f"您签署的授权（第 {m['v']} 版）已于{when_zh(m['w'])}到期"


@rule(r"Your signed limits \(version (?P<v>\d+)\) have been revoked by the owner")
def _limits_revoked(m: re.Match[str]) -> str:
    return f"您签署的授权（第 {m['v']} 版）已被您撤销"


@rule(r"Every operation is refused \(MANDATE_EXPIRED\) until the owner signs a new mandate")
def _mandate_expired_detail_2(m: re.Match[str]) -> str:
    return "在您签署新授权之前，所有操作都会被拒绝（MANDATE_EXPIRED）"


@rule(rf"Your signed limits \(version (?P<v>\d+)\) are valid until (?P<u>{UNTIL}); after that the agent can no longer act, "
      rf"although the forecast horizon runs until (?P<h>{UNTIL})")
def _mandate_detail(m: re.Match[str]) -> str:
    return f"您签署的授权（第 {m['v']} 版）的有效期到{until_zh(m['u'])}；之后代理不能再操作，尽管预测期一直延伸到{until_zh(m['h'])}"


@rule(r"Renewal is an offline owner step: sign a new mandate outside the agent")
def _renew(m: re.Match[str]) -> str:
    return "续期需要您在线下完成：请在代理之外签署新的授权"


@rule(r"The agent cannot renew or extend it, and it suggests no operation")
def _renew_2(m: re.Match[str]) -> str:
    return "代理无法续期或延期，也不会提出任何操作建议"


@rule(rf"Receivable (?P<inv>{INV}) is (?P<n>\d+) {DAYS} past due")
def _pastdue_title(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}已逾期 {m['n']} 天"


@rule(rf"(?P<amt>{M}) outstanding from (?P<buyer>{N}) was due (?P<w>{WHEN})(?P<moved> \(.+\))? and is still (?P<status>[A-Z]+)")
def _pastdue_detail(m: re.Match[str]) -> str:
    status = {"OPEN": "未收款", "FINANCED": "已融资"}.get(m["status"], m["status"])
    moved = "（发票上的到期日因生效中的账期延长而顺延）" if m["moved"] else ""
    return f"{m['buyer']}应付的 {m['amt']} 原定{when_zh(m['w'])}到期{moved}，目前仍{status}"


@rule(r"The cash forecast no longer counts on a dated receipt")
def _no_dated(m: re.Match[str]) -> str:
    return "现金预测不再把这笔款项当作有确定日期的回款"


@rule(r"The financing advance falls due with it")
def _advance_due(m: re.Match[str]) -> str:
    return "融资款也随之到期"


@rule(rf"Early payment on (?P<inv>{INV}) did not arrive")
def _early_missed_title(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}的提前付款没有到账"


@rule(rf"The early payment promised under (?P<c>{AGR}) (?:for )?(?P<w>{WHEN}) did not arrive")
def _early_missed_detail_1(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}约定于{when_zh(m['w'])}的提前付款没有到账"


@rule(rf"(?P<inv>{INV}) \((?P<amt>{M}) outstanding from (?P<buyer>{N})\) is back on its original due day, (?P<w>{WHEN}), "
      r"and the cash forecast is projected that way")
def _early_missed_detail_2(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}（{m['buyer']}尚欠 {m['amt']}）已回到原定到期日（{when_zh(m['w'])}），现金预测也按此计算"


@rule(r"Forward concessions at (?P<p>\d+)% of the cap")
def _agg_title(m: re.Match[str]) -> str:
    return f"远期让步已达上限的 {m['p']}%"


@rule(rf"Booked (?P<booked>{M}) plus projected contingent concessions at maximum give (?P<total>{M}) against the aggregate cap (?P<cap>{M})")
def _agg_detail_1(m: re.Match[str]) -> str:
    return f"已入账 {m['booked']}，加上按最大值计的预计附条件让步，合计 {m['total']}，对照总上限 {m['cap']}"


@rule(r"Terms extensions are valued separately by the verifier at the marginal cost of funds")
def _agg_detail_2(m: re.Match[str]) -> str:
    return "账期延长由核验方按边际资金成本另行估值"


@rule(rf"Concessions to (?P<buyer>{N}) at (?P<p>\d+)% of its cap")
def _buyer_title(m: re.Match[str]) -> str:
    return f"给{m['buyer']}的让步已达其上限的 {m['p']}%"


@rule(rf"Booked (?P<v>{M}) against the per-buyer cap (?P<cap>{M})")
def _buyer_detail(m: re.Match[str]) -> str:
    return f"已入账 {m['v']}，对照单个买方上限 {m['cap']}"


@rule(rf"(?P<fac>{N}) can be repaid")
def _repay_title(m: re.Match[str]) -> str:
    return f"{m['fac']}可以还款"


@rule(rf"(?P<amt>{M}) is drawn on (?P<fac>{N})")
def _repay_detail_1(m: re.Match[str]) -> str:
    return f"{m['fac']}已提取 {m['amt']}"


@rule(rf"Repaying it today costs (?P<int>{M}) interest to date, (?P<all>{M}) in all, and cash stays above your minimum cash reserve: "
      rf"the lowest projected close after repaying is (?P<low>{M}) (?P<w>{WHEN})")
def _repay_detail_2(m: re.Match[str]) -> str:
    return (f"今天还款需付迄今利息 {m['int']}，合计 {m['all']}，现金仍保持在最低现金储备以上："
            f"还款后预计最低收盘现金为 {m['low']}（{when_zh(m['w'])}）")


@rule(rf"A further (?P<amt>{M}) requested (?P<w1>{WHEN}) lands (?P<w2>{WHEN}) and can be repaid only after that")
def _repay_detail_3(m: re.Match[str]) -> str:
    return f"另有 {m['amt']} 于{when_zh(m['w1'])}申请，将于{when_zh(m['w2'])}到账，到账后才能还款"


@rule(rf"(?P<amt>{M}) requested (?P<w1>{WHEN}) on (?P<fac>{N}) lands (?P<w2>{WHEN})")
def _transit(m: re.Match[str]) -> str:
    return f"于{when_zh(m['w1'])}向{m['fac']}申请的 {m['amt']} 将于{when_zh(m['w2'])}到账"


@rule(rf"Cash is below your (?P<floor>{M}) minimum cash reserve until the funds land (?P<w>{WHEN})")
def _transit_below(m: re.Match[str]) -> str:
    return f"在资金{when_zh(m['w'])}到账之前，现金低于您 {m['floor']} 的最低现金储备"


@rule(rf"Reserve uncovered until (?P<fac>{N}) cash lands (?P<w>{WHEN})")
def _transit_title(m: re.Match[str]) -> str:
    return f"在{m['fac']}的资金{when_zh(m['w'])}到账之前，现金储备没有保障"


# ---------------------------------------------------------------- reconciliation


@rule(rf"agreed early payment for (?P<amt>{M}) of the invoice(?P<more>; .+)?")
def _recon_receipt(m: re.Match[str]) -> str:
    return f"约定的提前付款，对应发票 {m['amt']}" + (f"；{tr(m['more'][2:])}" if m["more"] else "")


@rule(r"amount equals what the accepted terms say is owed")
def _recon_equal(m: re.Match[str]) -> str:
    return "金额与已接受条款所规定的应付金额一致"


@rule(rf"partial payment: short by (?P<short>{M}) against (?P<what>face less the agreed discount|what is outstanding); "
      rf"(?P<left>{M}) of (?P<inv>{INV}) still due")
def _recon_partial(m: re.Match[str]) -> str:
    what = "发票金额减去约定折扣" if m["what"].startswith("face") else "未收金额"
    return f"部分付款：比{what}少 {m['short']}；{inv(m['inv'])}仍有 {m['left']} 未付"


@rule(rf"full face paid inside the discount window of accepted (?P<c>{AGR}); the agreed (?P<d>{M}) credit is still owed to the buyer")
def _recon_full(m: re.Match[str]) -> str:
    return f"在折扣期内付了全额发票金额（{agr(m['c'])}）；约定的 {m['d']} 折扣仍须退还买方"


@rule(rf"discount of (?P<d>{M}) deducted (?P<w1>{WHEN}), after the window closed (?P<w2>{WHEN}) \((?P<c>{AGR})\)")
def _recon_late_discount(m: re.Match[str]) -> str:
    return f"买方在{when_zh(m['w1'])}扣减了 {m['d']} 折扣，但折扣期已于{when_zh(m['w2'])}结束（{agr(m['c'])}）"


@rule(r"amount matches neither the face nor the discounted face")
def _recon_unexpected(m: re.Match[str]) -> str:
    return "金额既不等于发票金额，也不等于折扣后的金额"


@rule(rf"(?P<amt>{M}) promised for (?P<inv>{INV}) (?P<d>{DEADLINE}) under (?P<c>{AGR}); the day has not passed")
def _recon_promised(m: re.Match[str]) -> str:
    return f"{agr(m['c'])}约定，{inv(m['inv'])}的 {m['amt']} 应在{deadline_zh(m['d'])}到账；约定日尚未过"


@rule(rf"the agreed (?P<amt>{M}) for (?P<inv>{INV}) arrived(?: \((?P<c>{AGR})\))?")
def _recon_arrived(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}约定的 {m['amt']} 已到账"


@rule(rf"the agreed (?P<amt>{M}) for (?P<part>{M}) of the (?P<agreed>{M}) agreed for early settlement of (?P<inv>{INV}) arrived"
      rf"(?: \((?P<c>{AGR})\))?; the other (?P<other>{M}) (?P<tail>.+)")
def _recon_arrived_part(m: re.Match[str]) -> str:
    tail = m["tail"]
    may = re.fullmatch(rf"may still be settled early ({DEADLINE})", tail)
    could = re.fullmatch(rf"could be settled early until ({UNTIL})", tail)
    if tail == "is due on the invoice's own day":
        text = "在发票自己的到期日支付"
    elif may:
        text = f"仍可在{deadline_zh(may.group(1))}提前结算"
    elif could:
        text = f"可提前结算，直到{until_zh(could.group(1))}"
    else:
        text = tail
    return f"{inv(m['inv'])}已约定提前结算的 {m['agreed']} 中，{m['part']} 对应的约定款项 {m['amt']} 已到账；另外 {m['other']} {text}"


@rule(rf"(?P<inv>{INV}) was settled without the agreed (?P<amt>{M}) early payment(?: \((?P<c>{AGR})\))?")
def _recon_otherwise(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}已结清，但没有收到约定的 {m['amt']} 提前付款"


@rule(rf"(?P<amt>{M}) promised for (?P<w>{WHEN}) under (?P<c>{AGR}) did not arrive; (?P<out>{M}) of (?P<inv>{INV}) is still outstanding "
      rf"and falls back to its original due day, (?P<due>{WHEN})(?: \(lapsed: (?P<why>.+)\))?")
def _recon_lapsed(m: re.Match[str]) -> str:
    why = f"（已失效：{m['why']}）" if m["why"] else ""
    return (f"{agr(m['c'])}约定于{when_zh(m['w'])}支付的 {m['amt']} 没有到账；{inv(m['inv'])}仍有 {m['out']} 未收，"
            f"回到原定到期日（{when_zh(m['due'])}）{why}")


@rule(r"no open receivable or commitment explains this receipt \((?P<why>.+)\)")
def _recon_unexplained(m: re.Match[str]) -> str:
    return f"没有任何未结发票或协议能解释这笔回款（{m['why']}）"


# ---------------------------------------------------------------- the router: plan labels, notes and reasons


@rule(r"committed plan: (?P<cost>[^()]+?)(?P<cannot> \(cannot run today\))?")
def _plan_label(m: re.Match[str]) -> str:
    return f"已承诺方案：{m['cost']}" + ("（今天无法执行）" if m["cannot"] else "")


@rule(r"expected plan \(committed sources only\): (?P<cost>[^()]+?)(?P<cannot> \(cannot run today\))?")
def _expected_label(m: re.Match[str]) -> str:
    return f"预期方案（仅限已承诺的来源）：{m['cost']}" + ("（今天无法执行）" if m["cannot"] else "")


@rule(r"no funding needed")
def _no_funding(m: re.Match[str]) -> str:
    return "无需融资"


@rule(r"no admissible plan: the menu cannot cover the gap")
def _no_plan(m: re.Match[str]) -> str:
    return "没有可行方案：现有融资选项无法覆盖缺口"


@rule(rf"(?P<fac>{N}): draw (?P<amt>{M})(?:, repaid (?P<w>{WHEN}))?(?P<tag> \(expected\))?")
def _cost_draw(m: re.Match[str]) -> str:
    repaid = f"，预计{when_zh(m['w'])}还款" if m["w"] else ""
    return f"{m['fac']}：提款 {m['amt']}{repaid}" + ("（预期）" if m["tag"] else "")


@rule(rf"(?P<fac>{N}): advance (?P<amt>{M}) on (?P<inv>{INV})(?P<tag> \(expected\))?")
def _cost_advance(m: re.Match[str]) -> str:
    return f"{m['fac']}：以{inv(m['inv'])}融资 {m['amt']}" + ("（预期）" if m["tag"] else "")


@rule(rf"(?P<fac>{N}): early payment on (?P<amt>{M}) face of (?P<inv>{INV}) at (?P<r>{PCT})(?P<tag> \(expected\))?")
def _cost_early(m: re.Match[str]) -> str:
    return f"{m['fac']}：对{inv(m['inv'])}中 {m['amt']} 提前付款，折扣 {m['r']}" + ("（预期）" if m["tag"] else "")


@rule(rf"(?P<fac>{N}): discount (?P<amt>{M}) of bills(?P<tag> \(expected\))?")
def _cost_bills(m: re.Match[str]) -> str:
    return f"{m['fac']}：贴现票据 {m['amt']}" + ("（预期）" if m["tag"] else "")


@rule(rf"Buyer early-payment offer: early payment on (?P<amt>{M}) face of (?P<inv>{INV}) at (?P<r>{PCT})")
def _buyer_offer(m: re.Match[str]) -> str:
    return f"买方提前付款报价：对{inv(m['inv'])}中 {m['amt']} 提前付款，折扣 {m['r']}"


@rule(r"needs the buyer's agreement to pay early")
def _needs_buyer(m: re.Match[str]) -> str:
    return "需要买方同意提前付款"


@rule(r"(?P<what>.+?): needs the buyer's agreement to pay early")
def _needs_buyer_with_what(m: re.Match[str]) -> str:
    return f"{tr(m['what'])}：需要买方同意提前付款"


@rule(rf"(?P<inv>{INV}) is not an invoice the executor can finance today; it is issued (?P<w>{WHEN})")
def _not_issued(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}今天还不能融资；它将于{when_zh(m['w'])}开出"


@rule(rf"Discount the whole invoice at (?P<r>{PCT})")
def _discount_all(m: re.Match[str]) -> str:
    return f"对整张发票按 {m['r']} 折扣"


@rule(rf"Line \+ early payment on part of the invoice at (?P<r>{PCT})")
def _line_plus(m: re.Match[str]) -> str:
    return f"额度 + 对部分发票提前付款（折扣 {m['r']}）"


@rule(r"Line \+ guaranteed loan")
def _line_loan(m: re.Match[str]) -> str:
    return "额度 + 担保贷款"


@rule(r"Line only")
def _line_only(m: re.Match[str]) -> str:
    return "仅用额度"


@rule(rf"cost (?P<cost>{M}); (?P<rest>.+)")
def _note_cost(m: re.Match[str]) -> str:
    return f"成本 {m['cost']}；{tr(m['rest'])}"


@rule(r"within your limits but dearer than the selected plan")
def _dearer(m: re.Match[str]) -> str:
    return "在您的限额内，但比所选方案更贵"


@rule(r"within your limits, but you must approve it: (?P<why>.+)")
def _limits_approve(m: re.Match[str]) -> str:
    return f"在您的限额内，但需要您批准：{tr(m['why'])}"


@rule(rf"Forward concessions \(all buyers\) would reach (?P<amt>{M}), above the cap")
def _violation_agg(m: re.Match[str]) -> str:
    return f"所有买方的远期让步将达到 {m['amt']}，超过上限"


@rule(rf"Projected cash falls below the reserve (?P<w>{WHEN})(?P<note>.*)")
def _violation_reserve(m: re.Match[str]) -> str:
    return f"预计现金将在{when_zh(m['w'])}低于储备{tr(m['note']) if m['note'] else ''}"


# ---------------------------------------------------------------- chart and ledger labels


@rule(rf"Early settlement of (?P<inv>{INV})(?: \((?P<ref>[\w-]+)\))?")
def _label_early(m: re.Match[str]) -> str:
    return f"提前结算{inv(m['inv'])}" + (f"（{m['ref']}）" if m["ref"] else "")


@rule(rf"Discount on early settlement of (?P<inv>{INV})(?: \((?P<ref>[\w-]+)\))?")
def _label_discount(m: re.Match[str]) -> str:
    return f"{inv(m['inv'])}提前结算的折扣" + (f"（{m['ref']}）" if m["ref"] else "")


@rule(rf"Interest, (?P<fac>{N})(?: on (?P<inv>{INV}))?")
def _label_interest(m: re.Match[str]) -> str:
    return f"利息：{m['fac']}" + (f"（{inv(m['inv'])}）" if m["inv"] else "")


@rule(rf"Fee, (?P<fac>{N})(?: on (?P<inv>{INV}))?")
def _label_fee(m: re.Match[str]) -> str:
    return f"费用：{m['fac']}" + (f"（{inv(m['inv'])}）" if m["inv"] else "")


@rule(rf"Repay advance on (?P<inv>{INV})")
def _label_repay_advance(m: re.Match[str]) -> str:
    return f"偿还{inv(m['inv'])}的融资款"


@rule(rf"Receipt (?P<inv>{INV}) from (?P<buyer>{N})")
def _label_receipt(m: re.Match[str]) -> str:
    return f"{m['buyer']}的回款：{inv(m['inv'])}"


@rule(rf"Draw (?P<fac>{N})")
def _label_draw(m: re.Match[str]) -> str:
    return f"从{m['fac']}提款"


@rule(rf"Repay (?P<fac>{N})")
def _label_repay(m: re.Match[str]) -> str:
    return f"向{m['fac']}还款"


@rule(rf"Debt service \(principal\), (?P<name>.+?) \(rate (?P<r>{PCT}): a fixture assumption\)")
def _label_debt_principal(m: re.Match[str]) -> str:
    return f"债务还款（本金）：{m['name']}（利率 {m['r']}：示例假设）"


@rule(r"Debt service \(principal\), (?P<name>.+)")
def _label_debt(m: re.Match[str]) -> str:
    return f"债务还款（本金）：{m['name']}"


@rule(r"Debt service")
def _label_debt_short(m: re.Match[str]) -> str:
    return "债务还款"


@rule(r"Interest")
def _label_interest_short(m: re.Match[str]) -> str:
    return "利息"


@rule(r"Fee")
def _label_fee_short(m: re.Match[str]) -> str:
    return "费用"


@rule(rf"RESERVE_BREACH (?P<w>{WHEN})")
def _note_breach(m: re.Match[str]) -> str:
    return f"RESERVE_BREACH（{when_zh(m['w'])}）"


@rule(r"Option (?P<x>[A-Z])")
def _option(m: re.Match[str]) -> str:
    return f"方案 {m['x']}"


@rule(rf"committed marginal source: (?P<fac>{N}) (?P<r>[\d.]+%)")
def _marginal(m: re.Match[str]) -> str:
    return f"已承诺的边际资金来源：{m['fac']} {m['r']}"


# ---------------------------------------------------------------- suggestions, counters and their rationales

_NOTES = {
    "submit today: the invoice is open, buyer-confirmed and not yet due": "今天提交：发票未结清、已获买方确认且尚未到期",
    "Needs your approval: you apply; counted as zero until committed": "需要您批准：由您提出申请；获批前按零计算",
    "decline or counter terms that add debt service; the verifier prices it": "拒绝或还价那些会增加还本付息的条款；核验方会给出价格",
    "reduce drawn balances to bring leverage back inside its limit": "减少已提取的余额，把杠杆降回限值以内",
    "repay the line (or refinance a permanent need elsewhere)": "还清额度（或把长期需求转到别处融资）",
    "decide before expiry, or let it lapse": "请在到期前决定，或任其失效",
    "chase the buyer; record the receipt when the money lands": "向买方催收；款项到账后登记回款",
    "counter new concessions; the verifier enforces the cap": "对新的让步还价；核验方会执行上限",
    "counter further concessions": "对进一步的让步还价",
    "repay the whole drawn balance today": "今天还清全部已提取的余额",
    "repay the balance that has landed": "偿还已到账的余额",
    "Nothing else changes": "其他条款不变",
    "No rebate is on record, so none applies": "记录中没有返利，因此不适用",
    "A smaller rebate keeps every committed package inside the mandate": "较小的返利能让所有已承诺的方案都留在授权范围内",
    "Fewer extended invoices keep the forward concession inside the mandate": "减少延长账期的发票张数，可让远期让步留在授权范围内",
    "A firm credit is a FIRM gain and may offset the extension; a contingent one counts as zero":
        "确定的折让属于确定收益，可以抵消账期延长；附条件的折让按零计",
}


@rule(rf"draw requested (?P<w>{WHEN}); the router sizes and prices the final plan")
def _draw_requested(m: re.Match[str]) -> str:
    return f"{when_zh(m['w'])}提出提款申请；最终方案的规模和定价另行确定"


@rule(r"Terms stay at (?P<d>\d+) days(?:, (?P<rebate>no rebate))?")
def _terms_stay(m: re.Match[str]) -> str:
    return f"账期保持 {m['d']} 天" + ("，无返利" if m["rebate"] else "")


@rule(rf"We will accept early settlement on up to (?P<amt>{M}) of this invoice at (?P<r>{PCT}), paid (?P<d>{DEADLINE})")
def _counter_settle(m: re.Match[str]) -> str:
    return f"我们接受对本发票最多 {m['amt']} 提前结算，折扣 {m['r']}，付款期限：{deadline_zh(m['d'])}"


@rule(r"We can extend terms by (?P<d>\d+) days on (?P<inv>the next invoice|the next \w+ invoices)")
def _counter_extend(m: re.Match[str]) -> str:
    count = {"the next invoice": "下一张发票"}.get(m["inv"]) or "接下来的 " + {
        "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
        "eleven": "11", "twelve": "12"}.get(m["inv"].split()[2], m["inv"].split()[2]) + " 张发票"
    return f"我们可以将{count}的账期延长 {m['d']} 天"


@rule(rf"if the (?P<r>{PCT}) credit is firm on each of them")
def _counter_credit(m: re.Match[str]) -> str:
    return f"前提是每张发票都确定给予 {m['r']} 的折让"


@rule(rf"We can offer (?P<r>{PCT}) off next quarter's purchases of up to (?P<base>{M})")
def _counter_rebate(m: re.Match[str]) -> str:
    return f"我们可以对下季度最多 {m['base']} 的采购给予 {m['r']} 的返利"


@rule(r"(?P<d>\d+)-day terms accepted")
def _counter_terms_accepted(m: re.Match[str]) -> str:
    return f"接受 {m['d']} 天账期"


@rule(rf"with a (?P<r>{PCT}) price adjustment on future invoices, no rebate")
def _counter_price(m: re.Match[str]) -> str:
    return f"对今后的发票给予 {m['r']} 的价格调整，无返利"


@rule(rf"Early settlement at (?P<r>{PCT}) is cheaper than financing the invoice on the marginal committed source; "
      r"the line covers the rest of the near-term gap")
def _rationale_early(m: re.Match[str]) -> str:
    return f"按 {m['r']} 提前结算，比用边际已承诺资金来源为发票融资更便宜；其余近期缺口由额度覆盖"


# ---------------------------------------------------------------- the verifier: violations, notes, the verdict line

_NOTES.update({
    "immediate discount: settled in cash now and capped separately, not a forward concession": "立即折扣：现在以现金结算，单独设上限，不属于远期让步",
    "contingent rebate counted at maximum": "附条件返利按最大值计",
    "The price adjustment covers the per-invoice cost of funding the longer terms on the marginal committed source, so the net forward "
    "concession is about zero": "价格调整覆盖了为更长账期融资的每张发票成本（按边际已承诺资金来源计），因此净远期让步约为零",
    "No committed source can carry a permanent need; concessions valued at the maximum APR": "没有已承诺的来源能承担长期需求；让步按最高年化成本估值",
    "no admissible plan on sources able to carry a permanent need": "在能承担长期需求的来源上没有可行方案",
    "The mandate cannot be relied on; nothing evaluated": "授权不可依赖；未做任何评估",
    "Owner or buyer clarification needed; nothing booked": "需要您或买方进一步澄清；未入账任何内容",
    "Nothing booked": "未入账任何内容",
    "The verdict requires owner approval": "判定结果要求由您批准",
})


@rule("(?:" + "|".join(re.escape(k) for k in _NOTES) + ")")
def _fixed_note(m: re.Match[str]) -> str:
    return _NOTES[m.group(0)]


@rule(rf"Under this offer projected cash falls below the reserve (?P<w>{WHEN})")
def _under_offer(m: re.Match[str]) -> str:
    return f"按此报价，预计现金将在{when_zh(m['w'])}低于储备"


@rule(rf"Projected cash falls below the reserve (?P<w>{WHEN})(?P<note>.*)")
def _projected_below(m: re.Match[str]) -> str:
    return f"预计现金将在{when_zh(m['w'])}低于储备{tr(m['note']) if m['note'] else ''}"


@rule(rf"Early settlement at (?P<r>{PCT}) costs more than financing the invoice: break-even (?P<be>{PCT})")
def _early_costs_more(m: re.Match[str]) -> str:
    return f"按 {m['r']} 提前结算，比为发票融资成本更高：盈亏平衡点 {m['be']}"


@rule(rf"The early payment costs (?P<c1>{M}), not less than the plan without it \((?P<c0>{M})\)")
def _early_dearer(m: re.Match[str]) -> str:
    return f"提前付款的成本为 {m['c1']}，不低于没有它的方案（{m['c0']}）"


@rule(rf"No funding is needed without the early payment; taking it costs (?P<c1>{M}) for cash the books do not need")
def _early_not_needed(m: re.Match[str]) -> str:
    return f"没有提前付款也无需融资；接受它要花 {m['c1']}，换来账上并不需要的现金"


@rule(rf"cured on (?P<src>.+?) \(sources able to carry a permanent need\): (?P<plan>[^;]+)"
      rf"(?:; the extension itself costs (?P<c>{M}) per invoice)?(?:; the cure cannot run today: (?P<why>.+))?")
def _cured_on(m: re.Match[str]) -> str:
    out = f"可通过{m['src']}解决（能承担长期需求的来源）：{tr(m['plan'])}"
    if m["c"]:
        out += f"；账期延长本身每张发票的成本为 {m['c']}"
    if m["why"]:
        out += f"；该方案今天无法执行：{tr(m['why'])}"
    return out


@rule(rf"the extension itself costs (?P<c>{M}) per invoice")
def _extension_costs(m: re.Match[str]) -> str:
    return f"账期延长本身每张发票的成本为 {m['c']}"


@rule(r"the cure cannot run today: (?P<why>.+)")
def _cure_cannot(m: re.Match[str]) -> str:
    return f"该方案今天无法执行：{tr(m['why'])}"


@rule(r"The offered (?P<o>\d+)-day terms fail their own re-check; (?P<t>\d+) days is the longest that passes")
def _offered_fail(m: re.Match[str]) -> str:
    return f"提出的 {m['o']} 天账期未通过自身复核；{m['t']} 天是能通过的最长账期"


@rule(r"on current books with these terms the router's committed plan \((?P<plan>.+)\) keeps the reserve")
def _router_keeps(m: re.Match[str]) -> str:
    return f"按目前账目和这些条款，已承诺方案（{tr(m['plan'])}）可保住储备"


@rule(rf"(?:Re-checked as an offer|Option B passes its own re-check), its terms leave a shortfall of (?P<amt>{M}) (?P<w>{WHEN}), funded by the plan: (?P<plan>.+)")
def _recheck_a(m: re.Match[str]) -> str:
    return f"作为报价复核时，其条款会在{when_zh(m['w'])}留下 {m['amt']} 的缺口，由以下方案融资：{tr(m['plan'])}"


@rule(rf"Option B passes its own re-check: its terms leave a shortfall of (?P<amt>{M}) (?P<w>{WHEN}), funded by the plan: (?P<plan>.+)")
def _recheck_b(m: re.Match[str]) -> str:
    return f"方案 B 通过自身复核：其条款会在{when_zh(m['w'])}留下 {m['amt']} 的缺口，由以下方案融资：{tr(m['plan'])}"


@rule(r"Re-checked as an offer, its terms leave a shortfall of (?P<amt>" + M + r") (?P<w>" + WHEN + r"), funded by the plan: (?P<plan>.+)")
def _recheck_c(m: re.Match[str]) -> str:
    return f"作为报价复核时，其条款会在{when_zh(m['w'])}留下 {m['amt']} 的缺口，由以下方案融资：{tr(m['plan'])}"


@rule(r"Price-adjustment counter at (?P<t>\d+) days, not (?P<o>\d+): (?P<why>.+)")
def _pa_counter(m: re.Match[str]) -> str:
    return f"价格调整还价按 {m['t']} 天账期，而非 {m['o']} 天：{tr(m['why'])}"


@rule(rf"(?P<days>[\d\-, or]+)-day terms cannot be funded from committed sources: the shortfall of (?P<amt>{M}) (?P<w>{WHEN}) has no cure")
def _pa_no_cure(m: re.Match[str]) -> str:
    return f"{m['days']} 天账期无法用已承诺的来源融资：{when_zh(m['w'])}的 {m['amt']} 缺口没有解决办法"


@rule(rf"(?P<days>\d+)-day terms cannot be funded from committed sources: the shortfall of (?P<amt>{M}) (?P<w>{WHEN}) has no cure")
def _pa_no_cure_single(m: re.Match[str]) -> str:
    return f"{m['days']} 天账期无法用已承诺的来源融资：{when_zh(m['w'])}的 {m['amt']} 缺口没有解决办法"


@rule(rf"bound to (?P<inv>{INV}) \(face (?P<face>{M}), due (?P<w>{WHEN})\)")
def _bound_to(m: re.Match[str]) -> str:
    return f"对应{inv(m['inv'])}（金额 {m['face']}，{when_zh(m['w'])}到期）"


@rule(r"target (?P<t>\d+) days . current (?P<c>\d+) days \((?P<what>.+)\) = (?P<delta>[+\-−]?\d+) days")
def _target_terms(m: re.Match[str]) -> str:
    return f"目标 {m['t']} 天 − 当前 {m['c']} 天（{agr(inv(m['what']).replace('recurring invoice to', '定期发票：'))}）= {m['delta']} 天"


@rule(rf"terms extension priced as a loan: committed marginal source: (?P<fac>{N}) (?P<r>[\d.]+%)")
def _priced_as_loan(m: re.Match[str]) -> str:
    return f"账期延长按贷款定价：已承诺的边际资金来源 {m['fac']} {m['r']}"


@rule(rf"Forward concessions (?P<a>{M}) against (?P<b>{M})")
def _fwd_against(m: re.Match[str]) -> str:
    return f"远期让步 {m['a']}，对照上限 {m['b']}"


@rule(r"Counters: (?P<list>Option [A-Z](?:, Option [A-Z])*)")
def _counters_list(m: re.Match[str]) -> str:
    return "还价：" + "、".join(f"方案 {x[-1]}" for x in m["list"].split(", "))


@rule(r"Covenants hold: (?P<list>.+)")
def _covenants_hold(m: re.Match[str]) -> str:
    return "契约满足：" + m["list"].replace(", ", "、")


@rule(rf"rebate base: expected order of (?P<b>\S+): (?P<label>.+?) \(days (?P<a>\d+)–(?P<z>\d+)\) (?P<amt>{M}), (?P<firm>not firm|firm); counted at maximum")
def _rebate_base(m: re.Match[str]) -> str:
    label = {"next quarter": "下季度"}.get(m["label"], m["label"])
    firm = "不确定" if m["firm"] == "not firm" else "确定"
    return f"返利基数：{m['b']} 的预期订单：{label}（第 {m['a']}–{m['z']} 天）{m['amt']}，{firm}；按最大值计"


@rule(r"(?P<status>not applied|pending|committed|in use); cash (?P<w1>" + WHEN + r"), gap opens (?P<w2>" + WHEN + r")")
def _router_note(m: re.Match[str]) -> str:
    status = {"not applied": "尚未申请", "pending": "审批中", "committed": "已承诺", "in use": "使用中"}[m["status"]]
    return f"{status}；资金{when_zh(m['w1'])}到账，缺口{when_zh(m['w2'])}出现"


@rule(r"(?P<status>not applied|pending|committed|in use)")
def _router_status(m: re.Match[str]) -> str:
    return {"not applied": "尚未申请", "pending": "审批中", "committed": "已承诺", "in use": "使用中"}[m["status"]]


@rule(rf"cash (?P<w1>{WHEN}), gap opens (?P<w2>{WHEN})")
def _router_cash_gap(m: re.Match[str]) -> str:
    return f"资金{when_zh(m['w1'])}到账，缺口{when_zh(m['w2'])}出现"


@rule(rf"(?P<name>.+?): draw (?P<amt>{M}) \(arrives (?P<w>{WHEN})\)")
def _loan_component(m: re.Match[str]) -> str:
    return f"{m['name']}：提款 {m['amt']}（{when_zh(m['w'])}到账）"


@rule(r"Router optimum")
def _router_optimum(m: re.Match[str]) -> str:
    return "最优融资方案"


@rule(r"No funding needed")
def _no_funding_label(m: re.Match[str]) -> str:
    return "无需融资"


@rule(rf"(?P<n>\d+)-day terms accepted with a (?P<r>{PCT}) price adjustment on future invoices, no rebate")
def _counter_terms_price(m: re.Match[str]) -> str:
    return f"接受 {m['n']} 天账期，并对今后的发票给予 {m['r']} 的价格调整，无返利"


@rule(r"(?P<head>REJECT|COUNTER|ACCEPT|NEEDS OWNER APPROVAL|NO VERDICT|NO DEAL)(?:: (?P<items>(?:(?!\. [A-Z]).)+))?")
def _verdict_line(m: re.Match[str]) -> str:
    head = {"REJECT": "拒绝", "COUNTER": "建议还价", "ACCEPT": "接受", "NEEDS OWNER APPROVAL": "需要您批准", "NO VERDICT": "暂无结论",
            "NO DEAL": "未成交"}[m["head"]]
    if not m["items"]:
        return head
    items = m["items"]
    for pattern, words in _VERDICT_PHRASES:
        items = pattern.sub(words, items)
    return f"{head}：{items.replace('; ', '；')}"


_VERDICT_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = tuple((re.compile(p), w) for p, w in (
    (rf"curable at ({M})", r"可用 \1 解决"),
    (r"not curable on committed sources", "已承诺的来源无法解决"),
    (r"the cure cannot run today and needs your approval", "该方案今天无法执行，且需要您批准"),
    (r"the cure needs your approval and cannot run today", "该方案需要您批准，且今天无法执行"),
    (r"the cure cannot run today", "该方案今天无法执行"),
    (r"the cure needs your approval", "该方案需要您批准"),
    (r" vs ", " 对 "),
))


# ---------------------------------------------------------------- the owner's decision on a contract the agent read (brief 03)

# A document's title as the reading gives it: the demo titles and the defaults (`contracts.records.KIND_TITLES`, "Contract {ref}")
# are said in Chinese with the reference kept; a title the owner typed stays as written.
_DOC_TITLES = {"Supply agreement": "供货协议", "Credit line agreement": "信用额度协议", "Invoice financing agreement": "发票融资协议",
               "Buyer contract": "买方合同", "Lender agreement": "贷款协议", "Contract": "合同"}
_DOC_TITLE = re.compile(r"(?P<kind>" + "|".join(sorted(map(re.escape, _DOC_TITLES), key=len, reverse=True)) + r")(?: (?P<ref>[A-Z0-9][\w-]*))?")


def _doc_title(title: str) -> str:
    m = _DOC_TITLE.fullmatch(title)
    if m is None:
        return title
    return _DOC_TITLES[m["kind"]] + (f" {m['ref']}" if m["ref"] else "")


@rule(r"Document (?P<id>DOC-\d{6}) \((?P<title>.+?)\) confirmed by the owner: the agent read it, the owner confirmed it; nothing in the books"
      rf" changed(?:; linked to (?P<fac>{N}|FAC-[\w-]+) for reference \(the facility itself is unchanged\))?")
def _doc_confirmed(m: re.Match[str]) -> str:
    out = f"文件 {m['id']}（{_doc_title(m['title'])}）已由您确认：代理读取了该文件，您确认了读取结果；账本未作任何更改"
    return out + (f"；已关联到{m['fac']}以供参考（该融资工具本身未变）" if m["fac"] else "")


@rule(r"Document (?P<id>DOC-\d{6}) \((?P<title>.+?)\) rejected by the owner; nothing recorded from it")
def _doc_rejected(m: re.Match[str]) -> str:
    return f"文件 {m['id']}（{_doc_title(m['title'])}）已由您驳回；未从中记录任何内容"


# ---------------------------------------------------------------- the verdict's Advanced fold: passed checks and the autonomy proof
# `passed_checks[].label / observed / limit` and `autonomy.covered / gaps / notes` are the verifier's and the compiler's English. The
# evaluate view says each beside the original as `*_when`; these templates are what the Chinese one is made from. Figures, rates and names
# are carried over exactly; a sentence no template knows passes through unchanged (and is recorded in `MISSES`).


@rule(rf"Implied cost of early settlement of (?P<inv>{INV})")
def _chk_apr(m: re.Match[str]) -> str:
    return f"提前结算{inv(m['inv'])}的隐含成本"


@rule(r"DSCR with the extension funded \(pro-forma estimate\)")
def _chk_dscr_forma(m: re.Match[str]) -> str:
    return "账期延长并融资后的偿债覆盖率 DSCR（预估）"


@rule(r"Lowest monthly DSCR \(month (?P<n>\d+)\)")
def _chk_dscr(m: re.Match[str]) -> str:
    return f"最低月度偿债覆盖率 DSCR（第 {m['n']} 月）"


@rule(r"Highest monthly leverage \(month (?P<n>\d+)\)")
def _chk_leverage(m: re.Match[str]) -> str:
    return f"最高月度杠杆率（第 {m['n']} 月）"


@rule(rf"(?P<fac>{N}|[^:]+): clean-down")
def _chk_clean_down(m: re.Match[str]) -> str:
    return f"{m['fac']}：清零要求"


@rule(r"(?P<n>\d+) days at zero")
def _chk_zero_days(m: re.Match[str]) -> str:
    return f"已有 {m['n']} 天为零"


@rule(r"≥ (?P<n>\d+) consecutive days")
def _chk_zero_limit(m: re.Match[str]) -> str:
    return f"≥ 连续 {m['n']} 天"


@rule(r"Minimum cash( with the committed plan)?")
def _chk_min_cash(m: re.Match[str]) -> str:
    return "采用已承诺方案后的最低现金" if m.group(1) else "最低现金"


@rule(rf"(?P<amt>{M}) (?:on day (?P<d>\d+)|(?P<w>{WHEN}))")
def _chk_min_cash_observed(m: re.Match[str]) -> str:
    return f"{m['amt']}（{when_zh(m['w']) if m['w'] else '第 ' + m['d'] + ' 天'}）"


@rule(r"Early payment against the router's plan")
def _chk_early_vs_plan(m: re.Match[str]) -> str:
    return "提前付款与融资方案的对比"


@rule(r"no admissible plan without the offer")
def _chk_no_plan_without(m: re.Match[str]) -> str:
    return "没有该报价就没有可行的融资方案"


_OBLIGATION_ZH = {
    "immediate discount": "即时折扣", "terms extension": "账期延长", "contingent rebate": "或有返利", "volume commitment": "采购量承诺",
    "operational concession": "运营让步", "price adjustment": "价格调整", "claimed prior concession": "声称的既有让步",
}
_BASE_ZH = {"future invoices": "未来发票", "period purchases": "期间采购", "per event": "每次事件", "unspecified": "未指明范围", "invoice": "发票"}


def _covered_zh(what: str) -> str:
    """The tail of "terms extension on future invoices +15 days": the base, its figures and the day."""
    out = what
    for en, zh in _BASE_ZH.items():
        out = re.sub(rf"(?<![\w-]){en}(?![\w-])", zh, out)
    out = re.sub(rf"\bbase ({M})", r"基数 \1", out)
    out = re.sub(rf"\bof ({M})", r"金额 \1", out)
    out = re.sub(rf"\bat ({PCT})", r"比例 \1", out)
    out = re.sub(r"to (\d+)-day terms", r"改为 \1 天账期", out)
    out = re.sub(r"([+-]\d+) days?\b", r"\1 天", out)
    out = re.sub(rf"\b({WHEN})\b", lambda m: when_zh(m.group(1)), out)
    return out


@rule(r"(?P<type>" + "|".join(re.escape(k) for k in _OBLIGATION_ZH) + r") on (?P<what>.+)")
def _covered_term(m: re.Match[str]) -> str:
    return f"{_OBLIGATION_ZH[m['type']]}：{_covered_zh(inv(m['what']))}"


@rule(rf"early payment of (?:(?P<amt>{M}) of )?(?P<inv>{INV}|[\w:-]+) at (?P<r>{PCT})(?: (?P<w>{WHEN}))?")
def _covered_early_pay(m: re.Match[str]) -> str:
    amt = f"{m['amt']}，" if m["amt"] else ""
    when = f"，{when_zh(m['w'])}付款" if m["w"] else ""
    return f"提前付款：{amt}{inv(m['inv'])}，折扣 {m['r']}{when}"


@rule(r"the compiler could not account for every figure and request in the message(?:: (?P<why>.+))?")
def _autonomy_gap(m: re.Match[str]) -> str:
    head = "编译器无法逐项核对消息中的每个数字和请求"
    return head + (f"：{_each(m['why'], '; ', '；')}" if m["why"] else "")


@rule(r"(?P<id>[\w.:-]+): the message does not state the invoice amount")
def _gap_no_amount(m: re.Match[str]) -> str:
    return f"{m['id']}：消息没有写明发票金额"


@rule(r"(?P<id>[\w.:-]+): the stated amount is not the whole face of an open invoice")
def _gap_not_whole(m: re.Match[str]) -> str:
    return f"{m['id']}：所述金额不是某张未结发票的全额"


@rule(r"(?P<type>[A-Z_]+) leaves (?P<what>.+) unresolved")
def _note_unresolved(m: re.Match[str]) -> str:
    fields = {"base": "基数", "scope": "范围", "rate": "比例"}
    what = ", ".join(fields.get(x, x) for x in m["what"].split(", "))
    return f"{_OBLIGATION_ZH.get(m['type'].lower().replace('_', ' '), m['type'])}的 {what} 未能确定"


@rule(r"a settlement date or window is stated but not read into the terms")
def _note_date(m: re.Match[str]) -> str:
    return "消息写明了结算日期或期限，但没有读入条款"


@rule(r"(?P<doc>[\w.:-]+) holds a (?P<cue>.+) beyond the extracted terms")
def _note_cue(m: re.Match[str]) -> str:
    cue = {"question": "问题", "request": "请求", "condition": "附加条件", "other topic": "其他话题"}.get(m["cue"], m["cue"])
    return f"{m['doc']} 含有超出已提取条款的{cue}"


@rule(r"text not read into the terms: (?P<words>.+)")
def _note_unread(m: re.Match[str]) -> str:
    words = m["words"]
    more = words.endswith(".")  # the compiler lists five and ends with ", ..." (a matcher above this one may have taken a dot)
    return f"未读入条款的文字：{words.rstrip('., ') if more else words}" + (" 等" if more else "")


@rule(r"(?P<kind>an amount|a rate|a day count|a count|a date|an invoice or document reference|a number) in (?P<doc>[\w.:-]+) is not accounted for by the extracted terms")
def _note_mention(m: re.Match[str]) -> str:
    kind = {"an amount": "金额", "a rate": "比例", "a day count": "天数", "a count": "数量", "a date": "日期",
            "an invoice or document reference": "发票或文件编号", "a number": "数字"}[m["kind"]]
    return f"{m['doc']} 中的{kind}没有被已提取的条款解释"


@rule(r"the compilation is (?P<s>[A-Z_]+), not clean")
def _note_status(m: re.Match[str]) -> str:
    return f"编译状态为 {m['s']}，并不完整"


@rule(r"a term was not read \((?P<fields>.+)\)")
def _note_unread_term(m: re.Match[str]) -> str:
    return f"有条款没有读入（{m['fields']}）"


@rule(r"a discount rate is derived from a net amount, not stated")
def _note_derived_rate(m: re.Match[str]) -> str:
    return "折扣比例由净额推算，并非消息所述"


@rule(r"a base amount is stated only approximately")
def _note_approx(m: re.Match[str]) -> str:
    return "基数金额只给出了大约数"


@rule(r"no term was read")
def _note_no_term(m: re.Match[str]) -> str:
    return "没有读到任何条款"


@rule(r"the message asserts authority or a prior agreement \((?P<kinds>.+)\)")
def _note_authority(m: re.Match[str]) -> str:
    return f"消息声称有权限或既有协议（{m['kinds']}）"


@rule(r"the message asks for protected data")
def _note_protected(m: re.Match[str]) -> str:
    return "消息索要受保护的数据"


@rule(r"the message carries an unsolicited funding offer")
def _note_funding_offer(m: re.Match[str]) -> str:
    return "消息附带未经邀请的融资推介"


@rule(r"a concession is claimed as previously agreed")
def _note_claimed_prior(m: re.Match[str]) -> str:
    return "消息把某项让步说成是之前已经同意的"


@rule(r"a discount has no stated rate")
def _note_no_rate(m: re.Match[str]) -> str:
    return "折扣没有写明比例"


@rule(r"a discount does not state its invoice amount")
def _note_no_amount(m: re.Match[str]) -> str:
    return "折扣没有写明发票金额"


@rule(r"non-CNY currency stated")
def _note_currency(m: re.Match[str]) -> str:
    return "消息使用了非人民币币种"


@rule(r"a rate is stated per a period other than the invoice")
def _note_period(m: re.Match[str]) -> str:
    return "消息按发票以外的周期给出了比例"


@rule(r"the message refers to a document that was not supplied")
def _note_missing_doc(m: re.Match[str]) -> str:
    return "消息提到了未随附的文件"


# ---------------------------------------------------------------- the entry point

# "Co." and "Ltd." end in a full stop without ending a sentence (a name the caller did not lift out).
_ABBREV = re.compile(r"\b(Co|Ltd|Inc|Corp)\.(?=\s|$)")
_STOP = "\u0000"
_SENTENCE_BREAK = re.compile(r"(?<=[A-Za-z0-9)%\]⟧])\.\s+(?=[A-Z¥(⟦])")


def _lift(text: str, names: Sequence[str]) -> tuple[str, list[str]]:
    """Names the books give, replaced by tokens (longest first) so no template has to guess where a name ends."""
    lifted: list[str] = []
    ordered = sorted({n for n in names if n and len(n) > 1}, key=len, reverse=True)
    if not ordered:
        return text, lifted
    pattern = re.compile("|".join(re.escape(n) for n in ordered))

    def take(m: re.Match[str]) -> str:
        lifted.append(m.group(0))
        return f"⟦{len(lifted) - 1}⟧"

    return pattern.sub(take, text), lifted


def _restore(text: str, lifted: list[str]) -> str:
    return _TOKEN.sub(lambda m: lifted[int(m.group(1))], text)


def translate(text: str | None, names: Sequence[str] = ()) -> str | None:
    """The Chinese of a normalized English sentence (or several), unknown parts untouched. `names` are the buyer and facility names the
    books give; they are carried over exactly. None stays None; text with no Latin word (already Chinese, or only figures) is returned
    as it is."""
    if text is None or not _LATIN.search(text):
        return text
    body, lifted = _lift(text.strip(), names)
    whole = _match(body)
    if whole is not None:
        return _restore(whole + ("。" if body.endswith(".") else ""), lifted)
    protected = _ABBREV.sub(lambda m: m.group(1) + _STOP, body)
    sentences = _SENTENCE_BREAK.split(protected)
    out: list[str] = []
    for i, raw in enumerate(sentences):
        sentence = raw.replace(_STOP, ".")
        ended = i < len(sentences) - 1 or sentence.endswith(".")
        part = sentence.removesuffix(".")
        done = _match(part)
        if done is not None:
            out.append(done + ("。" if ended else ""))
            continue
        clauses = re.split(r";\s+", part)
        got = [_match(c) for c in clauses]
        if any(g is not None for g in got):
            out.append("；".join(g if g is not None else c for g, c in zip(got, clauses, strict=True)) + ("。" if ended else ""))
        else:
            if _LATIN.search(_TOKEN.sub(" ", part)):
                _miss(_restore(part, lifted))
            out.append(sentence + (". " if i < len(sentences) - 1 else ""))
    return _restore("".join(out), lifted)


def _miss(sentence: str) -> None:
    if len(MISSES) < _MISS_LIMIT:
        MISSES.add(sentence)
