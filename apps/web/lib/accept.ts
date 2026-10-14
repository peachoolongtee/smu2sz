import { ApiError } from "./errors";
import type { AcceptRefusedDetail } from "./types";

/** The server's refusal of an accept or a decline (a 409 that moved nothing): its sentence in the owner's language (`message_when`, else `message`) and which refusal it was; null for any other error. */
export function acceptRefusal(e: unknown): { code: string; text: string } | null {
  if (!(e instanceof ApiError) || e.status !== 409) return null;
  const d = (e.detail ?? {}) as Partial<AcceptRefusedDetail>;
  if (!d.code) return null;
  const text = d.message_when || d.message || e.message;
  return text ? { code: d.code, text } : null;
}
