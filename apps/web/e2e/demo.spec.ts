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
  // Work on the books (a spec before this one) is listed in the dialog first: this is the owner's confirmation.
  const dialog = page.getByTestId("books-dialog");
  // The dialog opens once a fresh read of the books has come back.
  await dialog.waitFor({ state: "visible", timeout: 2000 }).catch(() => undefined);
  if (await dialog.isVisible()) await page.getByTestId("books-dialog-confirm").click();
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
      const approve = page.getByRole("button", { name: /^(Approve|Authorize)/ });
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
  // Complete: the next control starts the story again, from scene one, after the dialog has listed what the books lose.
  await next(page).click();
  await expect(page.getByTestId("books-dialog")).toBeVisible();
  await expect(page.getByTestId("books-dialog-loss").locator("li").first()).toBeVisible();
  await expect(page.getByTestId("books-dialog-cancel")).toBeFocused();
  await page.getByTestId("books-dialog-cancel").click();
  await expect(page.getByTestId("demo-progress")).toContainText(/^All/);
  await next(page).click();
  await page.getByTestId("books-dialog-confirm").click();
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
  // Focus starts on the safe choice: Enter on open keeps the main books.
  await expect(page.getByTestId("demo-alternate-cancel")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  await open.click();
  await expect(dialog).toBeVisible(); // it opens once a fresh read of the books has come back
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
  // Loading a whole company takes the real API a few seconds.
  await expect(banner).toBeVisible({ timeout: 60_000 });
  await expect(banner).toHaveAttribute("role", "status");
  await expect(page.getByTestId("story")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(1);
  await expect(next(page)).toHaveAttribute("href", "/");
  // One click puts the main books back, at the first scene.
  await page.getByTestId("demo-restore").click();
  await expect(banner).toHaveCount(0, { timeout: 60_000 });
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

test("the strip on the other pages follows the server's story: its progress, its chips and its one next control are the page's", async ({ page }) => {
  test.setTimeout(120_000);
  await freshDemo(page);
  await openDemo(page);
  const label = (await next(page).textContent())?.trim();
  await pressNext(page);
  // The page is now Deals, in the Demo shell, with the strip.
  const strip = page.getByRole("region", { name: "Guided demo" });
  await expect(strip.getByTestId("demo-progress")).toHaveText(/Scene 2 of 6/);
  await expect(strip).not.toContainText(/step \d+ of 11/);
  await expect(strip.getByTestId("demo-chip-buyer")).toHaveAttribute("data-state", "done");
  await expect(strip.getByTestId("demo-chip-decision")).toHaveAttribute("data-state", "current");
  await expect(strip.getByTestId("demo-story-link")).toHaveAttribute("href", "/demo");
  // One forward control; it is the server's next, so the page agrees.
  await expect(strip.getByRole("button", { name: /^Back$/ })).toHaveCount(0);
  const stripLabel = (await strip.getByTestId("demo-next").textContent())?.trim();
  expect(stripLabel).not.toBe(label);
  await openDemo(page);
  expect((await next(page).textContent())?.trim()).toBe(stripLabel);
});

test("the filled buttons are the design language's ink, on a direct load of the Demo page and of its dialog", async ({ page }) => {
  await openDemo(page);
  await expect(next(page)).toHaveCSS("background-color", "rgb(23, 29, 30)");
  await page.getByTestId("demo-alternate-open").click();
  await expect(page.getByTestId("demo-alternate-confirm")).toHaveCSS("background-color", "rgb(23, 29, 30)");
});

test("a reset with work on the books asks first and resets nothing on cancel; on fresh books there is no dialog", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  // Fresh books: nothing to lose, so the reset happens at once.
  await openOperatorTools(page);
  await page.getByTestId("demo-tools-books").getByRole("button").first().click();
  await expect(page.getByTestId("books-dialog")).toBeHidden();
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const before = await page.getByTestId("demo-progress").textContent();
  await openOperatorTools(page);
  const reset = page.getByTestId("demo-tools-books").getByRole("button").first();
  await reset.click();
  const dialog = page.getByTestId("books-dialog");
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("books-dialog-loss").locator("li").first()).toBeVisible();
  // The safe choice has the focus: Enter on open changes nothing.
  await expect(page.getByTestId("books-dialog-cancel")).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeHidden();
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  // Escape does the same.
  await reset.click();
  await expect(dialog).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  // Only the confirmation resets.
  await reset.click();
  await page.getByTestId("books-dialog-confirm").click();
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
});

test("the optional scene that replaces the books asks first when work would be lost, and replaces nothing on cancel", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const before = await page.getByTestId("demo-progress").textContent();
  await openOperatorTools(page);
  await page.getByTestId("more-run-walk").click();
  const dialog = page.getByTestId("books-dialog");
  await expect(dialog).toBeVisible();
  await page.getByTestId("books-dialog-cancel").click();
  await expect(dialog).toBeHidden();
  await expect(page).toHaveURL(/\/demo$/);
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  await page.getByTestId("more-run-walk").click();
  await page.getByTestId("books-dialog-confirm").click();
  await expect(page).toHaveURL(/\/verdict/);
});

