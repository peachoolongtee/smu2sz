#!/usr/bin/env node
/**
 * On-demand capture of the connected pages (Home, Deals, Receivables, Customer overview, Cash with the stress link) at 1440 and 390, en and zh.
 * Same API/web setup as capture-remediation.mjs (API on 8184, web built with NEXT_PUBLIC_API_MODE=live on 3184). Resets the API books: use a throwaway API.
 * Variables: WEB, API, OUT, PW_CHROMIUM_PATH.
 */
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const repo = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const WEB = process.env.WEB ?? "http://localhost:3184";
const API = process.env.API ?? "http://localhost:8184";
const OUT = resolve(process.env.OUT ?? join(repo, "docs/screenshots/connected-pages-2026-10-12"));
const TOKEN = "demo-owner-token";
const head = execSync("git rev-parse --short HEAD", { cwd: repo }).toString().trim();
const WIDTHS = { desktop: { width: 1440, height: 900 }, phone: { width: 390, height: 844, mobile: true } };
mkdirSync(OUT, { recursive: true });
const manifest = [];

const reset = () => fetch(`${API}/demo/reset`, { method: "POST", headers: { "X-Owner-Token": TOKEN, "content-type": "application/json" }, body: "{}" });

async function openPage(browser, vp, lang) {
  const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height }, deviceScaleFactor: 1, isMobile: !!vp.mobile, hasTouch: !!vp.mobile, reducedMotion: "no-preference" });
  await context.addInitScript(([tok, l]) => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok }));
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
    } catch {}
  }, [TOKEN, lang]);
  const page = await context.newPage();
  page.setDefaultTimeout(20_000);
  return { context, page };
}

async function shoot(page, file, state, extra = {}) {
  await page.waitForLoadState("networkidle").catch(() => {});
  const settled = await page.waitForFunction(() => !document.querySelector('.animate-pulse, [aria-busy="true"]'), undefined, { timeout: 10_000 }).then(() => true, () => false);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(900);
  const text = await page.evaluate(() => document.body.innerText);
  await page.screenshot({ path: join(OUT, file), fullPage: true });
  manifest.push({ file, state, url: page.url().replace(/^https?:\/\/[^/]+/, ""), skeleton_still_visible: !settled, ...extra, text_figures: [...new Set(text.match(/[¥￥]\s?\d[\d,.]*k?/g) ?? [])].slice(0, 40) });
  console.log("  ", file, settled ? "" : "(skeleton still visible)");
}

async function walk(browser, wname, vp, lang) {
  const sfx = `${wname}-${lang}`;
  await reset();
  const { context, page } = await openPage(browser, vp, lang);
  const t = (id) => page.getByTestId(id);
  const facts = async () => page.evaluate(() => Object.fromEntries(["today", "lowest", "arriving"].map((k) => [k, document.querySelector(`[data-testid="home-fact-${k}"]`)?.textContent?.trim() ?? null])));

  await page.goto(`${WEB}/`);
  await t("home-fact-today").waitFor();
  await shoot(page, `01-home-day0-before-plan-${sfx}.png`, "Home, day 0, funding plan not run", { facts: await facts() });

  // Deals: Foshan decision selected, comparison fold open.
  await page.goto(`${WEB}/deals`);
  await t("inbox-list").getByTestId("inbox-msg-EX01").click();
  await t("queue-check-button").click().catch(() => {});
  await t("queue-recommends").waitFor();
  const fold = t("queue-compare");
  await fold.scrollIntoViewIfNeeded();
  await fold.locator("summary").first().click();
  await page.waitForTimeout(500);
  await shoot(page, `02-deals-foshan-comparison-${sfx}.png`, "Deals, Foshan decision selected, comparison open");

  await page.goto(`${WEB}/receivables`);
  await t("recv3-selected").waitFor();
  const sel = page.locator('[data-testid="recv-select-RCV-A"]').locator("visible=true").first();
  if (await sel.count()) await sel.click().catch(() => {});
  await shoot(page, `03-receivables-three-layers-${sfx}.png`, "Receivables, invoice RCV-A selected");

  await page.goto(`${WEB}/customers/BUYER-1`);
  await t("customer-overview").waitFor();
  await shoot(page, `04-customer-buyer1-${sfx}.png`, "Customer overview, BUYER-1");

  await page.goto(`${WEB}/cash?stress=BUYER-1:30&invoice=RCV-A&customer=BUYER-1&from=customer`);
  await t("cash-stress-context").waitFor();
  await t("cash-headline").waitFor();
  await shoot(page, `05-cash-stress-link-${sfx}.png`, "Cash, Foshan 30 days late (stress deep link)");

  // Run the funding plan on Home (two presses: open, confirm), then Home after.
  await page.goto(`${WEB}/`);
  const open = page.locator('[data-testid^="fix-open-ALERT-RESERVE"]');
  await open.waitFor();
  const alertId = ((await open.getAttribute("data-testid")) ?? "").replace("fix-open-", "");
  await open.click();
  await t(`fix-${alertId}`).click();
  await page.waitForTimeout(2500);
  await page.reload();
  await t("home-fact-today").waitFor();
  await shoot(page, `06-home-after-plan-${sfx}.png`, "Home, after the funding plan ran", { facts: await facts() });
  await context.close();
}

const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {});
const failures = [];
try {
  for (const [wname, vp] of Object.entries(WIDTHS)) {
    for (const lang of (process.env.LANGS ?? "en,zh").split(",")) {
      console.log(`== ${wname} ${vp.width} ${lang}`);
      try { await walk(browser, wname, vp, lang); } catch (e) { failures.push(`${wname}-${lang}: ${String(e.message).split("\n").slice(0,3).join(" | ")}`); console.log("  FAILED", failures.at(-1)); }
    }
  }
} finally {
  await reset().catch(() => {});
  await browser.close();
}
writeFileSync(join(OUT, "manifest.json"), JSON.stringify({ head, captured_at: new Date().toISOString(), shots: manifest, failures }, null, 2));
if (failures.length) process.exitCode = 1;
