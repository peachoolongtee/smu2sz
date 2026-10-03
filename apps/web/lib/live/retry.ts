/**
 * Retry of a write that lost a race. The API answers 409 with detail.code CONCURRENT_WRITE_CONFLICT and a
 * Retry-After hint when another writer committed first: nothing of the request was kept, so sending it again is safe.
 * The live transport retries such a write ONCE after the hint; a second conflict is shown as an error (no loop).
 * No imports: scripts/retry.test.mjs loads this file directly under Node's type stripping.
 */

export const CONFLICT_CODE = "CONCURRENT_WRITE_CONFLICT";
export const BOOKS_BUSY = "The books were busy: another change was being saved at the same moment, so nothing was saved. Try again.";

const DEFAULT_WAIT_MS = 1000;
const MAX_WAIT_MS = 5000;

/** True when an error body's `detail` is the API's concurrent-write conflict. */
export function isWriteConflictDetail(detail: unknown): boolean {
  return Boolean(detail) && typeof detail === "object" && (detail as { code?: unknown }).code === CONFLICT_CODE;
}

/** How long to wait: the hint in the body (`retry_after_seconds`), else the Retry-After header, else one second; never more than five. */
export function retryWaitMs(detail: unknown, header: string | null): number {
  const hints: unknown[] = [detail && typeof detail === "object" ? (detail as { retry_after_seconds?: unknown }).retry_after_seconds : undefined, header];
  for (const h of hints) {
    if (h === undefined || h === null || h === "") continue;
    const seconds = Number(h);
    if (Number.isFinite(seconds) && seconds >= 0) return Math.min(seconds * 1000, MAX_WAIT_MS);
  }
  return DEFAULT_WAIT_MS;
}

async function conflictOf(res: Response): Promise<{ wait: number } | null> {
  if (res.status !== 409) return null;
  let detail: unknown;
  try {
    detail = ((await res.clone().json()) as { detail?: unknown }).detail;
  } catch {
    return null;
  }
  return isWriteConflictDetail(detail) ? { wait: retryWaitMs(detail, res.headers.get("Retry-After")) } : null;
}

/**
 * Sends a write; if the answer is a concurrent-write conflict, waits for the hint and sends it exactly once more.
 * Whatever the second answer is (including another conflict) is returned as it is.
 */
export async function sendWriteWithRetry(
  send: () => Promise<Response>,
  sleep: (ms: number) => Promise<void> = (ms) => new Promise((r) => setTimeout(r, ms)),
): Promise<Response> {
  const first = await send();
  const conflict = await conflictOf(first);
  if (!conflict) return first;
  await sleep(conflict.wait);
  return send();
}
