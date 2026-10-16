import type { DemoState } from "./demo-store";
import type { StepId } from "./demo";
import type { DictKey } from "./dictionary";
import type { I18n } from "./i18n";

/** Sentences of a `demo.done.<step>` template are separated by this; each is told only when everything it names was supplied. */
const SEPARATOR = " / ";

/**
 * What a step says about itself. Before it has run, or when the server told it nothing it can use, that is its plain sentence
 * (`demo.desc.<step>`, no figures). After it has run, it is the `demo.done.<step>` template filled from the sentences and figures of the
 * responses the step just received (`DemoState.facts`). Each sentence of the template is told only if every name in it was supplied and
 * not empty: a figure the server did not give is omitted with its sentence, never shown as a hole or typed in here. Facts written in the
 * other language are not shown.
 */
export function stepNarration({ t, lang }: Pick<I18n, "t" | "lang">, id: StepId, demo: Pick<DemoState, "facts">): string {
  const facts = demo.facts[id];
  if (facts && facts.lang === lang) {
    const told = t(`demo.done.${id}` as DictKey)
      .split(SEPARATOR)
      .flatMap((sentence) => {
        const names = [...sentence.matchAll(/\{(\w+)\}/g)].map((m) => m[1]);
        if (names.some((n) => !facts.values[n]?.trim())) return [];
        const said = sentence.replace(/\{(\w+)\}/g, (_, n: string) => facts.values[n].trim());
        // A server headline used as a sentence may carry no full stop of its own; the next sentence must not run on from it.
        return [/[.!?。！？…:：)）"”]$/.test(said) ? said : `${said}${lang === "zh" ? "。" : "."}`];
      })
      .join(" ");
    if (told) return told;
  }
  return t(`demo.desc.${id}` as DictKey);
}
