import { expect, test as base } from "@playwright/test";

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
