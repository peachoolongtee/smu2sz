"""Wave 7 (map #65, ticket #76), the API side: language on every Business read (F28), the owner-layer terms (audit section 16) and the
freshness fields (F21).

Every route a Business page reads answers `?lang=zh` with the same figures, ids, statuses and days as `?lang=en`, with every `*_when` and
`*_text` in Chinese and no English sentence left outside the audit-level fields (the engine's own sentences, which stay as written:
stability mode). The helper that says what "English left over" means is tested first."""

from __future__ import annotations

import json
import re
from typing import Any

from app.api import engine_zh
from app.api.presentation import business_text, option_label
from app.api.runtime import get_runtime
from tests.api.conftest import english_leaks, figures, strip_names, unchanged_words
from tests.api.test_time_semantics import BANK, _act, _queue, _walk

EX01 = "EX01_PACKAGE"


# ---------------------------------------------------------------- the helper (tests/api/conftest.py)


def test_the_helper_lets_ids_codes_currency_and_names_stay_latin_and_nothing_else():
    names = ["Bank credit line", "Foshan Home Retail Co."]
    assert english_leaks({"a": "从Bank credit line提款 ¥150,000.00"}, names) == []
    assert english_leaks({"a": "发票 RCV-A 对应 CMT-0123456789abcdef，状态 PENDING_APPROVAL"}, names) == []
    assert english_leaks({"a": "Foshan Home Retail Co. 的 ¥420,000.00 发票（32 天后到期）"}, names) == []
    assert english_leaks({"a": "12 天后现金将低于最低现金储备"}) == []
    assert english_leaks({"path": "/decisions/alert:ALERT-RESERVE-12:v1:plan"}) == []
    # an English sentence, a half-translated sentence and a lone English word are all caught
    assert [p for p, _ in english_leaks({"x": {"y": ["Cash goes below zero in 8 days."]}})] == [".x.y[]"]
    assert english_leaks({"a": "您的现金 will fall 12 天后"}) != []
    assert english_leaks({"a": "Repayment"}) != []
    # the audit-level fields named by the caller are exempt, and only those
    data = {"reason": "effective annual cost 6.40% is above the ceiling", "presentation": {"reason": "Another English sentence here"}}
    assert [p for p, _ in english_leaks(data, raw_fields=[r"\.reason"])] == [".presentation.reason"]


def test_the_helper_compares_figures_and_finds_words_that_did_not_change():
    en = {"amount_fen": 100, "id": "A-1", "status": "OPEN", "rows": [{"day": 3, "title": "Cash goes below zero"}], "title_when": "in 3 days"}
    zh = {"amount_fen": 100, "id": "A-1", "status": "OPEN", "rows": [{"day": 3, "title": "现金将跌破零"}], "title_when": "3 天后"}
    assert figures(en) == figures(zh) and figures(en)[".id"] == "A-1" and ".rows[0].day" in figures(en)
    assert figures({**zh, "amount_fen": 101}) != figures(en)
    assert unchanged_words(en, zh) == []
    assert unchanged_words({"a_text": "Cash goes below zero", "b_text": "¥1.00"}, {"a_text": "Cash goes below zero", "b_text": "¥1.00"}) == [
        (".a_text", "Cash goes below zero")]  # a figure-only string may stay the same, a sentence may not
    assert strip_names("Bank credit line 提款", ["Bank credit line"]).strip() == "提款"


# ---------------------------------------------------------------- the templates (engine_zh)


def _zh(text: str, names: tuple[str, ...] = ("Bank credit line", "Foshan Home Retail Co.", "Invoice financing (onboarded platform)")) -> str:
    out = engine_zh.translate(text, names)
    assert out is not None
    return out


def test_the_executor_and_approval_sentences_are_said_in_chinese_with_their_figures():
    assert _zh("Drew ¥150,000.00 on Bank credit line today") == "已于今天从Bank credit line提取 ¥150,000.00"
    assert _zh("Drew ¥150,000.00 on Bank credit line today; the cash lands in 3 days, not today.") == (
        "已于今天从Bank credit line提取 ¥150,000.00；资金将于3 天后到账，不是今天。")
    assert _zh("Queued for owner approval (APR-000001): the yearly cost of 6.40% is above the 5.00% limit you signed for funding "
               "without your approval (6.4% simple)") == (
        "已排入待批准队列（APR-000001）：年化成本 6.40% 高于您签署的无需批准融资上限 5.00%（单利 6.4%）")
    assert _zh("Declined by the owner (APR-000001); nothing executed") == "您已拒绝（APR-000001）；未执行任何操作"
    assert _zh("Refused: Draw ¥990,000,000.00 exceeds Bank credit line's available ¥150,000.00") == (
        "已拒绝：提款 ¥990,000,000.00 超过Bank credit line的可用额度 ¥150,000.00")
    assert _zh("The agreement with Foshan Home Retail Co. is ACTIVE; forward concession ¥0.00 booked") == (
        "与Foshan Home Retail Co.的协议已生效；已计入远期让步 ¥0.00")
    assert _zh("Clock moved from 3 days ago to today: 0 scheduled flow(s) posted (net ¥0.00), 1 invoice(s) issued, 0 commitment(s) expired") == (
        "时间从3 天前推进到今天：已入账 0 笔计划收支（净额 ¥0.00），已开出 1 张发票，0 项协议已到期")


