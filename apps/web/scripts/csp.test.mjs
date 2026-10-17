import assert from "node:assert/strict";
import { test } from "node:test";
import { apiOriginOf, contentSecurityPolicy } from "../lib/csp.ts";

// SEC-12 (security register): verified in a browser against the production build on 16 Oct (an injected inline handler and a
// javascript: URL were blocked; sign-in, Home, Deals, Cash, Approvals and the chat raised no violation). These pin the policy's shape.
const directives = (csp) => Object.fromEntries(csp.split("; ").map((d) => [d.split(" ")[0], d.split(" ").slice(1)]));

test("scripts need the request's nonce: no unsafe-inline, and no unsafe-eval outside development", () => {
  const d = directives(contentSecurityPolicy("abc", false, "http://localhost:8000"));
  assert.deepEqual(d["script-src"], ["'self'", "'nonce-abc'", "'strict-dynamic'"]);
  assert.ok(!contentSecurityPolicy("abc", false, null).includes("unsafe-eval"));
  assert.ok(contentSecurityPolicy("abc", true, null).includes("'unsafe-eval'"));
});

test("nothing may frame the console, load plugins or rebase its URLs", () => {
  const d = directives(contentSecurityPolicy("n", false, null));
  assert.deepEqual(d["frame-ancestors"], ["'none'"]);
  assert.deepEqual(d["object-src"], ["'none'"]);
  assert.deepEqual(d["base-uri"], ["'none'"]);
});

test("requests go only to this origin and the API the build points at", () => {
  assert.deepEqual(directives(contentSecurityPolicy("n", false, "https://api.example.test"))["connect-src"], ["'self'", "https://api.example.test"]);
  assert.equal(apiOriginOf("https://api.example.test/v1/"), "https://api.example.test");
  assert.equal(apiOriginOf("not a url"), null);
});
