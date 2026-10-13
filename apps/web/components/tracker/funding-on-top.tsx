"use client";

import { LineRow } from "@/components/tracker/line-row";
import type { TrackerLine } from "@/lib/tracker";

/**
 * The funding on top of the agreed terms (the counted funding lines): its bar segments, its legend entries and its table rows. They live here, apart
 * from the terms, so that showing this part as a block of its own beside the cost card is a small change: `CostBlock` calls these three and nothing else.
 * A segment is plotted by the server's fen number only (a width); the labels are the lines' own. Nothing is added or subtracted.
 */
export const isFunding = (l: TrackerLine): boolean => l.key.startsWith("funding");
const measured = (l: TrackerLine): boolean => l.actual_fen !== null && l.actual_fen > 0;

export function FundingSegments({ lines }: { lines: TrackerLine[] }) {
  return (
    <>
      {lines.filter(isFunding).filter(measured).map((l) => (
        <div key={l.key} className="motion-grow bg-bad-solid" style={{ flex: l.actual_fen as number }} data-testid={`tracker-bar-${l.key}`} />
      ))}
    </>
  );
}

export function FundingLegend({ lines }: { lines: TrackerLine[] }) {
  return (
    <>
      {lines.filter(isFunding).filter(measured).map((l) => (
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
      {lines.filter(isFunding).map((l) => (
        <LineRow key={l.key} l={l} />
      ))}
    </>
  );
}
