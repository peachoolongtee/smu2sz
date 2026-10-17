import type { ApiMode } from "./types";

/** NEXT_PUBLIC_API_MODE=mock|live (default mock). */
export const API_MODE: ApiMode = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";

/** FastAPI base URL used in live mode. */
export const API_URL: string = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** Simulated network latency in mock mode, so loading states are real. */
export const MOCK_LATENCY_MS: number = Number(process.env.NEXT_PUBLIC_MOCK_LATENCY_MS ?? 160);

/**
 * Local demo builds only (NEXT_PUBLIC_DEMO=1): the owner sign-in dialog prefills the API's published demo
 * token and says so. A real deployment leaves this unset, so no token is in the bundle and the owner types
 * their own (kept in sessionStorage, see ./auth).
 */
export const DEMO_BUILD: boolean = process.env.NEXT_PUBLIC_DEMO === "1";
export const DEMO_OWNER_TOKEN: string = process.env.NEXT_PUBLIC_DEMO === "1" ? "demo-owner-token" : "";

/**
 * Build-time flag for the strategy MVP surfaces (the cash price sentence, the collections worth). Unset: none of the
 * new components is mounted and none of the new client functions is called, so the default build is unchanged. The API
 * routes behind it are separately flagged (FEATURE_PRICE_CURVE, FEATURE_COLLECTIONS_WORTH).
 */
export const STRATEGY_MVP: boolean = process.env.NEXT_PUBLIC_STRATEGY_MVP === "1";

/**
 * Build-time flag for the Safe Deal Envelope on a deal's Cash impact ("The most you can give" and "What you could answer
 * instead"): the strategy build AND NEXT_PUBLIC_STRATEGY_ENVELOPE=1. Its own flag because its first read of a set of books is
 * bound by the funding search it repeats (measured 17 Oct 2026, a fresh API: about 17 s on the golden books with the terms and
 * price table, 32 s without it and 81 s with it on the busy books), at or past the 20 s after which the web gives up. `pnpm demo`
 * leaves it off until that read is faster; the strategy e2e build (E2E_STRATEGY=1) and the pilot set it.
 */
export const STRATEGY_ENVELOPE: boolean = STRATEGY_MVP && process.env.NEXT_PUBLIC_STRATEGY_ENVELOPE === "1";

/**
 * Build-time flag for the shadow pilot's journal at the foot of Activity (map #58): the strategy build AND
 * NEXT_PUBLIC_PILOT_JOURNAL=1, in live mode only (the page checks API_MODE). Its own flag because the demo builds with the
 * strategy surfaces on while the API keeps FEATURE_PILOT_JOURNAL off: without it Activity would read a route that answers
 * 403 on every visit. The pilot (docs/pilot/RUNBOOK.md) sets both, with FEATURE_PILOT_JOURNAL=1 on the API.
 */
export const PILOT_JOURNAL: boolean = STRATEGY_MVP && process.env.NEXT_PUBLIC_PILOT_JOURNAL === "1";

/**
 * Demo builds only: the API's published buyer channel keys (X-Counterparty-Key). The server maps a key to the
 * buyer it belongs to; a buyer turn without one is only a proposal, which the API never books. A real
 * deployment leaves this empty: each buyer's own system holds its key.
 */
export const DEMO_BUYER_KEYS: Record<string, string> =
  process.env.NEXT_PUBLIC_DEMO === "1" ? { "BUYER-1": "demo-buyer-1-key", "BUYER-2": "demo-buyer-2-key" } : {};
