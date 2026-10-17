/**
 * The Content-Security-Policy of every page (security register SEC-12), built by proxy.ts with a fresh nonce per request.
 *
 * Scripts run only with this request's nonce, or when a script that has it loads them ('strict-dynamic'); an injected <script> tag,
 * an inline event handler or a javascript: URL does not run. Requests go only to this origin and the API the build points at.
 * Nothing may frame the console. Styles allow 'unsafe-inline' (server-rendered style attributes cannot carry a nonce, and a style
 * cannot read the token). No upgrade-insecure-requests: the local demo calls its API over http://localhost; HTTPS and HSTS belong to
 * the TLS proxy. Development adds 'unsafe-eval' (React rebuilds error stacks with eval; production never needs it).
 */
export function contentSecurityPolicy(nonce: string, dev: boolean, apiOrigin: string | null): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self' data:",
    `connect-src 'self'${apiOrigin ? ` ${apiOrigin}` : ""}`,
    "object-src 'none'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

/** The API origin the build calls (NEXT_PUBLIC_API_URL), or null when it is not a URL. */
export function apiOriginOf(url: string | undefined): string | null {
  try {
    return new URL(url ?? "http://localhost:8000").origin;
  } catch {
    return null;
  }
}
