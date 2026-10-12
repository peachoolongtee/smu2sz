"use client";

import { PageHeader, Stat } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceivableRow, ReceivablesRead } from "@/lib/types";
import { isFinanced, isLate, statusTone } from "./state";

/**
 * The top of the page, from the server's own strings: the status (a dot and a word, "read today"), the answer in two lines (what is expected and from
 * whom, then what becomes available at collection once the financing is repaid), one sentence under it, and the three plain cards. A line renders only
 * when the server sent what it needs; the only words added here are the dictionary's. Nothing is added up or rounded: the first row's `net_short` stands
 * for the whole only when there is one row, else the summary's own total.
 */
export function Summary({ read, rows }: { read: ReceivablesRead; rows: ReceivableRow[] }) {
  const { t } = useI18n();
  const summary = read.summary ?? {};
  const late = rows.filter(isLate).length;
  const tone = statusTone(rows);
  const next = summary.next_expected;
  // The buyer behind "next expected": rows come due first, so it is the first one not yet past its day.
  const lead = rows.find((r) => !r.past_due);
  const financed = rows.find(isFinanced);
  const net = rows.length === 1 ? rows[0].net?.net_short : summary.net_total_display;
  const line1 = next?.amount_display && lead?.buyer_name ? t("recv3.h1.expected", { amount: next.amount_display, buyer: lead.buyer_name }) : rows.length ? t("recv3.h1.expected.none") : null;
  const line2 = financed && net ? t("recv3.h1.net", { net }) : null;
  const repays = financed?.net?.repays_text;

  const title = (
    <>
      {line1 ? <span className="block" data-testid="recv3-h1-expected">{line1}</span> : t("nav.receivables")}
      {line2 ? <span className="block first-letter:uppercase" data-testid="recv3-h1-net">{line2}</span> : null}
    </>
  );
  const sub =
    rows.length === 0 ? undefined : (
      <span data-testid="recv3-sub">
        {late > 0 ? t("recv3.sub.late", { n: late }) : t("recv3.sub.clear")}
        {repays ? <> {repays}{t("recv3.sub.notLost")}</> : null}
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
      <PageHeader section="recv" title={title} subtitle={sub} />

      <dl className="grid gap-3 sm:grid-cols-3" aria-label={t("biz.recv.facts")} data-testid="recv3-cards">
        <Stat
          size="lg"
          label={t("recv3.card.owe")}
          value={summary.outstanding_total_display ?? "-"}
          testId="recv3-owe"
          caption={<span className="text-sm">{rows.length ? (late > 0 ? t("recv3.card.owe.late", { n: rows.length, late }) : t("recv3.card.owe.clear", { n: rows.length })) : t("recv3.list.empty")}</span>}
        />
        <Stat
          size="lg"
          label={t("recv3.card.next")}
          value={<span className="first-letter:uppercase">{next?.when_text ?? "-"}</span>}
          testId="recv3-next"
          caption={<span className="text-sm">{next?.amount_display && lead?.buyer_name ? t("recv3.card.next.sub", { amount: next.amount_display, buyer: lead.buyer_name }) : t("recv3.card.next.none")}</span>}
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

