"use client";

import { LineRow } from "@/components/tracker/line-row";
import { Block } from "@/components/tracker/parts";
import { useI18n } from "@/lib/i18n";
import type { TrackerLine } from "@/lib/tracker";
import { inTotal, isAgreementLine, outsideLines, tableLines } from "@/lib/tracker-lines";

/**
 * The related funding (funding the records tie to this deal), apart from the agreement's own components, so that showing it differently (counted on
 * top of the terms, or beside the cost card) is a small change: `CostBlock` calls `FundingSegments`, `FundingLegend` and `FundingRows` for what counts,
 * and the page calls `OutsideBlock` for what the server does not count. A segment is plotted by the server's fen number only (a width); the labels are
 * the lines' own. Nothing is added or subtracted.
 */
export function FundingSegments({ lines }: { lines: TrackerLine[] }) {
  return (
    <>
      {lines.filter((l) => !isAgreementLine(l) && inTotal(l)).map((l) => (
        <div key={l.key} className="motion-grow bg-bad-solid" style={{ flex: l.actual_fen as number }} data-testid={`tracker-bar-${l.key}`} />
      ))}
    </>
  );
}

export function FundingLegend({ lines }: { lines: TrackerLine[] }) {
  return (
    <>
      {lines.filter((l) => !isAgreementLine(l) && inTotal(l)).map((l) => (
        <li key={l.key} className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-bad-solid" />
          {l.label}
        </li>
      ))}
    </>
  );
}

export function FundingRows({ lines }: { lines: TrackerLine[] }) {
  return (
    <>
      {tableLines(lines).filter((l) => !isAgreementLine(l)).map((l) => (
        <LineRow key={l.key} l={l} />
      ))}
    </>
  );
}

/** "Also, outside this deal's cost": related funding the server does not count, each with its own figure, what it is, how sure, and why it is not counted. Absent with none. */
export function OutsideBlock({ lines }: { lines: TrackerLine[] }) {
  const { t } = useI18n();
  const out = outsideLines(lines);
  if (!out.length) return null;
  return (
    <Block id="tracker-outside" title={t("tracker.outside")} className="space-y-3 bg-warn-bg!" testId="tracker-outside">
      <ul className="mt-3 space-y-4">
        {out.map((l) => (
          <li key={l.key} data-testid={`tracker-outside-${l.key}`} data-relation={l.relation ?? undefined}>
            {l.figure_display ? <p className="type-value font-display text-ink">{l.figure_display}</p> : null}
            <p className="mt-1 text-body-lg font-semibold text-ink">{l.label}</p>
            <p className="mt-1 text-supporting text-ink-2">{l.certainty_text}</p>
            <p className="mt-1 text-body text-warn-fg">{l.counted_note_text}</p>
          </li>
        ))}
      </ul>
    </Block>
  );
}
