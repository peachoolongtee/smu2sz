"""Provenance is preserved on both supported local stores, including SQLite reload."""
from app.compiler import Compiler
from app.compiler.cross_check import check_against_rules
from app.domain.fixtures import offer_documents


def test_field_provenance_round_trips_without_gaining_authority(store):
    model = Compiler().compile_offer(offer_documents("EX01_PACKAGE"), "BUYER-1")
    rules = model.model_copy(update={"obligations": []})
    checked = check_against_rules(model, rules)
    store.put_offer(checked)
    restored = store.get_offer(checked.offer_id)
    assert restored == checked
    assert not restored.autonomy_eligible
    assert all(set(o.field_provenance.values()) == {"model"} for o in restored.obligations)
