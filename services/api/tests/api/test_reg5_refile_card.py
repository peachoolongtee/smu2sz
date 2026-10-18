"""REG-5 (card half): a refile-closed record is not "the contract you confirmed".

Confirming a contract replaces the buyer's earlier confirmed one, and a record the owner filed again under this buyer is also
superseded by it. The outcome card took the first record superseded by the new one, so it could name the refile-closed record
(never confirmed) as the contract the new one replaces."""

from __future__ import annotations

from tests.api.test_new_customer import reader  # noqa: F401

FOSHAN = "Foshan Home Retail Co."
LINGNAN = "Lingnan Homeware Manufacturing Co., Ltd."


def _text(extra: str) -> str:
    return (f"SUPPLY AGREEMENT\n\nThis Agreement is made between:\n\n(1) {LINGNAN} (the \"Supplier\"); and\n\n"
            f"(2) {FOSHAN} (the \"Buyer\").\n\n4. PAYMENT\n\n4.1 The Buyer pays each invoice within forty-five (45) days "
            f"after the Invoice Date.\n{extra}")


def _up(client, cp: str, extra: str) -> dict:
    r = client.post("/documents", json={"kind": "BUYER_CONTRACT", "counterparty_id": cp, "text": _text(extra)})
    assert r.status_code == 200, r.text
    return r.json()["document"]


def test_the_card_does_not_call_a_refile_closed_record_the_contract_you_confirmed(client, reader):  # noqa: F811
    wrong = _up(client, "BUYER-2", "A.")  # filed under the wrong buyer first, so it has the lowest id
    earlier = _up(client, "BUYER-1", "B.")  # an earlier contract of the right buyer
    assert client.post(f"/documents/{earlier['id']}/confirm", json={"doc_hash": earlier["doc_hash"]}).status_code == 200
    r = client.post(f"/documents/{wrong['id']}/refile", json={"counterparty_id": "BUYER-1", "doc_hash": wrong["doc_hash"]})
    assert r.status_code == 200, r.text
    new = r.json()["document"]
    done = client.post(f"/documents/{new['id']}/confirm?lang=en", json={"doc_hash": new["doc_hash"]})
    assert done.status_code == 200, done.text
    lines = done.json()["outcome"]["changed"]["lines"]
    assert any("It replaces the contract you confirmed" in x for x in lines), lines
    view = client.get(f"/documents/{new['id']}?lang=en").json()["document"]
    assert view["replaces"] == earlier["id"] and view["replaces_text"].startswith("Replaces the contract you confirmed")


def test_the_card_for_a_contract_that_only_replaced_a_refile_says_nothing_about_a_confirmed_one(client, reader):  # noqa: F811
    wrong = _up(client, "BUYER-2", "C.")
    new = client.post(f"/documents/{wrong['id']}/refile",
                      json={"counterparty_id": "BUYER-1", "doc_hash": wrong["doc_hash"]}).json()["document"]
    done = client.post(f"/documents/{new['id']}/confirm?lang=en", json={"doc_hash": new["doc_hash"]}).json()
    assert not any("you confirmed" in x for x in done["outcome"]["changed"]["lines"]), done["outcome"]
    assert done["document"]["replaces_text"].startswith("You filed this document here instead")
