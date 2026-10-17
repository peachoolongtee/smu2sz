"""The read-only answers to the owner's top 30 questions (app/nl/answers; research/owner-questions BASELINE section 4).

On the golden books at day 0, every wording of the bank (en and zh, with each paraphrase) is matched to its question, and the answer
leads with the yes/no or the figure that the existing read routes give (GET /home, /trajectory, /state, /mandate, /receivables,
/reconciliation, /approvals/queue, /ledger; POST /router/plan, /whatif, /capex/evaluate), computed here independently of the answer
package. The answers follow the books after a state change (the standing plan approved; the clock moved to day 34), never write, never
carry an id, and the Chinese ones carry no English word but FLOW's name.
"""

from __future__ import annotations

import re
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.api.nl import _owner_reads
from app.api.presentation import whole
from app.api.runtime import Runtime, set_runtime
from app.books import current_books
from app.config import get_settings
from app.domain.models import Mode
from app.financial import project
from app.mandate.fixture import demo_owner_public_key_hex
from app.nl import reset_sessions
from app.nl.answers import AnswerReply, answer, match, question_ids
from app.nl.answers.metrics import METRICS
from app.nl.context import NlContext
from app.nl.sessions import Session
from app.persistence import InMemoryLedgerStore
from tests.nl.conftest import OWNER, build_app

BANK_FILE = Path(__file__).resolve().parents[2] / "evals" / "owner_questions" / "questions.yaml"
BANK = {q["id"]: q for q in yaml.safe_load(BANK_FILE.read_text(encoding="utf-8"))["questions"]}
TOP30 = ["LIQ-01", "LIQ-03", "LIQ-04", "LIQ-05", "LIQ-06", "LIQ-09", "LIQ-10", "LIQ-14", "LIQ-15", "FUN-02", "FUN-04", "DEBT-01",
         "DEBT-04", "DEBT-06", "DEBT-08", "DEBT-03", "CUS-01", "CUS-03", "CUS-05", "CUS-07", "CUS-08", "DEAL-01", "DEAL-02", "DEAL-09",
         "COV-01", "COV-05", "CAP-01", "ACT-01", "MAN-01", "MAN-02"]
PARAMETRISED = {"cash_on", "late_payment_impact", "terms_extension_cost"}
IDS = re.compile(r"RCV-|FAC-|BUYER-|BANK-|PLATFORM-|LESSOR-|ALERT-|PLAN-|D-EQUIP|RI:|F-PAYROLL|F-SUPPLIER|F-BILL|SEC-|APR-|NL-|EX\d")


def wordings(qid: str, lang: str) -> list[str]:
    q = BANK[qid]
    return [q[f"text_{lang}"], *q.get(f"para_{lang}", [])]


ALL_WORDINGS = [(qid, lang, text) for qid in TOP30 for lang in ("en", "zh") for text in wordings(qid, lang)]


# ---------------------------------------------------------------- the books, and what the read routes say about them


def runtime() -> Runtime:
    rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=demo_owner_public_key_hex())
    rt.reset()
    set_runtime(rt)
    reset_sessions()
    return rt


def nl_ctx(rt: Runtime, lang: str) -> NlContext:
    """The context the /nl read handlers receive on an owner turn (app/nl/service.py), with the Home read lent to it."""
    return NlContext(store=rt.store, executor=rt.executor, day=rt.day, owner_key_hex=rt.owner_key_hex, owner_authenticated=True,
                     session=Session(id="answers-test", actor="OWNER", owner_auth=True, principal="owner"), lang=lang,
                     trace_id="answers-test:1", reads=_owner_reads(rt))


