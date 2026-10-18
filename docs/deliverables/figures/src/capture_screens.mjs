// The product screenshots of the submission (docs/deliverables/figures/screens), in mock mode. No API, no model, no money.
//
//   cd apps/web && NEXT_PUBLIC_API_MODE=mock NEXT_DIST_DIR=.next-shots pnpm exec next dev -p 3561      (a spare port, never 3000)
//   node docs/deliverables/figures/src/capture_screens.mjs [http://localhost:3561] [out dir]
//
// Chromium from apps/web's Playwright, 1440x900 at device scale 2, reduced motion, signed in with the published demo owner token
// (mock and local only). Writes one full-page PNG per frame and boxes.json (each frame's key elements, in CSS px), which
// crop_screens.py uses to cut the frames for the document.
import { createRequire } from "node:module";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

//
// The submission refresh (18 Oct 2026) adds a second set, taken from the build candidate int/final3 @ 2ce5265c:
//   SET=final WEB_DIR=<a checkout of apps/web at 2ce5265c, with node_modules> node capture_screens.mjs http://localhost:3571 <out>
// It writes 08-home, 09-approval, 10-capex-quick, 11-documents-attach and 12-ask-answer (see the end of this file).
const here = dirname(fileURLToPath(import.meta.url));
const web = resolve(process.env.WEB_DIR ?? resolve(here, "../../../../apps/web"));
const { chromium } = createRequire(join(web, "package.json"))("@playwright/test");

const SET = process.env.SET ?? "walk";
const BASE = process.argv[2] ?? "http://localhost:3561";
const OUT = resolve(process.argv[3] ?? join(here, "..", "screens", "raw"));
mkdirSync(OUT, { recursive: true });
const TOKEN = "demo-owner-token";

const browser = await chromium.launch(process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {});
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, reducedMotion: "reduce", locale: "en-GB" });
await context.addInitScript((tok) => {
  try {
    sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok }));
    localStorage.setItem("tl-lang", JSON.stringify({ lang: "en" }));
  } catch {
    /* storage unavailable */
  }
}, TOKEN);
const page = await context.newPage();
page.setDefaultTimeout(30_000);
const boxes = {};

async function settle() {
  await page.waitForLoadState("networkidle");
  // The dev server's own badge (the Next.js dev indicator) is not part of the product.
  await page.addStyleTag({ content: "nextjs-portal{display:none!important}" });
  await page.waitForTimeout(600);
}

async function shot(name, testids = []) {
  await settle();
  await page.evaluate(() => window.scrollTo(0, 0)); // a full-page shot draws the sticky header where the page was scrolled
  await page.waitForTimeout(300);
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true });
  const found = {};
  for (const id of testids) {
    const loc = page.getByTestId(id).first();
    if (await loc.count()) {
      const b = await loc.boundingBox();
      const scroll = await page.evaluate(() => ({ x: window.scrollX, y: window.scrollY }));
      if (b) found[id] = { x: b.x + scroll.x, y: b.y + scroll.y, w: b.width, h: b.height };
    }
  }
  boxes[name] = { url: page.url().replace(/^https?:\/\/[^/]+/, ""), boxes: found };
  console.log(name, page.url(), Object.keys(found).join(", "));
}

async function walkStory(steps) {
  for (let i = 0; i < steps; i++) {
    const button = page.getByTestId("demo-next");
    await button.waitFor();
    for (let t = 0; t < 60 && !(await button.isEnabled()); t++) await page.waitForTimeout(250);
    if ((await button.textContent())?.match(/Open the approval|Review the approval/)) {
      await button.click();
      await page.getByRole("button", { name: /^Authorize/ }).click();
      await page.waitForTimeout(800);
      continue;
    }
    await button.click();
    const dialog = page.getByTestId("books-dialog");
    await dialog.waitFor({ state: "visible", timeout: 1500 }).catch(() => undefined);
    if (await dialog.isVisible()) await page.getByTestId("books-dialog-confirm").click();
    await page.waitForTimeout(800);
  }
}

