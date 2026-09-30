def test_health(client):
    assert client.get("/health").json()["ok"]


def test_mandate_is_signed_and_valid(client):
    body = client.get("/mandate").json()
    assert body["valid"], body["problems"]
    assert body["display"]["min_cash"] == "¥300,000.00"


def test_baseline_trajectory_breaches_day_12(client):
    t = client.get("/trajectory").json()
    assert t["first_breach_day"] == 12
    assert next(d for d in t["days"] if d["day"] == 12)["closing"]["text"] == "¥60,000.00"


def test_ledger_empty_and_chain_valid_after_reset(client):
    client.post("/demo/reset")
    body = client.get("/ledger").json()
    assert body["chain_valid"] and body["operations"] == []