class Routes:
    """The figures the existing read routes give for the books as they are now."""

    def __init__(self, rt: Runtime, client: TestClient) -> None:
        def get(path: str) -> Any:
            r = client.get(path)
            assert r.status_code == 200, r.text
            return r.json()

        def post(path: str, body: Any) -> Any:
            r = client.post(path, json=body)
            assert r.status_code == 200, r.text
            return r.json()

        self.rt = rt
        self.home = get("/home?lang=en")
        self.cash = self.home["cash"]
        self.action = self.home["next_action"]
        self.traj = get("/trajectory")
        self.state = get("/state")["state"]
        self.mandate = get("/mandate")["mandate"]
        self.receivables = get("/receivables")
        self.recon = get("/reconciliation")["reconciliation"]
        self.approvals = get("/approvals/queue")["approvals"]
        self.ledger = get("/ledger")
        self.router = post("/router/plan", {})
        self.capex = post("/capex/evaluate", None)
        self.whatif60 = client.post("/whatif", json={"terms_days": 60, "discount_bp": 0, "rebate_bp": 0}).json()
        self.today = self.home["day"]

    def closing(self, day: int) -> int:
        return next(int(d["closing"]["fen"]) for d in self.traj["days"] if d["day"] == day)

    @property
    def undrawn(self) -> list[tuple[int, str]]:
        """(room, all-in rate) of each committed, owner-approved debt facility on the router's menu with room left."""
        out = []
        for m in self.router["menu"]:
            f = m["facility"]
            room = f["limit_fen"] - f["drawn_fen"]
            if m["committed"] and f["owner_approved"] and f["counts_in_leverage"] and room > 0:
                out.append((room, m["cost_display"]))
        return out

    @property
    def total_debt(self) -> int:
        return (sum(d["principal_fen"] for d in self.state["debts"])
                + sum(f["drawn_fen"] for f in self.state["facilities"] if f["counts_in_leverage"]))


def snapshot(rt: Runtime) -> tuple[Any, ...]:
    s = rt.store
    return (len(s.operations()), len(s.approvals()), len(s.verdicts()), len(s.security_events()), len(s.commitments()),
            s.get_state().model_dump_json(), s.get_mandate().model_dump_json(), s.verify_chain())


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
    set_runtime(rt)  # a state-change test in this module installs its own runtime; the Home read lent to the context reads the global one
    return rt, routes


@pytest.fixture
def fresh():
    rt = runtime()
    yield rt, TestClient(build_app(), headers=OWNER)
    set_runtime(None)
    reset_sessions()


def ask(rt: Runtime, text: str, lang: str) -> AnswerReply:
    reply = answer(text, lang, nl_ctx(rt, lang))
    assert reply is not None, text
    return reply


# ---------------------------------------------------------------- the leading figure or yes/no, from the routes


