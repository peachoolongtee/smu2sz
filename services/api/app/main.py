"""FastAPI entrypoint. Routers are mounted by the main architect in app/api/."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.read import router as read_router
from app.config import get_settings

app = FastAPI(title="TermsLedger API", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(read_router)


@app.get("/health")
def health() -> dict[str, object]:
    s = get_settings()
    return {"ok": True, "llm_mode": s.llm_mode, "features": s.features.__dict__}
