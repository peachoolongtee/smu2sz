import { expect, test, type APIRequestContext } from "@playwright/test";

/**
 * Live mode shares one in-memory API across specs, so a spec that reads the books (alerts, what-if) resets
 * them first. In mock mode every browser context starts with an empty store, so this does nothing.
 */
export async function resetBooks(request: APIRequestContext): Promise<void> {
  if (test.info().project.name !== "live") return;
  const res = await request.post("http://localhost:8000/demo/reset", {
    headers: { "X-Owner-Token": process.env.NEXT_PUBLIC_OWNER_TOKEN ?? "demo-owner-token" },
  });
  expect(res.ok()).toBeTruthy();
}
