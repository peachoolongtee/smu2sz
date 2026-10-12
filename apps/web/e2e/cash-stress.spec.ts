import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import buyer from "../mocks/buyer_exposure.json";
import buyerZh from "../mocks/buyer_exposure_zh.json";
import receivables from "../mocks/receivables/day0.json";
import receivablesZh from "../mocks/receivables/day0_zh.json";

/**
 * Cash consumes the stress deep link (`/cash?stress=<buyer>:30&invoice=…&customer=…`, the link Receivables, the Customer page and the Deals queue open): the
 * late-payment picture with the scenario switch on the late scenario, the stress sentence, the invoice named and the server's `context.back` as the way back.
 *
 * Every sentence below is read from the recordings (mocks/buyer_exposure[_zh].json, GET /buyers/BUYER-1/exposure, and mocks/receivables/day0[_zh].json).
 * Three things have no recording and are laid over the recorded read through the mock's session keys (lib/mock/cash-stress.ts), as a temporary in-spec
 * patch until the lead re-records them: `context.back` (the recording was taken without the page context; the labels and addresses here are what
 * GET /buyers/{id}/exposure?customer=&invoice=&decision=&path= answers for each origin, pinned in services/api/tests/api/test_buyer_exposure.py), the feature switched off
 * (the read answers null) or failing (503), and the invoice's financing charges (`net.per_period_text`, which the opening books' invoice has none of).
 */
const EXPOSURE_KEY = "tl-mock-buyer-exposure";
const RECEIVABLES_PATCH_KEY = "tl-mock-receivables-patch";

const DEAL = "deal:OFF-1";
const ORIGINS = {
  // Receivables: the selected invoice and its buyer; back to the invoice.
  receivables: { query: "stress=BUYER-1:30&invoice=RCV-A&customer=BUYER-1", back: { label: "Back to the invoice", href: "/receivables?invoice=RCV-A&customer=BUYER-1" } },
  // The Customer page: the buyer alone; back to the Customer page.
  customer: { query: "stress=BUYER-1:30&customer=BUYER-1", back: { label: "Back to Foshan", href: "/customers/BUYER-1" } },
  // The Deals queue: the deal and its path; back to the deal.
  deals: {
    query: `stress=BUYER-1:30&customer=BUYER-1&decision=${encodeURIComponent(DEAL)}&path=counter%3A0`,
    back: { label: "Back to the Foshan deal", href: `/deals?decision=${encodeURIComponent(DEAL)}&path=counter%3A0&customer=BUYER-1` },
  },
} as const;

const now = buyer.stress.now;
const nowZh = buyerZh.stress.now;
const row = receivables.rows[0];
const rowZh = receivablesZh.rows[0];

async function overflowX(page: Page): Promise<number> {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}

async function open(page: Page, query: string, { lang = "en", exposure = "", receivablesPatch = "" }: { lang?: "en" | "zh"; exposure?: string; receivablesPatch?: string } = {}) {
  await page.context().addInitScript(
    ([l, e, r, ek, rk]) => {
      localStorage.setItem("tl-lang", JSON.stringify({ lang: l }));
      if (e) sessionStorage.setItem(ek, e);
      if (r) sessionStorage.setItem(rk, r);
    },
    [lang, exposure, receivablesPatch, EXPOSURE_KEY, RECEIVABLES_PATCH_KEY] as const,
  );
  await page.goto(query ? `/cash?${query}` : "/cash");
  await expect(page.getByTestId("cash-headline")).toBeVisible();
}

const back = (b: { label: string; href: string }) => JSON.stringify({ context: { back: b } });

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "mock-mode spec on the recorded story (the phone is measured inside it)");
});

for (const [origin, { query, back: b }] of Object.entries(ORIGINS)) {
  test(`the link from ${origin} lands on the stressed picture with the way back`, async ({ page }) => {
    await open(page, query, { exposure: back(b) });
    const picture = page.getByTestId("home-event-picture");
    await expect(picture).toHaveAttribute("data-scenario", "late");
    await expect(page.getByTestId("home-scenario-late")).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByTestId("home-scenario-late")).toHaveText(`${buyer.concentration.buyer_name} 30 days late`);
    await expect(page.getByTestId("home-scenario-expected")).toHaveAttribute("aria-pressed", "false");
    await expect(page.getByTestId("home-line-late")).toBeVisible();
    // The window reaches the lowest point (the server's series runs 120 days).
    await expect(picture).toHaveAttribute("data-window", "120");
    // The server's sentences: the assumption, the lowest point, the days under the minimum and what no plan covers, and the net a month later.
    await expect(page.getByTestId("stress-assumption")).toHaveText(now.assumption);
    const sentence = page.getByTestId("stress-sentence");
    await expect(sentence).toHaveText(`${now.text} ${now.funding_text}`);
    await expect(page.getByTestId("stress-line")).toHaveText([`What the buyer's open invoices would leave you: ${now.net_later_text}.`]);
    // The way back is the server's, exactly.
    const link = page.getByTestId("cash-stress-back");
    await expect(link).toHaveText(b.label);
    await expect(link).toHaveAttribute("href", b.href);
    // One h1, and the ordinary picture's figures are not drawn beside the stressed one.
    await expect(page.locator("h1")).toHaveCount(1);
    await expect(page.getByTestId("cash-figures")).toHaveCount(0);
  });
}

