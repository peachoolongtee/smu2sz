import { readFileSync } from "node:fs";
import { join } from "node:path";
import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, resetBooks } from "./helpers";

/**
 * Deals as a decision queue (ticket #109): four count tiles as tabs over one list, the selected deal beside its aside, the cash on each path
 * with the exposure band, and the comparison behind one fold. Every sentence and figure is the server's (the recorded deals read, the offer picture
 * and the exposure read); the spec reads them from the recordings and compares what the page says.
 *
 * No client flag decides the page: the queue renders when the open offer's exposure read is present (the server's FEATURE_EXPOSURE; the mock carries the recording).
 * The last test strips the read in-spec and asserts the current page renders. Run (mock): E2E_TARGET=mock pnpm exec playwright test e2e/deals-queue.spec.ts
 */

const rec = (name: string) => JSON.parse(readFileSync(join(process.cwd(), "mocks", name), "utf8"));
const deals = rec("deals_day0_evaluated.json");
const open = deals.deals.find((d: { open_offer: unknown }) => d.open_offer).open_offer as { offer_id: string; headline_short: string; asks_text: string; cost_display: string };
const exposureEn = rec("offer_exposure_ex01.json").en;
const exposureZh = rec("offer_exposure_ex01.json").zh;
const pictureEn = rec("offer_picture_ex01.json").en;
const recheck = rec("verdict_ex01.json").workspace.priced_response.recheck_text as string;
const words = (key: string) => exposureEn.paths.find((p: { key: string }) => p.key === key);
const reply = pictureEn.paths.find((p: { recommended: boolean }) => p.recommended);
const asked = pictureEn.paths.find((p: { kind: string }) => p.kind === "asked");

test.beforeEach(async ({ request }) => {
  await resetBooks(request);
});

/** The owner reads the EX01 message in the inbox and has FLOW check it; the queue appears once the offer is open and its exposure read arrives. */
async function openQueue(page: Page) {
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-heading")).toHaveText(open.headline_short);
}

test("four tabs filter the list: the owner's reply first, the others by what they hold", async ({ page }) => {
  await openQueue(page);
  const counts = async () => Promise.all(["needs", "wait", "agreed", "setup"].map((k) => page.getByTestId(`queue-count-${k}`).innerText()));
  expect(await counts()).toEqual(["1", "0", "1", "1"]);
  await expect(page.getByTestId("queue-tab-needs")).toHaveAttribute("aria-selected", "true");
  const rows = page.getByTestId("queue-row");
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Foshan Home Retail Co.");
  await expect(rows.first()).toContainText(open.cost_display);
  await expect(rows.first()).toContainText("Counter with Option A");
  await expect(rows.first()).toHaveAttribute("aria-current", "true");

  await page.getByTestId("queue-tab-wait").click();
  await expect(page.getByTestId("queue-tab-wait")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("queue-empty")).toHaveText("No reply is out with a buyer right now.");
  await expect(page).toHaveURL(/tab=wait/);

  await page.getByTestId("queue-tab-agreed").click();
  await expect(rows).toHaveCount(1);
  // The terms in force (the contract reference, the days, the rebate), never the pending counter's figures.
  await expect(rows.first()).toContainText("FHR-2026-07");
  await expect(rows.first()).toContainText("Payment terms: 45 days");
  await expect(rows.first()).not.toContainText("0.85%");

  await page.getByTestId("queue-tab-setup").click();
  await expect(rows).toHaveCount(1);
  await expect(rows.first()).toContainText("Dongguan Office Supplies Ltd.");
  await expect(rows.first()).toContainText("No contract on file yet");
  // The detail stays: the queue and the selected deal are kept across tabs.
  await expect(page.getByTestId("queue-heading")).toHaveText(open.headline_short);

  // The keyboard moves between the tiles.
  await page.getByTestId("queue-tab-setup").focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByTestId("queue-tab-needs")).toHaveAttribute("aria-selected", "true");
});

test("selecting a deal replaces the detail in place and keeps ?decision=; the heading is the server's; one filled primary", async ({ page }) => {
  await openQueue(page);
  await expect(page).toHaveURL(new RegExp(`decision=deal(%3A|:)${open.offer_id}`));
  // The address carries the deal and the path, not the customer: a customer in it would say the page was opened from that customer's page.
  await expect(page).not.toHaveURL(/customer=/);
  await page.getByTestId("queue-select").click();
  await expect(page.getByTestId("queue-heading")).toHaveText(open.headline_short);
  await expect(page).toHaveURL(new RegExp(`decision=deal(%3A|:)${open.offer_id}`));
  await expect(page.getByTestId("queue-announce")).toContainText(open.headline_short);
  await expect(page.getByTestId("queue-ask")).toContainText(open.asks_text);
  // WHY COUNTER?: the server's reasons, two short sentences.
  await expect(page.getByTestId("queue-why")).toContainText("Why counter?");
  await expect(page.getByTestId("queue-why").locator("p")).toHaveCount(3);
  // The blue card: the option, the one-off cost if the buyer accepts, who decides, and the one filled primary.
  await expect(page.getByTestId("queue-option")).toHaveText(reply.reply_text);
  await expect(page.getByTestId("queue-cost")).toHaveText(`Estimated one-off cost ${reply.cost_once_display}, if Foshan accepts.`);
  await expect(page.getByTestId("queue-authority")).toContainText(reply.authority_text);
  await expect(page.getByTestId("queue-review-open")).toHaveText("Review and send the counter");
  // The server's sentence on what the send re-checks stands beside the button.
  if (recheck) await expect(page.getByTestId("queue-recommends")).toContainText(recheck); // (present once the verdict recording carries `recheck_text`)
  expect(await filledBrand(page)).toBe(1);
  // Opening the review replaces the button with the existing send: still one filled primary, the bound option and the server's lines.
  await page.getByTestId("queue-review-open").click();
  await expect(page.getByTestId("deal-send-scope")).toBeVisible();
  await expect(page.getByTestId("deal-send")).toBeVisible();
  expect(await filledBrand(page)).toBe(1);
  await page.getByTestId("queue-review-close").click();
  await expect(page.getByTestId("queue-review-open")).toBeVisible();
});

test("the cash on each path is always visible under the card, with the exposure band and the paid-late line", async ({ page }) => {
  await openQueue(page);
  const detail = page.getByTestId("queue-detail");
  await expect(detail.getByTestId("deal-paths")).toBeVisible();
  await expect(detail.getByTestId("deal-paths")).toContainText("Cash on each path");
  await expect(page.getByTestId("paths-chart")).toBeVisible();
  // Order: the card, the chart, then the comparison fold.
  const y = async (id: string) => (await page.getByTestId(id).boundingBox())!.y;
  expect(await y("queue-recommends")).toBeLessThan(await y("deal-paths"));
  expect(await y("deal-paths")).toBeLessThan(await y("queue-compare"));
  // The band: the server's three sentences for the picked path.
  const band = page.getByTestId("exposure-band");
  await expect(band).toContainText(exposureEn.band.concentration);
  await expect(band).toContainText(exposureEn.band.by_path[reply.key].stress);
  await expect(band).toContainText(exposureEn.band.by_path[reply.key].capacity);
  // Picking the asked path moves the band's late-payment and capacity sentences with it.
  await page.getByTestId("path-col-0").getByRole("radio").click();
  await expect(band).toContainText(exposureEn.band.by_path.asked.stress);
  await expect(band).toContainText(exposureEn.band.by_path.asked.capacity);
  // The paid-late toggle adds one dashed line and never changes the pick.
  await expect(page.getByTestId("stress-line")).toHaveCount(0);
  await page.getByTestId("stress-toggle").click();
  await expect(page.getByTestId("stress-toggle")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("stress-line")).toHaveCount(1);
  await expect(page.getByTestId("paths-picture")).toHaveAttribute("data-pick", "asked");
  await page.getByTestId("stress-toggle").click();
  await expect(page.getByTestId("stress-line")).toHaveCount(0);
});

