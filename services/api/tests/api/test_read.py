def test_health(client):
    assert client.get("/health").json()["ok"]


def test_mandate_is_signed_and_valid(client):
    body = client.get("/mandate").json()
    assert body["valid"], body["problems"]
    assert body["mandate"]["min_cash_display"] == "¥300,000.00" and body["signature"]["status"] == "VALID"


def test_baseline_trajectory_breaches_day_12(client):
    t = client.get("/trajectory").json()
    assert t["first_breach_day"] == 12
    assert next(d for d in t["days"] if d["day"] == 12)["closing"]["text"] == "¥60,000.00"


def test_ledger_empty_and_chain_valid_after_reset(client):
    client.post("/demo/reset")
    body = client.get("/ledger").json()
    assert body["chain_valid"] and body["operations"] == [] and body["chain_length"] == 0


def test_post_offer_fixture_compiles_three_obligations(client):
    body = client.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()
    types = sorted(o["type"] for o in body["offer"]["obligations"])
    assert types == ["CONTINGENT_REBATE", "IMMEDIATE_DISCOUNT", "TERMS_EXTENSION"]


def test_term_sheet_is_proposal_only(client):
    ts = client.post("/facilities/compile", json={"fixture_id": "EX09_TERM_SHEET_PG"}).json()["term_sheet"]
    assert ts["all_in_rate_bp"] == 590 and ts["tier3_clauses"]
    assert ts["proposed_facility"]["owner_approved"] is False


def test_evidence_has_run_header_and_verifies(client, tmp_path):
    import pathlib
    import subprocess
    import sys
    text = client.get("/evidence").text
    lines = text.strip().splitlines()
    assert '"record":"run"' in lines[0] and '"record":"chain"' in lines[-1]
    f = tmp_path / "ev.jsonl"
    f.write_text(text)
    script = pathlib.Path(__file__).resolve().parents[4] / "scripts" / "verify_evidence.py"
    out = subprocess.run([sys.executable, str(script), str(f)], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout
