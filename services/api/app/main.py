"""FastAPI entrypoint. Routers are mounted by the main architect in app/api/."""

from __future__ import annotations

import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.accept import router as accept_router
from app.api.activity import router as activity_router
from app.api.alerts import router as alerts_router
from app.api.auth import demo_mode
from app.api.borrower_file import router as borrower_file_router
from app.api.buyside import router as buyside_router
from app.api.capex import router as capex_router
from app.api.clock import router as clock_router
from app.api.collections import router as collections_router
from app.api.contract_terms import router as contract_terms_router
from app.api.customer_overview import router as customer_overview_router
from app.api.customers import router as customers_router
from app.api.deal_tracker import router as deal_tracker_router
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
from app.api.outbound import router as outbound_router
from app.api.pilot import router as pilot_router
from app.api.ratelimit import middleware as rate_limit
from app.api.read import router as read_router
from app.api.receivables import router as receivables_router
from app.api.setup import router as setup_router
from app.api.strategy import router as strategy_router
from app.api.whatif import router as whatif_router
from app.api.worklist import router as worklist_router
from app.config import get_settings, load_dotenv

load_dotenv()
_log = structlog.get_logger("termsledger.api")

# SEC-13: the interactive docs and the schema map every route; they are served for the demo only
_docs = demo_mode()
app = FastAPI(title="TermsLedger API", version="0.1.0", docs_url="/docs" if _docs else None, redoc_url="/redoc" if _docs else None,
              openapi_url="/openapi.json" if _docs else None)
install_error_handlers(app)  # a conflict that survives the retries is a 409 with a retry hint, never a 500

# SEC-12: every response (the API also serves the borrower file as HTML) is never sniffed, never framed and sends no referrer
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'",
                    "Referrer-Policy": "no-referrer"}


INTERNAL_ERROR = {"detail": {"code": "INTERNAL_ERROR", "message": "The service hit an error and could not answer. Try again; if it keeps "
                                                                 "happening, the service log has the details."}}


@app.middleware("http")
async def internal_error(request, call_next):  # type: ignore[no-untyped-def]
    """An unhandled exception is a JSON 500 that still carries the CORS headers. Without this, Starlette's ServerErrorMiddleware (outside
    CORS) answered a plain-text 500 with no Access-Control-Allow-Origin, so the browser reported a crash as a network failure and the web
    said the API could not be reached; uvicorn also closed the keep-alive connection, failing the next request on it. Registered first,
    so it runs inside every other middleware: the security headers, the rate limiter and CORS still apply. The answer names no exception
    text (no internals to the caller); the traceback goes to the log."""
    try:
        return await call_next(request)
    except Exception:  # noqa: BLE001  the catch-all: any unhandled exception becomes the JSON 500 below
        _log.exception("api.unhandled_exception", method=request.method, path=request.url.path)
        return JSONResponse(status_code=500, content=INTERNAL_ERROR)


app.middleware("http")(rate_limit)  # SEC-20: per-caller request rate limits (app/api/ratelimit.py); added before CORS, so it runs inside it


@app.middleware("http")
async def security_headers(request, call_next):  # type: ignore[no-untyped-def]
    response = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response

  # a conflict that survives the retries is a 409 with a retry hint, never a 500
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
app.include_router(deal_tracker_router)
app.include_router(capex_router)
app.include_router(buyside_router)  # ADR-0013, the buy side's company-wide reads
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
app.include_router(customers_router)
app.include_router(contract_terms_router)  # ADR-0014, behind FEATURE_CONTRACT_TERMS (default off)
app.include_router(deals_router)
app.include_router(nav_router)
app.include_router(offer_picture_router)
app.include_router(accept_router)
app.include_router(outbound_router)
app.include_router(worklist_router)
app.include_router(setup_router)


@app.get("/health")
def health() -> dict[str, object]:
    s = get_settings()
    # home_v2 stays on /health as a constant for one release: a web build that still asks (the old Home gate) reads true. Remove it next release.
    return {"ok": True, "llm_mode": s.llm_mode, "features": {**s.features.__dict__, "home_v2": True}}