def leads(g: Routes, qid: str, lang: str) -> tuple[str, list[str]]:
    """(the text the answer must start with, figures it must carry), from the read routes alone."""
    w, c, a, zh = whole, g.cash, g.action, lang == "zh"
    fb, low, low_day = c["first_breach_day"], c["lowest_fen"], c["lowest_day"]
    floor = c["floor_fen"]
    flows = sorted(g.state["flows"], key=lambda f: f["day"])
    payroll = next(f for f in flows if f["kind"] == "PAYROLL")
    rcv = min((r for r in g.receivables["rows"] if not r["past_due"]), key=lambda r: r["due_day"])
    debt = g.state["debts"][0]
    if qid == "LIQ-01":
        return ("按今日账目并不安全" if zh else "Not on today's books",
                [f"第 {fb} 天" if zh else f"day {fb}", w(floor), w(low), w(floor - low), a["cost_total_display"]])
    if qid == "LIQ-03":
        zero = next(d for d in g.traj["days"] if d["day"] >= g.today and d["closing"]["fen"] < 0)
        return (f"距离跌破储备线还有 {fb - g.today} 天" if zh else f"{fb - g.today} days to your reserve",
                [w(c["first_breach_cash_fen"]), f"第 {zero['day']} 天" if zh else f"day {zero['day']}", w(zero["closing"]["fen"])])
    if qid == "LIQ-04":
        assert (low, low_day) == (g.traj["min_cash"]["fen"], g.traj["min_cash_day"])
        return (f"最低为第 {low_day} 天的 {w(low)}" if zh else f"{w(low)} on day {low_day}",
                [w(rcv["face_fen"]), f"第 {rcv['due_day']} 天" if zh else f"day {rcv['due_day']}"])
    if qid == "LIQ-05":
        assert fb == g.traj["first_breach_ahead_day"]
        return (f"第 {fb} 天：当天现金收于 {w(c['first_breach_cash_fen'])}" if zh else f"On day {fb}: cash closes at {w(c['first_breach_cash_fen'])}",
                [w(floor - c["first_breach_cash_fen"]), w(floor)])
    if qid == "LIQ-06":
        assert c["lowest_headroom_fen"] < 0 < c["headroom_fen"]
        return ("没有可安全动用的钱" if zh else "Nothing safely", [w(c["headroom_fen"]), w(-c["lowest_headroom_fen"])])
    if qid == "LIQ-09":
        outs = [(f["day"], -f["amount_fen"]) for f in flows if f["amount_fen"] < 0 and g.today <= f["day"] < g.today + 60]
        day = debt["next_payment_day"]
        while day < g.today + 60:
            outs.append((day, debt["monthly_debt_service_fen"]))
            day += debt["payment_every_days"]
        total = sum(x for _, x in outs)
        return (f"未来 60 天共有 {len(outs)} 笔支出，合计 {w(total)}" if zh else f"{len(outs)} payments in the next 60 days, {w(total)} in all",
                [w(x) for _, x in outs])
    if qid == "LIQ-10":
        after = g.closing(payroll["day"])
        assert 0 <= after < floor
        return ("够" if zh else "Yes", [w(-payroll["amount_fen"]), w(after), w(floor - after)])
    if qid == "LIQ-14":
        return (f"因为第 {payroll['day']} 天要支付工资 {w(-payroll['amount_fen'])}" if zh
                else f"Because payroll of {w(-payroll['amount_fen'])} falls due on day {payroll['day']}",
                [w(rcv["face_fen"]), f"第 {rcv['due_day']} 天" if zh else f"day {rcv['due_day']}"])
    if qid == "LIQ-15":
        need = g.router["committed"]["need_fen"]
        assert need == -c["lowest_headroom_fen"]
        return (f"需要 {w(need)}" if zh else w(need), [whole(g.router["committed"]["total_cost_fen"])])
    if qid == "FUN-02":
        legs = a["legs"]
        return (f"今天从银行信用额度提款 {w(legs[0]['amount_fen'])}" if zh else f"Draw {w(legs[0]['amount_fen'])} on the credit line today",
                [w(leg["amount_fen"]) for leg in legs] + [leg["cost_display"] for leg in legs] + [a["cost_total_display"]])
    if qid == "FUN-04":
        assert a["cost_total_display"] == whole(g.router["committed"]["total_cost_fen"])
        return (a["cost_total_display"] + ("：" if zh else ":"), [cl["display"] for cl in g.router["committed"]["costs"]])
    if qid == "DEBT-01":
        assert g.total_debt == g.traj["days"][g.today]["debt"]["fen"]
        return (w(g.total_debt), [w(debt["monthly_debt_service_fen"])])
    if qid == "DEBT-04":
        return ("不能" if zh else "No.", [w(g.total_debt), w(c["headroom_fen"]), w(floor)])
    if qid == "DEBT-06":
        rows = g.undrawn
        total = sum(x for x, _ in rows)
        return (f"已承诺但未使用的额度共 {w(total)}" if zh else f"{w(total)} committed and unused",
                [w(x) for x, _ in rows] + [rate for _, rate in rows])
    if qid == "DEBT-08":
        amt, day = w(debt["monthly_debt_service_fen"]), debt["next_payment_day"]
        return (f"第 {day} 天，现有设备贷款还款 {amt}" if zh else f"{amt} on the existing equipment loan on day {day}", [])
    if qid == "DEBT-03":
        ds = g.traj["months"][0]["debt_service"]["fen"]
        return (f"每月还本付息 {w(ds)}" if zh else f"{w(ds)} a month of debt service", [w(g.traj["interest"]["fen"] + g.traj["fees"]["fen"])])
    if qid == "CUS-01":
        owed: dict[str, int] = defaultdict(int)
        for r in g.receivables["rows"]:
            owed[r["buyer_name"]] += r["outstanding_fen"]
        name, most = max(owed.items(), key=lambda x: x[1])
        assert name == "Foshan Home Retail Co."
        return (f"佛山：1 张发票共 {w(most)}" if zh else f"{name}: {w(most)}", [])
    if qid == "CUS-03":
        assert not [o for o in g.recon["outstanding"] if o["past_due"]]
        return ("没有" if zh else "Nobody", [w(rcv["face_fen"]), f"第 {rcv['due_day']} 天" if zh else f"day {rcv['due_day']}"])
    if qid == "CUS-05":
        owed_by: dict[str, int] = defaultdict(int)
        for r in g.receivables["rows"]:
            owed_by[r["buyer_id"]] += r["outstanding_fen"]
        share = f"{round(100 * max(owed_by.values()) / sum(owed_by.values()))}%"
        return (share + ("：" if zh else ":"), [w(sum(owed_by.values()))])
    if qid == "CUS-07":
        s = g.rt.store.get_state()
        moved = s.model_copy(update={"receivables": [r.model_copy(update={"terms_days": r.terms_days + 30}) if r.id == rcv["receivable_id"]
                                                      else r for r in s.receivables]})
        b = current_books(moved, g.rt.store.commitments())
        m = g.rt.store.get_mandate()
        t = project(b.state, b.with_([]), [], Mode.CONSERVATIVE, m.horizon_days, m.min_cash_fen)
        lo = min((d for d in t.days if d.day >= g.today), key=lambda d: (d.closing_fen, d.day))
        due, face = rcv["due_day"], w(rcv["face_fen"])
        return (f"如果佛山的 {face} 发票晚 30 天付款（第 {due + 30} 天而不是第 {due} 天）" if zh
                else f"If Foshan Home Retail Co. pays its {face} invoice 30 days late (day {due + 30} instead of day {due})",
                [w(lo.closing_fen), f"第 {lo.day} 天" if zh else f"day {lo.day}"])
    if qid == "CUS-08":
        full = next(r for r in g.router["comparison"] if r["key"] == "full_discount")
        return ("不划算" if zh else "No.", [g.router["marginal"]["break_even_display"], w(full["cost_fen"]), a["cost_total_display"]])
    if qid == "DEAL-01":
        assert not g.approvals
        return ("有 1 件事" if zh else "One thing:", [f"第 {fb} 天" if zh else f"day {fb}", a["cost_total_display"]])
    if qid == "DEAL-02":
        assert not g.approvals
        return ("没有" if zh else "No.", [])
    if qid == "DEAL-09":
        fwd = g.whatif60["forward"]
        lead = w(fwd["total_fen"])
        return (f"未来 12 个月佛山的发票共产生远期让步 {lead}" if zh else f"{lead} in forward concessions", [w(fwd["cap_fen"])])
    if qid == "COV-01":
        dscr = min(Fraction(m["dscr"].rstrip("x")) for m in g.traj["months"] if m["dscr"])
        lev = max(Fraction(m["leverage"].rstrip("x")) for m in g.traj["months"] if m["leverage"])
        return ("满足。预测的每个月都在契约范围内" if zh else "Yes. Every projected month is inside the covenants",
                [f"{float(dscr):.2f}×", f"{float(lev):.2f}×"])
    if qid == "COV-05":
        ebitda = g.state["monthly_ebitda_fen"]
        ds_max = ebitda * 10_000 // g.mandate["min_dscr_bp"]
        debt_max = g.mandate["max_leverage_bp"] * 12 * ebitda // 10_000
        return (f"每月还本付息超过 {w(ds_max)}" if zh else f"Monthly debt service above {w(ds_max)}",
                [w(debt_max), w(g.traj["months"][0]["debt_service"]["fen"]), w(g.traj["months"][0]["total_debt"]["fen"])])
    if qid == "CAP-01":
        sel = next(s for s in g.capex["structures"] if s["id"] == g.capex["selected_id"])
        cash = next(s for s in g.capex["structures"] if s["kind"] == "CASH_LINE")
        assert not cash["feasible"] and sel["feasible"]
        return ("只能融资购买" if zh else "Only financed.", [w(g.capex["request"]["price_fen"]), w(sel["monthly_payment_fen"]),
                                                       w(g.capex["npv_fen"])])
    if qid == "ACT-01":
        assert not g.ledger["operations"] and g.ledger["chain_valid"]
        return ("还没有" if zh else "Nothing yet", [])
    if qid == "MAN-01":
        m = g.mandate
        return (f"在您签署的授权内（有效至第 {m['expires_day']} 天）" if zh else f"Inside your signed mandate (valid to day {m['expires_day']})",
                [w(m["min_cash_fen"]), f"{m['max_apr_bp'] / 100:.2f}%", w(m["tier2_single_commitment_fen"]),
                 w(m["max_aggregate_forward_concession_fen"]), f"{m['max_immediate_discount_bp'] / 100:.2f}%"])
    if qid == "MAN-02":
        m = g.mandate
        return (f"单笔超过 {w(m['tier2_single_commitment_fen'])} 的承诺" if zh else f"A single commitment above {w(m['tier2_single_commitment_fen'])}",
                [f"{m['max_apr_bp'] / 100:.2f}%", w(m["min_cash_fen"])])
    raise AssertionError(f"no expectation for {qid}")


