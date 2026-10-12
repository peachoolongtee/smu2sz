// Screenshots of HomeV2Refined2.html in its states, the 1280 laptop check and the first-pass/second-pass side-by-side.
// Run: node docs/design/home-v2-2026-10-12/refined2/shoot.mjs   (uses the Playwright installed in apps/web)
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../../..");
const require = createRequire(path.join(repo, "apps/web/package.json"));
const { chromium } = require("@playwright/test");

const page = pathToFileURL(path.join(here, "HomeV2Refined2.html")).href;
const D = { width: 1440, height: 1000 }, P = { width: 390, height: 844 };
const shots = [
  { file: "desktop-default.png", q: "?state=default&shot=1", viewport: D },
  { file: "desktop-deal.png", q: "?state=deal&shot=1", viewport: D },
  { file: "desktop-compare.png", q: "?state=compare&shot=1", viewport: D },
  { file: "desktop-1280-deal.png", q: "?state=compare&shot=1", viewport: { width: 1280, height: 800 } },
  { file: "phone-default.png", q: "?state=default&shot=1", viewport: P, mobile: true, first: "phone-first-viewport.png" },
  { file: "phone-deal.png", q: "?state=deal&shot=1", viewport: P, mobile: true },
  { file: "phone-sheet.png", q: "?state=default&shot=1&sheet=1", viewport: P, mobile: true, full: false },
];

const browser = await chromium.launch();
for (const s of shots) {
  const ctx = await browser.newContext({ viewport: s.viewport, deviceScaleFactor: 2, isMobile: !!s.mobile, hasTouch: !!s.mobile });
  const p = await ctx.newPage();
  const errors = [];
  p.on("pageerror", (e) => errors.push(e.message));
  await p.goto(page + s.q, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(500);
  if (s.first) await p.screenshot({ path: path.join(here, s.first) });
  if (s.mobile && s.full !== false) {
    // a phone page's fixed sheet and tab bar belong at the bottom of the screen: grow the viewport to the page so they sit at its end
    const h = await p.evaluate(() => document.documentElement.scrollHeight);
    await p.setViewportSize({ width: s.viewport.width, height: h });
    await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(here, s.file) });
  } else await p.screenshot({ path: path.join(here, s.file), fullPage: s.full !== false });
  await ctx.close();
  console.log("wrote", s.file, errors.length ? "ERRORS: " + errors.join(" | ") : "");
}

// compare-v1-v2.png: the first pass's desktop-default beside this pass's, the same width.
const v1 = path.join(here, "../refined/desktop-default.png"), v2 = path.join(here, "desktop-default.png");
if (fs.existsSync(v1)) {
  const a = fs.readFileSync(v1).toString("base64"), b = fs.readFileSync(v2).toString("base64");
  const ctx = await browser.newContext({ viewport: { width: 1520, height: 800 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.setContent(`<!doctype html><html><body style="margin:0;background:#eef1f5;font:700 15px Lato,system-ui,sans-serif;color:#24324a">
    <div style="display:flex;gap:24px;padding:20px;align-items:flex-start">
      <figure style="margin:0"><figcaption style="margin:0 0 8px">First pass (refined/)</figcaption>
        <div style="width:720px;border:1px solid #d3d9e2;background:#fff"><img src="data:image/png;base64,${a}" style="width:720px;display:block"></div></figure>
      <figure style="margin:0"><figcaption style="margin:0 0 8px">Second pass (refined2/)</figcaption>
        <div style="width:720px;border:1px solid #d3d9e2;background:#fff"><img src="data:image/png;base64,${b}" style="width:720px;display:block"></div></figure>
    </div></body></html>`);
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(here, "compare-v1-v2.png"), fullPage: true });
  await ctx.close();
  console.log("wrote compare-v1-v2.png");
}
await browser.close();
