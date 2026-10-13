import { expect, test } from "./fixtures";
import { resetBooks } from "./helpers";

/** Live only: the header's Ask FLOW sends the question under the Home's scope (the URL contract) and the panel's chip says the server's own label for the scope it answered in (`scope_used`). */
test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name !== "live", "live-only: the real chat route and its scope contract");
});

test("Enter in the header sends the Home's scope with the question and the chip shows the server's label", async ({ page, request }) => {
  await resetBooks(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/?customer=BUYER-1");
  await expect(page.getByTestId("ask-input")).toBeVisible();
  const sent = page.waitForRequest((r) => r.method() === "POST" && /\/nl(\?|$)/.test(new URL(r.url()).pathname + new URL(r.url()).search));
  await page.getByTestId("ask-input").fill("What do I need to know about this customer?");
  await page.getByTestId("ask-input").press("Enter");
  const body = (await sent).postDataJSON() as { scope?: Record<string, string>; text: string };
  expect(body.text).toBe("What do I need to know about this customer?");
  expect(body.scope).toEqual({ customer: "BUYER-1" });
  const panel = page.getByTestId("chat-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("chat-reply").first()).toBeVisible({ timeout: 30000 });
  // The server answered in the customer's scope and said it in its own words.
  await expect(panel.getByTestId("chat-scope")).toHaveAttribute("data-scope", "customer");
  await expect(panel.getByTestId("chat-scope")).toContainText("Foshan");
  await expect(panel.getByTestId("chat-scope")).not.toContainText("this customer");
});

test("on the company's Home the scope is empty and the server answers in the company", async ({ page, request }) => {
  await resetBooks(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const sent = page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname.endsWith("/nl"));
  await page.getByTestId("ask-input").fill("When does the invoice financing land?");
  await page.getByTestId("ask-input").press("Enter");
  const body = (await sent).postDataJSON() as { scope?: Record<string, string> };
  expect(body.scope).toEqual({});
  await expect(page.getByTestId("chat-panel").getByTestId("chat-reply").first()).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId("chat-scope")).toHaveAttribute("data-scope", "company");
});