test("the comparison is closed by default; open it for seven rows with the server's strings", async ({ page }) => {
  await openQueue(page);
  const fold = page.getByTestId("queue-compare");
  await expect(fold).not.toHaveAttribute("open", "");
  await expect(page.getByTestId("queue-impact")).toBeHidden();
  await fold.locator("> summary").click();
  const table = page.getByTestId("queue-impact");
  await expect(table.locator("tbody tr")).toHaveCount(7);
  await expect(page.getByTestId("queue-impact-once")).toContainText(asked.cost_once_display);
  await expect(page.getByTestId("queue-impact-once")).toContainText(reply.cost_once_display);
  await expect(page.getByTestId("queue-impact-forward")).toContainText(asked.cost_forward_display);
  // Every cell of the cash, limit and share rows is the exposure read's words for that column; the first column is the do-nothing path (words only).
  const nothing = words("do_nothing");
  for (const [w, i] of [[nothing, 1], [words("asked"), 2], [words(reply.key), 3]] as const) {
    await expect(page.getByTestId("queue-impact-lowest").locator("td").nth(i - 1)).toContainText(w.lowest_display);
    await expect(page.getByTestId("queue-impact-lowest").locator("td").nth(i - 1)).toContainText(w.lowest_when_text);
    // A null `limit_word` (the do-nothing path, or a reply the picture cannot price) is a dash, never a word of ours.
    if (w.limit_word) await expect(page.getByTestId("queue-impact-limit").locator("td").nth(i - 1)).toHaveText(w.limit_text);
    else await expect(page.getByTestId("queue-impact-limit").locator("td").nth(i - 1)).toContainText("—");
    await expect(page.getByTestId("queue-impact-share").locator("td").nth(i - 1)).toHaveText(w.share_after_text);
  }
  await expect(page.getByTestId("queue-impact-spare")).toContainText(exposureEn.capacity.asked.spare.today_display);
  await expect(page.getByTestId("queue-impact-spare")).toContainText(exposureEn.capacity[reply.key].spare.x_star_display);
  // The do-nothing path is words only: it is not a line on the chart, a tile of the band or a column of the picture.
  await expect(page.locator('[data-testid^="path-col-"][data-selected]')).toHaveCount(3);
  await expect(page.locator('[data-testid^="path-line-"]')).toHaveCount(3);
  await expect(table.locator("thead")).toContainText("Do nothing");
  await expect(table.locator("thead")).toContainText("If Foshan accepts Option A");
});

test("the customer links carry customer, decision and path; the stress link carries stress and invoice; the aside has three facts", async ({ page }) => {
  await openQueue(page);
  for (const id of ["queue-customer", "queue-detail-customer", "aside-profile"]) {
    const href = (await page.getByTestId(id).first().getAttribute("href"))!;
    expect(href, id).toContain("/customers/BUYER-1?");
    const q = new URL(href, "http://x").searchParams;
    expect(q.get("customer"), id).toBe("BUYER-1");
    expect(q.get("decision"), id).toBe(`deal:${open.offer_id}`);
    expect(q.get("path"), id).toBe(reply.key);
  }
  const stress = new URL((await page.getByTestId("aside-stress").getAttribute("href"))!, "http://x");
  expect(stress.pathname).toBe("/cash");
  expect(stress.searchParams.get("stress")).toBe("BUYER-1:30");
  expect(stress.searchParams.get("invoice")).toBe("RCV-A");
  const aside = page.getByTestId("queue-aside");
  await expect(aside.locator("dt")).toHaveCount(3); // the contribution (with its note), what they owe now, their share: the read's `customer_context`
  const cc = exposureEn.customer_context;
  await expect(page.getByTestId("aside-contribution")).toContainText(cc.contribution_display);
  await expect(page.getByTestId("aside-contribution-note")).toHaveText(cc.contribution_note);
  await expect(page.getByTestId("aside-owes")).toHaveText(cc.owes_display);
  await expect(page.getByTestId("aside-share")).toHaveText(cc.share_text);
  expect(new URL((await page.getByTestId("aside-profile").getAttribute("href"))!, "http://x").pathname).toBe(cc.profile_href);
  await expect(aside).toContainText("Context, not a promise");
  // The picked path travels with the links.
  await page.getByTestId("path-col-0").getByRole("radio").click();
  expect(new URL((await page.getByTestId("aside-profile").getAttribute("href"))!, "http://x").searchParams.get("path")).toBe("asked");
});

test("the address restores the selection: a back link with customer, decision and path opens the same deal on the same path", async ({ page }) => {
  await openQueue(page);
  await page.getByTestId("path-col-0").getByRole("radio").click();
  await expect(page).toHaveURL(/path=asked/);
  await page.getByTestId("aside-profile").click(); // /customers/BUYER-1 does not exist on this branch; the link is the contract
  await page.waitForURL(/\/customers\/BUYER-1\?/);
  expect(page.url()).toContain("path=asked");
  await page.goBack();
  await expect(page.getByTestId("queue-heading")).toHaveText(open.headline_short);
  await expect(page.getByTestId("paths-picture")).toHaveAttribute("data-pick", "asked");
  await expect(page).toHaveURL(/path=asked/);
});

test("reduced motion: nothing transitions in the queue", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openQueue(page);
  const moving = await page.evaluate(() =>
    [...document.querySelectorAll("[data-testid=queue-body], [data-testid=queue-body] *, [data-testid=queue-tabs] *, [data-testid=queue-row]")].filter((el) => {
      const s = getComputedStyle(el);
      return s.transitionDuration.split(",").some((d) => parseFloat(d) > 0.001) && s.transitionProperty !== "none" && s.transitionProperty !== "";
    }).length,
  );
  expect(moving).toBe(0);
});

