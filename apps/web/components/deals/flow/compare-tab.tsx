"use client";

import { Fragment, useRef, useState, type ReactNode } from "react";
import { BeforeTheyAsk } from "@/components/deals/before-they-ask";
import { Disclosure } from "@/components/business/kit";
import { Button } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { STRATEGY_MVP } from "@/lib/config";
import { useI18n } from "@/lib/i18n";
import type { OfferPictureView, PicturePath } from "@/lib/types";
import { CostTable } from "./cost-table";
import { comparisonRows, type CompareCellModel, type CompareRowKey } from "./deal-model";
import { Cell, NONE, quietLink } from "./flow-parts";
import { EnvelopePackages, WhyDiffer } from "./investigate";
import { FinancialOutcomes } from "./outcomes";
import { ScopeTerms } from "./scope-terms";

const EXPANDABLE: CompareRowKey[] = ["terms", "economic"];

function Chevron({ open }: { open: boolean }) {
  return (
    <svg aria-hidden viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`ml-1 inline-block transition-transform duration-(--dur-fast) ${open ? "rotate-180" : ""}`}>
      <path d="m4 6 4 4 4-4" />
    </svg>
  );
}

function CellView({ row, cell }: { row: CompareRowKey; cell: CompareCellModel }) {
  if (row === "terms") {
    if (!cell.lines?.length) return NONE;
    return (
      <ul className="m-0 list-none space-y-0.5 p-0 text-sm text-ink">
        {cell.lines.map((l, i) => (
          <li key={i} className="leading-5">
            {l.scope ? <span className="text-supporting text-ink-3">{l.scope} </span> : null}
            {l.text}
          </li>
        ))}
      </ul>
    );
  }
  if (!cell.value && !cell.sub && !cell.note) return NONE;
  return <Cell value={row === "status" ? null : cell.value} sub={cell.sub} note={cell.note} bad={cell.bad} />;
}

/**
 * Compare responses (round three, sections 1, 4, 5 and 7): the commercial packages only (the buyer's request and each reply; doing nothing and the buyer stopping are Business consequences on Cash
 * impact), with the five default rows Commercial terms, Economic impact, Cash outcome, Authorization and Buyer status. Each cell is one server word. A row expands in place to its calculation (the
 * terms by scope, the cost rows, the funding each response rests on) behind "View ... →". Each reply's column ends with one quiet button that SELECTS it (`path` in the address) and brings the
 * review into view; nothing is sent here. The request's column says "Review the request" when accepting it is possible, and carries its authority word otherwise. Then the financial outcomes and
 * "Why these results differ", with the evidence behind folds; then "Review selected response" (outlined: the deal header holds the one filled button) and "Back to deal".
 */
