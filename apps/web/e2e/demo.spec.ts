import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";
import { filledBrand, openOperatorTools } from "./helpers";

/**
 * The Demo story (Slice D, ticket #145), read from GET /demo/story. The same spec runs in both Playwright projects: `desktop` (the recorded reads, picked by the mock's own state)
 * and `live` (the real FastAPI service). One current scene with the page's only filled button, the owner's step that only opens the approval, another set of books behind a
 * confirmation dialog with a one-click restore, the operator tools folded away and the proof appendix. Every sentence on the page is the server's.
 */

const next = (page: Page) => page.getByTestId("demo-next");

async function openDemo(page: Page): Promise<void> {
  await page.goto("/demo");
  await expect(page.getByTestId("demo-current")).toBeVisible();
}

/** The story page as the owner would read it, reset first: the opening books (live shares one API between specs). */
async function freshDemo(page: Page): Promise<void> {
  await openDemo(page);
  await openOperatorTools(page);
  await page.getByTestId("demo-tools-books").getByRole("button").first().click();
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
}

/** One press of the page's next control; the step opens its screen, so the story page is opened again afterwards. */
async function pressNext(page: Page): Promise<void> {
  await expect(next(page)).toBeEnabled();
  await next(page).click();
  // The step runs its server work and then opens its screen: wait for that before the story page is opened again.
  await expect(page).not.toHaveURL(/\/demo$/);
  await page.waitForLoadState("domcontentloaded");
}

test("one filled next control at every step of the walk; the owner's step only opens the approval", async ({ page }) => {
  test.setTimeout(240_000);
  await freshDemo(page);
  let sawOwner = false;
  for (let i = 0; i < 16; i++) {
    await openDemo(page);
    // Exactly one filled button on the page, and it is the next control.
    expect(await filledBrand(page), `filled buttons at press ${i}`).toBe(1);
    await expect(next(page)).toBeVisible();
    if ((await page.getByTestId("demo-progress").textContent())?.startsWith("All")) break;
    if ((await next(page).getAttribute("data-owner")) === "true") {
      sawOwner = true;
      // The owner's step is a link to the approval, with the sentence that says the approval is the owner's own click; nothing has been approved yet.
      await expect(next(page)).toHaveAttribute("href", /\/approvals/);
      await expect(page.getByTestId("demo-owner-text")).toBeVisible();
      await expect(page.getByTestId("demo-scene-owner")).toHaveAttribute("data-state", "current");
      await next(page).click();
      const approve = page.getByRole("button", { name: /^Approve/ });
      await expect(approve).toBeVisible();
      // The test is the owner here: the one click on the approval card.
      await approve.click();
      await expect(page.getByText("0 pending")).toBeVisible();
      continue;
    }
    await pressNext(page);
  }
  expect(sawOwner).toBe(true);
  await openDemo(page);
  await expect(page.getByTestId("demo-progress")).toContainText(/^All/);
  for (const id of ["buyer", "decision", "agreement", "reality", "owner", "proof"]) await expect(page.getByTestId(`demo-scene-${id}`)).toHaveAttribute("data-state", "done");
  // Complete: the next control starts the story again, from scene one.
  await next(page).click();
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
});