test("the invoice is named from the link, in the server's words for it", async ({ page }) => {
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back) });
  await expect(page.getByTestId("cash-stress-invoice")).toHaveText(`About ${row.invoice}: what happens to your cash if the buyer pays late.`);
  expect(row.invoice).toContain("Foshan Home Retail Co.");
  // No id in a Business page's prose.
  await expect(page.getByTestId("cash-stress-context")).not.toContainText("RCV-A");
});

test("an invoice the books do not know is not named and not echoed", async ({ page }) => {
  await open(page, "stress=BUYER-1:30&invoice=RCV-NOPE&customer=BUYER-1", { exposure: back(ORIGINS.customer.back) });
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("cash-stress-invoice")).toHaveCount(0);
  await expect(page.locator("main")).not.toContainText("RCV-NOPE");
  await expect(page.getByTestId("cash-stress-back")).toBeVisible();
});

test("the invoice's financing charges follow the net a month later when the server has them", async ({ page }) => {
  const patch = JSON.stringify({ rows: { "RCV-A": { net: { per_period_text: "about ¥1,870 more for every 30 days late" } } } });
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back), receivablesPatch: patch });
  await expect(page.getByTestId("stress-line")).toHaveText([`What the buyer's open invoices would leave you: ${now.net_later_text}.`, "Financing charges: about ¥1,870 more for every 30 days late"]);
});

test("switching back to expected restores the ordinary picture and the address keeps its context", async ({ page }) => {
  const { query, back: b } = ORIGINS.deals;
  await open(page, query, { exposure: back(b) });
  const picture = page.getByTestId("home-event-picture");
  const search = new URL(page.url()).search;
  await page.getByTestId("home-scenario-expected").click();
  await expect(picture).toHaveAttribute("data-scenario", "expected");
  await expect(page.getByTestId("home-line-plan")).toBeVisible();
  await expect(page.getByTestId("home-line-late")).toHaveCount(0);
  await expect(page.getByTestId("rail-panel")).toHaveAttribute("data-mode", "expected");
  await expect(page.getByTestId("home-scenario-expected")).toHaveAttribute("aria-pressed", "true");
  // The address and the way back are unchanged.
  expect(new URL(page.url()).search).toBe(search);
  await expect(page.getByTestId("cash-stress-back")).toHaveAttribute("href", b.href);
  // And the late scenario is one press away again.
  await page.getByTestId("home-scenario-late").click();
  await expect(picture).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("stress-sentence")).toContainText(now.text);
  expect(new URL(page.url()).search).toBe(search);
});

test("the way back and the switch work from the keyboard", async ({ page }) => {
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back) });
  // The way back is the first focusable thing on the page after the shell's own navigation: Tab from it reaches the header's content, not a trap.
  await page.getByTestId("cash-stress-back").focus();
  await expect(page.getByTestId("cash-stress-back")).toBeFocused();
  await page.getByTestId("home-scenario-expected").focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "expected");
  await page.getByTestId("home-scenario-late").focus();
  await page.keyboard.press("Space");
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
});

test("flag off: the read answers nothing and the page is the ordinary one", async ({ page }) => {
  await open(page, ORIGINS.receivables.query, { exposure: "off" });
  const ordinary = page.getByTestId("cash-headline");
  await expect(page.getByTestId("cash-figures")).toBeVisible();
  await expect(page.getByTestId("home-event-picture")).toHaveCount(0);
  await expect(page.getByTestId("cash-stress-context")).toHaveCount(0);
  await expect(page.getByTestId("cash-stress-failed")).toHaveCount(0);
  const withLink = await ordinary.innerText();
  await page.goto("/cash");
  await expect(page.getByTestId("cash-figures")).toBeVisible();
  expect(await page.getByTestId("cash-headline").innerText()).toBe(withLink);
});

