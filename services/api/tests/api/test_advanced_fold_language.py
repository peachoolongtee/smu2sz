"""Map #65 debt, ticket #83: the evaluate view's Advanced fold in Chinese. The verifier's passed checks and the compiler's autonomy proof are
English (hash-chained or audit level, so they stay as written); beside them the view now carries `label_when`, `observed_when` and `limit_when`
on each passed check and `covered_when`, `gaps_when` and `notes_when` on the autonomy block, said through the same `engine_zh` templates as every
other `*_when` field."""

from __future__ import annotations

import re

from app.api import engine_zh
from app.domain.fixtures import load_offers
from tests.api.conftest import english_leaks, figures
from tests.api.test_w7_language import _zh

NAMES = ["Bank credit line", "Foshan Home Retail Co.", "Invoice financing (onboarded platform)"]


def _evaluate(client, fixture: str, lang: str) -> dict:
    offer = client.post("/offers", json={"fixture_id": fixture}).json()["offer"]["offer_id"]
    r = client.post(f"/offers/{offer}/evaluate?lang={lang}", json={"fixture_id": fixture})
    assert r.status_code == 200, r.text
    return r.json()


def _fold(view: dict) -> dict:
    return {"passed_checks": [{k: c[k] for k in ("label_when", "observed_when", "limit_when")} for c in view["passed_checks"]],
            "autonomy": {k: view["autonomy"][k] for k in ("covered_when", "gaps_when", "notes_when")}}


def test_every_passed_check_and_the_autonomy_block_has_a_twin_and_the_originals_are_untouched(client):
    en = _evaluate(client, "EX01_PACKAGE", "en")
    assert en["passed_checks"] and all({"label_when", "observed_when", "limit_when"} <= set(c) for c in en["passed_checks"])
    assert {"covered_when", "gaps_when", "notes_when"} <= set(en["autonomy"])
    first = en["passed_checks"][0]
    assert first["label"] == "Implied cost of early settlement of RCV-A"  # the verifier's sentence, as written
    assert first["label_when"] == "Implied cost of early settlement of the ¥420,000.00 invoice to Foshan Home Retail Co. due in 32 days"
    assert first["observed_when"] == first["observed"] and first["limit_when"] == first["limit"]
    assert len(en["autonomy"]["covered_when"]) == len(en["autonomy"]["covered"])
    assert len(en["autonomy"]["gaps_when"]) == len(en["autonomy"]["gaps"]) and len(en["autonomy"]["notes_when"]) == len(en["autonomy"]["notes"])


def test_the_chinese_fold_keeps_every_figure_and_leaves_no_english_sentence(client):
    en, zh = _evaluate(client, "EX01_PACKAGE", "en"), _evaluate(client, "EX01_PACKAGE", "zh")
    assert figures(_fold(en)).keys() == figures(_fold(zh)).keys()
    checks = zh["passed_checks"]
    assert [c["label_when"] for c in checks] == [
        "提前结算Foshan Home Retail Co. 的 ¥420,000.00 发票（32 天后到期）的隐含成本", "账期延长并融资后的偿债覆盖率 DSCR（预估）",
        "最高月度杠杆率（第 1 月）", "Bank credit line：清零要求"]
    assert checks[3]["observed_when"] == "已有 59 天为零" and checks[3]["limit_when"] == "≥ 连续 30 天"
    assert checks[0]["observed_when"] == "14.78%" and checks[1]["limit_when"] == "≥ 1.25x"
    a = zh["autonomy"]
    assert a["covered_when"] == [
        "提前付款：¥420,000.00，Foshan Home Retail Co. 的 ¥420,000.00 发票（32 天后到期），折扣 1.20%，2 天后付款",
        "账期延长：未来发票 +15 天", "或有返利：期间采购 基数 ¥400,000.00 比例 1.00%"]
    assert a["gaps_when"][0].startswith("编译器无法逐项核对消息中的每个数字和请求：账期延长的 current_terms_days 未能确定；")
    assert a["notes_when"][-1] == "未读入条款的文字：'extend', 'standard', 'terms', 'going', 'forward' 等。"
    assert english_leaks({"a": a["covered_when"], "b": [c["label_when"] for c in checks]}, NAMES) == []
    assert zh["passed_checks"][0]["label"] == en["passed_checks"][0]["label"]  # the English original stays beside it


def test_the_other_checks_the_verifier_writes_are_known_to_the_templates():
    assert _zh("Minimum cash") == "最低现金"
    assert _zh("Minimum cash with the committed plan") == "采用已承诺方案后的最低现金"
    assert _zh("¥300,000.00 on day 42") == "¥300,000.00（第 42 天）"
    assert _zh("¥300,000.00 in 8 days") == "¥300,000.00（8 天后）"
    assert _zh("Lowest monthly DSCR (month 3)") == "最低月度偿债覆盖率 DSCR（第 3 月）"
    assert _zh("Early payment against the router's plan") == "提前付款与融资方案的对比"
    assert _zh("no admissible plan without the offer") == "没有该报价就没有可行的融资方案"
    assert _zh("a base amount is stated only approximately") == "基数金额只给出了大约数"
    assert _zh("EX03-msg holds a question beyond the extracted terms") == "EX03-msg 含有超出已提取条款的问题"
    assert _zh("an amount in EX03-msg is not accounted for by the extracted terms") == "EX03-msg 中的金额没有被已提取的条款解释"
    assert _zh("OBL-1: the message does not state the invoice amount") == "OBL-1：消息没有写明发票金额"
    assert _zh("a term was not read (rate_bp, base.amount_fen)") == "有条款没有读入（rate_bp, base.amount_fen）"


def test_a_note_no_template_knows_passes_through_unchanged_and_is_recorded():
    engine_zh.MISSES.clear()
    odd = "the compiler found a thing nobody wrote a template for yet"
    assert engine_zh.translate(odd) == odd and odd in engine_zh.MISSES


def test_the_evaluate_view_of_every_example_is_chinese_except_the_buyers_own_words(client):
    """Across the examples: no passed check and no covered term leaves English behind, and the autonomy sentences keep Latin only for the
    words the buyer wrote (quoted, as the compiler quotes them) and the identifiers of the terms it names."""
    quoted = re.compile(r"未读入条款的文字：.*?(?=；|$)")
    for fixture in load_offers():
        client.post("/demo/reset", json={})
        offer = client.post("/offers", json={"fixture_id": fixture})
        if offer.status_code != 200:
            continue
        zh = client.post(f"/offers/{offer.json()['offer']['offer_id']}/evaluate?lang=zh", json={"fixture_id": fixture}).json()
        if "passed_checks" not in zh:
            continue
        fold = _fold(zh)
        assert english_leaks({"checks": fold["passed_checks"], "covered": fold["autonomy"]["covered_when"]}, NAMES) == [], fixture
        sentences = {"gaps": [quoted.sub("", x) for x in fold["autonomy"]["gaps_when"]],
                     "notes": [quoted.sub("", x) for x in fold["autonomy"]["notes_when"]]}
        assert english_leaks(sentences, NAMES) == [], fixture
