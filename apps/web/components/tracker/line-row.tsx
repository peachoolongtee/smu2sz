"use client";

import { EvidenceLink } from "@/components/tracker/parts";
import { useI18n } from "@/lib/i18n";
import type { TrackerLine } from "@/lib/tracker";

const LINE_INK = { bad: "text-bad-fg", warn: "text-warn-fg", ok: "text-ok-fg", neutral: "text-ink" } as const;

/**
 * One row of the cost table: the label, the expected figure, what it has cost so far (the figure, or the server's note when there is none:
 * never a dash or a zero) and how sure the server is. On a phone the row stacks with its labels. Every string is the server's.
 */
export function LineRow({ l }: { l: TrackerLine }) {
  const { t } = useI18n();
  return (
    <tr data-testid={`tracker-line-${l.key}`} data-certainty={l.certainty} className="border-b border-line last:border-b-0 max-sm:block max-sm:py-3">
      <th scope="row" className="px-0 py-3 text-left align-top font-semibold text-ink max-sm:block max-sm:pb-1 sm:pr-4">
        {l.label}
      </th>
      <td className="py-3 align-top tabular-nums max-sm:flex max-sm:justify-between max-sm:gap-4 max-sm:py-0.5 sm:text-right">
        <span className="text-supporting text-ink-3 sm:hidden">{t("tracker.col.expected")}</span>
        <span className="whitespace-nowrap">{l.expected_display}</span>
      </td>
      <td className={`py-3 align-top max-sm:flex max-sm:justify-between max-sm:gap-4 max-sm:py-0.5 sm:pl-4 sm:text-right ${LINE_INK[l.tone]}`}>
        <span className="text-supporting text-ink-3 sm:hidden">{t("tracker.col.actual")}</span>
        <span className="min-w-0 text-right" data-testid={`tracker-line-${l.key}-actual`}>
          {l.actual_display ? <span className={`block whitespace-nowrap tabular-nums ${l.tone === "neutral" ? "" : "font-semibold"}`}>{l.actual_display}</span> : null}
          {l.actual_note_text ? <span className={`block text-supporting ${l.actual_display ? "text-ink-2" : "text-ink"}`}>{l.actual_note_text}</span> : null}
        </span>
      </td>
      <td className="py-3 align-top text-supporting text-ink-2 max-sm:block max-sm:pb-1 max-sm:pt-0.5 sm:pl-6">
        <span className="text-supporting text-ink-3 sm:hidden">{t("tracker.col.sure")}: </span>
        {l.certainty_text}
        {l.evidence_href ? (
          <span className="block">
            <EvidenceLink href={l.evidence_href} />
          </span>
        ) : null}
      </td>
    </tr>
  );
}
