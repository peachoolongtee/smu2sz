"use client";

import { ACTION_KEY } from "@/components/deals/decision";
import { Badge, Card, ErrorState, Formula, LoadingBlock, TableWrap, tableCls, tdCls, thCls, type Tone } from "@/components/ui";
import { getReliability } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { BuyerReliability, RankedDeal, ReliabilityGrade, ReliabilityTone, ReliabilityView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

export const GRADE_TONE: Record<ReliabilityGrade, Tone> = { RELIABLE: "ok", WATCH: "warn", RISKY: "bad", UNRATED: "neutral" };
const REASON_DOT: Record<ReliabilityTone, string> = { good: "bg-ok-fg", warn: "bg-warn-fg", bad: "bg-bad-fg", info: "bg-ink-3" };
const ROW_TONE: Record<ReliabilityTone, string> = { good: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", info: "text-ink-2" };

/** The server's reliability read for the deals opened in this session (the card and the inbox badges share it). */
export function useReliability(offerIds: string[]) {
  const { lang } = useI18n();
  return useAsync<ReliabilityView>(() => getReliability(lang, offerIds), [lang, offerIds.join(",")]);
}

/** A buyer's grade as a small badge (the inbox rows). */
export function GradeBadge({ buyer }: { buyer: BuyerReliability | undefined }) {
  const { t } = useI18n();
  if (!buyer) return null;
  return (
    <Badge tone={GRADE_TONE[buyer.grade]} title={buyer.advice}>
      {buyer.grade_words}
      {buyer.score !== null ? ` · ${t("biz.rel.score", { score: buyer.score })}` : ""}
    </Badge>
  );
}

function Reasons({ b }: { b: BuyerReliability }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {b.reasons.map((r) => (
        <li key={r.text} className="flex items-start gap-2">
          <span aria-hidden className={`mt-1.5 size-2 shrink-0 rounded-full ${REASON_DOT[r.tone]}`} />
          <span className="text-ink-2">{r.text}</span>
        </li>
      ))}
    </ul>
  );
}

function History({ b }: { b: BuyerReliability }) {
  const { t, te } = useI18n();
  if (!b.history.length) return null;
  return (
    <TableWrap label={t("biz.rel.history")}>
      <table className={tableCls}>
        <thead>
          <tr>
            <th className={thCls}>{t("biz.rel.col.invoice")}</th>
            <th className={thCls}>{t("biz.rel.col.amount")}</th>
            <th className={thCls}>{t("biz.rel.col.terms")}</th>
            <th className={thCls}>{t("biz.rel.col.paid")}</th>
          </tr>
        </thead>
        <tbody>
          {b.history.map((h) => (
            <tr key={h.invoice_id}>
              <td className={tdCls}>
                <span className="font-mono text-xs">{h.invoice_id}</span>{" "}
                <span className="text-xs text-ink-3">({te("biz.rel.source", h.source)})</span>
              </td>
              <td className={`${tdCls} tabular-nums`}>{h.face_display}</td>
              <td className={`${tdCls} tabular-nums`}>{t("biz.rel.termsDays", { n: h.terms_days })}</td>
              <td className={`${tdCls} font-medium ${ROW_TONE[h.tone]}`}>{h.words}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function BuyerRow({ b, mode }: { b: BuyerReliability; mode: Mode }) {
  const { t, te } = useI18n();
  const facts = [
    b.agreed_terms_days !== null && b.effective_terms_days !== null && b.effective_terms_days !== b.agreed_terms_days
      ? t("biz.rel.terms", { agreed: b.agreed_terms_days, effective: b.effective_terms_days })
      : null,
    b.on_time_rate_display ? t("biz.rel.onTime", { rate: b.on_time_rate_display }) : null,
    b.invoices_learned ? t("biz.rel.learned", { n: b.invoices_learned }) : null,
  ].filter(Boolean);
  return (
    <li className="px-4 py-3" data-testid={`reliability-buyer-${b.counterparty_id}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="w-6 shrink-0 text-sm font-semibold tabular-nums text-ink-3">#{b.rank}</span>
        <span className="min-w-0 flex-1 break-words text-sm font-semibold text-ink">{b.name}</span>
        {b.trend !== "STEADY" ? <Badge tone={b.trend === "WORSENING" ? "bad" : "ok"}>{te("biz.rel.trend", b.trend)}</Badge> : null}
        <Badge tone={GRADE_TONE[b.grade]}>{b.grade_words}</Badge>
        <span className="text-sm font-semibold tabular-nums text-ink" data-testid="reliability-score">
          {b.score !== null ? t("biz.rel.score", { score: b.score }) : t("biz.rel.unrated")}
        </span>
      </div>
      {/* The advice is the one line shown; it opens the why (facts, reasons, history). */}
      <details className="mt-1 pl-9">
        <summary className="cursor-pointer text-sm text-ink-2">
          {b.advice} <span className="text-xs font-medium text-brand-700">{t("biz.rel.why")}</span>
        </summary>
        <div className="mt-2 space-y-3">
          {facts.length ? <p className="text-xs text-ink-3">{facts.join(" · ")}</p> : null}
          <Reasons b={b} />
          <History b={b} />
          {mode === "demo" ? (
            <div>
              <p className="mb-1 text-xs text-ink-3">{t("biz.rel.formula")}</p>
              <Formula>{b.formula}</Formula>
            </div>
          ) : null}
        </div>
      </details>
    </li>
  );
}

function DealRow({ d }: { d: RankedDeal }) {
  const { t } = useI18n();
  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3" data-testid={`reliability-deal-${d.offer_id}`}>
      <span className="w-6 shrink-0 text-sm font-semibold tabular-nums text-ink-3">#{d.rank}</span>
      <span className="min-w-0 flex-1 basis-56">
        <span className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-ink">{d.buyer_name}</span>
          <Badge tone={GRADE_TONE[d.grade]}>{d.grade_words}</Badge>
        </span>
        <span className="mt-0.5 block text-sm text-ink-2">{d.why}</span>
      </span>
      <span className="shrink-0 text-xs font-medium text-ink">
        {d.business_action ? t(ACTION_KEY[d.business_action]) : t("biz.rel.notChecked")}
      </span>
    </li>
  );
}

/**
 * Who pays reliably: the open deals of this session ranked by how their buyer pays, then every buyer with the why
 * (the server's sentences, the payment history and, in Demo mode, the formula). Advice only; it decides nothing.
 */
export function ReliabilityCard({ data, mode }: { data: ReturnType<typeof useReliability>; mode: Mode }) {
  const { t } = useI18n();
  const r = data.data;
  return (
    <Card id="reliability" title={t("biz.rel.title")} subtitle={t("biz.rel.sub")}>
      {data.error ? (
        <ErrorState error={data.error} onRetry={data.reload} />
      ) : !r ? (
        <LoadingBlock rows={2} />
      ) : (
        <div className="-m-4 divide-y divide-line">
          {r.deals.length > 1 ? (
            <section aria-label={t("biz.rel.deals")} data-testid="reliability-deals">
              <h3 className="bg-subtle px-4 py-2 text-xs font-semibold text-ink-2">{t("biz.rel.deals")}</h3>
              <ul className="divide-y divide-line">
                {r.deals.map((d) => (
                  <DealRow key={d.offer_id} d={d} />
                ))}
              </ul>
            </section>
          ) : null}
          <section aria-label={t("biz.rel.buyers")} data-testid="reliability-buyers">
            {r.deals.length > 1 ? <h3 className="bg-subtle px-4 py-2 text-xs font-semibold text-ink-2">{t("biz.rel.buyers")}</h3> : null}
            <ul className="divide-y divide-line">
              {r.buyers.map((b) => (
                <BuyerRow key={b.counterparty_id} b={b} mode={mode} />
              ))}
            </ul>
          </section>
        </div>
      )}
    </Card>
  );
}
