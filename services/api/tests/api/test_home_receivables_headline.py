"""GET /home `receivables.headline`: the sentence the receivables card leads with, in every state and both languages."""

from __future__ import annotations

from app.api.runtime import get_runtime
from tests.api.test_home import _exhaust_line
from tests.api.test_time_semantics import _walk


def _block(client, lang="en"):
    return client.get("/home", params={"lang": lang}).json()["receivables"]


def _pair(client):
    return _block(client), _block(client, "zh")


def test_someone_late_leads_with_the_late_invoice(client):
    _walk(client, receipt="half")
    en, zh = _pair(client)
    assert en["headline"] == "¥291,400.00 from Foshan Home Retail Co. is 2 days late."
    assert zh["headline"] == "来自Foshan Home Retail Co.的 ¥291,400.00 已逾期 2 天。"
    assert en["headline_tone"] == zh["headline_tone"] == "bad"
    assert en["past_due"][0]["face_display"] == "¥291,400.00"


def test_nobody_late_names_the_next_invoice(client):
    client.post("/demo/reset", json={})
    en, zh = _pair(client)
    assert en["headline"] == "Nobody is late. Next: ¥420,000.00 from Foshan Home Retail Co., due in 32 days."
    assert zh["headline"] == "没有逾期。下一笔：来自Foshan Home Retail Co.的 ¥420,000.00，32 天后到期。"
    assert en["headline_tone"] == "ok" and en["headline_note"] is None


def test_nothing_open_says_nothing_is_owed(client):
    client.post("/demo/reset", json={})
    rt = get_runtime()
    state = rt.store.get_state()
    rt.store.put_state(state.model_copy(update={"receivables": [
        r.model_copy(update={"status": "SETTLED", "settled_fen": r.face_fen}) for r in state.receivables]}))
    en, zh = _pair(client)
    assert en["open_count"] == 0
    assert en["headline"] == "Nothing is owed to you right now." and zh["headline"] == "目前没有应收款。"
    assert en["headline_tone"] == "ok" and en["headline_note"] is None


def test_the_note_says_when_the_ranking_cannot_be_priced(client):
    client.post("/demo/reset", json={})
    _exhaust_line(get_runtime())
    en, zh = _pair(client)
    assert en["open_count"] > 0
    assert en["headline_note"] == ("No committed funding plan covers the shortfall, so nothing is priced: ranked by how late each "
                                   "invoice is, then by amount.")
    assert zh["headline_note"] == "没有已承诺的融资方案能补上缺口，所以不估算节省额：按逾期天数排序，其次按金额。"
    # the receivables-worth read (when its feature is on) agrees that nothing can be priced and writes the same sentence
    worth = client.get("/receivables/worth")
    if worth.status_code == 200:
        assert worth.json()["no_plan"] is True and worth.json()["ranking_note"] == en["headline_note"]
