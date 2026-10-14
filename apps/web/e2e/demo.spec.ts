import type { Page } from "@playwright/test";
import { DEMO_TOKEN, expect, test } from "./fixtures";
import { filledBrand, openOperatorTools } from "./helpers";

/**
 * The Demo story (Slice D, ticket #145), read from GET /demo/story. The same spec runs in both Playwright projects: `desktop` (the recorded reads, picked by the mock's own state)
 * and `live` (the real FastAPI service). One current scene with the page's only filled button, the owner's step that only opens the approval, three cards for "Which books?" (each Load through the guarded dialog) with a one-click restore, the operator tools folded away and the proof appendix. Every sentence on the page is the server's.
 */

const next = (page: Page) => page.getByTestId("demo-next");

async function openDemo(page: Page): Promise<void> {
  await page.goto("/demo");
  await expect(page.getByTestId("demo-current")).toBeVisible();
}

/** The story page as the owner would read it, reset first: the opening books (live shares one API between specs). */
async function freshDemo(page: Page): Promise<void> {
  await openDemo(page);
  // Other books than the main ones may be loaded (a spec before this one): the restore puts the main books back first.
  if (await page.getByTestId("demo-loaded-banner").isVisible()) {
    await page.getByTestId("demo-restore").click();
    const asked = page.getByTestId("books-dialog");
    await asked.waitFor({ state: "visible", timeout: 2000 }).catch(() => undefined);
    if (await asked.isVisible()) await page.getByTestId("books-dialog-confirm").click();
    await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0, { timeout: 60_000 });
  }
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
  // Complete: the card says so (never another books' name) and the next control, "Start again", starts the story from scene one after the dialog has listed what the books lose.
  // Activity's row for the bank's receipt says the amount and the payer; the bank's reference is evidence, in the row's fold.
  await page.goto("/activity");
  const receipt = page.getByTestId("activity-list").getByTestId("activity-row").filter({ hasText: /Received ¥/ }).first();
  await expect(receipt).toBeVisible();
  await expect(receipt.getByTestId("activity-event")).toContainText(/Received ¥[\d,.]+ from /);
  expect(await receipt.innerText()).not.toMatch(/DEMO-RCPT/);
  await receipt.getByTestId("activity-evidence").locator("> summary").click();
  await expect(receipt.getByTestId("activity-record-bank")).toContainText("DEMO-RCPT-1");
  await openDemo(page);
  await expect(page.getByTestId("demo-current-title")).toHaveText("The story is complete");
  await expect(next(page)).toHaveText("Start again");
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

test("Which books: Load on the busy card, with work on the books, shows the loss in a dialog; cancel changes nothing, confirm loads the busy books and restore brings the story back at scene one", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  const before = await page.getByTestId("demo-progress").textContent();
  const open = page.getByTestId("demo-scenario-load-busy");
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
  await expect(page.getByTestId("demo-books").getByRole("heading", { level: 2 })).toHaveText("用哪套账目？");
  await expect(page.getByTestId("demo-scenario-load-busy")).toHaveText("加载");
  await expect(page.getByTestId("demo-scenario-help-busy")).toHaveText("三位客户、六项谈判、一项待批准事项和逾期发票");
  await expect(page.getByTestId("demo-busy-home")).toHaveText("从首页查看 →");
});