def test_a_plan_with_several_legs_keeps_each_legs_reason_and_figures():
    text = ("Bank credit line: draw ¥150,000.00, repaid in 32 days: the yearly cost of 6.40% is above the 5.00% limit you signed for funding "
            "without your approval (6.4% simple); Invoice financing (onboarded platform): advance ¥255,000.00 on RCV-A: the yearly cost of "
            "11.22% is above the 5.00% limit you signed for funding without your approval (all charges on ¥255,000.00 held 29 days "
            "(from in 3 days to in 32 days), annualised = 11.22%)")
    out = _zh(text)
    assert out == (
        "Bank credit line：提款 ¥150,000.00，预计32 天后还款：年化成本 6.40% 高于您签署的无需批准融资上限 5.00%（单利 6.4%）；"
        "Invoice financing (onboarded platform)：以发票 RCV-A融资 ¥255,000.00：年化成本 11.22% 高于您签署的无需批准融资上限 5.00%"
        "（¥255,000.00 计息 29 天（从3 天后到32 天后），年化 11.22%）")
    for figure in ("¥150,000.00", "¥255,000.00", "6.40%", "11.22%", "5.00%"):
        assert figure in out


def test_alert_sentences_are_said_in_chinese_in_the_owners_words():
    assert _zh("Reserve breach ahead in 12 days") == "12 天后现金将低于最低现金储备"
    assert _zh("Cash is close to your minimum in 32 days") == "32 天后现金仅略高于最低现金储备"
    assert _zh("Cash stays above your minimum cash reserve by only ¥15,000.00 in 32 days (15 days with less than 10% of your minimum "
               "cash reserve to spare)") == "32 天后现金仅高出最低现金储备 ¥15,000.00（共 15 天高出的部分不足最低现金储备的 10%）"
    detail = _zh("Projected cash closes at ¥60,000.00 in 12 days, ¥240,000.00 below your minimum cash reserve; the gap peaks at "
                 "¥405,000.00 in 30 days and lasts until 31 days from now. A funding plan is available: draw on Bank credit line "
                 "¥150,000.00, cost ¥1,200.00 (6.4% a year for 29 days) + finance an invoice on Invoice financing (onboarded platform) "
                 "¥255,000.00, cost ¥2,272.29 (11.2% a year for 29 days)")
    assert detail.startswith("预计现金将在12 天后降至 ¥60,000.00，比最低现金储备低 ¥240,000.00；缺口在30 天后最大，为 ¥405,000.00，持续到31 天后。")
    assert "从Bank credit line提款 ¥150,000.00，成本 ¥1,200.00（年化 6.4%，29 天）" in detail
    assert "以发票在Invoice financing (onboarded platform)融资 ¥255,000.00，成本 ¥2,272.29（年化 11.2%，29 天）" in detail
    assert _zh("¥162,800.00 outstanding from Foshan Home Retail Co. was due 2 days ago and is still OPEN. The cash forecast no longer "
               "counts on a dated receipt.") == "Foshan Home Retail Co.应付的 ¥162,800.00 原定2 天前到期，目前仍未收款。现金预测不再把这笔款项当作有确定日期的回款。"


def test_a_sentence_no_template_knows_passes_through_unchanged_and_is_recorded():
    engine_zh.MISSES.clear()
    odd = "A sentence the engine might write one day that nobody has a template for."
    assert engine_zh.translate(odd) == odd
    assert odd.rstrip(".") in engine_zh.MISSES
    assert engine_zh.translate(None) is None and engine_zh.translate("¥1,000.00 · 12 天后") == "¥1,000.00 · 12 天后"
    assert option_label("Option A", "zh") == "方案 A" and option_label("Option A", "en") == "Option A" and option_label("Option Z9", "zh") == "Option Z9"


def test_the_owner_layer_terms_replace_the_engines_in_every_business_sentence(client):
    state = get_runtime().store.get_state()
    def said(text: str) -> str | None:
        return business_text(state, text, 0, "en")

    assert said("Reserve headroom thin on day 30") == "Cash is close to your minimum in 30 days"
    assert said("Cash stays above the floor but only by ¥15,000.00 on day 32 (15 day(s) under 10% of the floor).") == (
        "Cash stays above your minimum cash reserve by only ¥15,000.00 in 32 days (15 days with less than 10% of your minimum cash reserve "
        "to spare).")
    assert said("the conservative trajectory is projected that way") == "the cash forecast is projected that way"
    assert said("A committed cure exists: DRAW_FACILITY FAC-LINE ¥150,000.00") == "A funding plan is available: draw on Bank credit line ¥150,000.00"
    assert said("commitment CMT-1 of ¥70,000.00 is above the Tier-2 threshold ¥50,000.00") == (
        "the agreement of ¥70,000.00 is above the ¥50,000.00 you allow without your approval")
    assert said("Tier 2: the owner applies; zero until committed") == "Needs your approval: you apply; counted as zero until committed"
    assert said("Receivable RCV-A is under the live early-payment agreement of obligation OB-1") == (
        "Receivable the ¥420,000.00 invoice to Foshan Home Retail Co. due in 32 days is under the live early-payment agreement of the terms you "
        "agreed")
    assert "reserve floor" not in said("¥240,000.00 below the reserve floor") and "your minimum cash reserve" in said("¥240,000.00 below the reserve floor")


