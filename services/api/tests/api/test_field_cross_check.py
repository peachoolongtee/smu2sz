"""Reader provenance survives intake; single-reader proposals cannot authorize acceptance."""
from __future__ import annotations

import pytest

from app.compiler import Compiler
from app.compiler.cross_check import check_against_rules
from app.compiler.rules import RulesBackend
from app.domain.models import SourceDocument


def test_review_only_proposal_retains_provenance_through_owner_api(client, monkeypatch: pytest.MonkeyPatch) -> None:
    doc = SourceDocument(doc_id="field-review", channel="chat", sender_id="BUYER-1", received_day=0,
                         text="Hi, we can pay invoice RCV-A (¥420,000) early if you give us 0.5% off. Thanks!")
    model = Compiler([RulesBackend()]).compile_offer([doc], "BUYER-1")
    assert model.autonomy_eligible
    rules = model.model_copy(update={"obligations": [o.model_copy(update={"rate_bp": None}) for o in model.obligations]})
    reconciled = check_against_rules(model, rules)
    monkeypatch.setattr("app.api.offers.compile_offer", lambda *_args: reconciled)
    response = client.post("/offers", json={"counterparty_id": "BUYER-1", "documents": [doc.model_dump(mode="json")]})
    assert response.status_code == 200
    offer = response.json()["offer"]
    assert offer["obligations"][0]["field_provenance"]["rate_bp"] == "model"
    assert not offer["autonomy_eligible"]
    fetched = client.get(f"/offers/{offer['offer_id']}")
    assert fetched.status_code == 200
    assert fetched.json()["offer"]["obligations"][0]["field_provenance"] == offer["obligations"][0]["field_provenance"]
    result = client.post(f"/offers/{offer['offer_id']}/evaluate", json={})
    assert result.status_code == 200
    assert result.json()["outcome"] == "NEEDS_OWNER_APPROVAL"
    assert result.json()["required_tier"] == "TIER_2"