def check_language(reply: AnswerReply) -> None:
    assert not IDS.search(reply.text), reply.text
    assert reply.basis and reply.metric_ids and all(isinstance(v, str) for v in reply.figures.values())
    for mid in reply.metric_ids:
        assert mid in METRICS or mid in PARAMETRISED or mid == "break_even_discount", mid
    if reply.lang == "zh":
        latin = set(re.findall(r"[A-Za-z]+", reply.text)) - {"FLOW"}
        assert not latin, (latin, reply.text)
        assert not set(re.findall(r"[A-Za-z]+", reply.basis)) - {"FLOW"}, reply.basis


# ---------------------------------------------------------------- matching


def test_the_package_answers_exactly_the_top_30() -> None:
    assert sorted(question_ids()) == sorted(TOP30)


@pytest.mark.parametrize(("qid", "lang", "text"), ALL_WORDINGS)
def test_every_wording_of_the_bank_is_matched_to_its_question(qid: str, lang: str, text: str) -> None:
    found = match(text)
    assert found is not None and found[0] == qid, (text, found and found[0])


@pytest.mark.parametrize(("text", "qid"), [
    ("Do we have enough cash?", "LIQ-01"), ("现金够用吗？", "LIQ-01"), ("Do we have enough cash for payroll?", "LIQ-10"),
    ("What if Foshan pays two weeks late?", "CUS-07"), ("How much more can we borrow on our facilities?", "DEBT-06"),
    ("我们现在欠银行多少钱？", "DEBT-01"), ("Which invoices are overdue?", "CUS-03"),
    ("What would extending Foshan to 75 days cost us?", "DEAL-09"),
])
def test_other_common_wordings_are_matched_too(text: str, qid: str) -> None:
    found = match(text)
    assert found is not None and found[0] == qid, (text, found and found[0])


