import type { ReactNode } from "react";

export interface CompareColumn {
  key: string;
  /** The path's name. */
  head: string;
  /** Under the name: the tag (FLOW recommends, Over your limit, Needs your approval), already a `StateWord` or a word. */
  tag?: ReactNode;
  /** Under the tag: the server's evidence line for this column. */
  evidence?: ReactNode;
  recommended?: boolean;
}

export interface CompareRow {
  key: string;
  label: string;
  /** One cell per column, in the columns' order. */
  cells: ReactNode[];
}

/**
 * The responses side by side. A 150 px row head, then one column per path; hairline rows with 11 and 14 px cell padding. The recommended column has a `brand-50` header
 * with a 2 px brand rule on top, a light tint and `info-line` sides. At least 600 px wide: below that it scrolls sideways with the row heads sticky (the text never shrinks);
 * below 1024 px it stacks into one block per response. Both forms hold the same cells (`testId` and `${testId}-stack`); the page shows one of them.
 * `container`: the table lives in a pane that is narrower than the window (a queue beside it), so the switch follows the width of its own container (448 px, and the table may be as narrow as 420) and not the window's.
 */
export function ComparisonTable({ caption, columns, rows, testId, container = false }: { caption: string; columns: CompareColumn[]; rows: CompareRow[]; testId: string; container?: boolean }) {
  const tableShown = container ? "@min-[28rem]:block" : "lg:block";
  const stackHidden = container ? "@min-[28rem]:hidden" : "lg:hidden";
  return (
    <div data-testid={testId} className={container ? "@container" : undefined}>
      <div className={`hidden overflow-x-auto ${tableShown}`} data-testid={`${testId}-scroll`}>
        <table className={`w-full ${container ? "min-w-[420px]" : "min-w-[600px]"} table-fixed border-separate border-spacing-0 text-sm`} data-testid={`${testId}-table`}>
          <caption className="sr-only">{caption}</caption>
          <colgroup>
            <col className="w-[150px]" />
            {columns.map((c) => (
              <col key={c.key} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 bg-canvas border-b border-line-strong py-2.5 pr-3.5 text-left align-bottom">
                <span className="sr-only">{caption}</span>
              </th>
              {columns.map((c) => (
                <th
                  key={c.key}
                  scope="col"
                  data-recommended={c.recommended ? "true" : undefined}
                  className={`border-b border-line-strong px-3.5 py-2.5 text-left align-bottom font-bold text-ink ${c.recommended ? "rounded-t-control bg-brand-50 shadow-[inset_0_2px_0_var(--color-brand-600),inset_1px_0_0_var(--color-info-line),inset_-1px_0_0_var(--color-info-line)]" : ""}`}
                >
                  {c.head}
                  {c.tag ? <span className="mt-0.5 block text-supporting font-bold">{c.tag}</span> : null}
                  {c.evidence ? <span className="mt-1 block text-supporting font-normal text-ink-2">{c.evidence}</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, ri) => (
              <tr key={r.key} data-testid={`${testId}-row-${r.key}`}>
                <th scope="row" className="sticky left-0 z-10 bg-canvas border-b border-line py-2.5 pr-3.5 text-left align-top text-supporting font-bold text-ink-3">
                  {r.label}
                </th>
                {r.cells.map((cell, ci) => (
                  <td
                    key={columns[ci].key}
                    className={`border-b border-line px-3.5 py-2.5 align-top ${columns[ci].recommended ? `bg-brand-50/45 shadow-[inset_1px_0_0_var(--color-info-line),inset_-1px_0_0_var(--color-info-line)] ${ri === rows.length - 1 ? "shadow-[inset_1px_0_0_var(--color-info-line),inset_-1px_0_0_var(--color-info-line),inset_0_-1px_0_var(--color-info-line)]" : ""}` : ""}`}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className={`grid gap-3 ${stackHidden}`} data-testid={`${testId}-stack`}>
        {columns.map((c, ci) => (
          <div key={c.key} className={`rounded-tile border px-4 py-3 ${c.recommended ? "border-info-line bg-brand-50/45" : "border-line"}`}>
            <h3 className="font-bold text-ink">
              {c.head}
              {c.tag ? <span className="mt-0.5 block text-supporting font-bold">{c.tag}</span> : null}
              {c.evidence ? <span className="mt-1 block text-supporting font-normal text-ink-2">{c.evidence}</span> : null}
            </h3>
            <dl className="mt-2 divide-y divide-line">
              {rows.map((r) => (
                <div key={r.key} className="py-2">
                  <dt className="text-supporting font-bold text-ink-3">{r.label}</dt>
                  <dd className="mt-0.5 text-sm">{r.cells[ci]}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
