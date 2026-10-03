"""What-if parameters: the owner's sliders, validated strictly (ranges and step sizes).

Money is integer fen and rates are integer bp (INVARIANT 9). A value off the slider grid is rejected
rather than rounded, so a cached result always corresponds to exactly the numbers the owner chose.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

TERMS_MIN, TERMS_MAX, TERMS_STEP = 30, 90, 5
DISCOUNT_MAX_BP, RATE_STEP_BP = 200, 5
REBATE_MAX_BP = 200
PRICE_MAX_BP = 100
FACE_STEP_FEN = 10_000  # whole ¥100, the same grid the counters use


class WhatIfParamError(ValueError):
    """Parameters that are well-formed but do not fit the current state (e.g. a face above the invoice)."""


class WhatIfParams(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    terms_days: int = Field(ge=TERMS_MIN, le=TERMS_MAX, description="target payment terms, days")
    discount_bp: int = Field(ge=0, le=DISCOUNT_MAX_BP, description="early-settlement discount, bp")
    rebate_bp: int = Field(ge=0, le=REBATE_MAX_BP, description="next-quarter rebate, bp")
    price_adjustment_bp: int = Field(default=0, ge=0, le=PRICE_MAX_BP,
                                     description="price increase on future invoices (Option B's lever), bp")
    settle_face_fen: int | None = Field(default=None, gt=0,
                                        description="face settled early; None = the whole invoice")

    @field_validator("terms_days")
    @classmethod
    def _terms_step(cls, v: int) -> int:
        if v % TERMS_STEP:
            raise ValueError(f"terms_days must be a multiple of {TERMS_STEP}")
        return v

    @field_validator("discount_bp", "rebate_bp", "price_adjustment_bp")
    @classmethod
    def _rate_step(cls, v: int) -> int:
        if v % RATE_STEP_BP:
            raise ValueError(f"rates move in {RATE_STEP_BP} bp steps")
        return v

    @field_validator("settle_face_fen")
    @classmethod
    def _face_step(cls, v: int | None) -> int | None:
        if v is not None and v % FACE_STEP_FEN:
            raise ValueError("settle_face_fen must be a whole multiple of ¥100 (10000 fen)")
        return v


def grid(face_max_fen: int) -> dict[str, dict[str, int]]:
    """Slider bounds and steps, served to the UI so it never hard-codes them."""
    return {
        "terms_days": {"min": TERMS_MIN, "max": TERMS_MAX, "step": TERMS_STEP},
        "discount_bp": {"min": 0, "max": DISCOUNT_MAX_BP, "step": RATE_STEP_BP},
        "rebate_bp": {"min": 0, "max": REBATE_MAX_BP, "step": RATE_STEP_BP},
        "price_adjustment_bp": {"min": 0, "max": PRICE_MAX_BP, "step": RATE_STEP_BP},
        "settle_face_fen": {"min": FACE_STEP_FEN, "max": face_max_fen - face_max_fen % FACE_STEP_FEN,
                            "step": FACE_STEP_FEN},
    }


# The buyer's actual offer (EX01) and the two counters the verifier generated for it (DEMO_FLOW §1.6). Since existing
# debt service leaves cash, the verifier offers only Option A: `option_b` (60-day terms + 0.45%) fails its own re-check
# (day 47 ¥85,000 below the reserve) and stays here as a what-if package, not as a counter.
PRESETS: dict[str, WhatIfParams] = {
    "actual": WhatIfParams(terms_days=60, discount_bp=120, rebate_bp=100),
    # Option A's face nets the gap less the line, which includes the existing loan's day-30 payment (¥257,200)
    "option_a": WhatIfParams(terms_days=45, discount_bp=85, rebate_bp=0, settle_face_fen=25_720_000),
    "option_b": WhatIfParams(terms_days=60, discount_bp=0, rebate_bp=0, price_adjustment_bp=45),
    "status_quo": WhatIfParams(terms_days=45, discount_bp=0, rebate_bp=0),
}
