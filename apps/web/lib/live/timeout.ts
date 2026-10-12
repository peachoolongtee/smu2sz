/**
 * Request timeouts for the live transport (wayfinder #65 Wave 7, F23). A request that hangs must not hold the page for ever: it is aborted
 * after a time that suits the route, and the caller says "taking longer than usual" instead of waiting without end. What a timeout means
 * depends on the route: a read can simply be read again; a WRITE may already have landed, so its Retry reads the state first and never
 * sends it blindly; a model REPLY (`/nl`) is replayed under the same request id, which the server answers once.
 * No imports: scripts/timeout.test.mjs loads this file directly under Node's type stripping.
 */

/** Ordinary reads and writes. */
export const DEFAULT_TIMEOUT_MS = 20_000;
/** The model turn, the evaluation and the strategy reads, which can take a model call or a long projection. */
export const LONG_TIMEOUT_MS = 60_000;

export type RequestKind = "read" | "write" | "reply";

/** `NEXT_PUBLIC_REQUEST_TIMEOUT_MS` shortens every timeout to that many ms (the e2e build uses it to exercise the slow path; unset in production). */
export function timeoutFor(path: string, override?: number): number {
  if (override && override > 0) return override;
  const p = path.split("?")[0];
  if (p === "/nl" || p === "/nl/opener" || /^\/offers\/[^/]+\/evaluate$/.test(p) || p === "/cash/price-curve" || p === "/receivables/worth" || /^\/buyers\/[^/]+\/envelope$/.test(p) || /^\/decisions\/[^/]+\/exposure$/.test(p)) {
    return LONG_TIMEOUT_MS;
  }
  return DEFAULT_TIMEOUT_MS;
}

/** What a timed-out request was: a model reply, a write that may have landed, or a read. */
export function kindOf(method: string, path: string): RequestKind {
  const p = path.split("?")[0];
  if (p === "/nl" || p === "/nl/opener") return "reply";
  if (method !== "POST") return "read";
  if (/^\/(alerts\/[^/]+\/act|approvals\/[^/]+|negotiate\/[^/]+|offers|capex\/apply|clock\/advance|demo\/reset|circuit\/[^/]+\/reset)$/.test(p)) return "write";
  return "read";
}

/**
 * Runs `request` with an abort signal that fires after `ms`. When it fires and the request then fails (aborted or otherwise), the failure is
 * replaced by `onTimeout()`; a request that finishes first is returned as it is.
 */
export async function runWithTimeout<T>(request: (signal: AbortSignal) => Promise<T>, ms: number, onTimeout: () => Error): Promise<T> {
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, ms);
  try {
    return await request(controller.signal);
  } catch (e) {
    if (timedOut) throw onTimeout();
    throw e;
  } finally {
    clearTimeout(timer);
  }
}