# ---------------------------------------------------------------- the reads, in both languages


def _names() -> list[str]:
    state = get_runtime().store.get_state()
    flows = [part for x in state.flows for part in (x.label, x.label.split(",")[0], x.label.split(" (")[0])]  # the owner's own names
    shorts = [c.name.replace(",", " ").split()[0] for c in state.counterparties]  # the name an owner says aloud (the house buyer_short)
    return [*(c.name for c in state.counterparties), *shorts, *(f.name for f in state.facilities), *flows]


# The audit-level fields that stay the engine's own English by design (stability mode), as index-free dotted paths. Everything else a
# route returns is a Business field and must be Chinese in zh.
ALERTS_RAW = [r"\.alerts\[\]\.(title|detail|formula)", r"\.alerts\[\]\.inputs\..*", r"\.alerts\[\]\.suggested\[\]\.(note|cost_formula)",
              r"\.note"]
RECON_RAW = [r"\.reconciliation\.(promised|receipts)\[\]\.(detail|formula)"]
QUEUE_RAW = [r"\.approvals\[\]\.(reason|result_message|op_json|subject)", r"\.approvals\[\]\.operation\..*",
             r"\.approvals\[\]\.quote\.lines\[\]\.(op_id|kind)", r"\.approvals\[\]\.quote\.actual\[\]\..*",
             r"\.approvals\[\]\.presentation\.series_if_(declined|approved)\[\]\.events\[\]\.label(_short)?"]
LEDGER_RAW = [r"\.operations\[\]\.(message|summary)", r"\.operations\[\]\.violations\[\]\..*", r"\.commitments\[\]\..*"]
HOME_RAW = [r"\.next_action\.(formula|detail_raw)", r"\.next_action\.legs\[\]\.formula", r"\.next_action\.cost_breakdown\[\]\.formula",
            r"\.cash\.series\[\]\.events\[\]\.label", r"\.cash\.plan_series\[\]\.events\[\]\.label",
            r"\.cash\.series\[\]\.events\[\]\.label_short", r"\.cash\.plan_series\[\]\.events\[\]\.label_short",
            r"\.cash\.counterfactual_series\[\]\.events\[\]\.label(_short)?",
            # a route is not a sentence: the page links (`/deals?buyer=BUYER-1`) are the same in both languages
            r"\.attention\.items\[\]\.(primary|secondary)\.href", r"\.(deals_card\.rows\[\]|receivables_card|changes_card)\.href"]


def _read(client, path: str, lang: str, **params: Any) -> dict:
    r = client.get(path, params={"lang": lang, **params})
    assert r.status_code == 200, (path, r.text)
    return r.json()


def _both(client, path: str, raw: list[str], echoes_lang: bool = True, **params: Any) -> tuple[dict, dict]:
    en, zh = _read(client, path, "en", **params), _read(client, path, "zh", **params)
    assert figures(en) == figures(zh), path  # the same figures, ids, statuses and days
    assert unchanged_words(en, zh, _names(), raw) == [], path  # every *_when and *_text differs, or it is figures only
    assert english_leaks(zh, _names(), raw) == [], path  # and no English sentence is left outside the audit fields
    if echoes_lang:
        assert en["lang"] == "en" and zh["lang"] == "zh"
    return en, zh


def _freshness(body: dict) -> None:
    assert body["last_read_day"] >= 0 and body["last_read_when"]  # F21: the page can say "as of {when}" beside the conclusion