export function CompareTab({
  picture,
  paths,
  buyerId,
  focusKey,
  onPick,
  onReviewSelected,
  onReviewRequest,
  onBack,
}: {
  picture: OfferPictureView;
  paths: PicturePath[];
  buyerId: string;
  /** The response the review would be about (the address's `path`, else the recommended reply). */
  focusKey: string | null;
  onPick: (key: string) => void;
  /** Opens the send review of the selected response; absent when it cannot be sent. */
  onReviewSelected?: () => void;
  /** Opens the owner's accept review of the request; absent unless accepting is possible. */
  onReviewRequest?: () => void;
  onBack: () => void;
}) {
  const { t } = useI18n();
  const [open, setOpen] = useState<Set<CompareRowKey>>(new Set());
  const reviewRef = useRef<HTMLButtonElement>(null);
  const rows = comparisonRows(paths);
  const toggle = (k: CompareRowKey) =>
    setOpen((o) => {
      const n = new Set(o);
      if (n.has(k)) n.delete(k);
      else n.add(k);
      return n;
    });
  // The server's own label for each response, everywhere (one response, one name).
  const heads = (p: PicturePath) => p.label;
  const rowLabel = (k: CompareRowKey) => t(`deals.cmp.row.${k}` as const);
  const calcLabel = (k: CompareRowKey) => t(`deals.cmp.calc.${k as "terms" | "economic"}` as const);
  const choose = (p: PicturePath) => {
    onPick(p.key);
    // The selection brings the review into view (the button that opens it).
    window.requestAnimationFrame(() => reviewRef.current?.scrollIntoView({ block: "nearest", behavior: "auto" }));
  };
  const action = (p: PicturePath): ReactNode => {
    if (p.kind === "asked") {
      return onReviewRequest ? (
        <Button size="sm" variant="secondary" onClick={onReviewRequest} data-testid="deal-review-request">
          {t("accept.review")}
        </Button>
      ) : null;
    }
    if (!p.sendable) return null;
    const selected = focusKey === p.key;
    return (
      <Button size="sm" variant="secondary" aria-pressed={selected} onClick={() => choose(p)} data-testid={`deal-use-${p.key}`}>
        {selected ? t("deals.cmp.chosen", { label: p.label }) : p.authority === "flow_may" ? t("deals.cmp.choose", { label: p.label }) : t("deals.cmp.review", { label: p.label })}
      </Button>
    );
  };
  const expansion = (k: CompareRowKey): ReactNode => {
    if (k === "terms") return <ScopeTerms picture={picture} paths={paths} heads={paths.map(heads)} testId="deal-compare-scope-terms" />;
    return <CostTable paths={paths} heads={paths.map(heads)} caption={t("deals.cost.title")} testId="deal-cost-table" />;
  };
  const cols = paths.length;
  const labelCell = "border-b border-line py-3 pr-3 text-left align-top text-supporting font-bold text-ink-3";
  const bodyCell = "border-b border-line px-3 py-3 align-top text-sm";
  const anyAction = paths.some((p) => action(p));
  return (
    <div className="space-y-8" data-testid="deal-compare">
      <section aria-label={t("deals.cmp.table")} className="@container" data-testid="deal-compare-section">
        {/* From 44 rem of its own width the responses are columns; below it each response is a block of the same cells. */}
        <div className="hidden @min-[44rem]:block" data-testid="deal-compare-table">
          <table className="w-full table-fixed border-separate border-spacing-0">
            <caption className="sr-only">{t("deals.cmp.table")}</caption>
            <colgroup>
              <col className="w-[160px]" />
              {paths.map((p) => (
                <col key={p.key} />
              ))}
            </colgroup>
            <thead>
              <tr>
                <td className="border-b border-line-strong" />
                {paths.map((p) => (
                  <th key={p.key} scope="col" className={`border-b border-line-strong px-3 py-2 text-left align-bottom ${focusKey === p.key ? "bg-f-purple-soft" : ""}`} data-testid={`deal-compare-head-${p.kind === "asked" ? "asked" : "reply"}`} data-selected={focusKey === p.key ? "true" : undefined}>
                    <span className="block text-sm font-bold text-ink">{heads(p)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <Fragment key={r.key}>
                  <tr data-testid={`deal-compare-row-${r.key}`}>
                    <th scope="row" className={labelCell}>
                      {rowLabel(r.key)}
                      {EXPANDABLE.includes(r.key) ? (
                        <button type="button" aria-expanded={open.has(r.key)} aria-controls={`deal-calc-${r.key}`} onClick={() => toggle(r.key)} className={`${quietLink} mt-1 -ml-2 block text-left`} data-testid={`deal-compare-expand-${r.key}`}>
                          {open.has(r.key) ? t("deals.cmp.hide") : calcLabel(r.key)}
                          <Chevron open={open.has(r.key)} />
                        </button>
                      ) : null}
                    </th>
                    {r.cells.map((c, i) => (
                      <td key={paths[i].key} className={`${bodyCell} ${focusKey === paths[i].key ? "bg-f-purple-soft/40" : ""}`} data-testid={`deal-compare-cell-${r.key}-${paths[i].kind === "asked" ? "asked" : "reply"}`}>
                        {r.key === "status" ? (c.value ? <span className="text-ink">{c.value}</span> : NONE) : <CellView row={r.key} cell={c} />}
                      </td>
                    ))}
                  </tr>
                  {open.has(r.key) ? (
                    <tr>
                      <td colSpan={cols + 1} className="border-b border-line bg-subtle/50 px-3 py-3" id={`deal-calc-${r.key}`} data-testid={`deal-compare-calc-${r.key}`}>
                        {expansion(r.key)}
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
              {anyAction ? (
                <tr>
                  <th scope="row" className="py-3 pr-3" />
                  {paths.map((p) => (
                    <td key={p.key} className="px-3 py-3 align-top" data-testid={`deal-compare-action-${p.kind === "asked" ? "asked" : "reply"}`}>
                      {action(p)}
                    </td>
                  ))}
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
        <div className="space-y-4 @min-[44rem]:hidden" data-testid="deal-compare-stack">
          {paths.map((p, i) => (
            <article key={p.key} className={`rounded-tile border border-line p-4 ${focusKey === p.key ? "bg-f-purple-soft/40" : ""}`} aria-label={heads(p)}>
              <h3 className="text-sm font-bold text-ink">{heads(p)}</h3>
              <dl className="mt-3 divide-y divide-line">
                {rows.map((r) => (
                  <div key={r.key} className="py-2">
                    <dt className="text-supporting font-bold text-ink-3">{rowLabel(r.key)}</dt>
                    <dd className="m-0 mt-0.5 text-sm">{r.key === "status" ? (r.cells[i].value ?? NONE) : <CellView row={r.key} cell={r.cells[i]} />}</dd>
                  </div>
                ))}
              </dl>
              <div className="mt-3">{action(p)}</div>
            </article>
          ))}
          <div className="space-y-2" data-testid="deal-compare-stack-calcs">
            {EXPANDABLE.map((k) => (
              <Disclosure key={k} summary={calcLabel(k)} testId={`deal-compare-stack-calc-${k}`}>
                <div className="pt-2">{expansion(k)}</div>
              </Disclosure>
            ))}
          </div>
        </div>
      </section>

      <FinancialOutcomes picture={picture} paths={paths} />

      <WhyDiffer picture={picture} paths={paths} />

      <ActionGroup testId="deal-compare-actions" label={t("deals.actions")}>
        {onReviewSelected ? (
          <Button ref={reviewRef} variant="secondary" onClick={onReviewSelected} data-testid="deal-review-selected">
            {t("deals.cmp.reviewSelected")}
          </Button>
        ) : null}
        <button type="button" onClick={onBack} className={quietLink} data-testid="deal-back">
          {t("deals.cmp.back")}
        </button>
      </ActionGroup>

      {/* The evidence behind the comparison: what the owner can live with for this buyer, then the envelope's packages by who may send them (the strategy build). */}
      {STRATEGY_MVP ? (
        <div data-testid="deal-before-they-ask">
          <BeforeTheyAsk buyerId={buyerId} />
        </div>
      ) : null}
      <EnvelopePackages buyerId={buyerId} />
    </div>
  );
}