if (SET === "walk") {
// 1. Home on the opening books: the recommendation card.
await page.goto(`${BASE}/`);
await page.getByTestId("home-v2").waitFor();
await shot("01-home", ["home-v2", "hv2-outlook-card", "home-check-plan"]);

// 2. Deals: Foshan's request, read and checked against the limits: the verdict and the priced counters.
await page.goto(`${BASE}/deals`);
await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
await page.getByTestId("queue-check-button").click();
await page.getByTestId("queue-recommends").waitFor();
await shot("02-deal-verdict", ["queue-heading", "queue-recommends", "deal-ask-quote"]);

// 3. Cash & funding: the plan and the options it weighed.
await page.goto(`${BASE}/cash`);
await page.getByTestId("cash-options-list").or(page.locator("#cash-current")).first().waitFor({ state: "attached" });
await shot("03-cash-plan", ["cash-options-list", "cash-options-all", "cash-options"]);

// 4. Ask FLOW, the full page, one question answered as a card.
await page.goto(`${BASE}/ask`);
await page.getByTestId("ask-page").waitFor();
await page.getByTestId("ask-page").getByTestId("prompt-ask-safe").click();
await page.getByTestId("ask-page").getByTestId("card-lead").last().waitFor();
await shot("04-ask-answer", ["ask-page", "card-lead"]);

// 5. Documents: the reading of the supply agreement, each term beside its clause.
await page.goto(`${BASE}/documents?id=DOC-000001`);
const price = page.getByTestId("doc-terms").locator("li", { hasText: "per delivery batch" }).first();
await price.waitFor();
await price.focus(); // the term's clause lights up in the document text
await page.waitForTimeout(800);
await page.screenshot({ path: join(OUT, "05-documents-reading-viewport.png") });
await shot("05-documents-reading", ["doc-terms", "doc-review"]);

// 6. The deal tracker, after the buyer's early payment arrived from the (simulated) bank feed: story step 5.
await page.goto(`${BASE}/demo`);
await walkStory(5);
await page.goto(`${BASE}/decisions/${encodeURIComponent("deal:OFF-f806f79b6c21")}/tracker`);
await page.getByTestId("tracker").waitFor();
await shot("06-deal-tracker", ["tracker", "tracker-headline"]);

// 7. Activity: the evidence record and the chain check, after the story's approval (step 8).
await page.goto(`${BASE}/demo`);
await walkStory(3);
await page.goto(`${BASE}/activity`);
await page.getByText("Evidence", { exact: true }).nth(1).click(); // the approval request's evidence: the log entry and its hashes
await page.waitForTimeout(600);
await shot("07-activity", []);
}

if (SET === "final" || SET === "explore") {
  // 8. Home on the opening books (replaces screenshots/shot1-home).
  await page.goto(`${BASE}/`);
  await page.getByTestId("home-v2").waitFor();
  await shot("08-home", ["home-v2", "hv2-outlook-card", "home-check-plan"]);

  // 10. Capex: the quick check of the demo machine; a figure that does not apply reads "—".
  await page.goto(`${BASE}/capex`);
  await page.getByTestId("capex-quick").waitFor();
  await page.getByTestId("capex-quick").getByRole("button", { name: /^Evaluate the/ }).click();
  await page.getByTestId("capex-recommendation").first().waitFor();
  await shot("10-capex-quick", ["capex-health", "capex-purchases", "capex-quick", "capex-recommendation", "capex-basis"]);

  // 11. Documents: attach a contract (the drop zone and the upload button).
  await page.goto(`${BASE}/documents`);
  await page.getByTestId("doc-dropzone").waitFor();
  await shot("11-documents-attach", ["doc-dropzone", "doc-upload", "doc-terms"]);

  // 12. Ask FLOW, the full page, one recorded question answered as a card. The mocks hold no recording of
  // "Can I pay everyone?", so the frame uses the recorded "Are we safe?".
  await page.goto(`${BASE}/ask`);
  await page.getByTestId("ask-page").waitFor();
  await page.getByTestId("ask-page").getByTestId("prompt-ask-safe").click();
  await page.getByTestId("ask-page").getByTestId("card-lead").last().waitFor();
  await shot("12-ask-answer", ["ask-page", "card-lead"]);

  // 9. An approval waiting: walk the demo story to the cure, open the approval and stop before authorising.
  await page.goto(`${BASE}/demo`);
  for (let i = 0; i < 12; i++) {
    const button = page.getByTestId("demo-next");
    await button.waitFor();
    for (let t = 0; t < 60 && !(await button.isEnabled()); t++) await page.waitForTimeout(250);
    const label = (await button.textContent()) ?? "";
    console.log("story step", i, label.trim());
    if (/Open the approval|Review the approval/.test(label)) {
      await button.click();
      break;
    }
    await button.click();
    const dialog = page.getByTestId("books-dialog");
    await dialog.waitFor({ state: "visible", timeout: 1500 }).catch(() => undefined);
    if (await dialog.isVisible()) await page.getByTestId("books-dialog-confirm").click();
    await page.waitForTimeout(800);
  }
  await page.getByRole("button", { name: /^Authorize/ }).first().waitFor();
  await shot("09-approval", []);
}

writeFileSync(join(OUT, "boxes.json"), JSON.stringify(boxes, null, 2));
await browser.close();