@pytest.mark.parametrize("text", [
    "How much cash do we have today?", "What's our VAT position this quarter?", "Draw ¥50,000 on the credit line", "Fund the gap",
    "go ahead", "Repay the credit line", "Accept Foshan's offer", "Pay off the equipment loan", "Foshan wants 60-day terms. Can we accept?",
    "Send Foshan a counter at 0.8%", "给佛山60天账期", "批准", "好，执行", "现金余额是多少", "库存值多少钱？", "Approve APR-000003",
    "What's the weather like?", "",
])
def test_anything_else_is_left_to_the_caller(day0, text: str) -> None:
    rt, _ = day0
    assert match(text) is None
    assert answer(text, "en", nl_ctx(rt, "en")) is None


# ---------------------------------------------------------------- day 0: the answers lead with the routes' figures


@pytest.mark.parametrize(("qid", "lang", "text"), ALL_WORDINGS)
def test_day0_answer_leads_with_the_routes_figure(day0, qid: str, lang: str, text: str) -> None:
    rt, routes = day0
    before = snapshot(rt)
    reply = ask(rt, text, lang)
    assert snapshot(rt) == before  # nothing written: no operation, approval, verdict, security event, commitment or state change
    assert reply.question_id == qid and reply.lang == lang
    lead, figures = leads(routes, qid, lang)
    assert reply.text.startswith(lead), (lead, reply.text)
    for f in figures:
        assert f in reply.text, (f, reply.text)
    check_language(reply)


