const path = require("path");
// Playwright comes from the web app's install (apps/web, pnpm install); PLAYWRIGHT_FROM names another folder to resolve it from.
const repo = path.resolve(__dirname, "../../../..");
const from = process.env.PLAYWRIGHT_FROM || path.join(repo, "apps", "web");
const { chromium } = require(require.resolve("@playwright/test", { paths: [from] }));
const { pathToFileURL } = require("url");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1700, height: 1200 }, deviceScaleFactor: 2 });
  for (const f of process.argv.slice(2)) {
    await p.goto(pathToFileURL(path.resolve(f + ".html")).href);
    await p.locator("#fig").screenshot({ path: f + ".png" });
    console.log("rendered", f);
  }
  await b.close();
})();
