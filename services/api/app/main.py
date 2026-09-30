"""FastAPI entrypoint. Routers are mounted by the main architect in app/api/."""

from __future__ import annotations

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(title="TermsLedger API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, object]:
    s = get_settings()
    return {"ok": True, "llm_mode": s.llm_mode, "features": s.features.__dict__}
