import type { Page } from "@playwright/test";
import { expect, test } from "./fixtures";

/**
 * The owner home (`/`) in mock mode: six sections, the agent's opener after the clock reaches day 34, "Go ahead" running the
 * recorded cure, and "Let the agent fix this" on an actionable alert. The mock replays answers recorded from the real API
 * on the demo path (deal, receipt on day 2, clock to day 34), so every amount here is a server string.
 */

test.beforeEach(async ({ context }, testInfo) => {
  test.skip(testInfo.project.name === "live", "mock-mode spec: the recorded demo path");
  // Owner calls need a token; mock mode accepts any non-empty one (the sign-in dialog is covered by chat.spec.ts).
  await context.addInitScript(() => {
    try {
      sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "mock-owner" }));
    } catch {
      /* storage unavailable */
    }
  });
});

async function advanceTo34(page: Page) {
  await page.getByTestId("home-days").fill("34");
  await page.getByTestId("home-advance").click();
  await expect(page.getByTestId("home-day")).toHaveText("Day 34");
}

test("home renders the six sections and says nothing needs the owner on day 0", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeVisible();
  for (const name of ["Today", "What needs you", "Position", "Waiting for you", "At risk", "Done by the agent"]) {
    await expect(page.getByRole("heading", { name, level: 2 })).toBeVisible();
  }
  await expect(page.getByTestId("home-day")).toHaveText("Day 0");
  await expect(page.getByText("Demo control")).toBeVisible();
  await expect(page.getByTestId("home-opener")).toHaveAttribute("data-news", "false");
  await expect(page.getByTestId("home-opener")).toContainText("Nothing needs you today");
  await expect(page.getByTestId("home-goahead")).toHaveCount(0);
  // Position: server display strings only.
  await expect(page.getByTestId("home-waiting-empty")).toBeVisible();
  const position = page.locator("#home-position");
  await expect(position.getByText("¥400,000.00")).toBeVisible();
  await expect(position.getByText("¥300,000.00").first()).toBeVisible();
  await expect(page.getByRole("link", { name: "Home" }).first()).toBeVisible();
});

test("advancing to day 34 shows the opener; Go ahead runs the cure and the critical alert goes", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);

  const opener = page.getByTestId("home-opener");
  await expect(opener).toHaveAttribute("data-news", "true");
  await expect(opener).toContainText("Day 34");
  await expect(opener).toContainText("¥200,000.00");
  await expect(page.getByTestId("home-goahead")).toBeVisible();
  await expect(page.getByTestId("home-notnow")).toBeVisible();

  const critical = page.getByTestId("home-alert-ALERT-RESERVE-42");
  await expect(critical).toHaveAttribute("data-severity", "CRITICAL");
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toBeVisible();

  await page.getByTestId("home-goahead").click();
  const op = page.getByTestId("home-answer").getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING");
  await expect(op).toHaveAttribute("data-status", "EXECUTED");
  await expect(op).toContainText("¥200,000.00");
  await expect(page.getByTestId("home-alert-ALERT-RESERVE-42")).toHaveCount(0);
  await expect(page.getByTestId("home-goahead")).toHaveCount(0);
  await expect(page.getByTestId("home-done-SUBMIT_INVOICE_FOR_FINANCING")).toBeVisible();
});

test("the conversation also appears in the chat panel, opener first", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);
  await expect(page.getByTestId("home-goahead")).toBeVisible();
  await page.getByTestId("home-goahead").click();
  await expect(page.getByTestId("home-answer")).toBeVisible();
  await page.goto("/chat");
  const turns = page.getByTestId("chat-turn");
  await expect(turns.first()).toContainText("Go ahead?");
  await expect(turns.last().getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING")).toBeVisible();
});

test("Let the agent fix this works from the home alert and from the alerts page", async ({ page }) => {
  await page.goto("/");
  await advanceTo34(page);

  // The alerts page: the button is on the actionable alert only.
  await page.getByRole("link", { name: "Alerts" }).click();
  await expect(page).toHaveURL(/\/alerts/);
  await expect(page.getByRole("heading", { name: "Reserve breach ahead on day 42" })).toBeVisible();
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toBeVisible();
  await expect(page.getByRole("button", { name: "Let the agent fix this" })).toHaveCount(1);

  await page.getByTestId("fix-ALERT-RESERVE-42").click();
  const result = page.getByTestId("fix-result");
  await expect(result).toContainText("1 executed");
  await expect(result.getByTestId("chat-op-SUBMIT_INVOICE_FOR_FINANCING")).toHaveAttribute("data-status", "EXECUTED");
  await expect(result).toContainText("The alert is cleared.");
  await expect(page.getByTestId("alert-count-CRITICAL")).toContainText("0 Critical");
  await expect(page.getByTestId("fix-ALERT-RESERVE-42")).toHaveCount(0);
});
