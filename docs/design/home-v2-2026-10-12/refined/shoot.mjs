// Screenshots of HomeV2Refined.html in its three states, and the side-by-side with the slice-1 desktop.
// Run: node docs/design/home-v2-2026-10-12/refined/shoot.mjs [path/to/01-desktop-top.jpg]
// Uses the Playwright installed in apps/web (no install of its own).
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "../../../..");
const require = createRequire(path.join(repo, "apps/web/package.json"));
const { chromium } = require("@playwright/test");

const page = pathToFileURL(path.join(here, "HomeV2Refined.html")).href;
const shots = [
  { file: "desktop-default.png", q: "?state=default&shot=1", viewport: { width: 1440, height: 1000 } },
  { file: "desktop-deal-selected.png", q: "?state=deal&shot=1", viewport: { width: 1440, height: 1000 } },
  { file: "phone-default.png", q: "?state=default&shot=1", viewport: { width: 390, height: 844 }, mobile: true },
];

const browser = await chromium.launch();
for (const s of shots) {
  const ctx = await browser.newContext({ viewport: s.viewport, deviceScaleFactor: 2, isMobile: !!s.mobile, hasTouch: !!s.mobile });
  const p = await ctx.newPage();
  await p.goto(page + s.q, { waitUntil: "networkidle" });
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(400);
  await p.screenshot({ path: path.join(here, s.file), fullPage: true });
  if (s.mobile) await p.screenshot({ path: path.join(here, "phone-first-viewport.png") });
  await ctx.close();
  console.log("wrote", s.file);
}

// compare.png: the slice-1 desktop top beside the refined desktop's first 1000 px, the same height.
const current = process.argv[2] ?? path.join(repo, "docs/screenshots/home-v2-slice1-2026-10-13/01-desktop-top.jpg");
if (fs.existsSync(current)) {
  const a = fs.readFileSync(current).toString("base64");
  const b = fs.readFileSync(path.join(here, "desktop-default.png")).toString("base64");
  const ctx = await browser.newContext({ viewport: { width: 1640, height: 640 }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.setContent(`<!doctype html><html><body style="margin:0;background:#eef1f5;font:600 15px Lato,system-ui,sans-serif;color:#24324a">
    <div style="display:flex;gap:24px;padding:20px;align-items:flex-start">
      <figure style="margin:0"><figcaption style="margin:0 0 8px">Now (slice 1)</figcaption>
        <div style="height:556px;overflow:hidden;border:1px solid #d3d9e2;background:#fff"><img src="data:image/jpeg;base64,${a}" style="height:556px;display:block"></div></figure>
      <figure style="margin:0"><figcaption style="margin:0 0 8px">Refined reference</figcaption>
        <div style="height:556px;width:800px;overflow:hidden;border:1px solid #d3d9e2;background:#fff"><img src="data:image/png;base64,${b}" style="width:800px;display:block"></div></figure>
    </div></body></html>`);
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(here, "compare.png"), fullPage: true });
  await ctx.close();
  console.log("wrote compare.png");
} else console.log("no current screenshot at", current);
await browser.close();
