"use client";

import Link from "next/link";
import { FoldCard } from "@/components/business/surface";
import { CheckIcon, XIcon } from "@/components/icons";
import { Badge, ErrorState, LoadingBlock } from "@/components/ui";
import { getReconciliation } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { HomeTone } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { whenText } from "@/lib/when";

const TILE: Record<HomeTone, string> = { ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg", neutral: "text-ink" };

/** One figure of the reconciliation, as a tile: its label, the server's figure, large. */
function Tile({ label, value, tone = "neutral", testId }: { label: string; value: string | number; tone?: HomeTone; testId?: string }) {
  return (
    <div className="card-flat min-w-0" data-testid={testId}>
      <p className="text-supporting font-semibold text-ink-3">{label}</p>
      <p className={`mt-2 font-display text-[28px] font-extrabold leading-none tracking-[-0.02em] tabular-nums ${TILE[tone]}`}>{value}</p>
    </div>
  );
}

/**
 * The reconciliation log on Activity (the engine's GET /reconciliation, in the owner's words): four figures, then each list as a dropdown card. Rows are
 * read through the server's `detail_when` sentences and buyer names; days are distances from today. Every amount is the server's display string.
 */
export function ReconciliationSection({ today, buyerName }: { today: number; buyerName: (id: string) => string }) {
  const { t, te } = useI18n();
  const recon = useAsync(getReconciliation, []);
  const data = recon.data;
  if (recon.error) return <ErrorState error={recon.error} onRetry={recon.reload} />;
  if (!data) return <LoadingBlock rows={3} />;
  const promised = data.promised ?? [];
  return (
    <section id="activity-reconciliation" aria-labelledby="activity-reconciliation-title" className="space-y-4 scroll-mt-20" data-testid="activity-reconciliation">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="activity-reconciliation-title" className="font-display text-xl font-extrabold tracking-[-0.01em] text-ink">
            {t("recon.title")}
          </h2>
          <p className="text-supporting text-ink-3">{t("biz.recon.sub")}</p>
        </div>
        <Badge tone={data.chain_valid ? "ok" : "bad"}>
          {data.chain_valid ? <CheckIcon /> : <XIcon />}
          {data.chain_valid ? t("ledger.chainValid") : t("ledger.chainBroken")}
        </Badge>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile label={t("recon.matched")} value={data.matched} tone="ok" testId="recon-matched" />
        <Tile label={t("recon.flagged")} value={data.flagged} tone={data.flagged ? "bad" : "neutral"} testId="recon-flagged" />
        <Tile label={t("recon.received")} value={data.received_total_display} testId="recon-received" />
        <Tile label={t("recon.expected")} value={data.expected_total_display} testId="recon-expected" />
      </div>

      <FoldCard title={t("recon.receipts")} hint={data.receipts.length ? t("biz.recon.count", { n: data.receipts.length }) : t("recon.receipts.empty.title")} testId="recon-receipts" defaultOpen={data.flagged > 0}>
        {data.receipts.length ? (
          <ul className="divide-y divide-line">
            {data.receipts.map((r) => (
              <li key={r.entry_hash} className={`grid gap-x-4 gap-y-1 py-3 sm:grid-cols-[minmax(0,1fr)_auto] ${r.flagged ? "rounded-tile bg-bad-bg/50 px-3" : ""}`} data-testid={`receipt-${r.op_id}`}>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">{r.detail_when ?? r.detail}</p>
                  <p className="mt-0.5 text-supporting text-ink-3">
                    {r.counterparty_id ? `${buyerName(r.counterparty_id)} · ` : ""}
                    {whenText(r.day, today, t)}
                    {r.bank_reference ? ` · ${t("recon.bankRef", { ref: r.bank_reference })}` : ""}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 sm:justify-end">
                  <dl className="flex gap-4 text-supporting">
                    <div>
                      <dt className="text-ink-3">{t("recon.col.received")}</dt>
                      <dd className="font-bold tabular-nums text-ink">{r.received_display}</dd>
                    </div>
                    <div>
                      <dt className="text-ink-3">{t("recon.col.expected")}</dt>
                      <dd className="font-bold tabular-nums text-ink">{r.expected_display ?? t("common.none")}</dd>
                    </div>
                    {r.difference_display ? (
                      <div>
                        <dt className="text-ink-3">{t("recon.col.difference")}</dt>
                        <dd className="font-bold tabular-nums text-ink">{r.difference_display}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <Badge tone={r.flagged ? "bad" : "ok"}>{te("recstatus", r.status)}</Badge>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">{t("recon.receipts.empty.body")}</p>
        )}
      </FoldCard>

      <FoldCard title={t("recon.promised")} hint={`${t("recon.lapsed")}: ${data.lapsed_promises ?? 0}`} testId="recon-promised">
        <p className="mb-2 text-supporting text-ink-3">{t("recon.promised.sub")}</p>
        {promised.length ? (
          <ul className="divide-y divide-line">
            {promised.map((p) => (
              <li key={`${p.commitment_id}:${p.obligation_id}:${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-3 py-3" data-testid={`promised-${p.receivable_id}`} data-status={p.status}>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink">{p.detail_when ?? p.detail}</p>
                  <p className="mt-0.5 text-supporting text-ink-3">
                    {buyerName(p.counterparty_id)}
                    {p.promised_day !== null ? ` · ${t("biz.recon.promisedBy", { when: whenText(p.promised_day, today, t) })}` : ""}
                  </p>
                </div>
                <dl className="flex gap-4 text-supporting">
                  <div>
                    <dt className="text-ink-3">{t("recon.col.face")}</dt>
                    <dd className="font-bold tabular-nums text-ink">{p.face_display}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">{t("recon.col.discount")}</dt>
                    <dd className="font-bold tabular-nums text-ink">{p.discount_display}</dd>
                  </div>
                  <div>
                    <dt className="text-ink-3">{t("recon.col.expected")}</dt>
                    <dd className="font-bold tabular-nums text-ink">{p.expected_display}</dd>
                  </div>
                </dl>
                <Badge tone={p.status === "RECEIVED" ? "ok" : p.status === "AWAITED" ? "info" : "bad"}>{te("promstatus", p.status)}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">{t("recon.promised.empty")}</p>
        )}
      </FoldCard>

      <FoldCard title={t("recon.outstanding")} hint={data.outstanding.length ? t("biz.recon.count", { n: data.outstanding.length }) : t("recon.outstanding.empty")} testId="recon-outstanding">
        <p className="mb-2 text-supporting text-ink-3">{t("recon.outstanding.sub")}</p>
        {data.outstanding.length ? (
          <ul className="divide-y divide-line">
            {data.outstanding.map((o) => (
              <li key={o.receivable_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-ink">{buyerName(o.counterparty_id)}</p>
                  <p className="text-supporting text-ink-3">{t("biz.recon.due", { when: whenText(o.due_day, today, t) })}</p>
                </div>
                <span className="font-bold tabular-nums text-ink">{o.face_display}</span>
                <Badge tone={o.past_due ? "bad" : "neutral"}>{o.past_due ? t("recon.pastDue") : t("recon.onTime")}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-2">{t("recon.outstanding.empty")}</p>
        )}
        <Link href="/receivables" className="mt-3 inline-flex text-sm font-bold text-brand-700 hover:underline">
          {t("biz.recon.toReceivables")}
        </Link>
      </FoldCard>
    </section>
  );
}
