// CSP check on a production build in a browser: every page carries the nonce policy, raises no violation or page error, and an injected
// inline handler or javascript: URL does not run. Usage: node csp_check.mjs <web base> <out.json>  (run from apps/web for @playwright/test)
import { chromium } from "@playwright/test";
import { writeFileSync } from "node:fs";

const [base, out] = process.argv.slice(2);
const routes = ["/", "/deals", "/documents", "/cash", "/receivables", "/approvals", "/activity", "/limits", "/customers/BUYER-1",
  "/customers/BUYER-1/inputs", "/capex", "/buy", "/buy/contract", "/finance", "/plans", "/whatif", "/strategy"];
const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: "reduce" });
await ctx.addInitScript(() => {
  sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "demo-owner-token" }));
  window.__violations = [];
  document.addEventListener("securitypolicyviolation", (e) => window.__violations.push(`${e.violatedDirective} ${e.blockedURI}`));
});
const p = await ctx.newPage();
const pageErrors = [];
p.on("pageerror", (e) => pageErrors.push(String(e).slice(0, 200)));
const results = [];
for (const route of routes) {
  const before = pageErrors.length;
  const res = await p.goto(base + route, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2500);
  const csp = res?.headers()["content-security-policy"] ?? "";
  const violations = await p.evaluate(() => window.__violations.splice(0));
  results.push({ route, status: res?.status(), nonce: /'nonce-[A-Za-z0-9+/=_-]+'/.test(csp), strict_dynamic: csp.includes("'strict-dynamic'"),
    frame_ancestors_none: csp.includes("frame-ancestors 'none'"), violations, page_errors: pageErrors.slice(before) });
}
await p.goto(base + "/", { waitUntil: "domcontentloaded" });
await p.waitForTimeout(1500);
const injected = await p.evaluate(async () => {
  window.__pwned = 0;
  const d = document.createElement("div");
  d.innerHTML = '<img src="x" onerror="window.__pwned=1"><a id="jsl" href="javascript:window.__pwned=2">x</a>';
  document.body.appendChild(d);
  await new Promise((r) => setTimeout(r, 800));
  document.getElementById("jsl").click();
  await new Promise((r) => setTimeout(r, 800));
  return { pwned: window.__pwned, violations: window.__violations.splice(0) };
});
const summary = {
  pages: results.length,
  all_nonce: results.every((r) => r.nonce && r.strict_dynamic),
  violations: results.reduce((n, r) => n + r.violations.length, 0),
  page_errors: results.reduce((n, r) => n + r.page_errors.length, 0),
  injected_ran: injected.pwned !== 0,
  injected_blocked_reports: injected.violations,
};
writeFileSync(out, JSON.stringify({ base, summary, results }, null, 2));
console.log(JSON.stringify(summary));
await b.close();
