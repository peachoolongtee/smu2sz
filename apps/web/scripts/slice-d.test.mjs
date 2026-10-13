// Slice D (map #121): the Demo page and Activity read the server's words and decide nothing. Source-level guards that keep the owner's approval the owner's click.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";

const read = (p) => readFileSync(fileURLToPath(new URL(`../${p}`, import.meta.url)), "utf8");

test("no code on the Demo page or in the story control presses the owner's approval", () => {
  for (const file of ["app/demo/page.tsx", "components/demo/books-dialog.tsx"]) {
    const src = read(file);
    assert.doesNotMatch(src, /decideApproval|approveApproval|\/approve/, file);
  }
  // The control's one entry takes the server's action; the owner's step has no action, only an href.
  const control = read("lib/demo-control.ts");
  assert.match(control, /export async function runStoryAction/);
});

test("the Demo page has exactly one filled next control (a link for the owner's step, a button otherwise) and the dialog one filled confirm", () => {
  const page = read("app/demo/page.tsx");
  assert.equal((page.match(/variant="primary"/g) ?? []).length, 3); // the visitor's Start, the owner's link and the button: three states of the one control
  assert.match(page, /view\.next\.href \?/);
  const dialog = read("components/demo/books-dialog.tsx");
  assert.equal((dialog.match(/variant="primary"/g) ?? []).length, 1);
  assert.match(dialog, /showModal\(\)/);
  assert.match(dialog, /aria-modal="true"/);
});

test("Activity computes no sentence: every row's words come from the read, and the filter only hides rows", () => {
  const src = read("components/activity/activity-read.tsx");
  assert.match(src, /r\.search_text\.toLowerCase\(\)\.includes\(needle\)/);
  assert.doesNotMatch(src, /\.splice\(|\.filter\([^)]*benign_auth_count/);
  // Every kind the read carries has a place on the page.
  for (const kind of ["business", "system", "benign_auth", "security"]) assert.match(src, new RegExp(kind));
});

test("the books dialog's confirm acts only on a deliberate click, and confirm_loss is only ever sent with the dialog's token", () => {
  const dialog = read("components/demo/books-dialog.tsx");
  assert.match(dialog, /e\.detail > 1 \|\| !ready/);
  assert.match(dialog, /aria-disabled/);
  const guard = read("lib/books-guard.ts");
  assert.match(guard, /confirm: token/);
  assert.doesNotMatch(guard, /confirm: true|confirm: "1"/);
  // The only web functions that reset are reached through the guard: no un-guarded resetDemo / nextStep remain.
  assert.doesNotMatch(read("lib/demo-control.ts"), /export (async )?function (resetDemo|nextStep)/);
});
