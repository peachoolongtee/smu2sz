import type { ApiMode } from "./types";

/** NEXT_PUBLIC_API_MODE=mock|live (default mock). */
export const API_MODE: ApiMode = process.env.NEXT_PUBLIC_API_MODE === "live" ? "live" : "mock";

/** FastAPI base URL used in live mode. */
export const API_URL: string = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");

/** Simulated network latency in mock mode, so loading states are real. */
export const MOCK_LATENCY_MS: number = Number(process.env.NEXT_PUBLIC_MOCK_LATENCY_MS ?? 160);

/**
 * DEMO-ONLY owner credential, sent as X-Owner-Token on every live request (the API gates all owner-console
 * routes on it; only POST /offers intake and POST /nl are open). It is public by construction
 * (NEXT_PUBLIC_*): a real deployment sets OWNER_TOKEN on the API and authenticates the owner properly.
 * Never put a real secret here.
 */
export const OWNER_TOKEN: string = process.env.NEXT_PUBLIC_OWNER_TOKEN ?? "demo-owner-token";
