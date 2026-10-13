"use client";

import { PageHeader, Stat } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceivableRow, ReceivablesRead } from "@/lib/types";
import { isLate, statusTone } from "./state";

/**
 * The top of the page, from the server's own strings: the status (a dot and a word, "read today"), the answer in two lines (what is expected and from
 * whom; what becomes available at collection once the financing is repaid, only while an invoice is financed) and the three plain cards. The repayment is
 * said once here and once in the selected invoice's breakdown, nowhere else. A line renders only when the server sent what it needs; the only words added
 * here are the dictionary's. Nothing is counted, added up, rounded or picked from a row: the counts are the summary's `count_text`, the second line is the
 * server's `headline` and `headline_second`, rendered as they come.
 */
export function Summary({ read, rows }: { read: ReceivablesRead; rows: ReceivableRow[] }) {
  const { t } = useI18n();
  const summary = read.summary ?? {};
  const tone = statusTone(rows);
  const late = rows.some(isLate);
  const next = summary.next_expected;
  // The two heading lines are the server's, verbatim: it chooses them (what is expected and from whom, or what is overdue; what is left once the financing is repaid).
  const line1 = summary.headline ?? null;
  const line2 = summary.headline_second ?? null;

  const title = (
    <span className="block leading-tight">
      {line1 ? <span className="block" data-testid="recv3-h1-expected">{line1}</span> : t("nav.receivables")}
      {line2 ? <span className="mt-1 block" data-testid="recv3-h1-net">{line2}</span> : null}
    </span>
  );
  const dot = tone === "bad" ? "bg-bad-solid" : tone === "warn" ? "bg-warn-solid" : "bg-ok-solid";
  const word = tone === "bad" ? "text-bad-fg" : tone === "warn" ? "text-warn-fg" : "text-ok-fg";

  return (
    <>
      <p className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-3" data-testid="recv3-status" data-tone={tone}>
        <span aria-hidden className={`size-2.5 shrink-0 rounded-full ${dot}`} />
        <span className={`font-bold ${word}`}>{t(`recv3.status.${tone}`)}</span>
        {read.last_read_when ? (
          <>
            <span aria-hidden>·</span>
            <span data-testid="recv3-read-when">{t("biz.readWhen", { when: read.last_read_when })}</span>
          </>
        ) : null}
      </p>
      <PageHeader title={title} />

      {/* What customers owe is the page's figure: the large card on the deep block; the next payment and the net beside it are smaller. */}
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[1.5fr_1fr_1fr]" aria-label={t("biz.recv.facts")} data-testid="recv3-cards">
        <div className="relative isolate overflow-hidden rounded-[24px] bg-brand-900 p-6 text-on-deep shadow-(--shadow-pop) sm:col-span-2 lg:col-span-1" data-testid="recv3-owe">
          <span aria-hidden className="dash-dots absolute inset-y-0 right-0 -z-10 w-2/3" />
          <dt className="text-sm font-semibold text-on-deep-muted">{t("recv3.card.owe")}</dt>
          <dd className={`mt-3 font-display text-[40px] font-extrabold leading-none tracking-[-0.03em] tabular-nums ${late ? "text-bad-bright" : ""}`}>{summary.outstanding_total_display ?? "-"}</dd>
          {summary.count_text ? (
            <dd className="mt-3 text-sm text-on-deep-muted" data-testid="recv3-count">
              {summary.count_text}
            </dd>
          ) : null}
        </div>
        <Stat
          size="lg"
          label={t("recv3.card.next")}
          value={<span className="first-letter:uppercase">{next?.when_text ?? "-"}</span>}
          testId="recv3-next"
          caption={<span className="text-sm">{next?.amount_display && next.buyer_name ? t("recv3.card.next.sub", { amount: next.amount_display, buyer: next.buyer_name }) : t("recv3.card.next.none")}</span>}
        />
        <Stat
          size="lg"
          tone={tone === "ok" ? "ok" : "neutral"}
          label={t("recv3.card.net")}
          value={summary.net_total_display ?? "-"}
          testId="recv3-net"
          caption={<span className="block text-sm first-letter:uppercase">{summary.net_total_text}</span>}
        />
      </dl>
      {/* Billing that is scheduled but not invoiced has no row (it is not owed yet): the server says so in one sentence. */}
      {summary.scheduled_note ? (
        <p className="mt-3 text-sm text-ink-2" data-testid="recv3-scheduled-note">
          {summary.scheduled_note}
        </p>
      ) : null}
    </>
  );
}
