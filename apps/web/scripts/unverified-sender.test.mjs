// SEC-19, the web half: an anonymous request (no buyer's key) that names a registered buyer is marked "Unverified sender" wherever the owner can accept it or approve
// an operation on it (the deal's header, the accept review, an approval card), from the server's `sender_unverified` only. A recording made before the field (every
// mock today: the recorder, scripts/record-mocks.mjs, has not been run for it) carries no field and shows no label. Run: pnpm test:unit
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { register } from "node:module";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

register("./ts-resolve-hook.mjs", import.meta.url);
const m = await import("../components/ui/unverified-sender-model.ts");
const { en, zh } = await import("../lib/dictionary.ts");
const here = dirname(fileURLToPath(import.meta.url));
const web = join(here, "..");

test("the label shows only when a server view says the sender is unverified", () => {
  assert.equal(m.senderUnverified({ sender_unverified: true }), true);
  assert.equal(m.senderUnverified({ sender_unverified: false }), false);
  assert.equal(m.senderUnverified({ sender_unverified: null }), false);
  assert.equal(m.senderUnverified({}), false, "absent (an older server, a recording) is no label");
  assert.equal(m.senderUnverified(null, undefined), false);
  assert.equal(m.senderUnverified(), false);
  assert.equal(m.senderUnverified(undefined, { sender_unverified: false }, { sender_unverified: true }), true, "any of the deal's views (picture, accept block, record)");
  // only the boolean true decides: nothing truthy-but-not-true is read as a verdict on the sender
  assert.equal(m.senderUnverified({ sender_unverified: "true" }), false);
  assert.equal(m.senderUnverified({ sender_unverified: 1 }), false);
});

test("the label is in both languages, in the brief's words", () => {
  assert.equal(m.UNVERIFIED_SENDER_KEY, "sender.unverified");
  assert.equal(en["sender.unverified"], "Unverified sender: this message came without the buyer's key");
  assert.equal(zh["sender.unverified"], "未验证的发件人：此消息未附带买方密钥");
});

test("every view where the owner accepts a request or approves an operation on it draws the label", () => {
  for (const [file, views] of [
    ["components/deals/flow/decision-pane.tsx", "[picture, picture?.accept, record?.source]"],
    ["components/deals/flow/accept-block.tsx", "[accept]"],
    ["components/approval-card.tsx", "[a]"],
  ]) {
    const src = readFileSync(join(web, file), "utf8");
    assert.ok(src.includes(`<UnverifiedSender views={${views}}`), `${file} draws the label from ${views}`);
  }
});

test("no recording carries the field yet, so the mock suite shows no label (absence is no label)", () => {
  const walk = (dir) => readdirSync(dir).flatMap((n) => (statSync(join(dir, n)).isDirectory() ? walk(join(dir, n)) : n.endsWith(".json") ? [join(dir, n)] : []));
  const marked = walk(join(web, "mocks")).filter((f) => readFileSync(f, "utf8").includes('"sender_unverified": true'));
  assert.deepEqual(marked, [], "a recording that marks a sender must come from the recorder, never a hand edit");
});
