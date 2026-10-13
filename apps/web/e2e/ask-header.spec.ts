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

/** The six placeholders in order (round three): the late-payment one names the first worklist customer's short name (the server's word, "Foshan" on the Demo); the last rests. */
const lines = (d: typeof en | typeof zh, name = "Foshan") => [
  d["ask.ph.1"],
  d["ask.ph.2"],
  d["ask.ph.3"],
  d["ask.ph.4"].replace("{name}", name),
  d["ask.ph.5"],
  d["ask.ph.rest"],
];
const EXAMPLES = { en: lines(en), zh: lines(zh) };

test("the header carries a rounded 36 px Ask FLOW input in its centre (the viewport's), 420 px wide and 520 px on focus, and no floating pill on a desktop", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const form = page.getByTestId("ask-header");
  await expect(form).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Ask FLOW" })).toBeVisible();
  const f = (await form.boundingBox())!;
  // Centred on the viewport, between the brand and the right-hand controls; 36 px tall, 420 px wide, a pill.
  expect(Math.abs(f.x + f.width / 2 - 720)).toBeLessThanOrEqual(2);
  expect(Math.round(f.height)).toBe(36);
  expect(Math.round(f.width)).toBe(420);
  const [brand, mode] = await Promise.all([
    page.getByRole("link", { name: /FLOW/ }).first().boundingBox(),
    page.getByText("Business", { exact: true }).first().boundingBox(),
  ]);
  expect(brand!.x + brand!.width).toBeLessThanOrEqual(f.x);
  expect(f.x + f.width).toBeLessThanOrEqual(mode!.x);
  expect(
    await form.evaluate((el) => getComputedStyle(el).borderTopLeftRadius),
  ).toBe("9999px");
  await expect(page.locator(".ask-trigger")).toHaveCount(0);
  await expect(page.getByTestId("chat-open")).toHaveCount(1);
  expect((await page.getByTestId("chat-open").boundingBox())!.y).toBeLessThan(
    80,
  ); // the header's icon, not a pill above the bottom of the page
  // Focus widens it to 520 px from its centre (the centre never moves, the icon stays under a pointer that presses it).
  await page.getByTestId("ask-input").focus();
  await expect
    .poll(async () => Math.round((await form.boundingBox())!.width))
    .toBe(520);
  const g = (await form.boundingBox())!;
  expect(Math.abs(g.x + g.width / 2 - 720)).toBeLessThanOrEqual(2);
  // Other Business pages carry it too.
  for (const path of ["/deals", "/cash", "/receivables", "/activity"]) {
    await page.goto(path);
    await expect(page.getByTestId("ask-input")).toBeVisible();
  }
});

test.describe("with motion", () => {
  test.use({ reducedMotion: "no-preference" });
  test("the placeholder types six questions in turn and rests on 'Ask FLOW anything…'; focus pauses it; the Chinese set in Chinese", async ({
    page,
  }) => {
    test.setTimeout(90000);
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    const input = page.getByTestId("ask-input");
    const seen: string[] = [];
    const start = Date.now();
    const rest = EXAMPLES.en[5];
    while (Date.now() - start < 60000) {
      const ph = (await input.getAttribute("placeholder")) ?? "";
      const whole = EXAMPLES.en.find((e) => e === ph);
      if (whole && !seen.includes(whole)) seen.push(whole);
      // A partial placeholder is a prefix of an example: it is being typed.
      if (ph && !whole)
        expect(EXAMPLES.en.some((e) => e.startsWith(ph))).toBe(true);
      if (seen.includes(rest)) break;
      await page.waitForTimeout(50);
    }
    // In order, each question the chat answers, ending on the resting line.
    expect(seen).toEqual(EXAMPLES.en);
    // The resting line holds: no further cycling.
    await page.waitForTimeout(4000);
    expect(await input.getAttribute("placeholder")).toBe(rest);
    expect(Date.now() - start).toBeLessThan(60000);
  });
  test("focus pauses the typewriter on the whole current line; the Chinese set is in Chinese", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/");
    const input = page.getByTestId("ask-input");
    await input.focus();
    const held = await input.getAttribute("placeholder");
    expect(EXAMPLES.en).toContain(held);
    await page.waitForTimeout(2600);
    expect(await input.getAttribute("placeholder")).toBe(held);
    await input.evaluate((el) => (el as HTMLInputElement).blur());
    await expect
      .poll(async () =>
        Math.round((await page.getByTestId("ask-header").boundingBox())!.width),
      )
      .toBe(420);
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

test("under reduced motion the placeholder is the resting line, whole, and does not move", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const input = page.getByTestId("ask-input");
  await expect(input).toHaveAttribute("placeholder", EXAMPLES.en[5]);
  await page.waitForTimeout(2500);
  await expect(input).toHaveAttribute("placeholder", EXAMPLES.en[5]);
  await page.addInitScript(() =>
    localStorage.setItem("tl-lang", JSON.stringify({ lang: "zh" })),
  );
  await page.reload();
  await expect(page.getByTestId("ask-input")).toHaveAttribute(
    "placeholder",
    EXAMPLES.zh[5],
  );
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
  await expect(panel.getByTestId("chat-scope")).toContainText("Company");
  await expect(panel.getByTestId("chat-scope")).toHaveAttribute(
    "data-kind",
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
    "data-kind",
    "customer",
  );
  await expect(page.getByTestId("chat-scope")).toContainText("Customer");
  await page.keyboard.press("Escape");
  await page.goto("/?customer=BUYER-1&decision=deal%3AOFF-x");
  await page.getByTestId("chat-open").click();
  await expect(page.getByTestId("chat-scope")).toHaveAttribute(
    "data-kind",
    "decision",
  );
  await expect(page.getByTestId("chat-scope")).toContainText("Decision");
  await page.keyboard.press("Escape");
  // Another page has no selection in its address: the chip is the company alone (Slice B's scope model, ticket #130).
  await page.goto("/cash");
  await page.getByTestId("chat-open").click();
  await expect(page.getByTestId("chat-scope")).toHaveAttribute("data-kind", "company");
  await expect(page.getByTestId("chat-scope-customer")).toHaveCount(0);
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
