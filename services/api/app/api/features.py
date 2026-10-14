"""Feature gates for routes. `require_feature("envelope")` raises 403 FEATURE_DISABLED with one sentence when the flag is
off, the same shape as the alerts gate (map #47: the strategy MVP is off by default)."""

from __future__ import annotations

from fastapi import HTTPException

from app.config import get_settings

_MESSAGES = {
    "envelope": "The Safe Deal Envelope is switched off (FEATURE_ENVELOPE).",
    "price_curve": "The cash price curve is switched off (FEATURE_PRICE_CURVE).",
    "collections_worth": "Collections worth is switched off (FEATURE_COLLECTIONS_WORTH).",
    "exposure": "Buyer exposure is switched off (FEATURE_EXPOSURE).",
    "customer_economics": "Customer economics is switched off (FEATURE_CUSTOMER_ECONOMICS).",
    "pilot_journal": "The pilot journal is switched off (FEATURE_PILOT_JOURNAL).",
    "capex_contracts": "The buy side (capex contracts, health, eligibility, plans) is switched off (FEATURE_CAPEX_CONTRACTS).",
}


def require_feature(name: str) -> None:
    if not getattr(get_settings().features, name):
        message = _MESSAGES.get(name, f"This feature is switched off ({name}).")
        raise HTTPException(403, detail={"code": "FEATURE_DISABLED", "feature": name, "message": message})
