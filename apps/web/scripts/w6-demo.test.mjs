// Wave 6 part B (map #65, ticket #75): the guided Demo's narration. Every step has its sentences in both languages, no figure is typed into the
// dictionary (INVARIANT 13: the figures come from the responses a step received), and a sentence the server gave no figure for is omitted. Run: pnpm test:unit
import assert from "node:assert/strict";
import test from "node:test";
import { en, zh } from "../lib/dictionary.ts";
import { stepNarration } from "../lib/demo-text.ts";

const STEPS = ["ask", "decide", "agree", "cash", "bank", "time", "queue", "approve", "settle", "outcome", "proof"];
const SCENES = ["buyer", "decision", "agreement", "reality", "owner", "proof"];
const i18n = (lang) => {
  const dict = lang === "zh" ? zh : en;
  return { lang, t: (key, vars) => (dict[key] ?? key).replace(/\{(\w+)\}/g, (all, k) => (vars && k in vars ? String(vars[k]) : all)) };
};

test("every step and scene has its words in English and Chinese", () => {
  for (const dict of [en, zh]) {
    for (const id of STEPS) for (const prefix of ["demo.step", "demo.desc", "demo.done"]) assert.ok(dict[`${prefix}.${id}`], `${prefix}.${id}`);
    for (const id of SCENES) for (const prefix of ["scene", "scene.short"]) assert.ok(dict[`${prefix}.${id}`], `${prefix}.${id}`);
  }
});

test("no figure is typed into a step's sentences: the plain ones and the templates carry no digit and no money", () => {
  for (const dict of [en, zh]) {
    for (const id of STEPS) {
      for (const prefix of ["demo.desc", "demo.done"]) {
        const text = dict[`${prefix}.${id}`];
        assert.ok(!/[0-9¥$]/.test(text), `${prefix}.${id} holds a figure: ${text}`);
      }
    }
  }
});

test("a step is narrated from what the server told it, and each sentence is omitted when its figure is missing", () => {
  const t = i18n("en");
  const full = { facts: { agree: { lang: "en", values: { state: "Agreed", task: "Waiting for the buyer to pay." } } } };
  assert.equal(stepNarration(t, "agree", full), "Agreed. Waiting for the buyer to pay.");
  const partial = { facts: { agree: { lang: "en", values: { state: "Agreed", task: "" } } } };
  assert.equal(stepNarration(t, "agree", partial), "Agreed.");
  // Nothing told, nothing usable, or told in the other language: the plain sentence.
  assert.equal(stepNarration(t, "agree", { facts: {} }), en["demo.desc.agree"]);
  assert.equal(stepNarration(t, "agree", { facts: { agree: { lang: "en", values: { state: "", task: "" } } } }), en["demo.desc.agree"]);
  assert.equal(stepNarration(t, "agree", { facts: { agree: { lang: "zh", values: { state: "已达成", task: "x" } } } }), en["demo.desc.agree"]);
});
