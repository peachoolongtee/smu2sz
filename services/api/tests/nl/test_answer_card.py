"""The answer card (app/nl/answer_card.py; owner decision of 17 Oct 2026): an owner's answer with structure, laid out for Ask FLOW.

Pinned here:
  - every wording of the owner-question bank, in English and Chinese, at day 0 and at day 34, gets a card whose lead and body are the reply
    itself, whose figures are the reply's own (with a label in the turn's language), and whose words carry no id;
  - every action any question can emit (all question ids x both languages x the figures that change the choice x every customer) is a
    link (kind "link", never an approval or a send), and its href is one of the destinations the web serves and the browser spec opens
    (apps/web/e2e/ask-destinations.json): its route is a page of the web app and its anchor is an id that page renders;
  - the card reaches the owner only: the agent key and a buyer never get one; the opener carries its links too.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.nl import answer_card
from app.nl.answers import answer, question_ids
from app.nl.models import AnswerCard
from tests.nl.conftest import AGENT, OWNER, Chat, build_app
from tests.nl.test_answers import ALL_WORDINGS, IDS, TOP30, nl_ctx, runtime

ROOT = Path(__file__).resolve().parents[4]
WEB = ROOT / "apps" / "web"
DESTINATIONS = json.loads((WEB / "e2e" / "ask-destinations.json").read_text(encoding="utf-8"))["destinations"]
CJK = re.compile(r"[㐀-鿿]")
# Words that are not a customer's or a facility's name and must never reach the owner as English inside a Chinese label.
EN_WORD = re.compile(r"\b(?:the|and|of|see|open|your|day|cash)\b", re.IGNORECASE)


def web_source() -> str:
    parts = [p.read_text(encoding="utf-8") for d in ("app", "components") for p in (WEB / d).rglob("*.tsx")]
    return "\n".join(parts)


SOURCE = web_source()


@pytest.fixture
def day0():
    rt = runtime()
    yield rt, TestClient(build_app())


@pytest.fixture
def day34():
    rt = runtime()
    client = TestClient(build_app())
    r = client.post("/clock/advance", json={"to_day": 34}, headers=OWNER)
    assert r.status_code == 200, r.text
    yield rt, client


def card_of(rt, text: str, lang: str) -> tuple[str, AnswerCard | None]:
    """The reply and the card for one wording, built as the response builds it (the layer's reply, its seed, the reply laid out)."""
    got = answer(text, lang, nl_ctx(rt, lang))
    assert got is not None, text
    return got.text, answer_card.finish(answer_card.from_reply(got, lang, rt.store.get_state()), got.text)


def check_words(card: AnswerCard, lang: str) -> None:
    labels = [f.label for f in card.all_figures] + [a.label for a in card.actions]
    for label in labels:
        assert label.strip(), card
        assert not IDS.search(label), label  # no id or reference code in a word
        if lang == "zh":
            assert CJK.search(label), label
            assert not EN_WORD.search(label.replace("FLOW", "")), label
        else:
            assert not CJK.search(label), label
    for f in card.all_figures:
        assert not IDS.search(f.value), f
        assert f.tone in ("danger", "ok", "neutral")


def check_links(card: AnswerCard) -> None:
    allowed = {d["href"] for d in DESTINATIONS}
    for a in card.actions:
        assert a.kind == "link"
        assert a.href.startswith("/") and not a.href.startswith("//"), a.href
        template = re.sub(r"(?<=customer=)[A-Z0-9-]+$|(?<=/customers/)[A-Z0-9-]+$", "{id}", a.href)
        assert template in allowed, a.href
    assert len(card.actions) <= answer_card.MAX_ACTIONS
    assert len({a.href for a in card.actions}) == len(card.actions)


# ---------------------------------------------------------------- every wording, both languages, two points of the story


@pytest.mark.parametrize("point", ["day0", "day34"])
def test_every_answer_of_the_bank_is_a_card_made_of_its_own_reply(point, request) -> None:
    rt, _client = request.getfixturevalue(point)
    seen = set()
    for qid, lang, text in ALL_WORDINGS:
        reply, card = card_of(rt, text, lang)
        assert card is not None, (qid, lang, text)
        seen.add(qid)
        # the lead and the body ARE the reply: nothing is added, reworded or dropped
        joined = (card.lead + (" " if lang == "en" and card.body else "") + card.body)
        assert re.sub(r"\s+", "", joined) == re.sub(r"\s+", "", reply), (text, card.lead, card.body)
        assert card.lead and len(card.lead) <= len(reply)
        assert card.basis
        assert len(card.figures) <= answer_card.MAX_TILES and card.figures == card.all_figures[: len(card.figures)]
        check_words(card, lang)
        check_links(card)
    assert seen == set(TOP30)


def test_the_lead_is_the_yes_no_or_the_figure(day0) -> None:
    rt, _ = day0
    assert card_of(rt, "Are we inside our covenants?", "en")[1].lead == "Yes."
    assert card_of(rt, "我们满足契约吗？", "zh")[1].lead == "满足。"
    safe = card_of(rt, "Are we safe?", "en")[1]
    assert safe.lead.startswith("Not on today's books:") and safe.body.startswith("FLOW's plan covers it for ¥3,113.93")
    assert [(f.label, f.value, f.tone) for f in safe.figures] == [
        ("Funding needed", "¥405,000", "danger"), ("Lowest cash", "−¥105,000", "danger"), ("Below reserve from", "Day 12", "danger")]
    zh = card_of(rt, "我们安全吗？", "zh")[1]
    assert [(f.label, f.value) for f in zh.figures] == [("所需资金", "¥405,000"), ("最低现金", "−¥105,000"), ("跌破储备线", "第 12 天")]
    assert [a.href for a in safe.actions] == ["/cash#cash-chart", "/#home-v2-action"]
    assert [a.label for a in zh.actions] == ["查看现金预测", "查看 FLOW 的方案"]


def test_a_decimal_or_a_company_name_does_not_end_the_lead() -> None:
    assert answer_card.split_lead("It costs ¥3,113.93 today. Then more.", "en") == ("It costs ¥3,113.93 today.", "Then more.")
    assert answer_card.split_lead("Foshan Home Retail Co. pays on day 32. Fine.", "en") == ("Foshan Home Retail Co. pays on day 32.", "Fine.")
    assert answer_card.split_lead("满足。预测的每个月都在范围内。", "zh") == ("满足。", "预测的每个月都在范围内。")
    assert answer_card.split_lead("One sentence only.", "en") == ("One sentence only.", "")


def test_a_named_customer_links_to_its_invoices_and_its_page(day0) -> None:
    rt, _ = day0
    for lang, text in (("en", "Which customer owes us the most?"), ("zh", "谁欠我们最多？")):
        card = card_of(rt, text, lang)[1]
        assert [a.href for a in card.actions] == ["/receivables?customer=BUYER-1", "/customers/BUYER-1"], card.actions
        assert all("BUYER" not in a.label for a in card.actions)


# ---------------------------------------------------------------- every action any question can emit


FIGURE_SETS = [
    {},
    {"plan_cost": "¥3,113.93", "need": "¥405,000", "first_breach_day": "12", "approvals_pending": "1", "answer": "no"},
    {"plan_cost": "¥3,113.93", "need": "¥0", "approvals_pending": "0", "answer": "yes"},
]


def every_action(state) -> list[tuple[str, str, str, str]]:
    """(question id, lang, label, href) of every action a card can carry on these books."""
    names = [c.name for c in state.counterparties if c.role == "BUYER"] + ["someone the books do not hold"]
    out = []
    for qid in question_ids():
        for lang in ("en", "zh"):
            for figs in FIGURE_SETS:
                for name in names:
                    for a in answer_card.actions_for(qid, {**figs, "buyer": name}, lang, state):
                        out.append((qid, lang, a.label, a.href))
                    for a in answer_card.actions_for(qid, figs, lang, state):
                        out.append((qid, lang, a.label, a.href))
    return out


def test_every_action_is_a_link_to_a_destination_the_web_serves(day0) -> None:
    rt, _ = day0
    state = rt.store.get_state()
    acts = every_action(state)
    templates = set()
    for qid, lang, label, href in acts:
        assert not IDS.search(label), (qid, label)
        assert (CJK.search(label) is not None) == (lang == "zh"), (qid, lang, label)
        template = re.sub(r"(?<=customer=)[A-Z0-9-]+$|(?<=/customers/)[A-Z0-9-]+$", "{id}", href)
        templates.add(template)
    # every question has at least one link, and the questions together reach every destination: no destination is dead code
    assert {q for q, *_ in acts} == set(question_ids())
    assert templates == {d["href"] for d in DESTINATIONS} == {d.href for d in answer_card.DESTINATIONS.values()}
    # every customer link names a customer the books hold
    ids = {c.id for c in state.counterparties if c.role == "BUYER"}
    for *_, href in acts:
        if "customer" in href:
            assert href.rsplit("=", 1)[-1].rsplit("/", 1)[-1] in ids, href


@pytest.mark.parametrize("dest", DESTINATIONS, ids=lambda d: d["key"])
def test_each_destination_is_a_page_of_the_web_with_its_anchor(dest) -> None:
    page = WEB / "app" / dest["route"] / "page.tsx" if dest["route"] else WEB / "app" / "page.tsx"
    assert page.exists(), page
    if "#" in dest["href"]:
        anchor = dest["href"].split("#", 1)[1]
        assert f'id="{anchor}"' in SOURCE, f"no element with id {anchor} in apps/web"
        assert dest["target"] == f"#{anchor}"
    if "customer=" in dest["href"]:
        assert 'params.get("customer")' in (WEB / "app" / "receivables" / "page.tsx").read_text(encoding="utf-8")


def test_the_href_list_is_every_href_on_the_books(day0) -> None:
    rt, _ = day0
    hrefs = set(answer_card.every_href(rt.store.get_state()))
    assert "/receivables?customer=BUYER-1" in hrefs and "/customers/BUYER-1" in hrefs
    assert all(h.startswith("/") for h in hrefs)


# ---------------------------------------------------------------- who gets a card


def test_the_owner_gets_the_card_and_the_agent_key_and_a_buyer_do_not(day0) -> None:
    _rt, client = day0
    owner = Chat(client, "card-owner").say("Are we safe?", lang="en")
    assert owner["intent"] == "ASK_BOOKS" and owner["card"]["lead"].startswith("Not on today's books")
    assert owner["reply"].startswith(owner["card"]["lead"])
    agent = Chat(client, "card-agent", owner=False).say("Are we safe?", lang="en")
    assert "card" not in agent or agent["card"] is None
    assert "¥405,000" not in json.dumps(agent, ensure_ascii=False)
    buyer = Chat(client, "card-buyer", actor="COUNTERPARTY", counterparty_id="BUYER-1").say("Are we safe?")
    assert "card" not in buyer
    raw = client.post("/nl", json={"session_id": "card-raw", "actor": "OWNER", "text": "Are we safe?"}, headers=AGENT).json()
    assert raw.get("card") is None


def test_a_turn_without_structure_has_no_card(day0) -> None:
    _rt, client = day0
    chat = Chat(client, "card-plain")
    assert chat.say("Fund the cash gap", lang="en").get("card") is None  # a plan awaiting the go-ahead keeps its own layout
    assert chat.say("go ahead", lang="en").get("card") is None


def test_the_opener_carries_links_to_what_it_raised(day0) -> None:
    _rt, client = day0
    for lang in ("en", "zh"):
        r = client.post("/nl/opener", json={"session_id": f"card-opener-{lang}", "lang": lang}, headers=OWNER).json()
        assert r["has_news"] is True
        card = AnswerCard.model_validate(r["card"])
        # Laid out like an answer (lead, 17 Oct): the bold lead, the tiles, FLOW's plan in one sentence in the owner's words, the other
        # warning on its own line; never an id, never "I". The reply and the plan waiting for the go-ahead are unchanged.
        assert card.lead == {"en": "Cash falls below your ¥300,000 reserve in 12 days, ¥240,000 short.",
                             "zh": "现金将在12 天后低于您 ¥300,000 的最低现金储备，缺口 ¥240,000。"}[lang]
        assert [(f.value, f.tone) for f in card.figures] == [("¥240,000", "danger"), ("−¥105,000", "danger"), ("¥3,113.93", "neutral")]
        plan, warning = card.body.split("\n")
        assert plan == {"en": "FLOW's plan: draw ¥150,000 on the Bank credit line today and finance ¥255,000 of the ¥420,000 invoice to "
                              "Foshan Home Retail Co. (due in 32 days), cash in 3 days; ¥3,113.93 in all.",
                        "zh": "FLOW 的方案：从Bank credit line提款 ¥150,000，今天到账；以Foshan Home Retail Co. 的 ¥420,000 发票（32 天后到期）"
                              "融资 ¥255,000，3 天后到账；合计 ¥3,113.93。"}[lang]
        assert warning.startswith({"en": "1 more warning:", "zh": "另有 1 项提醒："}[lang])
        for words in (card.lead, card.body):
            assert not IDS.search(words) and not re.search(r"\bI\b|我", words), words
        assert r["awaiting_confirmation"] is True and r["reply"].endswith({"en": "Go ahead?", "zh": "要执行吗？"}[lang])
        assert [a.href for a in card.actions] == ["/#home-v2-action", "/cash#cash-chart"]
        check_words(card, lang)
        check_links(card)
    # The go-ahead still runs exactly the plan the opener holds (the consent is unchanged).
    done = Chat(client, "card-opener-en").say("go ahead", lang="en")
    assert [(o["kind"], o["status"]) for o in done["operations"]] == [("DRAW_FACILITY", "EXECUTED"), ("SUBMIT_INVOICE_FOR_FINANCING", "EXECUTED")]


def test_the_opener_at_day_34_links_the_late_customer(day34) -> None:
    _rt, client = day34
    r = client.post("/nl/opener", json={"session_id": "card-opener-34", "lang": "en"}, headers=OWNER).json()
    hrefs = [a["href"] for a in r["card"]["actions"]]
    assert "/receivables?customer=BUYER-1" in hrefs and "/cash#cash-chart" in hrefs
    card = AnswerCard.model_validate(r["card"])
    check_links(card)
    assert card.lead.startswith("Cash is ¥405,000 below your ¥300,000 reserve today")
    assert "invoice to Foshan Home Retail Co." in card.body and "was due 2 days ago and has not arrived." in card.body
    for words in (card.lead, card.body):
        assert not IDS.search(words) and not re.search(r"\bI\b", words), words


# ---------------------------------------------------------------- the reply's language follows the question (lead, 17 Oct)


@pytest.mark.parametrize(("page", "text", "lang", "lead", "chip"), [
    ("en", "我们安全吗？", "zh", "按今日账目并不安全", "查看现金预测"),
    ("zh", "Are we safe?", "en", "Not on today's books", "See the cash forecast"),
    ("en", "Are we safe?", "en", "Not on today's books", "See the cash forecast"),
    ("zh", "我们安全吗？", "zh", "按今日账目并不安全", "查看现金预测"),
])
def test_a_question_in_the_other_language_is_answered_in_its_language(day0, page, text, lang, lead, chip) -> None:
    _rt, client = day0
    r = Chat(client, f"card-lang-{page}-{lang}").say(text, lang=page)
    assert r["lang"] == lang
    assert r["reply"].startswith(lead) and r["card"]["lead"].startswith(lead)
    assert r["card"]["actions"][0]["label"] == chip
    assert all((CJK.search(f["label"]) is not None) == (lang == "zh") for f in r["card"]["figures"])


def test_a_figure_or_an_option_pick_keeps_the_page_language(day0) -> None:
    _rt, client = day0
    chat = Chat(client, "card-lang-pick")
    ask = chat.say("帮我处理一下资金问题", lang="zh")
    assert ask["lang"] == "zh" and ask["clarification"] is not None
    picked = chat.say(ask["clarification"]["options"][0]["id"], lang="zh")
    assert picked["lang"] == "zh"
    assert Chat(client, "card-lang-num").say("1", lang="zh")["lang"] == "zh"
