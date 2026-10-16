/**
 * A failed API call. `message` is the English line (what a developer or a log reads); `code` names the failure the client itself
 * recognised (no sign-in, a rejected token, an unreachable API, busy books, a missing offer), so the screen can say it in the owner's
 * language through `errorText` (lib/error-text.ts) instead of showing the English line. A failure the server explained carries the
 * server's own words and no code.
 */
export type ErrorCode = "owner_required" | "owner_rejected" | "not_configured" | "books_busy" | "unreachable" | "download_failed" | "mock_download" | "mock_setup" | "offer_missing" | "approval_missing" | "approval_done" | "executor_refused" | "timeout" | "timeout_write" | "timeout_reply";

export class ApiError extends Error {
  readonly status: number;
  /** The API's structured `detail` (for example the ALERT_CHANGED object), when it sent one. */
  readonly detail?: unknown;
  readonly code?: ErrorCode;
  /** The values the translated sentence names (`err.<code>` in the dictionary). */
  readonly vars?: Record<string, string | number>;
  constructor(status: number, message: string, detail?: unknown, code?: ErrorCode, vars?: Record<string, string | number>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.code = code;
    this.vars = vars;
  }
}

/** A request that ran out of time (a read, a write that may have landed, or a model reply). */
export function isTimeout(e: unknown): e is ApiError {
  return e instanceof ApiError && (e.code === "timeout" || e.code === "timeout_write" || e.code === "timeout_reply");
}
