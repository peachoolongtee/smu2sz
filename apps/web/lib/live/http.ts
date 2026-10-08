/** Transport for live mode: the only place that calls fetch(). */

import { API_URL } from "../config";
import { getOwnerToken, requestSignIn } from "../auth";
import { ApiError } from "../errors";
import { BOOKS_BUSY, isWriteConflictDetail, sendWriteWithRetry } from "./retry";

interface HttpOptions {
  body?: unknown;
  as?: "json" | "text";
  /** "none" sends no credential (a counterparty's /nl turn). Default: the signed-in owner token, if any. */
  auth?: "owner" | "none";
  /** A buyer channel key, sent as X-Counterparty-Key (demo builds only; use with auth "none"). */
  buyerKey?: string;
  /** Try this token instead of the stored one (the sign-in dialog checks a token before keeping it). */
  token?: string;
  /** Do not open the sign-in dialog on a 401 (the caller shows the failure itself). */
  silent?: boolean;
  /** The route answers 403 (not 401) when the owner credential is missing or wrong: open the sign-in dialog for that too. */
  ownerOn403?: boolean;
}

/**
 * The API gates every owner-console route on X-Owner-Token (only POST /offers intake and counterparty
 * POST /nl turns are open). The token is whatever the owner typed into the sign-in dialog (sessionStorage).
 */
function ownerHeaders(opts: Pick<HttpOptions, "auth" | "token"> = {}): Record<string, string> {
  if (opts.auth === "none") return {};
  const token = opts.token ?? getOwnerToken();
  return token ? { "X-Owner-Token": token } : {};
}

const UNAUTHORIZED = "Owner sign-in required (401). Sign in with the owner token to use this.";
const REJECTED = "The API rejected the owner token (401). Sign in again with the correct token.";
export const NOT_CONFIGURED = "Server credentials not configured (503). Set OWNER_TOKEN and AGENT_KEY on the API, or run it in demo mode.";
const unreachable = () => new ApiError(0, `Cannot reach the API at ${API_URL}. Is the service running?`, undefined, "unreachable", { url: API_URL });

function unauthorized(opts: Pick<HttpOptions, "auth" | "token" | "silent">): ApiError {
  const hadToken = Boolean(opts.token ?? getOwnerToken());
  if (!opts.silent && opts.auth !== "none") requestSignIn(hadToken ? "rejected" : "required");
  return new ApiError(401, hadToken ? REJECTED : UNAUTHORIZED, undefined, hadToken ? "owner_rejected" : "owner_required");
}

function detailMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d: unknown) => {
        if (!d || typeof d !== "object" || !("msg" in d)) return "";
        const { loc, msg } = d as { loc?: unknown[]; msg: string };
        return `${loc?.slice(1).join(".") ?? ""} ${msg}`.trim();
      })
      .filter(Boolean);
    return parts.length ? parts.join("; ") : fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail && typeof (detail as { message: unknown }).message === "string") {
    return (detail as { message: string }).message;
  }
  return detail === undefined ? fallback : JSON.stringify(detail);
}

export async function http<T>(method: "GET" | "POST", path: string, opts: HttpOptions = {}): Promise<T> {
  const headers: Record<string, string> = ownerHeaders(opts);
  if (opts.buyerKey) headers["X-Counterparty-Key"] = opts.buyerKey;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  const send = () =>
    fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  try {
    // A write that lost a race (409 CONCURRENT_WRITE_CONFLICT) is sent once more after the API's Retry-After hint.
    res = method === "POST" ? await sendWriteWithRetry(send) : await send();
  } catch {
    throw unreachable();
  }
  if (res.status === 401) throw unauthorized(opts);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    let detail: unknown;
    let busy = false;
    try {
      const data = (await res.json()) as { detail?: unknown };
      if (res.status === 403 && opts.ownerOn403 && !/FEATURE_DISABLED/.test(JSON.stringify(data.detail))) throw unauthorized(opts);
      if (res.status === 503 && /NOT_CONFIGURED/.test(JSON.stringify(data.detail))) throw new ApiError(503, NOT_CONFIGURED, undefined, "not_configured");
      busy = res.status === 409 && isWriteConflictDetail(data.detail);
      message = busy ? BOOKS_BUSY : detailMessage(data.detail, message);
      detail = data.detail;
    } catch (e) {
      if (e instanceof ApiError) throw e;
      /* keep the status line */
    }
    throw new ApiError(res.status, message, detail, busy ? "books_busy" : undefined);
  }
  return (opts.as === "text" ? await res.text() : await res.json()) as T;
}

/**
 * Downloads an authenticated file (for example a borrower file). A plain link cannot send X-Owner-Token,
 * so the bytes are fetched with the header and saved from an object URL.
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { headers: ownerHeaders() });
  } catch {
    throw unreachable();
  }
  if (res.status === 401) throw unauthorized({});
  if (!res.ok) throw new ApiError(res.status, `Download failed: ${res.status} ${res.statusText}`, undefined, "download_failed", { status: res.status });
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
