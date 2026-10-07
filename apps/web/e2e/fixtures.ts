import { expect, test as base, type Page } from "@playwright/test";

/** The API's published demo owner token. Only the live project (a local API in demo mode) accepts it. */
export const DEMO_TOKEN = "demo-owner-token";

/**
 * `test` for specs that are not about sign-in: in the live project the context starts already signed in as the
 * owner (token in sessionStorage, exactly where the sign-in dialog would put it), and so is the mock project.
 * Specs that test the sign-in flow import `test` from "@playwright/test" instead.
 */
export const test = base.extend({
  context: async ({ context }, provide, testInfo) => {
    // The mock's demo reset is an owner action too (as live), and it accepts any non-empty token; specs that test
    // the sign-in flow import `test` from "@playwright/test" and start signed out.
    const token = testInfo.project.name === "live" ? DEMO_TOKEN : "mock-owner";
    await context.addInitScript((tok) => {
      try {
        sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: tok }));
      } catch {
        /* storage unavailable */
      }
    }, token);
    await provide(context);
  },
});

export { expect };

/**
 * The page's prose: the body text without scripts and styles, without the engine's formulas (`<code>`, the `Formula` block)
 * and without `exclude` selectors when given. A Business page never says "day N" in its prose; a formula is the audit level
 * and keeps the engine's day numbers.
 */
export async function proseOf(page: Page, exclude: string[] = []): Promise<string> {
  return page.evaluate((selectors) => {
    const body = document.body.cloneNode(true) as HTMLElement;
    for (const s of ["script", "style", "code", ...selectors]) body.querySelectorAll(s).forEach((el) => el.remove());
    return body.textContent ?? "";
  }, exclude);
}
