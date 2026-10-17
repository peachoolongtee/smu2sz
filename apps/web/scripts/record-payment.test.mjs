// Feature inventory gap 1: the owner records a payment. The typed amount is read as whole fen without adding anything up, and the recording the
// mock serves (scripts/record-mocks.mjs --receipts) is the API's own answer with the owner's words in both languages.
// Run: pnpm test:unit
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { en, zh } from "../lib/dictionary.ts";
import { yuanTextToFen } from "../lib/money-input.ts";

const here = dirname(fileURLToPath(import.meta.url));
const recording = JSON.parse(readFileSync(join(here, "..", "mocks", "receipts.json"), "utf8"));

test("a typed amount is read as whole fen, and anything that is not an amount is null", () => {
  assert.equal(yuanTextToFen("100000"), 10_000_000);
  assert.equal(yuanTextToFen("100,000"), 10_000_000);
  assert.equal(yuanTextToFen(" ¥100,000.5 "), 10_000_050);
  assert.equal(yuanTextToFen("￥1，234.56"), 123_456);
  assert.equal(yuanTextToFen("0.01"), 1);
  for (const bad of ["", "0", "0.00", "abc", "1,00", "1.234", "-5", "1e5", "100 000", ",100", "12.", "9999999999999999"]) {
    assert.equal(yuanTextToFen(bad), null, bad);
  }
});

test("the recorded answers carry the server's words in both languages, and a booked payment its books after", () => {
  for (const [point, at] of Object.entries(recording)) {
    for (const a of at.answers) {
      for (const lang of ["en", "zh"]) {
        const r = a.answer[lang];
        assert.equal(r.result.kind, "RECEIVE_PAYMENT", `${point} ${a.variant}`);
        assert.equal(r.result.op_id, `owner-receipt-rec-${point}-${a.variant}`);
        assert.ok(r.receipt?.headline_text, `${point} ${a.variant} ${lang}`);
        assert.equal(r.lang, lang);
      }
      assert.equal(a.after === null, a.answer.en.result.status !== "EXECUTED", `${point} ${a.variant}`);
    }
  }
  assert.ok(recording.settled.answers[0].answer.en.receipt.lines[0].includes("first, to repay the advance"));
});

test("every label of the form is in both dictionaries", () => {
  const keys = Object.keys(en).filter((k) => k.startsWith("recv3.pay."));
  assert.ok(keys.length >= 15);
  for (const k of keys) assert.ok(zh[k] && zh[k] !== en[k], k);
});
