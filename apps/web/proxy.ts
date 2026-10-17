/**
 * Sets the Content-Security-Policy with a nonce per request (security register SEC-12; the Next.js guide "Content Security Policy").
 * The policy itself is lib/csp.ts. The owner token lives in sessionStorage, so a script injected into this origin could read it:
 * only scripts carrying this request's nonce run (Next.js adds it to its own scripts, app/layout.tsx to the pre-hydration script).
 */
import { NextResponse, type NextRequest } from "next/server";
import { apiOriginOf, contentSecurityPolicy } from "./lib/csp";

export function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = contentSecurityPolicy(nonce, process.env.NODE_ENV === "development", apiOriginOf(process.env.NEXT_PUBLIC_API_URL));
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api|_next/static|_next/image|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