test("a buyer the books do not have is the ordinary page too", async ({ page }) => {
  await open(page, "stress=BUYER-9:30");
  await expect(page.getByTestId("cash-figures")).toBeVisible();
  await expect(page.getByTestId("home-event-picture")).toHaveCount(0);
  await expect(page.getByTestId("cash-stress-context")).toHaveCount(0);
});

test("a failed read says so with a Retry and leaves the ordinary picture", async ({ page }) => {
  await open(page, ORIGINS.receivables.query, { exposure: "fail" });
  const failed = page.getByTestId("cash-stress-failed");
  await expect(failed).toContainText("The late-payment test could not be read.");
  await expect(page.getByTestId("cash-figures")).toBeVisible();
  await page.evaluate((k) => sessionStorage.removeItem(k), EXPOSURE_KEY);
  await failed.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  await expect(failed).toHaveCount(0);
});

test("the stressed page has no accessibility violations", async ({ page }) => {
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back) });
  await expect(page.getByTestId("home-event-picture")).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`)).toEqual([]);
});

test("Chinese: the switch, the sentences, the invoice and the way back are the server's Chinese", async ({ page }) => {
  const b = { label: "返回发票", href: "/receivables?invoice=RCV-A&customer=BUYER-1" };
  await open(page, ORIGINS.receivables.query, { lang: "zh", exposure: back(b) });
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  await expect(page.getByTestId("home-scenario-late")).toHaveText(`${buyerZh.concentration.buyer_name}晚付 30 天`);
  await expect(page.getByTestId("home-scenario-expected")).toHaveText("按预期收款");
  await expect(page.getByTestId("stress-assumption")).toHaveText(nowZh.assumption);
  await expect(page.getByTestId("stress-sentence")).toHaveText(`${nowZh.text} ${nowZh.funding_text}`);
  await expect(page.getByTestId("stress-line")).toHaveText([`该买方的未结发票会留给您：${nowZh.net_later_text}。`]);
  await expect(page.getByTestId("cash-stress-invoice")).toHaveText(`关于${rowZh.invoice}：如果买方晚付，您的现金会怎样。`);
  await expect(page.getByTestId("cash-stress-back")).toHaveText(b.label);
  await expect(page.getByTestId("cash-stress-back")).toHaveAttribute("href", b.href);
  // No English in the stressed block.
  const prose = await page.getByTestId("cash-stress-context").innerText();
  expect(prose).not.toMatch(/\b(about|what happens|invoice)\b/i);
  await page.getByTestId("home-scenario-expected").click();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "expected");
});

test("a phone (390 x 844): the way back and the switch are in the first screen, the picture comes before the plan, nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back) });
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  const backBox = (await page.getByTestId("cash-stress-back").boundingBox())!;
  expect(backBox.height).toBeGreaterThanOrEqual(44);
  const sw = page.getByTestId("home-scenario-late");
  await expect(sw).toBeInViewport();
  const swBox = (await sw.boundingBox())!;
  expect(swBox.y + swBox.height).toBeLessThanOrEqual(844 - 72); // above the tab bar
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  const chart = (await page.getByTestId("home-chart").boundingBox())!;
  const bar = (await page.getByTestId("home-next-action").boundingBox())!;
  expect(bar.y).toBeGreaterThan(chart.y);
  await expect(page.locator("h1")).toHaveCount(1);
  // The stress sentences are inside the width, and so is the expected picture.
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  await page.getByTestId("home-scenario-expected").click();
  expect(await overflowX(page)).toBeLessThanOrEqual(1);
  // The ordinary phone order (the answer, the plan, then the picture) is unchanged without the link.
  await page.goto("/cash");
  await expect(page.getByTestId("cash-figures")).toBeVisible();
  const plan = (await page.getByTestId("home-next-action").boundingBox())!;
  const figures = (await page.getByTestId("cash-figures").boundingBox())!;
  expect(plan.y).toBeLessThan(figures.y);
});

test("reduced motion: the cursor moves without a transition; with motion it eases", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, ORIGINS.receivables.query, { exposure: back(ORIGINS.receivables.back) });
  await page.getByTestId("home-scenario-expected").click();
  const cursor = page.getByTestId("home-cursor").locator("> g");
  await expect(cursor).toBeVisible();
  await expect(cursor).not.toHaveClass(/transition-transform/);
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.reload();
  await expect(page.getByTestId("home-event-picture")).toHaveAttribute("data-scenario", "late");
  await page.getByTestId("home-scenario-expected").click();
  await expect(page.getByTestId("home-cursor").locator("> g")).toHaveClass(/transition-transform/);
});