test("each done scene shows what happened and its proof, and every proof link opens a record that exists", async ({ page }) => {
  test.setTimeout(240_000);
  await freshDemo(page);
  for (let i = 0; i < 3; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const done = page.locator('[data-testid^="demo-scene-"][data-state="done"]');
  expect(await done.count()).toBeGreaterThan(0);
  await expect(page.getByTestId("demo-result-buyer")).not.toBeEmpty();
  const links = await page.locator('[data-testid^="demo-proof-"] a').evaluateAll((as) => as.map((a) => (a as HTMLAnchorElement).getAttribute("href") ?? ""));
  expect(links.length).toBeGreaterThan(0);
  for (const href of links) {
    await page.goto(href);
    await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    const entry = /[?&]entry=(\d+)/.exec(href)?.[1];
    if (entry) await expect(page.getByTestId(`trust-entry-${entry}`)).toHaveAttribute("aria-current", "true");
    await expect(page.getByText(/not found|404/i)).toHaveCount(0);
  }
});

test("another set of books: the dialog shows the loss, cancel changes nothing, confirm loads the busy books and restore brings the story back at scene one", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const before = await page.getByTestId("demo-progress").textContent();
  const open = page.getByTestId("demo-alternate-open");
  await expect(page.getByTestId("demo-alternate-dialog")).toBeHidden();
  await open.click();
  const dialog = page.getByTestId("demo-alternate-dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(dialog).toHaveAccessibleName(/./);
  // The loss preview, in words, from the books as they stand; the dialog's one filled button is the confirmation.
  await expect(page.getByTestId("demo-alternate-loss").locator("li").first()).toBeVisible();
  await expect(dialog.getByRole("button")).toHaveCount(2);
  // Escape closes it and focus returns to the button that opened it; nothing changed.
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  // Cancel does the same.
  await open.click();
  await page.getByTestId("demo-alternate-cancel").click();
  await expect(dialog).toBeHidden();
  await expect(open).toBeFocused();
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  // Confirm loads the busy books: the banner offers the restore, the story is put aside and the next control opens Home.
  await open.click();
  await page.getByTestId("demo-alternate-confirm").click();
  const banner = page.getByTestId("demo-loaded-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toHaveAttribute("role", "status");
  await expect(page.getByTestId("story")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(1);
  await expect(next(page)).toHaveAttribute("href", "/");
  // One click puts the main books back, at the first scene.
  await page.getByTestId("demo-restore").click();
  await expect(banner).toHaveCount(0);
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
  await expect(page.getByTestId("demo-restored")).toBeVisible();
});

test("operator tools are closed by default and hold the clock, the books and the engine views", async ({ page }) => {
  await openDemo(page);
  const tools = page.getByTestId("demo-operator-tools");
  await expect(tools).toBeVisible();
  expect(await tools.evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
  await expect(page.getByTestId("home-days")).toBeHidden();
  await openOperatorTools(page);
  await expect(page.getByTestId("demo-tools-clock")).toBeVisible();
  await expect(page.getByTestId("demo-tools-books")).toBeVisible();
  await expect(page.getByTestId("demo-tools-engine")).toBeVisible();
  await expect(page.getByTestId("home-days")).toBeVisible();
  // The old cards and the scenario select are gone; the optional scenes are inside the tools.
  await expect(page.getByTestId("story-scenario")).toHaveCount(0);
  await expect(page.getByTestId("more-run-capex")).toBeVisible();
});

test("the optional scenes run from the operator tools and never move the story's pointer", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  await openDemo(page);
  await pressNext(page);
  await openDemo(page);
  const progress = await page.getByTestId("demo-progress").textContent();
  await openOperatorTools(page);
  await page.getByTestId("more-run-capex").click();
  await expect(page).toHaveURL(/\/capex/);
  await openDemo(page);
  expect(await page.getByTestId("demo-progress").textContent()).toBe(progress);
});

test("in Chinese the page reads in Chinese with one filled next control", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })));
  await openDemo(page);
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await expect(page.getByTestId("demo-progress")).toContainText(/\d/);
  expect(await filledBrand(page)).toBe(1);
  await expect(page.getByTestId("demo-operator-tools")).toContainText("操作");
  await page.getByTestId("demo-alternate-open").click();
  await expect(page.getByTestId("demo-alternate-loss")).toBeVisible();
  await page.keyboard.press("Escape");
});

test("on a phone the current scene and its button are in the first screen and the two side blocks are closed folds", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openDemo(page);
  await expect(next(page)).toBeInViewport();
  const box = (await next(page).boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(844);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  for (const id of ["demo-alternate-fold", "demo-operator-tools"]) {
    await expect(page.getByTestId(id)).toBeVisible();
    expect(await page.getByTestId(id).evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
  }
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
});

test("the tour points at the current scene on the Demo and its card does not cover it", async ({ page }) => {
  await openDemo(page);
  await page.getByTestId("demo-tour").click();
  const tour = page.getByTestId("tour");
  await expect(tour).toContainText(/current scene/i);
  await page.waitForTimeout(450);
  const [h, c] = [(await page.getByTestId("tour-hole").boundingBox())!, (await page.getByTestId("tour-card").boundingBox())!];
  const overlap = h.x < c.x + c.width && c.x < h.x + h.width && h.y < c.y + c.height && c.y < h.y + h.height;
  expect(overlap).toBe(false);
});
