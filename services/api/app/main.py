"""FastAPI entrypoint. Routers are mounted by the main architect in app/api/."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.accept import router as accept_router
from app.api.activity import router as activity_router
from app.api.alerts import router as alerts_router
from app.api.borrower_file import router as borrower_file_router
from app.api.capex import router as capex_router
from app.api.clock import router as clock_router
from app.api.collections import router as collections_router
from app.api.customer_overview import router as customer_overview_router
from app.api.deals import router as deals_router
from app.api.decide import router as decide_router
from app.api.decisions import router as decisions_router
from app.api.demo_bank import router as demo_bank_router
from app.api.demo_story import router as demo_story_router
from app.api.documents import router as documents_router
from app.api.errors import install_error_handlers
from app.api.home import router as home_router
from app.api.nav import router as nav_router
from app.api.nl import router as nl_router
from app.api.offer_picture import router as offer_picture_router
from app.api.offers import router as offers_router
from app.api.operations import router as operations_router
from app.api.pilot import router as pilot_router
from app.api.read import router as read_router
from app.api.receivables import router as receivables_router
from app.api.strategy import router as strategy_router
from app.api.whatif import router as whatif_router
from app.api.worklist import router as worklist_router
from app.config import get_settings, load_dotenv

load_dotenv()

app = FastAPI(title="TermsLedger API", version="0.1.0")
install_error_handlers(app)  # a conflict that survives the retries is a 409 with a retry hint, never a 500
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(read_router)
app.include_router(activity_router)
app.include_router(demo_story_router)
app.include_router(offers_router)
app.include_router(operations_router)
app.include_router(decide_router)
app.include_router(decisions_router)
app.include_router(capex_router)
app.include_router(whatif_router)
app.include_router(borrower_file_router)
app.include_router(alerts_router)
app.include_router(nl_router)
app.include_router(clock_router)
app.include_router(demo_bank_router)
app.include_router(home_router)
app.include_router(strategy_router)
app.include_router(pilot_router)
app.include_router(collections_router)
app.include_router(receivables_router)
app.include_router(customer_overview_router)
app.include_router(documents_router)
app.include_router(deals_router)
app.include_router(nav_router)
app.include_router(offer_picture_router)
app.include_router(accept_router)
app.include_router(worklist_router)


@app.get("/health")
def health() -> dict[str, object]:
    s = get_settings()
    # home_v2 stays on /health as a constant for one release: a web build that still asks (the old Home gate) reads true. Remove it next release.
    return {"ok": True, "llm_mode": s.llm_mode, "features": {**s.features.__dict__, "home_v2": True}}
