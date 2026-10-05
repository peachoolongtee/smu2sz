import { expect, test } from "./fixtures";

/**
 * The simulated inbox (mock mode): each message says where it came from and who sent it, opening one reads it (no
 * separate read button), reopening a read message does not read it again, and a sender outside the registry is marked.
 */

test.beforeEach(async ({}, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the inbox copies are the recorded demo messages");
});

test("each message shows its source and sender; opening one reads it", async ({ page }) => {
  await page.goto("/inbox");
  const wechat = page.getByTestId("inbox-msg-EX01");
  await expect(wechat).toContainText("WeChat");
  await expect(wechat).toContainText("Foshan Home Retail Co.");
  await expect(wechat).toContainText("Li Wei");
  await expect(page.getByTestId("inbox-msg-EX01B")).toContainText("Email");
  await expect(page.getByTestId("inbox-msg-SEC")).toContainText("Not in your contacts");
  await expect(page.getByText("Pick a message")).toBeVisible();

  await wechat.click();
  await expect(wechat).toContainText("Showing below");
  await expect(page.locator("#doc-EX01-msg")).toContainText("Foshan Home Retail Co. · Li Wei");
  await expect(page.locator("#doc-EX01-msg")).toContainText("WeChat");
  await expect(page.getByRole("button", { name: "Check against my limits" })).toBeVisible();

  // Another message, then back: the first is shown again from the session, already marked read.
  await page.getByTestId("inbox-msg-SEC").click();
  await expect(page.locator("#doc-SEC-msg")).toBeVisible();
  await expect(wechat).toContainText("Read");
  await wechat.click();
  await expect(page.locator("#doc-EX01-msg")).toBeVisible();
});