def test_the_example_sentences_of_the_brief(day0) -> None:
    rt, _ = day0
    assert ask(rt, "Are we safe?", "en").text == (
        "Not on today's books: without new funding, cash falls below your ¥300,000 reserve from day 12, lowest −¥105,000 on day 30 "
        "(¥405,000 short of the reserve). FLOW's plan covers it for ¥3,113.93, and your loan covenants hold.")
    assert ask(rt, "Are we safe?", "en").basis == "Conservative forecast, today's books, day 0"
    figures = {
        "What is our cash runway?": "12 days", "When do we first drop below our minimum cash reserve?": "¥60,000",
        "How much do we need to raise to stay safe?": "¥405,000", "How much debt do we have?": "¥1,500,000",
        "Are we inside our covenants?": "2.00×", "Should we take Foshan's early-payment offer at 1.2%?": "0.88%",
    }
    for text, figure in figures.items():
        assert figure in ask(rt, text, "en").text, text
    assert "1.35×" in ask(rt, "Are we inside our covenants?", "en").text


def test_data_the_books_do_not_hold_is_said_not_invented(day0) -> None:
    rt, _ = day0
    assert "do not record who lent" in ask(rt, "How much do we owe the banks?", "en").text
    assert "账目中没有记录" in ask(rt, "我们总共欠多少债？", "zh").text
    assert "do not say whether it can be repaid early" in ask(rt, "Can we clear our debts?", "en").text


def test_a_late_payment_of_another_length_is_one_projection(day0) -> None:
    rt, _ = day0
    reply = ask(rt, "What if Foshan pays 15 days late?", "en")
    assert reply.question_id == "CUS-07" and "(day 47 instead of day 32)" in reply.text
    assert "nothing was changed" in reply.text


# ---------------------------------------------------------------- after a state change


def approve_the_plan(client: TestClient) -> None:
    a = client.get("/home?lang=en").json()["next_action"]
    body = {"state_version": a["state_version"],
            "suggestions": [{k: s[k] for k in ("operation_kind", "facility_id", "receivable_id", "amount_fen")} for s in a["suggestions"]]}
    r = client.post(f"/alerts/{a['alert_id']}/act", json=body)
    assert r.status_code == 200, r.text
    assert all(x["status"] == "EXECUTED" for x in r.json()["results"])