def test_the_fresh_books_read_the_same_in_both_languages(client):
    for path, raw in (("/alerts", ALERTS_RAW), ("/reconciliation", RECON_RAW), ("/approvals/queue", QUEUE_RAW), ("/ledger", LEDGER_RAW)):
        en, zh = _both(client, path, raw)
        _freshness(en)
        _freshness(zh)
    en, zh = _both(client, "/alerts", ALERTS_RAW)
    breach = next(a for a in zh["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")
    assert breach["title_when"] == "12 天后现金将低于最低现金储备"
    assert breach["title"] == next(a for a in en["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")["title"]  # the engine's title is untouched
    assert breach["detail_when"].startswith("预计现金将在12 天后降至 ¥60,000.00，比最低现金储备低 ¥240,000.00")
    assert "A funding plan is available" in next(a for a in en["alerts"] if a["kind"] == "RESERVE_BREACH_AHEAD")["detail_when"]
    assert zh["alerts"][0]["suggested"][0]["note_when"].startswith("今天提出提款申请")
    assert zh["note_when"].startswith("建议的步骤") and en["note_when"].startswith("A suggested step")


def test_the_home_reads_the_same_in_both_languages_with_the_alert_words_in_chinese(client):
    en, zh = _both(client, "/home", HOME_RAW)  # day 0: a breach ahead with its plan
    assert zh["warnings"] and all(w["title"] != e["title"] for w, e in zip(zh["warnings"], en["warnings"], strict=True))
    assert zh["next_action"]["detail"].startswith("预计现金将在12 天后降至 ¥60,000.00") and zh["next_action"]["detail"] != en["next_action"]["detail"]
    assert zh["warnings"][0]["title"] == "32 天后现金仅略高于最低现金储备" and en["warnings"][0]["title"] == "Cash is close to your minimum in 32 days"
    assert "headroom" not in json.dumps(en["warnings"]) and "floor" not in json.dumps(en["warnings"])
    _walk(client, to=2)  # after the deal: changes, a promise and the thin-cash warning
    _both(client, "/home", HOME_RAW)


def test_the_approvals_queue_in_chinese_end_to_end(client):
    _walk(client)
    _act(client)  # the day-34 cure is above the rate ceiling: it waits for the owner
    en, zh = _both(client, "/approvals/queue", QUEUE_RAW)
    assert [r["status"] for r in zh["approvals"]] == ["PENDING"] and zh["approvals"][0]["presentation"]["headline"].startswith("批准")
    p = zh["approvals"][0]["presentation"]
    assert p["reason"].startswith("年化成本") and "您签署的无需批准融资上限" in p["reason"]
    assert p["created_when"] and p["if_decline"] and zh["approvals"][0]["quote"]["after"]
    _freshness(zh)
    client.post(f"/approvals/{zh['approvals'][0]['id']}", json={"decision": "APPROVE"})
    en, zh = _both(client, "/approvals/queue", QUEUE_RAW)
    done = zh["approvals"][0]["presentation"]
    assert done["decided_when"] == "今天" and en["approvals"][0]["presentation"]["decided_when"] == "today"
    assert "已于" in done["result_message"] and "到账" in done["result_message"]
    assert zh["approvals"][0]["execution"]["summary_text"]


def test_the_ledger_and_the_audit_in_chinese(client):
    _walk(client)
    client.post("/operations", headers=BANK, json={
        "kind": "DRAW_FACILITY", "op_id": "t-big", "idempotency_key": "t-big", "mandate_version": 1, "requested_by": "AGENT",
        "facility_id": "FAC-LINE", "amount_fen": 99_000_000_000, "day": get_runtime().day})
    en, zh = _both(client, "/ledger", LEDGER_RAW)
    _freshness(zh)
    kinds = {o["kind"]: o for o in zh["operations"]}
    assert kinds["ACCEPT_OFFER"]["message_when"] == "与Foshan Home Retail Co.的协议已生效；已计入远期让步 ¥0.00"
    assert next(o for o in en["operations"] if o["kind"] == "ACCEPT_OFFER")["message_when"].startswith("The agreement with Foshan")
    refused = next(o for o in zh["operations"] if o["status"] == "REFUSED")
    assert refused["message_when"].startswith("已拒绝：") and refused["summary"].startswith("Refused: ")  # the raw sentence is the audit level
    assert refused["event_text"].startswith("已拒绝")
    audit_en, audit_zh = _read(client, "/audit", "en"), _read(client, "/audit", "zh")
    assert audit_zh["lang"] == "zh" and figures(audit_en) == figures(audit_zh)
    assert english_leaks({k: v for k, v in audit_zh.items() if k in ("refusals", "refusal_summary")}, _names(),
                         [r"\.refusals\[\]\.(message|summary|violations.*|commitments.*)"]) == []


def test_the_reconciliation_in_chinese_names_the_promise_and_the_receipt(client):
    _walk(client, to=2)
    promise = _read(client, "/reconciliation", "zh")["reconciliation"]["promised"][0]
    assert promise["detail_when"] == ("与Foshan Home Retail Co.的协议约定，Foshan Home Retail Co. 的 ¥420,000.00 发票（30 天后到期）的 ¥255,013.80 "
                                      "应在今天之前到账；约定日尚未过。")
    version = client.get("/mandate").json()["mandate"]["version"]
    client.post("/operations", headers=BANK, json={
        "kind": "RECEIVE_PAYMENT", "op_id": "rc-1", "idempotency_key": "rc-1", "mandate_version": version, "requested_by": "SYSTEM",
        "receivable_id": promise["receivable_id"], "amount_fen": promise["expected_fen"] // 2, "bank_reference": "B-1"})
    en, zh = _both(client, "/reconciliation", RECON_RAW)
    receipt = zh["reconciliation"]["receipts"][0]
    assert receipt["window_state_text"].startswith("提前付款期限") and en["reconciliation"]["receipts"][0]["window_state_text"].startswith("The early")
    assert receipt["detail_when"] == "约定的提前付款，对应发票 ¥128,600.00；另有最多 ¥128,600.00 仍可在今天之前提前结算"
    _freshness(zh)


def test_a_late_invoice_and_a_missed_early_payment_in_chinese(client):
    _walk(client, receipt="half")
    for path, raw in (("/alerts", ALERTS_RAW), ("/reconciliation", RECON_RAW), ("/home", HOME_RAW), ("/ledger", LEDGER_RAW),
                      ("/approvals/queue", QUEUE_RAW)):
        _both(client, path, raw)
    late = [a for a in _read(client, "/alerts", "zh")["alerts"] if a["kind"] == "RECEIVABLE_PAST_DUE"]
    assert late and all("已逾期" in a["title_when"] or "没有到账" in a["title_when"] for a in late)
    assert not any("trajectory" in a["detail_when"] for a in _read(client, "/alerts", "en")["alerts"])


def test_the_decision_record_and_the_chase_read_the_same_in_both_languages(client):
    _walk(client, receipt="half")
    _act(client)
    client.post(f"/approvals/{_queue(client)[0]['id']}", json={"decision": "APPROVE"})
    listed_en, listed_zh = _read(client, "/decisions", "en"), _read(client, "/decisions", "zh")
    assert figures(listed_en) == figures(listed_zh) and len(listed_zh["decisions"]) >= 2
    raw = [r"\.(receipts|promises)\[\]\.(detail|formula)", r"\.response\.counters\[\]\.label",
           r"\.response\.sent\.(chosen_label|accepted_label|counters_sent\[\]\.label)"]
    for row in listed_zh["decisions"]:
        _both(client, f"/decisions/{row['id']}", raw, echoes_lang=False)
    deal = next(r for r in listed_zh["decisions"] if r["id"].startswith("deal:"))
    sent = _read(client, f"/decisions/{deal['id']}", "zh")["response"]["sent"]
    assert sent["accepted_label_text"] == "方案 A" and sent["counters_sent"][0]["label_text"] == "方案 A"
    _both(client, "/receivables/RCV-A/chase", [r"\.thread_href"], echoes_lang=False)


# ---------------------------------------------------------------- the writes, in both languages


def _same_ids(body: Any) -> Any:
    """Two walks of the same steps mint different agreement ids (each carries a fresh nonce): read them as one."""
    return json.loads(re.sub(r"CMT-[0-9a-f]+", "CMT-x", json.dumps(body)))


# The evaluate view: the fields a Business page reads, and the engine's own sentences among them that stay as written (each has a
# `*_when` or `*_text` twin in the page's language). `passed_checks`, `autonomy` and `concession_values` are the folded audit evidence.
EVALUATE_BUSINESS = ("workspace", "counters", "comparison", "violations", "notes", "plan", "plan_committed", "plan_expected", "cure_plan",
                     "evaluated_when", "summary_when")
_PLANS = r"\.(plan|plan_committed|plan_expected|cure_plan)"
EVALUATE_RAW = [
    r"\.workspace\.financial_impact\.lines\[\]\.basis", r"\.workspace\.priced_response\.label", r"\.workspace\.priced_responses\[\]\.label",
    r"\.counters\[\]\.(label|text|rationale|formula|obligations\[\]\.spans\[\]\.text|economics\.components\[\]\.basis)",
    r"\.comparison\[\]\.(label|components\[\]|note|not_executable_reason)",
    r"\.violations\[\]\.(message|formula|spans\[\]\.text|cure_note|inputs\..*)", r"\.notes\[\]\.message",
    _PLANS + r"\.(label|not_executable_reason|costs\[\]\.(label|formula|not_executable_reason)|rejected\[\]\.(label|note))",
]


def _walk_for(client, lang: str, steps) -> Any:
    client.post("/demo/reset", json={})
    return steps(client, lang)


def _twice(client, steps) -> tuple[Any, Any]:
    return _walk_for(client, "en", steps), _walk_for(client, "zh", steps)


def test_act_on_an_alert_answers_in_the_requested_language(client):
    def steps(c, lang):
        action = c.get("/home").json()["next_action"]
        r = c.post(f"/alerts/{action['alert_id']}/act", params={"lang": lang},
                   json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
        assert r.status_code == 200, r.text
        return r.json()

    en, zh = _twice(client, steps)
    assert figures(en) == figures(zh) and zh["lang"] == "zh"
    assert unchanged_words(en, zh, _names(), [r".*\.message"]) == []
    assert english_leaks(zh, _names(), [r"\.results\[\]\.(message|op_id|idempotency_key)", r"\.alert_id", r"\.decision_id"]) == []
    assert [r["event_text"] for r in zh["results"]][1].startswith("已")
    assert zh["results"][0]["message"].startswith(("Advance ", "Drew "))  # the executor's sentence is untouched


def test_act_refusals_carry_their_message_in_the_requested_language(client):
    def steps(c, lang):
        action = c.get("/home").json()["next_action"]
        r = c.post(f"/alerts/{action['alert_id']}/act", params={"lang": lang}, json={"state_version": 0, "suggestions": action["suggestions"]})
        assert r.status_code == 409, r.text
        return r.json()["detail"]

    en, zh = _twice(client, steps)
    assert en["code"] == zh["code"] == "ALERT_CHANGED" and en["message"] == zh["message"]  # the raw message is the same for the audit level
    assert en["message_when"].startswith("The alert changed") and zh["message_when"].startswith("该提醒在您阅读之后已发生变化")
    assert zh["alert"]["title_when"].endswith("现金将低于最低现金储备")


def test_the_owners_decision_answers_in_the_requested_language(client):
    def steps(c, lang):
        _walk(c)
        _act(c)
        approval = _queue(c)[0]["id"]
        r = c.post(f"/approvals/{approval}", params={"lang": lang}, json={"decision": "APPROVE"})
        assert r.status_code == 200, r.text
        return r.json()

    en, zh = _twice(client, steps)
    assert figures(en) == figures(zh) and zh["lang"] == "zh"
    assert unchanged_words(en, zh) == []
    assert zh["result"]["event_text"].startswith("您已批准") and zh["result"]["message"] == en["result"]["message"]
    assert english_leaks(zh, _names(), [r"\.result\.(message|op_id|idempotency_key|approval_id)"]) == []


def test_the_owner_declines_in_the_requested_language(client):
    def steps(c, lang):
        _walk(c)
        _act(c)
        approval = _queue(c)[0]["id"]
        return c.post(f"/approvals/{approval}", params={"lang": lang}, json={"decision": "REJECT"}).json()

    en, zh = _twice(client, steps)
    assert zh["result"]["message_when"] == "您已拒绝（APR-000001）；未执行任何操作" or zh["result"]["message_when"].startswith("您已拒绝")
    assert en["result"]["message_when"].startswith("Declined by the owner")
    assert zh["result"]["event_text"].startswith("您已拒绝")


def test_evaluate_and_negotiate_answer_in_the_requested_language(client):
    def steps(c, lang):
        c.post("/demo/reset", json={})
        offer = c.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
        evaluated = c.post(f"/offers/{offer}/evaluate", params={"lang": lang}, json={"fixture_id": EX01}).json()
        sent = c.post(f"/negotiate/{offer}", params={"lang": lang}, json={"buyer_profile": "cooperative"}).json()
        stale = c.post(f"/negotiate/{offer}", params={"lang": lang}, json={"buyer_profile": "cooperative", "counter_id": "nope"})
        return evaluated, sent, stale.json()["detail"]

    (ev_en, ng_en, st_en), (ev_zh, ng_zh, st_zh) = _twice(client, steps)
    # evaluate: the same figures, and the Business fields in Chinese (the folded audit evidence, the checks and the verifier's own
    # working, stays as written)
    assert figures(_same_ids(ev_en)) == figures(_same_ids(ev_zh)) and ev_zh["lang"] == "zh"
    business = {k: ev_zh[k] for k in EVALUATE_BUSINESS}
    assert english_leaks(business, _names(), EVALUATE_RAW) == []
    assert unchanged_words({k: ev_en[k] for k in EVALUATE_BUSINESS}, business, _names(), EVALUATE_RAW) == []
    assert ev_zh["workspace"]["priced_response"]["label_text"] == "方案 A" and "方案 A" in ev_zh["workspace"]["priced_response"]["send_scope"]
    counter = ev_zh["counters"][0]
    assert counter["text_when"].startswith("账期保持 45 天") and counter["rationale_when"].startswith("按 0.85% 提前结算")
    assert counter["text"] == ev_en["counters"][0]["text"] and counter["label_when"] == "方案 A"  # what is sent to the buyer stays as written
    assert {v["code"] for v in ev_zh["violations"]} == {v["code"] for v in ev_en["violations"]}
    assert all(any("一" <= ch <= "鿿" for ch in v["message_when"]) for v in ev_zh["violations"])
    assert ev_zh["last_read_day"] == ev_en["last_read_day"] and ev_zh["last_read_when"] == "今天" and ev_en["last_read_when"] == "today"
    assert all(r["label_when"] for r in ev_zh["comparison"]) and ev_zh["plan_committed"]["label_when"].startswith("已承诺方案：")
    # negotiate: the execution summary, the message and the 409 in Chinese, the same facts in both
    assert figures(_same_ids(ng_en)) == figures(_same_ids(ng_zh)) and ng_zh["lang"] == "zh"
    assert ng_zh["execution"]["summary_text"].startswith("已记录与Foshan Home Retail Co.的协议")
    assert ng_zh["message_when"] == "方案 A已被接受，协议已记录；其余缺口已融资。" and ng_en["message_when"].startswith("Option A was accepted")
    assert ng_zh["message"] == ng_en["message"] and "commitment recorded" in ng_zh["message"]  # the engine's sentence is the audit level
    assert st_en["code"] == st_zh["code"] == "COUNTER_CHANGED"
    assert st_zh["message_when"].startswith("还价在您阅读之后已发生变化") and st_en["message_when"].startswith("The counter changed")
    assert ng_zh["plan"]["label_when"].startswith("已承诺方案：")


def test_a_second_identical_send_says_so_in_both_languages(client):
    def steps(c, lang):
        c.post("/demo/reset", json={})
        offer = c.post("/offers", json={"fixture_id": EX01}).json()["offer"]["offer_id"]
        verdict = c.post(f"/offers/{offer}/evaluate", json={"fixture_id": EX01}).json()
        body = {"buyer_profile": "cooperative", "verdict_id": verdict["id"], "counter_id": verdict["counters"][0]["id"],
                "state_version": verdict["state_version"]}
        c.post(f"/negotiate/{offer}", params={"lang": lang}, json=body)
        return c.post(f"/negotiate/{offer}", params={"lang": lang}, json=body).json()["detail"]

    en, zh = _twice(client, steps)
    assert en["code"] == zh["code"] == "ALREADY_SENT"
    assert en["message_when"].startswith("This counter was already sent") and zh["message_when"].startswith("这项还价已发送")


# ---------------------------------------------------------------- names, the raw log and the defaults


def test_a_name_with_a_full_stop_and_a_comma_is_carried_over_exactly():
    buyer = "Foshan, Home Retail Co. Ltd."
    assert _zh(f"Drew ¥150,000.00 on {buyer} today", (buyer,)) == f"已于今天从{buyer}提取 ¥150,000.00"
    assert _zh(f"¥1,000.00 promised for the ¥5,000.00 invoice to {buyer} within 2 days under the agreement with {buyer}; the day has not passed.",
               (buyer,)) == (f"与{buyer}的协议约定，{buyer} 的 ¥5,000.00 发票的 ¥1,000.00 应在2 天内到账；约定日尚未过。")


def test_the_raw_engine_sentences_are_exactly_what_the_log_wrote(client):
    _walk(client)
    _act(client)
    zh = _read(client, "/ledger", "zh")
    en = _read(client, "/ledger", "en")
    for field in ("message", "summary", "entry_hash", "prev_hash", "kind", "status", "op_id"):
        assert [o[field] for o in zh["operations"]] == [o[field] for o in en["operations"]], field
    assert zh["head_hash"] == en["head_hash"] and zh["chain_valid"] is True


def test_every_read_defaults_to_english_and_an_unknown_language_falls_back_to_english(client):
    _walk(client, to=2)
    for path in ("/alerts", "/reconciliation", "/approvals/queue", "/ledger", "/audit", "/home"):
        default = client.get(path).json()
        assert default.get("lang", "en") == "en", path
        assert client.get(path, params={"lang": "fr"}).json() == default, path


# ---------------------------------------------------------------- every kind of alert the engine writes, said in both languages


def _alert_cases():
    """(name, state, alerts at `day`) for each kind the alert engine writes: the Business sentences are the same alert read two ways."""
    from app.alerts import alerts as engine_alerts
    from app.domain.fixtures import load_scenario
    from app.domain.models import CashFlow, Commitment, CommitmentStatus, DebtPosition, FlowKind, FundingLot
    from tests.alerts.test_alerts import _draw_line, _store
    from tests.verifier.conftest import bundle

    def cases(store, day=0, **kw):
        state = store.get_state()
        return state, engine_alerts(state, store.get_mandate(), store, day, **kw)

    base, _ = load_scenario()
    out = [("baseline", *cases(_store())), ("deal", *cases(_store(), obligations=bundle("EX01_PACKAGE").bound_obligations)),
           ("late", *cases(_store(), day=40))]
    thin = base.model_copy(update={"cash_fen": 65_000_000})
    out.append(("thin", *cases(_store(thin))))
    for name, service in (("dscr-tight", 7_000_000), ("dscr-breach", 8_000_000)):
        debt = DebtPosition(id="D-1", facility_id=None, label="loan", principal_fen=150_000_000, monthly_debt_service_fen=service)
        out.append((name, *cases(_store(base.model_copy(update={"debts": [debt]})))))
    big = CashFlow(id="F-BIG", day=115, amount_fen=-200_000_000, kind=FlowKind.OTHER, label="Big payment", confirmed=True)
    store = _store(base.model_copy(update={"flows": [*base.flows, big]}))
    _draw_line(store)
    out.append(("clean-down", *cases(store)))
    store = _store()
    offer = bundle("EX01_PACKAGE")
    store.put_commitment(Commitment(id="CMT-0123456789abcdef", offer_id="OFF-1", offer_version=1, counterparty_id="BUYER-1", verdict_id="V-1", terms_hash="h",
                                    obligations=offer.bound_obligations[:1], status=CommitmentStatus.PROPOSED, nonce="n", expires_day=5,
                                    mandate_version=1, forward_value_fen=0))
    out.append(("expiring", *cases(store)))
    for name, expires, day in (("mandate-soon", 10, 0), ("mandate-expired", 3, 4)):
        store = _store()
        store.put_mandate(store.get_mandate().model_copy(update={"expires_day": expires}))
        out.append((name, *cases(store, day)))
    store = _store(base.model_copy(update={"cash_fen": 25_000_000}))
    line = next(f for f in base.facilities if f.id == "FAC-LINE")
    lot = FundingLot(id="LOT-T", facility_id="FAC-LINE", principal_fen=15_000_000, remaining_fen=15_000_000, request_day=0, arrival_day=3, settled=False)
    low = store.get_state().model_copy(update={"lots": [lot], "facilities": [
        f.model_copy(update={"drawn_fen": 15_000_000}) if f.id == line.id else f for f in base.facilities]})
    out.append(("in-transit", low, engine_alerts(low, store.get_mandate(), store, 0)))
    return out


OWNER_LAYER_WORDS = ("headroom", "trajectory", "Tier 2", "Tier-2", "obligation", "committed cure", "reserve floor", "the floor")


def test_every_kind_of_alert_is_said_in_both_languages_without_the_engines_own_terms():
    from app.alerts import AlertKind
    from app.api.presentation import book_names

    seen: set[AlertKind] = set()
    for name, state, found in _alert_cases():
        names = book_names(state)
        for a in found:
            seen.add(a.kind)
            for field in ("title", "detail"):
                en = business_text(state, getattr(a, field), 10, "en")
                zh = business_text(state, getattr(a, field), 10, "zh")
                assert en and zh and en != zh, (name, field, en)
                if a.kind != AlertKind.COVENANT_HEADROOM_LOW:  # a covenant's headroom is finance detail, which keeps its word
                    assert not any(w.lower() in en.lower() for w in OWNER_LAYER_WORDS), (name, field, en)
                assert english_leaks({"x": zh}, names) == [], (name, field, zh)
            for note in (s.note for s in a.suggested if s.note):
                zh = business_text(state, note, 10, "zh")
                assert english_leaks({"x": zh}, names) == [], (name, note, zh)
    assert seen >= {AlertKind.RESERVE_BREACH_AHEAD, AlertKind.RESERVE_HEADROOM_LOW, AlertKind.COVENANT_HEADROOM_LOW,
                    AlertKind.CLEAN_DOWN_AT_RISK, AlertKind.COMMITMENT_EXPIRING, AlertKind.MANDATE_EXPIRING,
                    AlertKind.RECEIVABLE_PAST_DUE, AlertKind.CONCESSIONS_NEAR_CAP, AlertKind.FUNDING_IN_TRANSIT}


def test_the_end_of_the_demo_walk_reads_the_same_in_both_languages_and_the_repayment_act_answers_in_chinese(client):
    from tests.alerts.test_repay_alert import REPAY_ID, to_day47

    to_day47(client, get_runtime())
    for path, raw in (("/alerts", ALERTS_RAW), ("/reconciliation", RECON_RAW), ("/home", HOME_RAW), ("/ledger", LEDGER_RAW),
                      ("/approvals/queue", QUEUE_RAW)):
        _both(client, path, raw)
    repay = next(a for a in _read(client, "/alerts", "zh")["alerts"] if a["id"] == REPAY_ID)
    assert repay["title_when"].endswith("可以还款") and "今天还款需付迄今利息" in repay["detail_when"]
    acted = client.post(f"/alerts/{REPAY_ID}/act", params={"lang": "zh"}).json()
    assert acted["results"][0]["event_text"].startswith("已向") or acted["results"][0]["message_when"].startswith("已向")
    assert english_leaks(acted, _names(), [r"\.results\[\]\.(message|op_id|idempotency_key)", r"\.alert_id", r"\.decision_id"]) == []
    _both(client, "/ledger", LEDGER_RAW)


# ---------------------------------------------------------------- F21: what could not be read is named, and the conclusion stands


def test_a_failed_supporting_read_is_named_on_the_home_and_never_fails_the_route(client, monkeypatch):
    from app.api import home as home_module

    ok = _read(client, "/home", "en")
    assert ok["partial"] is None  # nothing missing: the field is there and empty

    def broken(*_a, **_k):
        raise RuntimeError("the decision record is unreadable")

    monkeypatch.setattr(home_module, "load_context", broken)
    en, zh = _read(client, "/home", "en"), _read(client, "/home", "zh")
    for body in (en, zh):
        assert body["partial"]["missing"] == ["decision_record"] and body["headline"] and body["next_action"]["alert_id"]  # the answer stands
        assert body["open_decisions"] == [] and body["cash"]["cash_fen"] == ok["cash"]["cash_fen"]
    assert en["partial"]["text"] == "Some supporting facts could not be read: the record of your decisions."
    assert zh["partial"]["text"] == "部分辅助信息未能读取：您的决策记录。" and zh["partial"]["missing_text"] == ["您的决策记录"]


def test_a_failed_reconciliation_is_named_on_the_home_in_both_languages(client, monkeypatch):
    from app.api import home as home_module

    _walk(client, receipt="half")  # a promise kept in part: the home reads the reconciliation to say so
    assert _read(client, "/home", "en")["partial"] is None

    def broken(*_a, **_k):
        raise RuntimeError("the reconciliation is unreadable")

    monkeypatch.setattr(home_module, "reconcile", broken)
    en, zh = _read(client, "/home", "en"), _read(client, "/home", "zh")
    assert en["partial"]["missing"] == zh["partial"]["missing"] == ["reconciliation"]
    assert en["partial"]["text"].startswith("Some supporting facts could not be read:") and zh["partial"]["text"].startswith("部分辅助信息未能读取")
    assert en["headline"] and zh["headline"] and en["status"] == zh["status"] and en["changes"] and zh["changes"]


def test_every_business_read_says_when_the_books_were_read(client):
    _walk(client, to=2)
    today = get_runtime().day
    for path in ("/home", "/approvals/queue", "/reconciliation", "/ledger", "/alerts"):
        en, zh = _read(client, path, "en"), _read(client, path, "zh")
        if path == "/home":
            en, zh = en["cash"], zh["cash"]
        assert en["last_read_day"] == zh["last_read_day"] == today, path
        assert (en["last_read_when"], zh["last_read_when"]) == ("today", "今天"), path
