"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { TrackerCost, TrackerLine } from "@/lib/tracker";
import { tableLines, inTotal, isAgreementLine } from "@/lib/tracker-lines";
import { FundingLegend, FundingRows, FundingSegments } from "./funding-on-top";
import { LineRow } from "./line-row";
import { Block } from "./parts";

const ACTUAL_INK = { bad: "text-bad-fg", ok: "text-ok-fg", neutral: "text-ink" } as const;

function Figure({ label, testId, children, note }: { label: string; testId: string; children: ReactNode; note?: string | null }) {
  return (
    <div className="min-w-0 flex-1 basis-52" data-testid={testId}>
      <p className="text-body-lg text-ink-2">{label}</p>
      <div className="mt-1">{children}</div>
      {note ? <p className="mt-1 text-supporting text-ink-2">{note}</p> : null}
    </div>
  );
}

/**
 * The bar: one segment per line the server has a figure for, the agreed terms in ink and the funding on top in the bad tone (`FundingSegments`), each
 * sized by its own fen number (a width, never a label), with a legend of the lines' own labels so colour is never alone.
 */
function CostBar({ lines }: { lines: TrackerLine[] }) {
  const terms = lines.filter((l) => isAgreementLine(l) && inTotal(l));
  const hasFunding = lines.some((l) => !isAgreementLine(l) && inTotal(l));
  if (!terms.length && !hasFunding) return null;
  return (
    <div data-testid="tracker-bar">
      <div aria-hidden className="flex h-4 overflow-hidden rounded-pill bg-track">
        {terms.map((l) => (
          <div key={l.key} className="motion-grow bg-ink" style={{ flex: l.actual_fen as number }} data-testid={`tracker-bar-${l.key}`} />
        ))}
        <FundingSegments lines={lines} />
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-supporting text-ink-2">
        {terms.map((l) => (
          <li key={l.key} className="flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 shrink-0 rounded-full bg-ink" />
            {l.label}
          </li>
        ))}
        <FundingLegend lines={lines} />
      </ul>
    </div>
  );
}

/** "What it costs you": three figures, the bar, the line table with how sure each line is, and the method beneath. Every word and figure is the server's. */
export function CostBlock({ cost }: { cost: TrackerCost }) {
  const { t } = useI18n();
  const toCome = cost.to_come;
  return (
    <Block id="tracker-cost" title={t("tracker.cost")} className="space-y-6">
      <div className="mt-4 flex flex-wrap gap-x-10 gap-y-5">
        <Figure label={t("tracker.expected")} testId="tracker-expected" note={cost.expected.basis_text}>
          <p className="type-value font-display text-ink" data-testid="tracker-expected-figure">
            {cost.expected.amount_display}
          </p>
        </Figure>
        <Figure label={t("tracker.actual")} testId="tracker-actual" note={cost.actual.note_text}>
          <p className={`type-value font-display ${ACTUAL_INK[cost.actual.tone]}`} data-tone={cost.actual.tone} data-testid="tracker-actual-figure">
            {cost.actual.amount_display}
          </p>
        </Figure>
        {(cost.unmeasured_fen ?? 0) > 0 && cost.unmeasured_display ? (
          <Figure label={t("tracker.unmeasured")} testId="tracker-unmeasured">
            <p className="type-value font-display text-ink" data-testid="tracker-unmeasured-figure">
              {cost.unmeasured_display}
            </p>
          </Figure>
        ) : null}
      </div>

      <div className="text-body text-ink-2" data-testid="tracker-to-come">
        {toCome.amount_display ? (
          <p>
            <span className="font-semibold tabular-nums text-ink" data-testid="tracker-to-come-figure">{toCome.amount_display}</span> {toCome.note_text}
          </p>
        ) : (
          <p>{toCome.note_text}</p>
        )}
      </div>

      <CostBar lines={cost.lines} />

      <table className="w-full border-collapse text-left text-body">
        <caption className="sr-only">{t("tracker.lines")}</caption>
        <thead className="max-sm:sr-only">
          <tr>
            <th scope="col" className="border-b border-line px-0 py-2 text-supporting font-semibold text-ink-2">
              {t("tracker.col.cost")}
            </th>
            <th scope="col" className="border-b border-line py-2 text-right text-supporting font-semibold text-ink-2">
              {t("tracker.col.expected")}
            </th>
            <th scope="col" className="border-b border-line py-2 pl-4 text-right text-supporting font-semibold text-ink-2">
              {t("tracker.col.actual")}
            </th>
            <th scope="col" className="border-b border-line py-2 pl-6 text-supporting font-semibold text-ink-2">
              {t("tracker.col.sure")}
            </th>
          </tr>
        </thead>
        <tbody>
          {tableLines(cost.lines).filter(isAgreementLine).map((l) => (
            <LineRow key={l.key} l={l} />
          ))}
          <FundingRows lines={cost.lines} />
        </tbody>
      </table>

      <p className="text-supporting text-ink-2" data-testid="tracker-method">
        {cost.method_text}
      </p>
    </Block>
  );
}
