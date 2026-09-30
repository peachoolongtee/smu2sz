import { expect, test as base } from "@playwright/test";

/** The API's published demo owner token. Only the live project (a local API in demo mode) accepts it. */
export const DEMO_TOKEN = "demo-owner-token";

/**
 * `test` for specs that are not about sign-in: in the live project the context starts already signed in as the
 * owner (token in sessionStorage, exactly where the sign-in dialog would put it). Mock mode needs no token.
 * Specs that test the sign-in flow import `test` from "@playwright/test" instead.
 */
export const test = base.extend({
  context: async ({ context }, provide, testInfo) => {
    if (testInfo.project.name === "live") {
      await context.addInitScript((token) => {
        try {
          sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token }));
        } catch {
          /* storage unavailable */
        }
      }, DEMO_TOKEN);
    }
    await provide(context);
  },
});

export { expect };
