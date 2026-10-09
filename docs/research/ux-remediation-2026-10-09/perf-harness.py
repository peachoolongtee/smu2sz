"""Profile and pin the four decision reads (map #65, ticket #87): GET /decisions, /home, /approvals/queue and /ledger.

Each read is timed (best of a few repeats) and the calls to reconcile(), alerts() and read_entries(), and to json.loads, that one request
makes are counted by wrapping the functions where the API imported them. The JSON of every read is written to OUTDIR (scrubbed of
timestamps), so two runs on the same books can be compared with perf-compare.py (random ids are renamed by first appearance).

  python perf-harness.py MODE OUTDIR [--half]

  MODE golden       the golden books: the EX01 package, a cooperative buyer, day 34, then the cure queued (--half: a half receipt first)
  MODE public       the public-record SME (fixtures/scenarios/public_sme.json and its mandate), eight ADVANCE_CLOCK weeks as
                    scripts/pilot_dry_run.py does, then four offers and two pending approvals
  MODE scale        golden books, 5, 20 then 80 offers evaluated (every other one negotiated)
  MODE stress       golden books, 50/200/400/800 refused Tier-3 operations (log growth, no lots) and 12/50/100/200 pending approvals
  MODE stresslots   as stress with executed DRAW_FACILITY operations (each makes a funding lot), up to 400 and 100

Run it with the API project's interpreter (uv run --project services/api python <this file> MODE OUTDIR). Set WT to
another checkout's root to measure that code instead (for a before/after). SKIP_PERF_BENCH=1. An in-process TestClient: no port is opened."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

WT = Path(os.environ.get("WT", str(Path(__file__).resolve().parents[3])))
API = WT / "services/api"
sys.path.insert(0, str(API))
sys.path.insert(0, str(API / "scripts"))

books, out = sys.argv[1], Path(sys.argv[2])
SCALE = books in ('scale', 'stress', 'stresslots')
STRESS = books in ('stress', 'stresslots')
LOTS = books == 'stresslots'
if SCALE:
    books = 'golden'
out.mkdir(parents=True, exist_ok=True)
os.environ.update({"TERMSLEDGER_NO_DOTENV": "1", "DATABASE_URL": "memory", "LLM_MODE": "cache", "PYTHONUTF8": "1"})
HDR = {"X-Owner-Token": "demo-owner-token"}
if books == "public":
    os.environ.update({"DEMO_MODE": "0", "OWNER_TOKEN": "tok-owner", "AGENT_KEY": "tok-agent", "FEATURE_ENVELOPE": "1",
                       "FEATURE_PRICE_CURVE": "1", "FEATURE_COLLECTIONS_WORTH": "1", "FEATURE_PILOT_JOURNAL": "1"})
    HDR = {"X-Owner-Token": "tok-owner"}

from fastapi.testclient import TestClient  # noqa: E402

import app.alerts as alerts_pkg  # noqa: E402,F401
from app.api.runtime import Runtime, set_runtime  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.persistence import InMemoryLedgerStore  # noqa: E402

COUNTS: dict[str, int] = {"reconcile": 0, "alerts": 0, "read_entries": 0, "json_loads": 0}


def patch_everywhere() -> None:
    import importlib
    import json as _json

    import app.alerts.engine as eng
    rec = sys.modules['app.alerts.reconcile']
    import app.operations.log as oplog
    import app.main  # noqa: F401  (imports every route module)

    originals = {"reconcile": rec.reconcile, "alerts": sys.modules["app.alerts.engine"].alerts, "read_entries": oplog.read_entries}

    def wrap(name):
        orig = originals[name]

        def inner(*a, **k):
            COUNTS[name] += 1
            return orig(*a, **k)

        return inner

    wrapped = {n: wrap(n) for n in originals}
    for mod in list(sys.modules.values()):
        if mod is None or not getattr(mod, "__name__", "").startswith("app"):
            continue
        for n, orig in originals.items():
            if getattr(mod, n, None) is orig:
                setattr(mod, n, wrapped[n])
    orig_loads = _json.loads

    def loads(*a, **k):
        COUNTS["json_loads"] += 1
        return orig_loads(*a, **k)

    _json.loads = loads


def make_runtime():
    if books == "golden":
        rt = Runtime(settings=get_settings(), store=InMemoryLedgerStore(), owner_key_hex=__import__("app.mandate.fixture", fromlist=["x"]).demo_owner_public_key_hex())
        rt.reset()
        return rt
    import pilot_runtime as pr

    d = json.loads((WT / "fixtures/scenarios/public_sme.json").read_text())
    (out / "_state.json").write_text(json.dumps(d["state"]))
    return pr.build_runtime(out / "_state.json", WT / "fixtures/scenarios/public_sme.mandate.json")


READS = [("/decisions", "decisions"), ("/home", "home"), ("/approvals/queue", "queue"), ("/ledger", "ledger")]
VOLATILE = ("recorded_at", "computed_in_seconds")


def scrub(x):
    if isinstance(x, dict):
        return {k: scrub(v) for k, v in x.items() if k not in VOLATILE}
    if isinstance(x, list):
        return [scrub(v) for v in x]
    return x


def measure(client, tag: str, repeat: int = 3) -> dict:
    res = {}
    if os.environ.get("PROF"):
        import cProfile, pstats, io
        for path, name in READS:
            pr = cProfile.Profile(); pr.enable(); client.get(path, headers=HDR); pr.disable(); pr.dump_stats(str(out / f'{tag}-{name}.prof'))
            buf = io.StringIO(); pstats.Stats(pr, stream=buf).sort_stats("cumulative").print_stats(28)
            (out / f"{tag}-{name}.prof.txt").write_text(buf.getvalue())
    for path, name in READS:
        times = []
        for i in range(repeat):
            for k in COUNTS:
                COUNTS[k] = 0
            t0 = time.perf_counter()
            r = client.get(path, headers=HDR)
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200, (path, r.status_code, r.text[:300])
            if i == 0:
                body = r.json()
                (out / f"{tag}-{name}.json").write_text(json.dumps(scrub(body), indent=1, sort_keys=True, ensure_ascii=False))
        res[name] = {"wall_s_min": round(min(times), 3), "wall_s_max": round(max(times), 3), **dict(COUNTS)}
    return res


def main():
    patch_everywhere()
    from app.main import app

    rt = make_runtime()
    set_runtime(rt)
    client = TestClient(app, headers=HDR)
    results = {}
    if STRESS:
        c = client
        c.post("/demo/reset", json={})
        AG = {"X-Owner-Token": "", "X-Agent-Key": "demo-agent-key"}
        made_d = made_a = 0
        for draws, applies in ((50, 12), (200, 50), (400, 100)) if LOTS else ((50, 12), (200, 50), (400, 100), (800, 200)):
            while made_d < draws:
                made_d += 1
                r = c.post("/operations", headers=AG, json={**({"kind": "DRAW_FACILITY", "amount_fen": 100} if LOTS else {"kind": "SIGN_PERSONAL_GUARANTEE"}), "op_id": f"sd-{made_d}", "idempotency_key": f"sd-{made_d}", "mandate_version": 1, "requested_by": "AGENT", "facility_id": "FAC-LINE"})
                assert r.json()["result"]["status"] in (("EXECUTED", "REFUSED") if LOTS else ("REFUSED",)), r.text
            while made_a < applies:
                made_a += 1
                r = c.post("/operations", headers=AG, json={"kind": "APPLY_FOR_FACILITY", "op_id": f"sa-{made_a}", "idempotency_key": f"sa-{made_a}", "mandate_version": 1, "requested_by": "AGENT", "facility_id": "FAC-GGL", "amount_fen": 20_000_000})
                assert r.json()["result"]["status"] in ("PENDING_APPROVAL", "REFUSED"), r.text
            n_dec = c.get("/decisions?limit=200").json()["count"]
            n_ops = len(c.get("/ledger").json()["operations"])
            print("decisions", n_dec, "ops", n_ops, flush=True)
            results[f"stress{draws}"] = {"n_decisions": n_dec, "ops": n_ops, **measure(c, f"stress{draws}", repeat=1 if LOTS else 2)}
        print(json.dumps({k: {kk: (vv if not isinstance(vv, dict) else (vv['wall_s_min'], vv['reconcile'], vv['alerts'], vv['read_entries'], vv['json_loads'])) for kk, vv in v.items()} for k, v in results.items()}, indent=1))
        (out / "numbers.json").write_text(json.dumps(results, indent=1))
        set_runtime(None)
        return
    if SCALE:
        c = client
        c.post("/demo/reset", json={})
        made = 0
        for target in (5, 20, 80):
            while made < target:
                made += 1
                text = f"Deduct 0.6% and we'll settle the open invoice early. Ref {made}."
                r = c.post("/offers", json={"documents": [{"doc_id": f"s{made}", "channel": "chat", "sender_id": "BUYER-1", "received_day": 0, "text": text}], "counterparty_id": "BUYER-1"})
                oid = r.json()["offer"]["offer_id"]
                c.post(f"/offers/{oid}/evaluate", json={})
                if made % 2 == 0:
                    n = c.post(f"/negotiate/{oid}", json={"buyer_profile": "cooperative"})
                if made % 5 == 0:
                    c.post("/clock/advance", json={"to_day": made // 5})
            n_dec = c.get("/decisions?limit=200").json()["count"]
            print("decisions", n_dec, "ops", len(c.get("/ledger").json()["operations"]))
            results[f"scale{target}"] = {"n_decisions": n_dec, **measure(c, f"scale{target}", repeat=2)}
        print(json.dumps(results, indent=1))
        (out / "numbers.json").write_text(json.dumps(results, indent=1))
        set_runtime(None)
        return
    if books == "golden":
        c = client
        c.post("/demo/reset", json={})
        offer = c.post("/offers", json={"fixture_id": "EX01_PACKAGE"}).json()["offer"]
        c.post(f"/offers/{offer['offer_id']}/evaluate", json={"fixture_id": "EX01_PACKAGE"})
        c.post(f"/negotiate/{offer['offer_id']}", json={"buyer_profile": "cooperative"})
        c.post("/clock/advance", json={"to_day": 2})
        half = "--half" in sys.argv
        if half:
            promise = c.get("/reconciliation").json()["reconciliation"]["promised"][0]
            version = c.get("/mandate").json()["mandate"]["version"]
            r = c.post("/operations", headers={"X-Agent-Key": "demo-agent-key", "X-Bank-Feed-Key": "demo-bank-feed-key"}, json={
                "kind": "RECEIVE_PAYMENT", "op_id": "rc-half", "idempotency_key": "rc-half", "mandate_version": version,
                "requested_by": "SYSTEM", "receivable_id": promise["receivable_id"], "amount_fen": promise["expected_fen"] // 2,
                "bank_reference": "BANK-1"})
            assert r.json()["result"]["status"] == "EXECUTED"
        c.post("/clock/advance", json={"to_day": 30})
        c.post("/clock/advance", json={"to_day": 34})
        results["day34"] = measure(c, "day34")
        action = c.get("/home").json()["next_action"]
        r = c.post(f"/alerts/{action['alert_id']}/act", json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
        assert r.status_code == 200, r.text
        results["day34_cured"] = measure(c, "day34cured")
    else:
        for week in range(1, 9):
            rt.advance_to(rt.day + 7)
        results["weeks8"] = measure(client, "weeks8")
        ver = rt.store.get_mandate().version
        for i, buyer in enumerate(("BUYER-A", "BUYER-B", "BUYER-C", "BUYER-A"), start=1):
            text = f"Deduct 0.6% and we'll settle the open invoice early. Ref {i}."
            r = client.post("/offers", headers=HDR, json={"documents": [{"doc_id": f"p{i}", "channel": "chat", "sender_id": buyer, "received_day": rt.day, "text": text}], "counterparty_id": buyer})
            print("offer", r.status_code, r.text[:120], flush=True)
            if r.status_code == 200:
                oid = r.json()["offer"]["offer_id"]
                v = client.post(f"/offers/{oid}/evaluate", headers=HDR, json={})
                print("eval", v.status_code, v.text[:100], flush=True)
                if i % 2 == 0:
                    n = client.post(f"/negotiate/{oid}", headers=HDR, json={"buyer_profile": "cooperative"})
                    print("neg", n.status_code, n.text[:100], flush=True)
        for i in (1, 2):
            r = client.post("/operations", headers={"X-Agent-Key": "tok-agent", "X-Owner-Token": ""}, json={"kind": "APPLY_FOR_FACILITY", "op_id": f"pa-{i}", "idempotency_key": f"pa-{i}", "mandate_version": ver, "requested_by": "AGENT", "facility_id": "FAC-GGL", "amount_fen": 20_000_000})
            print("apply", r.status_code, r.text[:150], flush=True)
        results["weeks8_offers"] = measure(client, "weeks8offers")
        try:
            action = client.get("/home", headers=HDR).json().get("next_action")
            print("next_action", bool(action))
            if action:
                r = client.post(f"/alerts/{action['alert_id']}/act", headers=HDR, json={"state_version": action["state_version"], "suggestions": action["suggestions"]})
                print("act:", r.status_code, r.text[:200])
                results["weeks8_cured"] = measure(client, "weeks8cured")
        except Exception as e:  # noqa
            print("no cure:", e)
    print(json.dumps(results, indent=1))
    (out / "numbers.json").write_text(json.dumps(results, indent=1))
    set_runtime(None)


main()