test("on a phone the three books cards are in the first screen before the scene card, and the operator tools are a closed fold", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openDemo(page);
  await expect(page.getByTestId("demo-scenario-load-busy")).toBeInViewport();
  const [cards, scene] = [(await page.getByTestId("demo-books").boundingBox())!, (await page.getByTestId("demo-current").boundingBox())!];
  expect(cards.y + cards.height).toBeLessThanOrEqual(scene.y + 1);
  for (const id of ["golden", "busy", "short"]) {
    const card = (await page.getByTestId(`demo-scenario-${id}`).boundingBox())!;
    expect(card.y + card.height, `the ${id} card is inside the first screen`).toBeLessThanOrEqual(844);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false);
  await expect(page.getByTestId("demo-alternate")).toHaveCount(0);
  await expect(page.getByTestId("demo-operator-tools")).toBeVisible();
  expect(await page.getByTestId("demo-operator-tools").evaluate((el) => (el as HTMLDetailsElement).open)).toBe(false);
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

test("the filled buttons are the design language's ink, on a direct load of the Demo page, of its dialog, of the story's strip and of the tour", async ({ page }) => {
  test.setTimeout(180_000);
  const INK = "rgb(23, 29, 30)";
  await freshDemo(page);
  await openDemo(page);
  await expect(next(page)).toHaveCSS("background-color", INK);
  // The tour's last button ("Done") is the ink primary too, not the engine's blue.
  await page.getByTestId("demo-tour").click();
  await expect(page.getByTestId("tour")).toBeVisible();
  for (let i = 0; i < 4 && !(await page.getByTestId("tour-skip").count() === 0); i++) await page.getByTestId("tour-next").click();
  await expect(page.getByTestId("tour-next")).toHaveText("Done");
  await expect(page.getByTestId("tour-next")).toHaveCSS("background-color", INK);
  await page.getByTestId("tour-next").click();
  // With work on the books the dialog opens, and its one filled button is ink.
  for (let i = 0; i < 2; i++) {
    await openDemo(page);
    await pressNext(page);
  }
  await openDemo(page);
  await page.getByTestId("demo-scenario-load-busy").click();
  await expect(page.getByTestId("demo-alternate-confirm")).toHaveCSS("background-color", INK);
  await page.getByTestId("demo-alternate-cancel").click();
  // The story's strip on another page: its one forward control is ink as well (the owner's step is "Review the approval", a link).
  await pressNext(page);
  await expect(page.getByRole("region", { name: "Guided demo" }).getByTestId("demo-next")).toHaveCSS("background-color", INK);
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
  // Page A loads the busy books from its card (fresh books: nothing to lose, so no dialog).
  await page.getByTestId("demo-scenario-load-busy").click();
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
  await openOperatorTools(page);
  const controls = [
    { open: page.getByTestId("demo-scenario-load-busy"), dialog: page.getByTestId("demo-alternate-dialog"), confirm: page.getByTestId("demo-alternate-confirm"), cancel: page.getByTestId("demo-alternate-cancel") },
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

test("the confirmation is bound to the list shown: books that gained work under an open page are listed by the server's refusal, and nothing is reset until a second, informed click", async ({ page, request }, info) => {
  test.skip(info.project.name !== "live", "a second writer: the live API");
  test.setTimeout(180_000);
  const api = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
  const owner = { "X-Owner-Token": "demo-owner-token" };
  await freshDemo(page);
  const entries = async () => ((await (await request.get(`${api}/ledger`, { headers: owner })).json()) as { operations: unknown[] }).operations.length;
  // The page is open on fresh main books: it believes a load loses nothing, so Load would go straight through.
  const dialog = page.getByTestId("demo-alternate-dialog");
  await expect(dialog).toBeHidden();
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
  // The first click replaces nothing: the server refuses, and the dialog opens with the true list and the server's sentence.
  await page.getByTestId("demo-scenario-load-busy").click();
  await expect(dialog).toBeVisible();
  await expect(page.getByTestId("demo-alternate-note")).toBeVisible();
  await expect(page.getByTestId("demo-alternate-loss").locator("li").first()).toBeVisible();
  expect(await entries()).toBe(before);
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
  // The second, informed click loads the busy books.
  const confirm = page.getByTestId("demo-alternate-confirm");
  await expect(confirm).not.toHaveAttribute("aria-disabled", "true");
  await confirm.click();
  await expect(page.getByTestId("demo-loaded-banner")).toBeVisible({ timeout: 60_000 });
  // Leave the shared API on the main books for the specs after this one.
  await page.getByTestId("demo-restore").click();
  const asked = page.getByTestId("books-dialog");
  await asked.waitFor({ state: "visible", timeout: 2000 }).catch(() => undefined);
  if (await asked.isVisible()) await page.getByTestId("books-dialog-confirm").click();
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0, { timeout: 60_000 });
});

test("Which books comes first: three cards with their help, the loaded one marked and without a button, the busy one linking to Home; the old fold and the engine sidebar are gone", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  await openDemo(page);
  const books = page.getByTestId("demo-books");
  await expect(books.getByRole("heading", { level: 2 })).toHaveText("Which books?");
  expect(await books.evaluate((el, ref) => !!(el.compareDocumentPosition(document.querySelector(`[data-testid="${ref}"]`)!) & Node.DOCUMENT_POSITION_FOLLOWING), "demo-current")).toBe(true);
  await expect(page.getByTestId("demo-scenario-golden").locator("h3")).toHaveText("Golden story");
  await expect(page.getByTestId("demo-scenario-busy").locator("h3")).toHaveText("Busy company");
  await expect(page.getByTestId("demo-scenario-short").locator("h3")).toHaveText("Short facilities");
  for (const id of ["golden", "busy", "short"]) await expect(page.getByTestId(`demo-scenario-help-${id}`)).not.toBeEmpty();
  await expect(page.getByTestId("demo-scenario-help-busy")).toHaveText("Three customers, six negotiations, an approval and overdue invoices");
  // The golden books are loaded: marked, no button; the other two offer Load.
  await expect(page.getByTestId("demo-scenario-golden")).toHaveAttribute("data-loaded", "true");
  await expect(page.getByTestId("demo-scenario-loaded-golden")).toHaveText("Loaded");
  await expect(page.getByTestId("demo-scenario-golden").getByRole("button")).toHaveCount(0);
  await expect(page.getByTestId("demo-scenario-load-busy")).toBeVisible();
  await expect(page.getByTestId("demo-scenario-load-short")).toBeVisible();
  await expect(page.getByTestId("demo-busy-home")).toHaveText("Explore it from Home →");
  await expect(page.getByTestId("demo-busy-home")).toHaveAttribute("href", "/");
  // The old fold is gone and the one filled button is still the next control.
  await expect(page.getByTestId("demo-alternate")).toHaveCount(0);
  await expect(page.getByTestId("demo-alternate-fold")).toHaveCount(0);
  expect(await filledBrand(page)).toBe(1);
  // From fresh books one click loads the busy books: no dialog, the card is marked and the restore is offered.
  await page.getByTestId("demo-scenario-load-busy").click();
  await expect(page.getByTestId("books-dialog")).toBeHidden();
  await expect(page.getByTestId("demo-scenario-busy")).toHaveAttribute("data-loaded", "true", { timeout: 60_000 });
  await expect(page.getByTestId("demo-scenario-busy").getByRole("button")).toHaveCount(0);
  await expect(page.getByTestId("demo-scenario-load-golden")).toBeVisible();
  await expect(page.getByTestId("demo-loaded-banner")).toBeVisible();
  await expect(page.getByTestId("demo-current-title")).toHaveText("Busy company");
  // The short-facilities books name themselves, never "Busy company".
  await page.getByTestId("demo-scenario-load-short").click();
  await expect(page.getByTestId("demo-scenario-short")).toHaveAttribute("data-loaded", "true", { timeout: 60_000 });
  await expect(page.getByTestId("demo-current-title")).toHaveText("Short facilities");
  // One click restores the main books, which are the golden card again.
  await page.getByTestId("demo-restore").click();
  await expect(page.getByTestId("demo-scenario-golden")).toHaveAttribute("data-loaded", "true", { timeout: 60_000 });
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
});

test("the busy card's Load is visible without scrolling at 1440 and at 390, and from worked books it asks first", async ({ page }) => {
  test.setTimeout(180_000);
  await freshDemo(page);
  for (const size of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(size);
    await openDemo(page);
    await expect(page.getByTestId("demo-scenario-load-busy")).toBeInViewport();
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDemo(page);
  await pressNext(page);
  await openDemo(page);
  await page.getByTestId("demo-scenario-load-busy").click();
  await expect(page.getByTestId("demo-alternate-dialog")).toBeVisible();
  await expect(page.getByTestId("demo-alternate-loss").locator("li").first()).toBeVisible();
  await page.getByTestId("demo-alternate-cancel").click();
  await expect(page.getByTestId("demo-loaded-banner")).toHaveCount(0);
});

/** The engine destinations the server lists in Operator tools (`operator_tools`, group `engine`, the items with a link): the recorded read in mock mode, the API's own in live mode. */
async function serverEngineLinks(request: import("@playwright/test").APIRequestContext, info: { project: { name: string } }): Promise<number> {
  type Tools = { groups: { key: string; items: { href?: string }[] }[] };
  let tools: Tools;
  if (info.project.name === "live") {
    const res = await request.get(`http://localhost:${process.env.E2E_API_PORT ?? 8000}/demo/story?lang=en`, { headers: { "X-Owner-Token": DEMO_TOKEN } });
    expect(res.ok()).toBeTruthy();
    tools = ((await res.json()) as { operator_tools: Tools }).operator_tools;
  } else {
    const { readFileSync } = await import("node:fs");
    const recorded = JSON.parse(readFileSync("mocks/slice_d/story.json", "utf8")) as Record<string, { en: { operator_tools: Tools } }>;
    tools = recorded.fresh.en.operator_tools;
  }
  const links = tools.groups.find((g) => g.key === "engine")!.items.filter((i) => i.href).length;
  expect(links, "the server lists engine views").toBeGreaterThan(0);
  return links;
}

test("the Demo uses the app's own rail: no engine-views sidebar, and the engine views are reachable inside Operator tools", async ({ page, request }, info) => {
  test.skip(info.project.name === "phone", "the rail is the desktop's; the phone has the tab bar");
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDemo(page);
  await expect(page.getByTestId("nav-rail")).toBeVisible();
  await expect(page.getByTestId("nav-pills").getByRole("link")).toHaveCount(5);
  await expect(page.getByText("Engine views", { exact: true })).toBeHidden();
  for (const name of ["Mandate", "Verdict", "Ledger", "Reconciliation"]) await expect(page.getByTestId("nav-pills").getByRole("link", { name })).toHaveCount(0);
  await expect(page.getByTestId("demo-strip")).toBeVisible();
  await openOperatorTools(page);
  const engine = page.getByTestId("demo-tools-engine");
  await expect(engine).toBeVisible();
  await expect(engine.getByRole("link")).toHaveCount(await serverEngineLinks(request, info)); // the engine destinations the server lists (it writes this list)
  await engine.getByRole("link", { name: "Ledger" }).click();
  await expect(page).toHaveURL(/\/ledger/);
  // An engine view wears the same shell: the rail and the Demo strip, and the story's way back.
  await expect(page.getByTestId("nav-rail")).toBeVisible();
  await expect(page.getByTestId("demo-strip")).toBeVisible();
});

test("the proof appendix: the chain badge is the server's verdict (green when valid) and its scope is text under it, not a tooltip", async ({ page }) => {
  await freshDemo(page);
  await openDemo(page);
  const chain = page.getByTestId("demo-chain");
  await expect(chain).toHaveAttribute("data-valid", "true");
  await expect(chain).toHaveText("Record chain checks passed");
  const scope = page.getByTestId("demo-chain-scope");
  await expect(scope).toBeVisible();
  await expect(scope).toContainText("does not confirm bank facts or buyer promises");
  // The ok tone, not the red of a failed check.
  await expect(chain.locator("span").first()).toHaveClass(/bg-ok-bg/);
});

test("operator tools hold the clock once: the day's own control, not a second pair of advance buttons", async ({ page }) => {
  await openDemo(page);
  await openOperatorTools(page);
  const clock = page.getByTestId("demo-tools-clock");
  await expect(clock.getByRole("button", { name: /^Advance [17] days?$/ })).toHaveCount(0);
  await expect(clock.getByRole("button", { name: /Advance time/ })).toHaveCount(1);
});
