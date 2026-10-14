import { test } from "./fixtures";
import { checkedDeal } from "./helpers";
test("probe", async ({ page }) => {
  test.skip(test.info().project.name !== "desktop");
  await page.setViewportSize({ width: 390, height: 844 });
  await checkedDeal(page);
  for (const v of ["overview", "compare", "cash", "messages"]) {
    await page.getByTestId("deal-tab-" + v).click();
    await page.waitForTimeout(500);
    const hits = await page.evaluate(() => {
      const out: string[] = [];
      for (const el of Array.from(document.querySelectorAll("main *"))) {
        const r = el.getBoundingClientRect();
        if (r.width > 0 && r.right > 391) {
          let p: Element | null = el.parentElement, clipped = false;
          while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === "auto" || o === "hidden" || o === "scroll") { clipped = true; break; } p = p.parentElement; }
          if (!clipped) out.push(`${el.tagName}[${el.getAttribute("data-testid") ?? ""}] right=${Math.round(r.right)}`);
        }
      }
      return out.slice(0, 6);
    });
    console.log(v, document_width(await page.evaluate(() => document.documentElement.scrollWidth)), JSON.stringify(hits));
  }
});
const document_width = (n: number) => n;
