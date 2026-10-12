"use client";

import { Chip } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { BorrowerFileSection } from "@/lib/types";

/**
 * The borrower file's contents on the page, laid out like the downloaded file: a table section is a real table with the
 * server's column names and one figure per cell, any other section a list of label and value. Every text is the
 * server's; the page only arranges it. Long hashes are shortened on screen, the full value stays in the tooltip and the
 * downloaded file.
 */

/** A figure's text with every 64-character hash shortened to its first 12 characters. */
function Shortened({ text }: { text: string }) {
  const short = text.replace(/\b([0-9a-f]{12})[0-9a-f]{52}\b/g, "$1…");
  return short === text ? <>{text}</> : <span title={text}>{short}</span>;
}

/** The figures of a row as the server lists them, or its joined value from an older recording. */
function figuresOf(row: BorrowerFileSection["rows"][number]): { text: string; evidence?: string }[] {
  return row.figures?.length ? row.figures : [{ text: row.value, evidence: row.evidence }];
}

function TableSection({ s, title }: { s: BorrowerFileSection; title: string }) {
  const columns = s.columns ?? [];
  return (
    // Wide tables scroll inside their card on a phone; the page itself never scrolls sideways. As with TableWrap, the
    // scrolling area is a named region a keyboard can reach.
    <div className="-mx-1 overflow-x-auto px-1" role="region" aria-label={title} tabIndex={0}>
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr className="border-b border-line text-supporting text-ink-3">
            <th scope="col" className="py-2 pr-4 text-left font-medium">
              <span className="sr-only">{title}</span>
            </th>
            {columns.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 text-right font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {s.rows.map((r) => {
            const figs = figuresOf(r);
            return (
              <tr key={r.label} className="border-b border-line/60 last:border-0">
                <th scope="row" className="whitespace-nowrap py-2 pr-4 text-left font-normal text-ink-2">
                  {r.label}
                </th>
                {(figs.length === columns.length ? figs : [{ text: r.value }]).map((f, i) => (
                  <td
                    key={i}
                    colSpan={figs.length === columns.length ? undefined : columns.length}
                    className={`whitespace-nowrap px-3 py-2 text-right font-medium tabular-nums ${f.text.startsWith("−") ? "text-bad-fg" : "text-ink"}`}
                  >
                    <Shortened text={f.text} />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ListSection({ s }: { s: BorrowerFileSection }) {
  const { t } = useI18n();
  return (
    <dl className="divide-y divide-line/60 text-sm">
      {s.rows.map((r) => {
        const figs = figuresOf(r);
        const estimate = figs.some((f) => f.evidence === "OWNER_ESTIMATE");
        return (
          <div key={r.label} className="grid gap-1 py-2 sm:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] sm:gap-4">
            <dt className="text-ink-2">
              {r.label}
              {r.note ? <span className="mt-0.5 block text-supporting text-ink-3">{r.note}</span> : null}
            </dt>
            <dd className="min-w-0 break-words font-medium tabular-nums text-ink">
              {figs.map((f, i) => (
                <span key={i}>
                  {i > 0 ? <span className="px-1.5 text-ink-3">·</span> : null}
                  <Shortened text={f.text} />
                </span>
              ))}
              {estimate ? (
                <span className="ml-2 align-middle">
                  <Chip tone="info">{t("biz.capex.file.ownerEstimate")}</Chip>
                </span>
              ) : null}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function BorrowerFileSections({ sections }: { sections: BorrowerFileSection[] }) {
  const { lang } = useI18n();
  return (
    <div className="space-y-3" data-testid="file-sections">
      {sections.map((s) => {
        const title = lang === "zh" && s.title_zh ? s.title_zh : s.title;
        return (
          <section key={s.key ?? s.title} className="rounded-tile border border-line p-3" data-testid={`file-section-${s.key ?? s.title}`}>
            <h3 className="mb-2 text-sm font-semibold text-ink">{title}</h3>
            {s.columns?.length ? <TableSection s={s} title={title} /> : <ListSection s={s} />}
            {s.notes?.length ? (
              <ul className="mt-2 list-disc space-y-1 pl-5 text-supporting text-ink-3">
                {s.notes.map((n) => (
                  <li key={n}>
                    <Shortened text={n} />
                  </li>
                ))}
              </ul>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
