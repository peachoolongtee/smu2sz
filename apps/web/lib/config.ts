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
