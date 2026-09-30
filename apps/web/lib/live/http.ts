/** Transport for live mode: the only place that calls fetch(). */

import { API_URL, OWNER_TOKEN } from "../config";
import { ApiError } from "../errors";

interface HttpOptions {
  body?: unknown;
  as?: "json" | "text";
}

/**
 * The API gates every owner-console route on X-Owner-Token (only POST /offers intake and POST /nl are open),
 * so every request carries it. The value is the demo token: see OWNER_TOKEN in ../config.
 */
const ownerHeaders = (): Record<string, string> => ({ "X-Owner-Token": OWNER_TOKEN });

const UNAUTHORIZED =
  "The API rejected the owner token (401). Set NEXT_PUBLIC_OWNER_TOKEN to the API's OWNER_TOKEN (the demo default is demo-owner-token) and reload.";

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
  const headers: Record<string, string> = ownerHeaders();
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the service running?`);
  }
  if (res.status === 401) throw new ApiError(401, UNAUTHORIZED);
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = (await res.json()) as { detail?: unknown };
      message = detailMessage(data.detail, message);
    } catch {
      /* keep the status line */
    }
    throw new ApiError(res.status, message);
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
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the service running?`);
  }
  if (res.status === 401) throw new ApiError(401, UNAUTHORIZED);
  if (!res.ok) throw new ApiError(res.status, `Download failed: ${res.status} ${res.statusText}`);
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
