# The judges' demo API: the certified local configuration of `pnpm demo` (scope S), in a container behind the demo's proxy.
# In-memory books, recorded model answers (no provider is called), the published demo credentials (reachable only through the
# proxy's password gate), one process. Build context: the repository root.
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.10 /uv /usr/local/bin/uv
WORKDIR /app/services/api
COPY services/api/pyproject.toml services/api/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . /app
RUN uv sync --frozen --no-dev
# Exactly the environment scripts/demo.mjs gives the API (scripts/dev-api.sh), plus the proxy's forwarded address for the
# per-client rate limits (only the proxy can reach this port: it is not published).
ENV TERMSLEDGER_NO_DOTENV=1 DATABASE_URL=memory DEMO_MODE=1 LLM_MODE=cache PYTHONUTF8=1 SKIP_PERF_BENCH=1 \
    FEATURE_ENVELOPE=1 FEATURE_PRICE_CURVE=1 FEATURE_COLLECTIONS_WORTH=1 FEATURE_EXPOSURE=1 FEATURE_CAPEX_CONTRACTS=1 \
    FEATURE_CONTRACT_TERMS=1 FEATURE_ASK_ROUTER=1 DEMO_WARM_STRATEGY=1
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