def test_after_the_plan_is_approved_the_answers_follow_the_books(fresh) -> None:
    rt, client = fresh
    approve_the_plan(client)
    g = Routes(rt, client)
    c = g.cash
    assert c["first_breach_day"] is None and g.action is None
    for lang in ("en", "zh"):
        safe = ask(rt, wordings("LIQ-01", lang)[0], lang)
        assert safe.text.startswith("安全" if lang == "zh" else "Yes:"), safe.text
        assert whole(c["lowest_fen"]) in safe.text and whole(c["floor_fen"]) in safe.text
        need = ask(rt, wordings("LIQ-15", lang)[0], lang)
        assert need.text.startswith("不需要" if lang == "zh" else "Nothing:"), need.text
        cost = ask(rt, wordings("FUN-04", lang)[0], lang)
        assert cost.text.startswith("不需要花钱" if lang == "zh" else "Nothing:"), cost.text
        debt = ask(rt, wordings("DEBT-01", lang)[0], lang)
        assert debt.text.startswith(whole(g.total_debt)) and g.total_debt == 190_500_000, debt.text
        did = ask(rt, wordings("ACT-01", lang)[0], lang)
        ran = len(g.ledger["operations"])
        assert did.text.startswith(f"最近 7 天执行了 {ran} 项操作" if lang == "zh" else f"{ran} operations in the last 7 days"), did.text
        cov = ask(rt, wordings("COV-01", lang)[0], lang)
        lev = max(Fraction(m["leverage"].rstrip("x")) for m in g.traj["months"] if m["leverage"])
        assert f"{float(lev):.2f}×" in cov.text and "1.72×" in cov.text
        waits = ask(rt, wordings("DEAL-01", lang)[0], lang)
        assert waits.text.startswith("目前没有需要您处理的事项" if lang == "zh" else "Nothing is waiting for you"), waits.text
        borrow = ask(rt, wordings("DEBT-06", lang)[0], lang)
        assert whole(sum(x for x, _ in g.undrawn)) in borrow.text
        for reply in (safe, need, cost, debt, did, cov, waits, borrow):
            check_language(reply)


def test_after_the_clock_moves_to_day_34_the_answers_follow_the_books(fresh) -> None:
    rt, client = fresh
    r = client.post("/clock/advance", json={"to_day": 34})
    assert r.status_code == 200, r.text
    g = Routes(rt, client)
    c = g.cash
    assert g.today == 34 and c["first_breach_day"] == 34
    late = [o for o in g.recon["outstanding"] if o["past_due"]]
    assert late
    for lang in ("en", "zh"):
        before = snapshot(rt)
        safe = ask(rt, wordings("LIQ-01", lang)[0], lang)
        assert safe.text.startswith("不安全" if lang == "zh" else "No: cash is already below"), safe.text
        assert whole(c["cash_fen"]) in safe.text and whole(c["lowest_fen"]) in safe.text
        breach = ask(rt, wordings("LIQ-05", lang)[0], lang)
        assert breach.text.startswith("已经跌破" if lang == "zh" else "Already:"), breach.text
        assert whole(c["floor_fen"] - c["cash_fen"]) in breach.text
        chase = ask(rt, wordings("CUS-03", lang)[0], lang)
        days_late = g.today - late[0]["due_day"]
        assert chase.text.startswith(f"佛山：{whole(late[0]['face_fen'])}，已逾期 {days_late} 天" if lang == "zh"
                                     else f"Foshan Home Retail Co.: {whole(late[0]['face_fen'])}, {days_late} days late"), chase.text
        loan = ask(rt, wordings("DEBT-08", lang)[0], lang)
        debt = g.state["debts"][0]
        assert (f"第 {debt['next_payment_day']} 天" if lang == "zh" else f"on day {debt['next_payment_day']}") in loan.text
        owed = ask(rt, wordings("DEBT-01", lang)[0], lang)
        assert owed.text.startswith(whole(g.total_debt)) and g.total_debt == g.traj["days"][g.today]["debt"]["fen"]
        most = ask(rt, wordings("CUS-01", lang)[0], lang)
        assert whole(sum(x["outstanding_fen"] for x in g.receivables["rows"])) in most.text
        runway = ask(rt, wordings("LIQ-03", lang)[0], lang)
        assert runway.text.startswith("已经没有" if lang == "zh" else "None:"), runway.text
        assert snapshot(rt) == before
        for reply in (safe, breach, chase, loan, owed, most, runway):
            check_language(reply)


def test_no_answer_ever_writes(fresh) -> None:
    rt, client = fresh
    approve_the_plan(client)
    before = snapshot(rt)
    for qid, lang, text in ALL_WORDINGS:
        assert answer(text, lang, nl_ctx(rt, lang)) is not None, text
    assert snapshot(rt) == before