test("Chinese: the same page in the owner's voice, with the same figures", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("queue-check-button").click();
  await expect(page.getByTestId("queue-tab-needs")).toContainText("需要您回复");
  await expect(page.getByTestId("queue-heading")).not.toHaveText(open.headline_short);
  await expect(page.getByTestId("queue-why")).toContainText("为什么还价？");
  await expect(page.getByTestId("exposure-band")).toContainText(exposureZh.band.concentration);
  await expect(page.getByTestId("queue-review-open")).toHaveText("查看并发送还价");
  await expect(page.getByTestId("aside-owes")).toHaveText(exposureZh.customer_context.owes_display);
  expect(await page.locator("main").innerText()).not.toMatch(/\bday \d/i);
});

test("a phone: tiles scroll sideways, the primary is in the first screens, nothing overflows", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openQueue(page);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.getByTestId("queue-tab-needs")).toBeVisible();
  // Order on a phone: the list, the heading, the ask, why, the card with its button, the chart, the fold, then the aside.
  const ys = [];
  for (const id of ["queue-list", "queue-heading", "queue-why", "queue-recommends", "deal-paths", "queue-compare", "queue-aside"]) ys.push((await page.getByTestId(id).boundingBox())!.y);
  expect([...ys].sort((a, b) => a - b)).toEqual(ys);
  const row = await page.getByTestId("queue-row").first().boundingBox();
  expect(row!.height).toBeLessThan(120); // two lines per row
  await expect(page.getByTestId("queue-review-open")).toBeVisible();
  // The one filled primary ends in the first screen and above the tab bar (390 x 844).
  const box = (await page.getByTestId("queue-review-open").boundingBox())!;
  const bar = (await page.getByTestId("tab-bar").boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(bar.y);
  expect(box.y + box.height).toBeLessThanOrEqual(844);
});

test("axe finds nothing serious or critical on the queue, with the comparison and the review open, at either width", async ({ page }) => {
  await openQueue(page);
  await page.getByTestId("queue-compare").locator("> summary").click();
  await page.getByTestId("queue-review-open").click();
  const result = await new AxeBuilder({ page }).analyze();
  const bad = result.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  expect(result.passes.length).toBeGreaterThan(10);
  expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test("with the exposure read stripped the current Deals page renders exactly: no queue, the verdict heading, the reply bar and the paths", async ({ page }) => {
  await page.addInitScript(() => sessionStorage.setItem("tl-mock-exposure-off", "1"));
  await page.goto("/deals");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await page.getByTestId("next-step").getByRole("button", { name: "Check against my limits" }).click();
  await expect(page.getByTestId("deal-recommendation")).toContainText(open.headline_short);
  await expect(page.getByTestId("path-reply")).toBeVisible();
  await expect(page.getByTestId("deal-paths")).toBeVisible();
  for (const id of ["queue-tabs", "queue-list", "queue-detail", "queue-aside", "exposure-band", "stress-toggle", "queue-compare"]) await expect(page.getByTestId(id)).toHaveCount(0);
  await expect(page.locator("h1")).toHaveCount(1);
  await expect(page.locator("h1")).toHaveText(open.headline_short);
});

test("opened from the list there is no back link", async ({ page }) => {
  await openQueue(page);
  await expect(page.getByTestId("queue-back")).toHaveCount(0);
});

test("opened from a customer or an invoice, the server's back link stands above the queue", async ({ page }) => {
  const back = rec("deals_day0_evaluated_back.json").deals[0].open_offer.context.back as { label: string; href: string };
  await page.goto("/deals?customer=BUYER-1");
  await page.getByTestId("inbox-list").getByTestId("inbox-msg-EX01").click();
  await expect(page.getByTestId("queue-heading")).toBeVisible();
  const link = page.getByTestId("queue-back");
  await expect(link).toHaveText(`‹ ${back.label}`);
  await expect(link).toHaveAttribute("href", back.href);
});

test("returning from the Customer page: the address's decision and path select the deal and the path, and a pick is written back to it", async ({ page }) => {
  await openQueue(page);
  await page.goto(`/deals?decision=${encodeURIComponent(`deal:${open.offer_id}`)}&path=asked`);
  await expect(page.getByTestId("queue-heading")).toHaveText(open.headline_short);
  await expect(page.getByTestId("paths-picture")).toHaveAttribute("data-pick", "asked");
  await expect(page.getByTestId("path-col-pick-0")).toHaveAttribute("aria-checked", "true");
  await page.getByTestId("path-col-pick-2").click();
  await expect.poll(() => new URL(page.url()).searchParams.get("path")).toMatch(/^CTR-/);
  expect(new URL(page.url()).searchParams.get("decision")).toBe(`deal:${open.offer_id}`);
});
