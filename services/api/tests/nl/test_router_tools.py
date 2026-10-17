"""The read-only tools of the Ask FLOW router (app/nl/router/catalogue.py, app/nl/router/tools/).

The model routes and code answers: every tool is answered here from the books, in English and Chinese, and its figures equal
those the existing read routes give (GET /home, /trajectory, /state, /mandate, /receivables, /reconciliation, /approvals/queue,
/ledger; POST /router/plan, /whatif, /capex/evaluate) on the golden books at day 0 and after the clock moves to day 34. A slot
schema is a closed JSON Schema (draft 2020-12) with bounds; the catalogue sent to the model holds no name, figure or id from the
books; a customer slot is resolved in the tool; a question beyond the 120-day forecast is answered on the forecast and says so;
and no tool writes to the store.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from fractions import Fraction
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.presentation import whole
from app.api.runtime import Runtime, set_runtime
from app.nl import reset_sessions
from app.nl.answers import AnswerReply
from app.nl.answers.metrics import METRICS, Reading
from app.nl.router.catalogue import TOOLS, SlotError, Tool, catalogue_for_prompt, validate_slots
from app.nl.router.tools.common import resolve_customer
from tests.nl.conftest import OWNER, build_app
from tests.nl.test_answers import IDS, PARAMETRISED, Routes, leads, nl_ctx, runtime, snapshot

REQUIRED = {
    "cash_safety", "runway", "lowest_point", "first_breach", "cash_on_day", "upcoming_payments", "payroll_cover", "funding_need",
    "funding_plan", "plan_cost", "compare_financing", "total_debt", "debt_by_facility", "repay_all_today", "borrowing_headroom",
    "next_loan_payment", "debt_service", "who_owes_most", "overdue", "receivables_by_customer", "concentration", "customer_summary",
    "late_payment_whatif", "early_pay_offer", "terms_extension_cost", "waiting_for_me", "approvals_pending", "covenant_status",
    "covenant_breakpoints", "plan_covenants", "capex_afford", "activity", "mandate_limits", "needs_approval", "mandate_validity",
    "general_advice",
}

# The slots a model would copy from a typical question, per tool (a tool not listed takes none).
SLOTS: dict[str, dict[str, Any]] = {
    "cash_on_day": {"day": 30},
    "customer_summary": {"customer": "Foshan"},
    "late_payment_whatif": {"customer": "佛山", "days_late": 30},
    "early_pay_offer": {"customer": "Foshan"},
    "terms_extension_cost": {"customer": "Foshan", "days": 60},
}

# The tools that answer one of the bank's top-30 questions: their answer leads with what the read routes give
# (tests/nl/test_answers.py `leads`, computed from the routes alone).
LEADS = {
    "cash_safety": "LIQ-01", "runway": "LIQ-03", "lowest_point": "LIQ-04", "first_breach": "LIQ-05", "safe_to_spend": "LIQ-06",
    "upcoming_payments": "LIQ-09", "payroll_cover": "LIQ-10", "why_short": "LIQ-14", "funding_need": "LIQ-15",
    "funding_plan": "FUN-02", "plan_cost": "FUN-04", "total_debt": "DEBT-01", "repay_all_today": "DEBT-04",
    "borrowing_headroom": "DEBT-06", "next_loan_payment": "DEBT-08", "debt_service": "DEBT-03", "who_owes_most": "CUS-01",
    "overdue": "CUS-03", "concentration": "CUS-05", "late_payment_whatif": "CUS-07", "early_pay_offer": "CUS-08",
    "waiting_for_me": "DEAL-01", "approvals_pending": "DEAL-02", "terms_extension_cost": "DEAL-09", "covenant_status": "COV-01",
    "covenant_breakpoints": "COV-05", "capex_afford": "CAP-01", "activity": "ACT-01", "mandate_limits": "MAN-01",
    "needs_approval": "MAN-02",
}


# ---------------------------------------------------------------- the books


@pytest.fixture(scope="module")
def books():
    rt = runtime()
    client = TestClient(build_app(), headers=OWNER)
    yield rt, Routes(rt, client)
    set_runtime(None)
    reset_sessions()


@pytest.fixture
def day0(books):
    rt, routes = books
    set_runtime(rt)
    return rt, routes


@pytest.fixture
def fresh():
    rt = runtime()
    yield rt, TestClient(build_app(), headers=OWNER)
    set_runtime(None)
    reset_sessions()


def run(rt: Runtime, name: str, lang: str, slots: dict[str, Any] | None = None) -> AnswerReply:
    """One tool call as the router makes it: the slots validated against the schema, then answered from the books."""
    tool = TOOLS[name]
    given = SLOTS.get(name, {}) if slots is None else slots
    return tool.answer(nl_ctx(rt, lang), lang, validate_slots(tool, given))


def check_language(reply: AnswerReply, name: str) -> None:
    assert reply.text.strip() and reply.basis, reply
    assert not IDS.search(reply.text), reply.text
    assert reply.extra.get("tool") == name
    assert all(isinstance(v, str) for v in reply.figures.values())
    for mid in reply.metric_ids:
        assert mid in METRICS or mid in PARAMETRISED or mid in ("break_even_discount", "plan_covenant_ratios"), mid
    if reply.lang == "zh":
        latin = set(re.findall(r"[A-Za-z]+", reply.text)) - {"FLOW"}
        assert not latin, (latin, reply.text)
        assert not set(re.findall(r"[A-Za-z]+", reply.basis)) - {"FLOW"}, reply.basis


# ---------------------------------------------------------------- the catalogue


def test_the_catalogue_holds_the_required_tools() -> None:
    assert REQUIRED <= set(TOOLS), REQUIRED - set(TOOLS)
    assert 30 <= len(TOOLS) <= 40
    for name, tool in TOOLS.items():
        assert isinstance(tool, Tool) and tool.name == name and callable(tool.answer)
        assert tool.description and "\n" not in tool.description


_KEYWORDS_2020_12 = {"type", "properties", "required", "additionalProperties", "minimum", "maximum", "minLength", "maxLength",
                     "enum", "description"}


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_slot_schema_is_a_closed_bounded_object(name: str) -> None:
    s = TOOLS[name].slots_schema
    assert s["type"] == "object" and s["additionalProperties"] is False
    assert set(s) <= _KEYWORDS_2020_12 and isinstance(s["properties"], dict) and isinstance(s["required"], list)
    assert set(s["required"]) <= set(s["properties"]) and len(set(s["required"])) == len(s["required"])
    for key, p in s["properties"].items():
        assert re.fullmatch(r"[a-z][a-z_]*", key), key
        assert set(p) <= _KEYWORDS_2020_12 and p.get("description"), (key, p)
        assert p["type"] in ("integer", "string", "boolean"), (key, p)
        if p["type"] == "integer":
            assert isinstance(p["minimum"], int) and isinstance(p["maximum"], int) and p["minimum"] <= p["maximum"], (key, p)
        if p["type"] == "string":
            assert "enum" in p or (p["minLength"] >= 1 and 1 <= p["maxLength"] <= 200), (key, p)


def test_every_slot_schema_is_valid_draft_2020_12() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    for name, tool in TOOLS.items():
        jsonschema.Draft202012Validator.check_schema(tool.slots_schema)
        validator = jsonschema.Draft202012Validator(tool.slots_schema)
        assert not list(validator.iter_errors(SLOTS.get(name, {}))), name


def test_the_bounds_the_brief_sets() -> None:
    bounds = {("cash_safety", "horizon_days"): (1, 365), ("cash_on_day", "day"): (0, 365), ("upcoming_payments", "window_days"): (1, 365),
              ("late_payment_whatif", "days_late"): (1, 180), ("early_pay_offer", "rate_bp"): (1, 500),
              ("terms_extension_cost", "days"): (1, 180), ("activity", "window_days"): (1, 90), ("general_advice", "horizon_days"): (1, 365)}
    for (name, key), (lo, hi) in bounds.items():
        p = TOOLS[name].slots_schema["properties"][key]
        assert (p["minimum"], p["maximum"]) == (lo, hi), (name, key)
    for name in ("customer_summary", "late_payment_whatif", "terms_extension_cost"):
        assert "customer" in TOOLS[name].slots_schema["required"]
    for name in ("early_pay_offer", "concentration"):
        assert "customer" not in TOOLS[name].slots_schema["required"]


@pytest.mark.parametrize("name", sorted(TOOLS))
def test_validate_slots_holds_the_schema(name: str) -> None:
    tool = TOOLS[name]
    props, required = tool.slots_schema["properties"], tool.slots_schema["required"]
    good = dict(SLOTS.get(name, {}))
    for key in required:
        good.setdefault(key, props[key].get("minimum", "Foshan"))
    assert validate_slots(tool, good) == good
    with pytest.raises(SlotError):
        validate_slots(tool, {**good, "anything_else": 1})
    with pytest.raises(SlotError):
        validate_slots(tool, "not an object")
    for key in required:
        with pytest.raises(SlotError):
            validate_slots(tool, {k: v for k, v in good.items() if k != key})
    for key, p in props.items():
        if p["type"] == "integer":
            for ok in (p["minimum"], p["maximum"]):
                validate_slots(tool, {**good, key: ok})
            for bad in (p["minimum"] - 1, p["maximum"] + 1, True, "30", 1.5):
                with pytest.raises(SlotError):
                    validate_slots(tool, {**good, key: bad})
        if p["type"] == "string":
            for bad in ("", "x" * (p["maxLength"] + 1), 7):
                with pytest.raises(SlotError):
                    validate_slots(tool, {**good, key: bad})
        if p["type"] == "boolean":
            with pytest.raises(SlotError):
                validate_slots(tool, {**good, key: "yes"})


def test_the_catalogue_for_the_prompt_carries_no_books_data(fresh) -> None:
    rt, client = fresh
    sent = catalogue_for_prompt()
    assert [x["name"] for x in sent] == list(TOOLS) and all(set(x) == {"name", "description", "parameters"} for x in sent)
    assert all(x["parameters"] == TOOLS[x["name"]].slots_schema for x in sent)
    blob = json.dumps(sent, ensure_ascii=False)
    # every name the books hold: counterparties (name, a customer's short form and Chinese alias), facilities, debts
    client.post("/customers", json={"name": "Shenzhen Precision Parts Co.", "short_name": "SPP", "idempotency_key": "cat-1"})
    s = rt.store.get_state()
    words: set[str] = set()
    for c in s.counterparties:
        if c.role == "OWNER":
            continue
        words |= {c.name, c.id} | ({c.name.split()[0].strip(".,")} if c.role == "BUYER" else set())  # a customer's short name
    words |= {"佛山", "东莞", "SPP"}
    words |= {f.name for f in s.facilities} | {f.id for f in s.facilities} | {d.label for d in s.debts}
    words |= {r.id for r in s.receivables}
    for word in words:
        assert word.lower() not in blob.lower(), word
    assert "¥" not in blob and not re.search(r'fen": -?\d', blob)
    for x in sent:  # no figure in a description: every number lives in a schema bound
        assert not re.search(r"\d", x["description"]), x["description"]
        for p in x["parameters"]["properties"].values():
            assert not re.search(r"\d", p["description"]), p["description"]
    figures = {s.cash_fen, rt.store.get_mandate().min_cash_fen, *(r.face_fen for r in s.receivables), *(f.limit_fen for f in s.facilities),
               *(d.principal_fen for d in s.debts)}
    for n in figures - {0}:
        for text in (str(n), str(n // 100), f"{n // 100:,}"):
            assert not re.search(rf"(?<!\d){re.escape(text)}(?!\d)", blob), text
    r = client.post("/clock/advance", json={"to_day": 34})
    assert r.status_code == 200, r.text
    assert catalogue_for_prompt() == sent  # the same for every day and every company


# ---------------------------------------------------------------- day 0: every tool, en and zh, read-only


@pytest.mark.parametrize("lang", ["en", "zh"])
@pytest.mark.parametrize("name", sorted(TOOLS))
def test_every_tool_answers_on_day_0_and_writes_nothing(day0, name: str, lang: str) -> None:
    rt, _ = day0
    before = snapshot(rt)
    reply = run(rt, name, lang)
    assert snapshot(rt) == before  # no operation, approval, verdict, security event, commitment, state, mandate or chain change
    assert reply.lang == lang
    check_language(reply, name)


@pytest.mark.parametrize("lang", ["en", "zh"])
@pytest.mark.parametrize("name", sorted(LEADS))
def test_a_tool_leads_with_the_routes_figure(day0, name: str, lang: str) -> None:
    rt, routes = day0
    reply = run(rt, name, lang)
    lead, figures = leads(routes, LEADS[name], lang)
    assert reply.text.startswith(lead), (lead, reply.text)
    for f in figures:
        assert f in reply.text, (f, reply.text)


def test_the_brief_figures_on_day_0(day0) -> None:
    rt, g = day0
    c, a = g.cash, g.action
    # the figures, read from the routes, are the brief's
    assert whole(int(g.state["cash_fen"])) == "¥400,000" and whole(c["floor_fen"]) == "¥300,000"
    assert c["first_breach_day"] == 12 and (whole(c["lowest_fen"]), c["lowest_day"]) == ("−¥105,000", 30)
    assert whole(g.router["committed"]["need_fen"]) == "¥405,000" and a["cost_total_display"] == "¥3,113.93"
    assert whole(g.total_debt) == "¥1,500,000" and g.router["marginal"]["break_even_display"] == "0.88%"
    dscr = min(Fraction(m["dscr"].rstrip("x")) for m in g.traj["months"] if m["dscr"])
    lev = max(Fraction(m["leverage"].rstrip("x")) for m in g.traj["months"] if m["leverage"])
    assert (f"{float(dscr):.2f}×", f"{float(lev):.2f}×") == ("2.00×", "1.35×")
    # ... and the tools say them
    assert run(rt, "cash_position", "en").text == "¥400,000 in cash today, ¥100,000 above your ¥300,000 reserve."
    assert run(rt, "cash_position", "zh").text == "今天现金 ¥400,000，比您 ¥300,000 的最低现金储备高 ¥100,000。"
    safe = run(rt, "cash_safety", "en").text
    for f in ("¥300,000", "day 12", "−¥105,000 on day 30", "¥405,000", "¥3,113.93"):
        assert f in safe, f
    assert run(rt, "first_breach", "en").text.startswith("On day 12")
    assert run(rt, "funding_need", "en").text.startswith("¥405,000")
    assert run(rt, "plan_cost", "en").text.startswith("¥3,113.93")
    assert run(rt, "total_debt", "en").text.startswith("¥1,500,000")
    cov = run(rt, "covenant_status", "en").text
    assert "2.00×" in cov and "1.35×" in cov
    assert "0.88%" in run(rt, "early_pay_offer", "en").text
    assert "0.88%" in run(rt, "early_pay_offer", "zh").text


def test_the_new_tools_agree_with_the_routes_on_day_0(day0) -> None:
    rt, g = day0
    for lang in ("en", "zh"):
        on30 = run(rt, "cash_on_day", lang, {"day": 30}).text
        assert on30.startswith(whole(g.closing(30)) if lang == "en" else f"第 30 天现金为 {whole(g.closing(30))}"), on30
        rel = run(rt, "cash_on_day", lang, {"day": 20, "relative": True}).text
        assert whole(g.closing(20)) in rel
        owed: dict[str, int] = defaultdict(int)
        for r in g.receivables["rows"]:
            owed[r["buyer_id"]] += r["outstanding_fen"]
        by = run(rt, "receivables_by_customer", lang).text
        assert whole(sum(owed.values())) in by and whole(owed["BUYER-1"]) in by
        summary = run(rt, "customer_summary", lang, {"customer": "Foshan Home Retail Co."}).text
        ri = g.state["recurring_invoices"][0]
        assert whole(owed["BUYER-1"]) in summary and str(ri["terms_days"]) in summary and "1.20%" in summary
        debt = run(rt, "debt_by_facility", lang).text
        assert debt.startswith(whole(g.total_debt) if lang == "en" else f"合计 {whole(g.total_debt)}")
        for room, _ in g.undrawn:
            assert whole(room) in debt
        compare = run(rt, "compare_financing", lang).text
        assert whole(g.router["committed"]["total_cost_fen"]) in compare
        full = next(r for r in g.router["comparison"] if r["key"] == "full_discount")
        assert whole(full["cost_fen"]) in compare
        rcv = min((r for r in g.receivables["rows"] if not r["past_due"]), key=lambda r: r["due_day"])
        ins = run(rt, "upcoming_receipts", lang, {"window_days": 40}).text
        assert whole(rcv["face_fen"]) in ins and (f"day {rcv['due_day']}" if lang == "en" else f"第 {rcv['due_day']} 天") in ins
        valid = run(rt, "mandate_validity", lang).text
        assert valid.startswith("Yes" if lang == "en" else "有效") and str(g.mandate["expires_day"]) in valid
        advice = run(rt, "general_advice", lang).text
        assert g.action["cost_total_display"] in advice and ("day 12" if lang == "en" else "第 12 天") in advice
        assert ("before it expires on day 90" if lang == "en" else "第 90 天到期前续签") in advice
        plan_cov = run(rt, "plan_covenants", lang).text
        assert plan_cov.startswith("Yes. With FLOW's plan" if lang == "en" else "满足。执行 FLOW 的方案后")
    short = run(rt, "cash_safety", "en", {"horizon_days": 10}).text
    low10 = min(g.closing(d) for d in range(11))
    assert short.startswith("Yes: for the next 10 days") and whole(low10) in short and "from day 12" in short
    assert run(rt, "cash_safety", "zh", {"horizon_days": 10}).text.startswith("安全：未来 10 天")
    assert run(rt, "cash_safety", "en", {"horizon_days": 30}).text.startswith("Not on today's books")


def test_a_question_beyond_the_forecast_is_answered_on_the_forecast(day0) -> None:
    rt, g = day0
    end = g.traj["days"][-1]["day"]
    assert end == 120
    for lang in ("en", "zh"):
        note = "FLOW's forecast runs 120 days, to day 120, so this answers on those 120 days, not 365." if lang == "en" else \
            "FLOW 的预测只覆盖 120 天（到第 120 天），以下按这 120 天回答，而不是 365 天。"
        for name in ("cash_safety", "general_advice"):
            reply = run(rt, name, lang, {"horizon_days": 365})
            assert reply.text.startswith(note) and reply.figures["horizon_capped"] == "yes", reply.text
        pays = run(rt, "upcoming_payments", lang, {"window_days": 365})
        assert pays.text.startswith(note) and ("until the forecast ends on day 120" if lang == "en" else "到预测结束的第 120 天为止") in pays.text
        day300 = run(rt, "cash_on_day", lang, {"day": 300})
        assert ("forecast runs to day 120" if lang == "en" else "预测只到第 120 天") in day300.text
        assert whole(g.closing(120)) in day300.text
        late = run(rt, "late_payment_whatif", lang, {"customer": "Foshan", "days_late": 120})
        assert ("past the end of FLOW's 120-day forecast" if lang == "en" else "已超出 FLOW 120 天预测的终点") in late.text
        for reply in (pays, day300, late):
            check_language(reply, reply.extra["tool"])
    assert run(rt, "cash_safety", "en", {"horizon_days": 120}).text.startswith("Not on today's books")  # the forecast itself: no note


# ---------------------------------------------------------------- customers


def test_customer_resolution(fresh) -> None:
    rt, client = fresh
    r = Reading.of(nl_ctx(rt, "en"))
    for said in ("Foshan Home Retail Co.", "foshan home retail co", "Foshan", "FOSHAN", "Foshan Home", "Foshan's", "佛山", "佛山那家客户"):
        assert resolve_customer(r, said).buyer_id == "BUYER-1", said
    for said in ("Dongguan Office Supplies Ltd.", "Dongguan", "东莞"):
        assert resolve_customer(r, said).buyer_id == "BUYER-2", said
    for said in ("Shenzhen Widgets", "Co., Ltd.", "the customer", "Main bank", "", "  "):
        res = resolve_customer(r, said)
        assert res.buyer_id is None and not res.ambiguous and set(res.candidates) == {"BUYER-1", "BUYER-2"}, said
    both = resolve_customer(r, "Foshan or Dongguan")
    assert both.buyer_id is None and both.ambiguous and set(both.candidates) == {"BUYER-1", "BUYER-2"}
    # a second Foshan company, added with a short name of its own
    added = client.post("/customers", json={"name": "Foshan Metal Works Ltd.", "short_name": "Metalworks", "idempotency_key": "rt-1"})
    assert added.status_code == 200, added.text
    new_id = added.json()["customer"]["id"]
    r = Reading.of(nl_ctx(rt, "en"))
    same = resolve_customer(r, "Foshan")
    assert same.ambiguous and set(same.candidates) == {"BUYER-1", new_id}
    assert resolve_customer(r, "Foshan Home Retail").buyer_id == "BUYER-1"
    assert resolve_customer(r, "Foshan Metal Works").buyer_id == new_id
    assert resolve_customer(r, "metalworks").buyer_id == new_id


def test_an_unknown_or_ambiguous_customer_is_asked_about(fresh) -> None:
    rt, client = fresh
    before = snapshot(rt)
    for name in ("customer_summary", "late_payment_whatif", "terms_extension_cost", "early_pay_offer", "concentration"):
        slots = {**SLOTS.get(name, {}), "customer": "Shenzhen Widgets"}
        slots.setdefault("days_late" if name == "late_payment_whatif" else "x", 30)
        slots.pop("x", None)
        en, zh = run(rt, name, "en", slots), run(rt, name, "zh", slots)
        assert en.text == ("Which customer do you mean? I could not tell from the question. Your customers are Foshan Home Retail Co. "
                           "and Dongguan Office Supplies Ltd."), en.text
        assert zh.text == "您指的是哪位客户？我无法从问题中确定。您的客户有佛山和东莞。", zh.text
        assert "Shenzhen" not in en.text and en.extra["needs"] == "customer" and not en.figures
        for reply in (en, zh):
            check_language(reply, name)
    assert snapshot(rt) == before
    both = run(rt, "customer_summary", "en", {"customer": "Foshan or Dongguan"})
    assert both.text.startswith("Which customer do you mean: Foshan Home Retail Co. or Dongguan Office Supplies Ltd.?"), both.text
    assert run(rt, "customer_summary", "zh", {"customer": "佛山还是东莞"}).text.startswith("您指的是哪位客户：佛山还是东莞？")
    client.post("/customers", json={"name": "Foshan Metal Works Ltd.", "idempotency_key": "rt-2"})
    two = run(rt, "customer_summary", "en", {"customer": "Foshan"})
    assert two.text.startswith("Which customer do you mean: Foshan Home Retail Co. or Foshan Metal Works Ltd.?"), two.text
    two_zh = run(rt, "customer_summary", "zh", {"customer": "佛山"})
    assert two_zh.text == "有 2 位客户都符合，请用完整的客户名称再问一次。", two_zh.text
    check_language(two_zh, "customer_summary")


def test_a_named_customer_is_answered_for_that_customer(day0) -> None:
    rt, _ = day0
    dg = run(rt, "customer_summary", "en", {"customer": "Dongguan"})
    assert dg.text.startswith("Dongguan Office Supplies Ltd. owes you nothing right now."), dg.text
    assert run(rt, "customer_summary", "zh", {"customer": "东莞"}).text.startswith("东莞目前不欠您款项。")
    share = run(rt, "concentration", "en", {"customer": "Dongguan"})
    assert share.text.startswith("0%: Dongguan Office Supplies Ltd. accounts for 0% of what you are owed"), share.text
    assert run(rt, "concentration", "en", {"customer": "佛山"}).text.startswith("100%: Foshan Home Retail Co.")
    none = run(rt, "late_payment_whatif", "en", {"customer": "Dongguan", "days_late": 10})
    assert none.text.startswith("Dongguan Office Supplies Ltd. has no unpaid invoice"), none.text
    offer = run(rt, "early_pay_offer", "en", {"customer": "Dongguan"})
    assert offer.text.startswith("There is no early-payment offer from Dongguan Office Supplies Ltd. on your books"), offer.text
    cheap = run(rt, "early_pay_offer", "en", {"rate_bp": 50})
    assert cheap.text.startswith("Yes on price: 0.50% is at or below your 0.88% break-even"), cheap.text
    quick = run(rt, "late_payment_whatif", "en", {"customer": "Foshan Home Retail", "days_late": 15})
    assert "(day 47 instead of day 32)" in quick.text and "nothing was changed" in quick.text


# ---------------------------------------------------------------- after a state change


def test_after_the_clock_moves_to_day_34_the_tools_follow_the_books(fresh) -> None:
    rt, client = fresh
    r = client.post("/clock/advance", json={"to_day": 34})
    assert r.status_code == 200, r.text
    g = Routes(rt, client)
    c = g.cash
    assert g.today == 34 and c["first_breach_day"] == 34
    late = [o for o in g.recon["outstanding"] if o["past_due"]]
    assert late
    days_late = g.today - late[0]["due_day"]
    for lang in ("en", "zh"):
        before = snapshot(rt)
        replies = []
        cash = run(rt, "cash_position", lang)
        assert whole(int(g.state["cash_fen"])) in cash.text and whole(c["floor_fen"]) in cash.text
        safe = run(rt, "cash_safety", lang)
        assert safe.text.startswith("不安全" if lang == "zh" else "No: cash is already below"), safe.text
        breach = run(rt, "first_breach", lang)
        assert breach.text.startswith("已经跌破" if lang == "zh" else "Already:"), breach.text
        chase = run(rt, "overdue", lang)
        assert chase.text.startswith(f"佛山：{whole(late[0]['face_fen'])}，已逾期 {days_late} 天" if lang == "zh"
                                     else f"Foshan Home Retail Co.: {whole(late[0]['face_fen'])}, {days_late} days late"), chase.text
        summary = run(rt, "customer_summary", lang, {"customer": "Foshan"})
        assert whole(late[0]["face_fen"]) in summary.text and str(days_late) in summary.text
        on = run(rt, "cash_on_day", lang, {"day": 10, "relative": True})
        assert whole(g.closing(44)) in on.text and ("day 44 (in 10 days)" if lang == "en" else "第 44 天（10 天后）") in on.text
        past = run(rt, "cash_on_day", lang, {"day": 20})
        assert ("Day 20 has already passed" if lang == "en" else "第 20 天已经过去") in past.text
        loan = run(rt, "next_loan_payment", lang)
        debt = g.state["debts"][0]
        assert (f"第 {debt['next_payment_day']} 天" if lang == "zh" else f"on day {debt['next_payment_day']}") in loan.text
        owed = run(rt, "total_debt", lang)
        assert owed.text.startswith(whole(g.total_debt))
        did = run(rt, "activity", lang, {"window_days": 90})
        ran = len([o for o in g.ledger["operations"] if o.get("status", "EXECUTED") == "EXECUTED"])
        assert ran and did.text.startswith(f"最近 90 天执行了 {ran} 项操作" if lang == "zh"
                                           else "One operation" if ran == 1 else f"{ran} operations"), did.text
        valid = run(rt, "mandate_validity", lang)
        assert ("valid until day 90, 56 days from now" if lang == "en" else "有效至第 90 天，还有 56 天") in valid.text
        advice = run(rt, "general_advice", lang)
        assert ("cash is already below your reserve" if lang == "en" else "现金已低于您的储备线") in advice.text
        assert ("chase Foshan Home Retail Co." if lang == "en" else "催收佛山") in advice.text
        replies += [cash, safe, breach, chase, summary, on, past, loan, owed, did, valid, advice]
        for name in TOOLS:  # every other tool still answers on the moved books
            replies.append(run(rt, name, lang))
        assert snapshot(rt) == before
        for reply in replies:
            check_language(reply, reply.extra["tool"])


def test_after_the_mandate_lapses_the_validity_tool_says_so(fresh) -> None:
    rt, client = fresh
    assert client.post("/clock/advance", json={"to_day": 95}).status_code == 200
    en, zh = run(rt, "mandate_validity", "en"), run(rt, "mandate_validity", "zh")
    assert en.text.startswith("No: it expired on day 90, so FLOW only proposes and you decide"), en.text
    assert zh.text.startswith("无效：它已于第 90 天到期"), zh.text
    assert "sign a new mandate" in run(rt, "general_advice", "en").text


def test_after_the_plan_is_approved_the_plan_covenants_were_the_books(fresh) -> None:
    """The plan's pro forma, read before the plan runs, is the leverage the books carry once it has run."""
    from tests.nl.test_answers import approve_the_plan

    rt, client = fresh
    before = run(rt, "plan_covenants", "en").text
    approve_the_plan(client)
    g = Routes(rt, client)
    lev = max(Fraction(m["leverage"].rstrip("x")) for m in g.traj["months"] if m["leverage"])
    assert f"highest leverage {float(lev):.2f}×" in before, before
    snap = snapshot(rt)
    for lang in ("en", "zh"):
        for name in TOOLS:
            check_language(run(rt, name, lang), name)
    assert snapshot(rt) == snap
    assert run(rt, "funding_need", "en").text.startswith("Nothing:")
    assert run(rt, "compare_financing", "en").text.startswith(("Nothing to compare", "FLOW's plan", "None of the ways")), \
        run(rt, "compare_financing", "en").text
