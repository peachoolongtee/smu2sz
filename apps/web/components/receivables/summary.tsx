"use client";

import { PageHeader, Stat } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceivableRow, ReceivablesRead } from "@/lib/types";
import { isFinanced, isLate, statusTone } from "./state";

/**
 * The top of the page, from the server's own strings: the status (a dot and a word, "read today"), the answer in two lines (what is expected and from
 * whom; what becomes available at collection once the financing is repaid, only while an invoice is financed) and the three plain cards. The repayment is
 * said once here and once in the selected invoice's breakdown, nowhere else. A line renders only when the server sent what it needs; the only words added
 * here are the dictionary's. Nothing is counted, added up, rounded or picked from a row: the counts are the summary's `count_text`, the second line is the
 * server's `repays_line` when it sends one (else the dictionary's sentence around the summary's own net total).
 */
export function Summary({ read, rows }: { read: ReceivablesRead; rows: ReceivableRow[] }) {
  const { t } = useI18n();
  const summary = read.summary ?? {};
  const tone = statusTone(rows);
  const late = rows.some(isLate);
  const next = summary.next_expected;
  const amount = next?.amount_short ?? next?.amount_display;
  const financed = summary.financed_count !== undefined ? summary.financed_count > 0 : rows.some(isFinanced);
  // While something is overdue the server's own sentence leads, when it sends one; the overdue state is the status word and the first card meanwhile.
  const line1 =
    late && summary.h1_overdue
      ? summary.h1_overdue
      : amount && next?.buyer_name
        ? t("recv3.h1.expected", { amount, buyer: next.buyer_name })
        : rows.length
          ? t("recv3.h1.expected.none")
          : null;
  const line2 = financed ? (summary.repays_line ?? (summary.net_total_display ? t("recv3.h1.net", { net: summary.net_total_display }) : null)) : null;

  const title = (
    <span className="block leading-tight">
      {line1 ? <span className="block" data-testid="recv3-h1-expected">{line1}</span> : t("nav.receivables")}
      {line2 ? <span className="mt-1 block first-letter:uppercase" data-testid="recv3-h1-net">{line2}</span> : null}
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

      <dl className="grid gap-3 sm:grid-cols-3" aria-label={t("biz.recv.facts")} data-testid="recv3-cards">
        <Stat
          size="lg"
          tone={late ? "bad" : "neutral"}
          label={t("recv3.card.owe")}
          value={summary.outstanding_total_display ?? "-"}
          testId="recv3-owe"
          caption={summary.count_text ? <span className="text-sm" data-testid="recv3-count">{summary.count_text}</span> : undefined}
        />
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
    </>
  );
}
