/**
 * The context the connected pages (Deals, Receivables, Customer, Cash) share, and where it lives: in the address and nowhere else.
 * `customer` (a buyer id), `decision` (a deal decision), `path` (the deal path on screen) and `invoice` (a receivable id). A link from one of
 * these pages to another carries what is set, so coming back restores the selection. No store; nothing here is money or a date.
 */

export const CONTEXT_KEYS = ["customer", "decision", "path", "invoice"] as const;
export type ContextKey = (typeof CONTEXT_KEYS)[number];

type Params = { get(name: string): string | null };

/** `path` with the context that is set in `params`, the `overrides` applied on top (null removes a key). */
export function withContext(path: string, params: Params, overrides: Partial<Record<ContextKey, string | null>> = {}, extra: Record<string, string> = {}): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(extra)) q.set(k, v);
  for (const key of CONTEXT_KEYS) {
    const value = key in overrides ? overrides[key] : params.get(key);
    if (value) q.set(key, value);
  }
  const s = q.toString();
  return s ? `${path}?${s}` : path;
}
