from app.domain.fixtures import golden_values, load_offers, load_scenario, offer_documents


def test_golden_scenario_loads_strict():
    state, mandate = load_scenario()
    assert state.cash_fen == 40_000_000
    assert mandate.min_cash_fen == 30_000_000
    assert {f.id for f in state.facilities} >= {"FAC-LINE", "FAC-IF", "FAC-GGL"}


def test_every_offer_document_validates():
    for oid in load_offers():
        assert offer_documents(oid)


def test_oracle_matches_spec_where_spec_is_ledger_consistent():
    g = golden_values()
    assert g["line_interest_150k_32d"] == 84164
    assert g["if_cost_210k_30d"] == 187130
    assert g["v1_optimum_total"] == 339225
    assert g["extension_extra_receivables"] == 20712329
    assert g["extension_committed_12m"] == 2245562
    assert g["extension_notional_line_12m"] == 1325589
    assert g["extension_expected_12m"] == 1105230
    assert g["forward_ledger_total"] == 2645562
    assert g["break_even_discount_display"] == "0.88%"
    assert g["capex"]["npv"] == 38088577 and g["capex"]["payback_month"] == 31


def test_oracle_documented_differences_from_spec():
    # ADR-0002: totals are sums of posted fen amounts; the spec rounded unrounded sums.
    g = golden_values()
    assert g["v2_optimum_total"] == 271294  # spec: ¥2,712.95
    assert g["counter_a_total"] == 264194  # spec: ¥2,641.95
    assert g["capex"]["loan_36m"]["total_interest"] == 5320614  # spec: ¥53,206.17
