const { chromium } = require("<worktree>/apps/web/node_modules/@playwright/test");
(async () => {
  const b = await chromium.launch(); const p = await b.newPage(); const logs = [];
  p.on("console", (m) => { if (["warning","error"].includes(m.type())) logs.push(m.type()+": "+m.text()); });
  p.on("pageerror", (e) => logs.push("pageerror: "+e.message));
  await p.addInitScript(() => sessionStorage.setItem("tl-owner-auth", JSON.stringify({ token: "demo-owner-token" })));
  const r = await p.goto("http://localhost:3255/decisions/deal:OFF-x");
  await p.waitForTimeout(3000);
  console.log("status", r.status());
  console.log("main text:", JSON.stringify((await p.locator("main").innerText()).slice(0, 600)));
  console.log("browser warnings/errors:", JSON.stringify(logs));
  await b.close();
})();
