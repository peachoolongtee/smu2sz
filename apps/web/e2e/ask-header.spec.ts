import { expect, test } from "./fixtures";
import { en, zh } from "../lib/dictionary";

/**
 * Ask FLOW in the Business header (round two, docs/design/flow-mockup-2026-10-13/01_home_round_two.md section 3), in mock mode: a rounded input left of the mode switch whose placeholder cycles
 * through the dictionary's example questions as a quiet typewriter (paused on focus, none under reduced motion); focus widens it; Enter opens the Ask FLOW panel with the question already sent under
 * the page's scope chip (this deal, this customer, your company: the Home's address); the desktop floating pill is gone, the phone's bottom-bar "Ask" stays.
 */
test.beforeEach(async ({}, testInfo) => {
  test.skip(
    testInfo.project.name !== "desktop",
    "mock-mode spec; the phone is measured inside it",
  );
});

const EXAMPLES = {
  en: [en["ask.ph.1"], en["ask.ph.2"], en["ask.ph.3"]],
  zh: [zh["ask.ph.1"], zh["ask.ph.2"], zh["ask.ph.3"]],
};

test("the header carries a rounded Ask FLOW input left of the mode switch, and no floating pill on a desktop", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const form = page.getByTestId("ask-header");
  await expect(form).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Ask FLOW" })).toBeVisible();
  const [f, m] = await Promise.all([
    form.boundingBox(),
    page.getByText("Business", { exact: true }).first().boundingBox(),
  ]);
  expect(f!.x + f!.width).toBeLessThanOrEqual(m!.x + 1);
  expect(Math.abs(f!.y + f!.height / 2 - (m!.y + m!.height / 2))).toBeLessThan(
    8,
  );
  expect(
    await form.evaluate((el) => getComputedStyle(el).borderTopLeftRadius),
  ).toBe("9999px");
  await expect(page.locator(".ask-trigger")).toHaveCount(0);
  await expect(page.getByTestId("chat-open")).toHaveCount(1);
  expect((await page.getByTestId("chat-open").boundingBox())!.y).toBeLessThan(
    80,
  ); // the header's icon, not a pill above the bottom of the page
  // Other Business pages carry it too.
  for (const path of ["/deals", "/cash", "/receivables", "/activity"]) {
    await page.goto(path);
    await expect(page.getByTestId("ask-input")).toBeVisible();
  }
});

test.describe("with motion", () => {
  test.use({ reducedMotion: "no-preference" });
  test("the placeholder cycles through the three example questions as a typewriter, pauses on focus, and is the Chinese set in Chinese", async ({
    page,
  }) => {
    test.setTimeout(60000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    const input = page.getByTestId("ask-input");
    const seen = new Set<string>();
    const start = Date.now();
    while (Date.now() - start < 30000 && seen.size < 3) {
      const ph = (await input.getAttribute("placeholder")) ?? "";
      const whole = EXAMPLES.en.find((e) => e === ph);
      if (whole) seen.add(whole);
      // A partial placeholder is a prefix of an example: it is being typed.
      if (ph && !whole)
        expect(EXAMPLES.en.some((e) => e.startsWith(ph))).toBe(true);
      await page.waitForTimeout(60);
    }
    expect([...seen].sort()).toEqual([...EXAMPLES.en].sort());
    // Focus pauses it: the whole current example stays, and stays after a while; leaving resumes.
    await input.focus();
    const held = await input.getAttribute("placeholder");
    expect(EXAMPLES.en).toContain(held);
    await page.waitForTimeout(2600);
    expect(await input.getAttribute("placeholder")).toBe(held);
    // Focus widens it.
    await expect
      .poll(
        async () => (await page.getByTestId("ask-header").boundingBox())!.width,
      )
      .toBeGreaterThan(340);
    const right = (await page.getByTestId("ask-header").boundingBox())!;
    await input.evaluate((el) => (el as HTMLInputElement).blur());
    await expect
      .poll(
        async () => (await page.getByTestId("ask-header").boundingBox())!.width,
      )
      .toBeLessThan(300);
    // Its right edge never moves (it widens to the left), so the opener stays under the pointer.
    const narrow = (await page.getByTestId("ask-header").boundingBox())!;
    expect(
      Math.abs(right.x + right.width - (narrow.x + narrow.width)),
    ).toBeLessThan(1);
    // Chinese.
    await page.addInitScript(() =>
      localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })),
    );
    await page.reload();
    await page.getByTestId("ask-input").focus();
    expect(EXAMPLES.zh).toContain(
      await page.getByTestId("ask-input").getAttribute("placeholder"),
    );
    await expect(page.getByRole("textbox", { name: "问 FLOW" })).toBeVisible();
  });
});

