import { DEMO_TOKEN, expect, test } from "./fixtures";
import { en, zh } from "../lib/dictionary";
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
  await expect(panel.getByTestId("chat-scope")).toHaveAttribute("data-kind", "customer");
  await expect(panel.getByTestId("chat-discussing")).toContainText("Foshan");
  await expect(panel.getByTestId("chat-discussing")).toHaveAttribute("data-mismatch", "false");
});

test("on the company's Home the scope is empty and the server answers in the company", async ({ page, request }) => {
  await resetBooks(request);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const sent = page.waitForRequest((r) => r.method() === "POST" && new URL(r.url()).pathname.endsWith("/nl"));
  await page.getByTestId("ask-input").fill("When does the invoice financing land?");
  await page.getByTestId("ask-input").press("Enter");
  const body = (await sent).postDataJSON() as { scope?: Record<string, string> };
  expect(body.scope ?? {}).toEqual({}); // the company is no scope key at all
  await expect(page.getByTestId("chat-panel").getByTestId("chat-reply").first()).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId("chat-scope")).toHaveAttribute("data-kind", "company");
});

// Every placeholder is a question the chat answers (round three): asked in both languages against the real chat route, none is out of scope or ambiguous, and each gets a reply.
const API = `http://localhost:${process.env.E2E_API_PORT ?? 8000}`;
for (const lang of ["en", "zh"] as const) {
  const d = lang === "en" ? en : zh;
  const questions = [d["ask.ph.1"], d["ask.ph.2"], d["ask.ph.3"], d["ask.ph.4"].replace("{name}", "Foshan"), d["ask.ph.5"]];
  test(`the header's example questions are answered by the chat (${lang}): none is out of scope or ambiguous`, async ({ request }) => {
    await resetBooks(request);
    for (const [i, text] of questions.entries()) {
      const res = await request.post(`${API}/nl`, { headers: { "X-Owner-Token": DEMO_TOKEN }, data: { session_id: `ph-${lang}-${i}`, actor: "OWNER", text, lang, context: { page: "/" }, scope: {} } });
      expect(res.ok(), text).toBeTruthy();
      const body = (await res.json()) as { intent: string; reply: string; clarification: unknown };
      expect(["OUT_OF_SCOPE", "AMBIGUOUS"], `${text} -> ${body.intent}`).not.toContain(body.intent);
      expect(body.clarification, text).toBeNull();
      expect(body.reply.trim().length, text).toBeGreaterThan(0);
    }
  });
}