test("a stale page cannot reset books it did not read: the server's sentence is shown and the main books are untouched", async ({ page, request }, info) => {
  test.skip(info.project.name !== "live", "the stale page is a second writer: the live API");
  test.setTimeout(180_000);
  const api = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
  const owner = { "X-Owner-Token": "demo-owner-token" };
  await freshDemo(page);
  // Page A loads the busy books through the dialog.
  await page.getByTestId("demo-alternate-open").click();
  await page.getByTestId("demo-alternate-confirm").click();
  await expect(page.getByTestId("demo-loaded-banner")).toBeVisible({ timeout: 60_000 });
  // Meanwhile another writer restores the main books and does work on them, through the API.
  expect((await request.post(`${api}/demo/restore`, { headers: owner, data: {} })).ok()).toBeTruthy();
  expect((await request.post(`${api}/offers`, { headers: owner, data: { fixture_id: "EX01_PACKAGE" } })).ok()).toBeTruthy();
  const entries = async () => ((await (await request.get(`${api}/ledger`, { headers: owner })).json()) as { operations: unknown[] }).operations.length;
  const before = await entries();
  // Page A is stale: its "Reset these books" names the busy books, which are no longer loaded.
  await openOperatorTools(page);
  await page.getByTestId("demo-tools-books").getByRole("button").first().click();
  await expect(page.getByTestId("books-notice")).toContainText("changed");
  expect(await entries()).toBe(before);
  // The page reads the story again: it now shows the main books.
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
});

test("a double click on a book-replacing control never confirms, at 390 px", async ({ page }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await freshDemo(page);
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const before = await page.getByTestId("demo-progress").textContent();
  await page.getByTestId("demo-alternate-fold").locator("> summary").click();
  await openOperatorTools(page);
  const controls = [
    { open: page.getByTestId("demo-alternate-open"), dialog: page.getByTestId("demo-alternate-dialog"), confirm: page.getByTestId("demo-alternate-confirm"), cancel: page.getByTestId("demo-alternate-cancel") },
    { open: page.getByTestId("demo-tools-books").getByRole("button").first(), dialog: page.getByTestId("books-dialog"), confirm: page.getByTestId("books-dialog-confirm"), cancel: page.getByTestId("books-dialog-cancel") },
    { open: page.getByTestId("more-run-walk"), dialog: page.getByTestId("books-dialog"), confirm: page.getByTestId("books-dialog-confirm"), cancel: page.getByTestId("books-dialog-cancel") },
  ];
  for (const c of controls) {
    await c.open.scrollIntoViewIfNeeded();
    // The realistic double click: the second click lands wherever the first one put the dialog's confirm, a moment after it opened.
    await c.open.click();
    await expect(c.dialog).toBeVisible();
    const box = (await c.confirm.boundingBox())!;
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await expect(c.confirm).toHaveAttribute("aria-disabled", "true");
    await page.mouse.click(x, y, { clickCount: 2 });
    await page.mouse.click(x, y); // even a single click is ignored until the dialog has been open for a moment
    await expect(c.dialog).toBeVisible();
    await expect(page).toHaveURL(/\/demo$/);
    await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
    await c.cancel.click();
    await expect(c.dialog).toBeHidden();
    expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  }
  // Playwright's own double click on the opener does the same.
  await controls[0].open.dblclick();
  await page.waitForTimeout(200);
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
  await page.keyboard.press("Escape");
  expect(await page.getByTestId("demo-progress").textContent()).toBe(before);
  // A deliberate click, once the dialog is ready, still confirms (and so does the keyboard).
  await controls[1].open.click();
  await expect(controls[1].confirm).not.toHaveAttribute("aria-disabled", "true");
  await controls[1].confirm.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("demo-progress")).toContainText(/Scene 1 of 6/);
});

test("the confirmation is bound to the list shown: a list that changed under an open dialog is replaced, and nothing is reset until a second, informed click", async ({ page, request }, info) => {
  test.skip(info.project.name !== "live", "a second writer: the live API");
  test.setTimeout(180_000);
  const api = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
  const owner = { "X-Owner-Token": "demo-owner-token" };
  await freshDemo(page);
  const entries = async () => ((await (await request.get(`${api}/ledger`, { headers: owner })).json()) as { operations: unknown[] }).operations.length;
  // The page is open on fresh main books and so is the dialog (it always says what loading the alternate books does).
  await page.getByTestId("demo-alternate-open").click();
  const dialog = page.getByTestId("demo-alternate-dialog");
  await expect(dialog).toBeVisible();
  const emptyList = await page.getByTestId("demo-alternate-loss").innerText();
  // Meanwhile another writer walks the story to the agreement through the API.
  const post = async (path: string, data: object) => {
    const res = await request.post(`${api}${path}`, { headers: owner, data });
    expect(res.ok(), path).toBeTruthy();
    return res.json();
  };
  const { offer } = await post("/offers", { fixture_id: "EX01_PACKAGE" });
  await post(`/offers/${offer.offer_id}/evaluate`, { fixture_id: "EX01_PACKAGE" });
  await post(`/negotiate/${offer.offer_id}`, { buyer_profile: "cooperative" });
  const before = await entries();
  // The first confirm, on the list that was shown, replaces nothing: the dialog says the list changed and shows the true one.
  const confirm = page.getByTestId("demo-alternate-confirm");
  await expect(confirm).not.toHaveAttribute("aria-disabled", "true");
  await confirm.click();
  await expect(page.getByTestId("demo-alternate-note")).toBeVisible();
  await expect(dialog).toBeVisible();
  expect(await page.getByTestId("demo-alternate-loss").innerText()).not.toBe(emptyList);
  expect(await entries()).toBe(before);
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
  // The second, informed click loads the busy books.
  await expect(confirm).not.toHaveAttribute("aria-disabled", "true");
  await confirm.click();
  await expect(page.getByTestId("demo-loaded-banner")).toBeVisible({ timeout: 60_000 });
});