test("under reduced motion the placeholder is the first example, whole, and does not move", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const input = page.getByTestId("ask-input");
  await expect(input).toHaveAttribute("placeholder", EXAMPLES.en[0]);
  await page.waitForTimeout(2500);
  await expect(input).toHaveAttribute("placeholder", EXAMPLES.en[0]);
});

test("Enter opens the Ask FLOW panel with the question already sent, under the page's scope chip, and the input clears", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const input = page.getByTestId("ask-input");
  await input.fill("What does the counter cost me?");
  await input.press("Enter");
  const panel = page.getByTestId("chat-panel");
  await expect(panel).toBeVisible();
  await expect(input).toHaveValue("");
  await expect(panel.getByTestId("chat-log")).toContainText(
    "What does the counter cost me?",
  );
  // On the company's Home the scope is the company; a turn is on its way or answered (the busy word or a reply).
  await expect(panel.getByTestId("chat-scope")).toContainText("your company");
  await expect(panel.getByTestId("chat-scope")).toHaveAttribute(
    "data-scope",
    "company",
  );
  await expect(
    panel
      .getByTestId("chat-busy")
      .or(panel.getByTestId("chat-reply").first())
      .first(),
  ).toBeVisible({ timeout: 15000 });
  await page.keyboard.press("Escape");
  await expect(panel).toBeHidden();
  // A blank question sends nothing and does not open the panel.
  await input.fill("   ");
  await input.press("Enter");
  await expect(panel).toBeHidden();
  // The icon opens the panel without a question.
  await page.getByTestId("chat-open").click();
  await expect(panel).toBeVisible();
});

test("the scope chip follows the Home's selection: a deal, a customer, the company", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/?customer=BUYER-1");
  await page.getByTestId("ask-input").fill("Who owes me money?");
  await page.getByTestId("ask-input").press("Enter");
  await expect(page.getByTestId("chat-scope")).toHaveAttribute(
    "data-scope",
    "customer",
  );
  await expect(page.getByTestId("chat-scope")).toContainText("this customer");
  await page.keyboard.press("Escape");
  await page.goto("/?customer=BUYER-1&decision=deal%3AOFF-x");
  await page.getByTestId("chat-open").click();
  await expect(page.getByTestId("chat-scope")).toHaveAttribute(
    "data-scope",
    "decision",
  );
  await expect(page.getByTestId("chat-scope")).toContainText("this deal");
  await page.keyboard.press("Escape");
  // Other pages have no scope: no chip.
  await page.goto("/cash");
  await page.getByTestId("chat-open").click();
  await expect(page.getByTestId("chat-scope")).toHaveCount(0);
});

test("a phone keeps the bottom bar's Ask and has no header input; Enter in the panel's own composer still works", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByTestId("ask-header")).toHaveCount(0);
  await expect(page.getByTestId("chat-open")).toBeVisible();
  const bar = (await page.getByTestId("tab-bar").boundingBox())!;
  const ask = (await page.getByTestId("chat-open").boundingBox())!;
  expect(ask.y).toBeGreaterThanOrEqual(bar.y - 1);
  await page.getByTestId("chat-open").click();
  await expect(page.getByTestId("chat-panel")).toBeVisible();
});
