"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/lib/i18n";
import type { TrackerCost, TrackerLine } from "@/lib/tracker";
import { Block, EvidenceLink } from "./parts";

const ACTUAL_INK = { bad: "text-bad-fg", ok: "text-ok-fg", neutral: "text-ink" } as const;
const LINE_INK = { bad: "text-bad-fg", warn: "text-warn-fg", ok: "text-ok-fg", neutral: "text-ink" } as const;

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
 * The two-part bar: what was expected, then what it costs beyond that. It is plotted from the server's fen numbers only (a width, never a label);
 * the words beside it are the server's. With the cost at or under the expectation the bar is the cost so far against the expected length.
 */
function CostBar({ cost }: { cost: TrackerCost }) {
  const { t } = useI18n();
  const over = cost.difference_fen > 0;
  const lead = over ? cost.expected.amount_fen : cost.actual.amount_fen;
  const rest = over ? cost.difference_fen : cost.expected.amount_fen - cost.actual.amount_fen;
  return (
    <div data-testid="tracker-bar" data-over={over ? "true" : "false"}>
      <div aria-hidden className="flex h-4 overflow-hidden rounded-pill bg-track">
        <div className="motion-grow bg-ink" style={{ flex: Math.max(lead, 1) }} />
        {rest > 0 ? <div className={`motion-grow ${over ? "bg-bad-solid" : "bg-track"}`} style={{ flex: rest }} /> : null}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-supporting text-ink-2">
        <li className="flex items-center gap-1.5">
          <span aria-hidden className="size-2.5 rounded-full bg-ink" />
          {over ? t("tracker.bar.expected") : t("tracker.bar.sofar")}
        </li>
        {over ? (
          <li className="flex items-center gap-1.5">
            <span aria-hidden className="size-2.5 rounded-full bg-bad-solid" />
            {t("tracker.bar.more")} <span className="font-semibold tabular-nums text-bad-fg">{cost.difference_display}</span>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function LineCells({ l }: { l: TrackerLine }) {
  const { t } = useI18n();
  return (
    <>
      <th scope="row" className="px-0 py-3 text-left align-top font-semibold text-ink max-sm:block max-sm:pb-1 sm:pr-4">
        {l.label}
      </th>
      <td className="py-3 align-top tabular-nums max-sm:flex max-sm:justify-between max-sm:gap-4 max-sm:py-0.5 sm:text-right">
        <span className="text-supporting text-ink-3 sm:hidden">{t("tracker.col.expected")}</span>
        <span className="whitespace-nowrap">{l.expected_display}</span>
      </td>
      <td className={`py-3 align-top max-sm:flex max-sm:justify-between max-sm:gap-4 max-sm:py-0.5 sm:pl-4 sm:text-right ${LINE_INK[l.tone]}`}>
        <span className="text-supporting text-ink-3 sm:hidden">{t("tracker.col.actual")}</span>
        <span className="min-w-0 max-sm:text-right sm:text-right">
          {l.actual_display ? <span className={`block whitespace-nowrap tabular-nums ${l.tone === "neutral" ? "" : "font-semibold"}`}>{l.actual_display}</span> : null}
          {l.actual_note_text ? <span className={`block text-supporting ${l.actual_display ? "text-ink-2" : ""}`}>{l.actual_note_text}</span> : null}
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
    </>
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
        <Figure label={t("tracker.toCome")} testId="tracker-to-come" note={toCome.amount_display ? toCome.note_text : null}>
          {toCome.amount_display ? (
            <p className="type-value font-display text-ink" data-testid="tracker-to-come-figure">
              {toCome.amount_display}
            </p>
          ) : (
            <p className="text-body-lg font-semibold text-ink">{toCome.note_text}</p>
          )}
        </Figure>
      </div>

      <CostBar cost={cost} />

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
          {cost.lines.map((l) => (
            <tr key={l.key} data-testid={`tracker-line-${l.key}`} data-certainty={l.certainty} className="border-b border-line last:border-b-0 max-sm:block max-sm:py-3">
              <LineCells l={l} />
            </tr>
          ))}
        </tbody>
      </table>

      <p className="text-supporting text-ink-2" data-testid="tracker-method">
        {cost.method_text}
      </p>
    </Block>
  );
}
