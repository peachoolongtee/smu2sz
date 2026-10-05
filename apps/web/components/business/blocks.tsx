"use client";

import Link from "next/link";
import { approvalHref } from "@/components/operation-result";
import { Card, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeApproval, HomeChange, HomeReceivables, HomeView } from "@/lib/types";

const CHANGE_GLYPH: Record<string, string> = { RECEIPT: "↓", LATE: "!", WAITING: "…", REFUSED: "✕", LANDED: "↓", OPERATION: "✓", AGREEMENT: "✓" };
const CHANGE_TONE: Record<string, string> = {
  RECEIPT: "bg-ok-bg text-ok-fg",
  LANDED: "bg-ok-bg text-ok-fg",
  LATE: "bg-bad-bg text-bad-fg",
  WAITING: "bg-warn-bg text-warn-fg",
  REFUSED: "bg-bad-bg text-bad-fg",
  OPERATION: "bg-subtle text-ink-2",
  AGREEMENT: "bg-ok-bg text-ok-fg",
};

/** Level 2: what requires the owner's decision, as questions. The buttons are on the approval card, never here. */
export function DecisionsBlock({ approvals }: { approvals: HomeApproval[] }) {
  const { t } = useI18n();
  return (
    <Card id="home-decisions" title={t("biz.decisions")} subtitle={t("biz.decisions.sub")} actions={<Link href="/approvals" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("home.waiting.open")}</Link>}>
      {approvals.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-waiting-empty">
          {t("biz.decisions.none")}
        </p>
      ) : (
        <ul className="space-y-2" data-testid="home-waiting-list">
          {approvals.map((a) => (
            <li key={a.id} className="rounded-md border border-warn-line bg-warn-bg/40 px-3 py-2" data-testid={`home-approval-${a.id}`}>
              <p className="text-sm font-semibold text-ink">{a.headline}</p>
              <p className="mt-0.5 text-xs text-ink-2">
                {[a.cost_display ? t("alerts.cost", { cost: a.cost_display }) : null, a.lands_day !== null ? t("biz.landsShort", { n: a.lands_day }) : null, a.protects]
                  .filter(Boolean)
                  .join(" · ")}
              </p>
              <Link href={approvalHref(a.id)} className="mt-1 inline-block text-xs font-medium text-brand-700 underline underline-offset-2">
                {t("biz.review")}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Level 1 news: receipts, late payers, what ran, what waits, what landed. Server sentences, newest first. */
export function ChangesBlock({ changes }: { changes: HomeChange[] }) {
  const { t } = useI18n();
  return (
    <Card id="home-changes" title={t("biz.changes")} subtitle={t("biz.changes.sub")} actions={<Link href="/activity" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("biz.changes.open")}</Link>}>
      {changes.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-changes-empty">
          {t("biz.changes.none")}
        </p>
      ) : (
        <ul className="space-y-2" data-testid="home-changes-list">
          {changes.map((c, i) => (
            <li key={`${c.day}-${c.seq}-${i}`} className="flex items-start gap-3" data-testid={`home-change-${c.kind}`}>
              <span className={`mt-0.5 grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold ${CHANGE_TONE[c.kind] ?? CHANGE_TONE.OPERATION}`} aria-hidden>
                {CHANGE_GLYPH[c.kind] ?? "•"}
              </span>
              <span className="min-w-0">
                <span className="block break-words text-sm text-ink">{c.text}</span>
                <span className="block text-xs text-ink-3">{c.day !== null ? t("common.dayN", { n: c.day }) : ""}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Who has not paid, and what comes in next. */
export function ReceivablesBlock({ r }: { r: HomeReceivables }) {
  const { t } = useI18n();
  return (
    <Card id="home-receivables" title={t("biz.receivables")} subtitle={t("biz.receivables.sub", { total: r.open_total_display, n: r.open_count })} actions={<Link href="/receivables" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("biz.receivables.open")}</Link>}>
      {r.past_due.length ? (
        <ul className="space-y-2" data-testid="home-late-list">
          {r.past_due.map((x) => (
            <li key={x.receivable_id} className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-bad-line bg-bad-bg/40 px-3 py-2 text-sm" data-testid={`home-late-${x.receivable_id}`}>
              <span className="font-medium text-ink">{x.buyer_name}</span>
              <span className="text-ink-2">{t("biz.late", { amount: x.face_display, days: x.days_late, due: x.due_day })}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-3" data-testid="home-late-none">
          {t("biz.late.none")}
        </p>
      )}
      <p className="mt-3 text-sm text-ink-2" data-testid="home-next-receipt">
        {r.promised
          ? t("biz.promised", { amount: r.promised.expected_display, buyer: r.promised.buyer_name, day: r.promised.promised_day ?? "" })
          : r.next_receipt
            ? t("biz.nextReceipt", { amount: r.next_receipt.face_display, buyer: r.next_receipt.buyer_name, day: r.next_receipt.due_day })
            : t("biz.nextReceipt.none")}
      </p>
    </Card>
  );
}

/** Levels 3 and 4, closed by default: what is on its way, the warnings, the facilities and the debt readings. */
export function DetailsBlock({ h }: { h: HomeView }) {
  const { t } = useI18n();
  return (
    <details className="rounded-(--radius-card) border border-line bg-surface shadow-(--shadow-card)" data-testid="home-details">
      <summary className="cursor-pointer px-4 py-3 text-sm font-semibold text-ink">{t("biz.details")}</summary>
      <div className="space-y-5 border-t border-line p-4">
        {h.cash.in_transit ? (
          <section>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("transit.title")}</h3>
            <ul className="text-sm">
              {h.cash.in_transit.lots.map((l, i) => (
                <li key={i} data-testid="in-transit-lot">
                  {t("transit.lands", { amount: l.amount_display, n: l.arrival_day })} <span className="text-ink-3">· {l.facility_name}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {h.warnings.length ? (
          <section>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.warnings")}</h3>
            <ul className="space-y-1.5 text-sm">
              {h.warnings.map((w) => (
                <li key={w.id} data-testid={`home-warning-${w.kind}`}>
                  <span className="font-medium text-ink">{w.title}</span>
                  <span className="block text-xs text-ink-2">{w.detail}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <section>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.facilities")}</h3>
          <TableWrap label={t("biz.facilities")}>
            <table className={tableCls}>
              <thead>
                <tr>
                  <th scope="col" className={thCls}>{t("fund.source")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("biz.available")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("biz.drawn")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("fund.limit")}</th>
                  <th scope="col" className={`${thCls} text-right`}>{t("biz.leadTime")}</th>
                </tr>
              </thead>
              <tbody>
                {h.facilities.map((f) => (
                  <tr key={f.id}>
                    <td className={tdCls}>{f.name}</td>
                    <td className={`${tdCls} text-right tabular-nums`}>{f.available_display}</td>
                    <td className={`${tdCls} text-right tabular-nums`}>{f.drawn_display}</td>
                    <td className={`${tdCls} text-right tabular-nums`}>{f.limit_display}</td>
                    <td className={`${tdCls} text-right tabular-nums`}>{t("common.days", { n: f.lead_time_days })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        </section>
        <section>
          <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.readings")}</h3>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs text-ink-3">{t("biz.dscr")}</dt>
              <dd className="font-semibold tabular-nums">{h.cash.dscr_text ?? t("common.none")}</dd>
              <dd className="text-xs text-ink-3">{t("home.position.limitMin", { limit: h.cash.min_dscr_display })}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">{t("biz.leverage")}</dt>
              <dd className="font-semibold tabular-nums">{h.cash.leverage_text ?? t("common.none")}</dd>
              <dd className="text-xs text-ink-3">{t("home.position.limitMax", { limit: h.cash.max_leverage_display })}</dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-ink-3">{t("biz.readings.note")}</p>
        </section>
        <p className="text-xs text-ink-3">
          {h.note_basis}{" "}
          <Link href="/cash" className="font-medium text-brand-700 underline underline-offset-2">
            {t("biz.openCash")}
          </Link>
        </p>
      </div>
    </details>
  );
}
