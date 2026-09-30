"use client";

import { useMemo } from "react";
import { createStore } from "./create-store";
import { en, zh, type DictKey } from "./dictionary";

export type Lang = "en" | "zh";

const langStore = createStore<{ lang: Lang }>({ lang: "en" }, { storage: "local", key: "tl-lang" });

export function setLang(lang: Lang): void {
  langStore.set({ lang });
  if (typeof document !== "undefined") document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
}

type Vars = Record<string, string | number>;

function interpolate(template: string, vars?: Vars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (_, k: string) => (k in vars ? String(vars[k]) : `{${k}}`));
}

export interface I18n {
  lang: Lang;
  /** Label lookup. All UI strings live in lib/dictionary.ts. */
  t: (key: DictKey, vars?: Vars) => string;
  /** Enum lookup such as te("outcome", "REJECT"); falls back to the raw code so nothing is ever blank. */
  te: (prefix: string, value: string | null | undefined) => string;
}

export function useI18n(): I18n {
  const { lang } = langStore.useValue();
  return useMemo(() => {
    const dict: Record<string, string> = lang === "zh" ? zh : en;
    return {
      lang,
      t: (key, vars) => interpolate(dict[key] ?? en[key] ?? key, vars),
      te: (prefix, value) => (value ? (dict[`${prefix}.${value}`] ?? en[`${prefix}.${value}` as DictKey] ?? value) : ""),
    };
  }, [lang]);
}
