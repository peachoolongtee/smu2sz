// Ticket #112 (the design-system wave): the segmented control's keyboard, ARIA and badge rules, and the one state vocabulary.
// The components are TSX (node cannot strip JSX), so what is tested is their model: plain functions in components/ui/*-model.ts that the components render from.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import test from "node:test";
import { BADGE_CLASS, badgeShown, nextTabIndex, tabAttrs, tabStop } from "../components/ui/segmented-tabs-model.ts";

const four = [{ id: "a", controls: "panel" }, { id: "b", controls: "panel" }, { id: "c", controls: "panel" }, { id: "d", controls: "panel" }];

test("SegmentedTabs keyboard: arrows move and wrap, Home and End jump, other keys are left alone", () => {
  assert.equal(nextTabIndex("ArrowRight", 0, four), 1);
  assert.equal(nextTabIndex("ArrowDown", 1, four), 2);
  assert.equal(nextTabIndex("ArrowRight", 3, four), 0, "wraps forward");
  assert.equal(nextTabIndex("ArrowLeft", 0, four), 3, "wraps back");
  assert.equal(nextTabIndex("ArrowUp", 2, four), 1);
  assert.equal(nextTabIndex("Home", 2, four), 0);
  assert.equal(nextTabIndex("End", 0, four), 3);
  assert.equal(nextTabIndex("Enter", 0, four), null);
  assert.equal(nextTabIndex("a", 0, four), null);
  assert.equal(nextTabIndex("ArrowRight", 0, []), null);
});

test("SegmentedTabs keyboard: a disabled tab is skipped, and is never the first or last stop", () => {
  const some = [{}, { disabled: true }, {}, { disabled: true }];
  assert.equal(nextTabIndex("ArrowRight", 0, some), 2);
  assert.equal(nextTabIndex("ArrowRight", 2, some), 0, "wraps past the disabled last tab");
  assert.equal(nextTabIndex("ArrowLeft", 0, some), 2);
  assert.equal(nextTabIndex("End", 0, some), 2);
  assert.equal(nextTabIndex("Home", 2, [{ disabled: true }, {}, {}]), 1);
  assert.equal(nextTabIndex("ArrowRight", 1, [{ disabled: true }, {}, { disabled: true }]), 1, "nothing else to move to: the focus stays");
  assert.equal(nextTabIndex("ArrowRight", 0, [{ disabled: true }, { disabled: true }]), null);
});

test("SegmentedTabs ARIA: role tab, aria-selected on the chosen one only, one tab stop, the id and the panel it controls", () => {
  const attrs = four.map((_, i) => tabAttrs(i, 2, four));
  assert.deepEqual(attrs.map((a) => a.role), ["tab", "tab", "tab", "tab"]);
  assert.deepEqual(attrs.map((a) => a["aria-selected"]), [false, false, true, false]);
  assert.deepEqual(attrs.map((a) => a.tabIndex), [-1, -1, 0, -1], "roving tabindex: Tab enters the list once, at the chosen tab");
  assert.deepEqual(attrs.map((a) => a.id), ["a", "b", "c", "d"]);
  assert.equal(attrs[0]["aria-controls"], "panel");
  assert.equal("aria-controls" in tabAttrs(0, 0, [{}]), false, "no panel, no aria-controls");
  assert.equal(tabAttrs(0, 0, [{ disabled: true }]).disabled, true);
});

test("SegmentedTabs ARIA: with nothing chosen, or the chosen tab disabled, the first tab that can be chosen is the stop", () => {
  const tabs = [{ disabled: true }, {}, {}];
  assert.equal(tabStop(-1, tabs), 1);
  assert.equal(tabStop(0, tabs), 1);
  assert.equal(tabStop(2, tabs), 2);
  assert.deepEqual(tabs.map((_, i) => tabAttrs(i, -1, tabs)["aria-selected"]), [false, false, false]);
});

test("SegmentedTabs badge: a number (zero too) or a word is shown, nothing else; red is its own tone and neutral the other", () => {
  for (const shown of [3, 0, "9+", "new"]) assert.equal(badgeShown(shown), true, String(shown));
  for (const hidden of [null, undefined, ""]) assert.equal(badgeShown(hidden), false, String(hidden));
  assert.match(BADGE_CLASS.alert, /bg-bad-solid/);
  assert.doesNotMatch(BADGE_CLASS.neutral, /bad/);
  assert.notEqual(BADGE_CLASS.alert, BADGE_CLASS.neutral);
});
