"use client";

import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";

/** The few finance words the screens still use, each in one plain sentence. Folded away until asked for. */
const TERMS = ["floor", "terms", "discount", "giveaway", "line", "invoiceFin", "dscr", "leverage", "limits", "approval"] as const;

export function Glossary() {
  const { t } = useI18n();
  return (
    <details className="rounded-(--radius-card) border border-line bg-surface px-4 py-3 shadow-(--shadow-card)" id="home-glossary">
      <summary className="cursor-pointer text-sm font-semibold text-ink">{t("gloss.title")}</summary>
      <dl className="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        {TERMS.map((k) => (
          <div key={k}>
            <dt className="font-medium text-ink">{t(`gloss.${k}.term` as DictKey)}</dt>
            <dd className="mt-0.5 text-ink-2">{t(`gloss.${k}.def` as DictKey)}</dd>
          </div>
        ))}
      </dl>
    </details>
  );
}
