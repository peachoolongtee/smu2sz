// Wave 1 (map #65): the approval gate, the agreement label, deadline words and the two stylesheet rules that broke the cold start
// and the reduced-motion ellipsis. Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { approveDisabled, termsGate } from "../lib/approval-terms.ts";
import { en } from "../lib/dictionary.ts";
import { agreementState } from "../lib/execution-summary.ts";
import { whenText } from "../lib/when.ts";

const css = readFileSync(fileURLToPath(new URL("../app/globals.css", import.meta.url)), "utf8");

const commercial = (presentation) => ({ operation_kind: "ACCEPT_OFFER", operation: { kind: "ACCEPT_OFFER", op_id: "x" }, presentation });
const funding = (presentation) => ({ operation_kind: "SUBMIT_INVOICE_FOR_FINANCING", operation: { kind: "SUBMIT_INVOICE_FOR_FINANCING", op_id: "y" }, presentation });

test("Approve is disabled for a commercial approval whose terms are not available", () => {
  assert.equal(approveDisabled(commercial({ terms_available: false, terms_unavailable_reason: "expired" }), false), true);
  assert.equal(termsGate(commercial({ terms_available: false })).available, false);
});

test("an older answer without the field fails closed on a commercial approval", () => {
  assert.equal(approveDisabled(commercial({}), false), true);
  assert.equal(approveDisabled(commercial(undefined), false), true);
});

test("available but empty terms also fail closed", () => {
  assert.equal(approveDisabled(commercial({ terms_available: true, terms: [] }), false), true);
});

test("Approve is enabled when the terms are shown, and a funding approval needs no terms", () => {
  assert.equal(approveDisabled(commercial({ terms_available: true, terms: ["Pay early at 0.5%."] }), false), false);
  assert.equal(approveDisabled(commercial({ terms_available: true, what_you_agree_to: "Pay early at 0.5%." }), false), false);
  assert.equal(approveDisabled(funding({}), false), false);
  assert.equal(approveDisabled(funding(undefined), false), false);
});

test("a decision in flight disables Approve whatever the terms say", () => {
  assert.equal(approveDisabled(funding({}), true), true);
});

test("the agreement label follows the commitment's status", () => {
  assert.equal(agreementState("ACTIVE"), "agreed");
  assert.equal(agreementState("ACCEPTED"), "agreed");
  assert.equal(agreementState("FULFILLED"), "settled");
  assert.equal(agreementState("EXPIRED"), "expired");
  assert.equal(agreementState("PROPOSED"), "waiting");
  assert.equal(agreementState(null), "none");
});

// The dictionary's interpolation (lib/i18n.ts): `{n|one|other}` picks the word for a count, then `{n}` is the value.
const t = (key, vars) =>
  en[key].replace(/\{(\w+)\|([^|{}]*)\|([^|{}]*)\}/g, (_, k, one, other) => (Number(vars?.[k]) === 1 ? one : other)).replace(/\{(\w+)\}/g, (_, k) => String(vars?.[k]));

test("a deadline that has passed is a distance in the past and is never rewritten to today", () => {
  assert.equal(whenText(2, 34, t), "32 days ago");
  assert.equal(whenText(33, 34, t), "yesterday");
  assert.equal(whenText(34, 34, t), "today");
  assert.equal(whenText(36, 34, t), "in 2 days");
  assert.ok(![whenText(2, 34, t), whenText(33, 34, t)].includes("today"));
});

test("globals.css: the touch variant is the block form that keeps both branches", () => {
  assert.match(css, /@custom-variant touch \{\s*@media \(max-width: 63\.999rem\) \{\s*@slot;\s*\}\s*@media \(pointer: coarse\) \{\s*@slot;\s*\}\s*\}/);
  assert.doesNotMatch(css, /@custom-variant touch \(/);
});

test("globals.css: the reduced-motion ellipsis comes after the base rule that hides it", () => {
  const base = css.indexOf(".spinner-dots {\n  display: none;");
  const reduced = css.indexOf("@media (prefers-reduced-motion: reduce)");
  const shown = css.indexOf("display: inline;", reduced);
  assert.ok(base !== -1 && reduced !== -1 && shown !== -1);
  assert.ok(base < reduced && reduced < shown, "the hiding rule must precede the media block that shows it");
  assert.equal(css.indexOf(".spinner-dots {\n  display: none;", reduced), -1, "no hiding rule after the media block");
});
