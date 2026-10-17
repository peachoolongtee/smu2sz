const { chromium } = require("C:/Users/ian/Documents/Projects/smu2sz/.claude/worktrees/cert-719c/apps/web/node_modules/@playwright/test");
const path = require("path");
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
