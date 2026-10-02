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
    # The existing loan's ¥45,000 day-30 payment is cash (FINANCIAL_SEMANTICS §5), so the gap before day 32 is
    # 340,000 + 120,000 + 45,000 + 300,000 − 400,000 = 405,000: line 150,000 + a 255,000 second leg.
    assert g["debt_service_day30"] == 4_500_000 and g["debt_payments_to_day120"] == [30, 60, 90, 120]
    assert g["funding_need_before_day_32"] == 40_500_000 and g["plan_advance"] == 25_500_000
    # 255,000 × 7.8% × 30/365 = 1,634.7945 -> 1,634.79; fee 255,000 × 0.25% = 637.50; total 2,272.29
    assert g["if_cost_plan_advance"] == 227229
    # v1: face 255,000 / (1 − 1.2%) = 258,097.1659 -> 258,097.17; discount 3,097.17; + line 841.64 = 3,938.81
    assert g["v1_partial_face"] == 25809717 and g["v1_optimum_total"] == 393881
    assert g["extension_extra_receivables"] == 21_000_000  # F x 15 / 30: the steady state (F-FIN-07)
    assert g["extension_committed_12m"] == 2432692  # 13 invoices in the window
    assert g["extension_notional_line_12m"] == 1436055
    assert g["extension_expected_12m"] == 1197332
    assert g["forward_ledger_total"] == 2832692
    assert g["break_even_discount_display"] == "0.88%"
    assert g["capex"]["npv"] == 38088577 and g["capex"]["payback_month"] == 31


def test_oracle_documented_differences_from_spec():
    # ADR-0002: totals are sums of posted fen amounts; the spec rounded unrounded sums.
    g = golden_values()
    # spec: ¥2,712.95 for line + ¥210,000 advance; the day-30 debt payment makes the advance ¥255,000:
    # 841.64 + 2,272.29 = 3,113.93
    assert g["v2_optimum_total"] == 311393
    # Counter A: face = 255,000 / (1 − 0.85%) = 257,186.08, rounded up to a whole 100 = 257,200; discount
    # 257,200 × 0.85% = 2,186.20; the line carries 405,000 − (257,200 − 2,186.20) = 149,986.20 for 32 days at 6.4%:
    # 149,986.20 × 6.4% × 32/365 = 841.5664 -> 841.57; total 2,186.20 + 841.57 = 3,027.77
    # (spec: ¥2,641.95 with the old face ¥211,800 and no debt payment in the gap)
    assert g["counter_a_face"] == 25_720_000 and g["counter_a_discount"] == 218620
    assert g["counter_a_total"] == 302777
    assert g["capex"]["loan_36m"]["total_interest"] == 5320614  # spec: ¥53,206.17
