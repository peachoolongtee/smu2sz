"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertIcon, ArrowDownIcon, CheckIcon, ClockIcon, XIcon } from "@/components/icons";
import { approvalHref } from "@/components/operation-result";
import { Avatar, Disclosure, Row, initials, toneFor, type AvatarTone } from "@/components/business/kit";
import { Card, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { daysLate } from "@/lib/when";
import type { HomeApproval, HomeChange, HomeReceivables, HomeView } from "@/lib/types";

/** A change row's icon sits on the status tint it has always had: money in is ok, late or refused is bad, waiting is warn. */
const CHANGE_ICON: Record<string, ReactNode> = {
  RECEIPT: <ArrowDownIcon />,
  LANDED: <ArrowDownIcon />,
  LATE: <AlertIcon />,
  WAITING: <ClockIcon />,
  REFUSED: <XIcon />,
  OPERATION: <CheckIcon />,
  AGREEMENT: <CheckIcon />,
};
const CHANGE_TONE: Record<string, AvatarTone> = {
  RECEIPT: "ok",
  LANDED: "ok",
  LATE: "bad",
  WAITING: "warn",
  REFUSED: "bad",
  OPERATION: "neutral",
  AGREEMENT: "ok",
};

/** How many recent changes show before "Show more". */
const CHANGES_SHOWN = 3;

/**
 * Level 2: what requires the owner's decision, as a question with its cost and landing. The one place the pending
 * approval is spelled out on the home (the recent changes keep its row). The buttons are on the approval card, never here.
 */
export function DecisionsBlock({ approvals, primary = false }: { approvals: HomeApproval[]; primary?: boolean }) {
  const { t } = useI18n();
  return (
    <Card id="home-decisions" title={t("biz.decisions")} subtitle={t("biz.decisions.sub")} actions={<Link href="/approvals" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("home.waiting.open")}</Link>}>
      {approvals.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-waiting-empty">
          {t("biz.decisions.none")}
        </p>
      ) : (
        <ul className="-my-1 divide-y divide-line" data-testid="home-waiting-list">
          {approvals.map((a) => (
            <li key={a.id}>
              <Row
                testId={`home-approval-${a.id}`}
                href={approvalHref(a.id)}
                avatar={<Avatar tone="warn"><ClockIcon /></Avatar>}
                title={a.headline}
                sub={[a.cost_display ? t("alerts.cost", { cost: a.cost_display }) : null, a.lands_day !== null ? t("biz.landsShort", { when: a.lands_when ?? "" }) : null, a.protects]
                  .filter(Boolean)
                  .join(" · ")}
                right={
                  // The page's one primary action while no plan waits to be run: the question is the thing to answer.
                  primary ? (
                    <span className="inline-flex min-h-10 items-center rounded-md bg-brand-600 px-3.5 text-sm font-medium text-white" data-testid="home-review-primary">
                      {t("biz.review")}
                    </span>
                  ) : (
                    <span className="text-xs font-medium text-brand-700">{t("biz.review")}</span>
                  )
                }
              />
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Level 1 news: receipts, late payers, what ran, what waits, what landed. Server sentences, newest first; three show, the rest wait behind "Show more". */
export function ChangesBlock({ changes, sinceWhen }: { changes: HomeChange[]; sinceWhen?: string | null }) {
  const { t } = useI18n();
  const row = (c: HomeChange, i: number) => (
    <li key={`${c.day}-${c.seq}-${i}`}>
      <Row testId={`home-change-${c.kind}`} titleTestId="home-change-text" avatar={<Avatar tone={CHANGE_TONE[c.kind] ?? "neutral"}>{CHANGE_ICON[c.kind] ?? <CheckIcon />}</Avatar>} title={c.event_text ?? c.text} sub={c.when} />
    </li>
  );
  const rest = changes.slice(CHANGES_SHOWN);
  return (
    <Card id="home-changes" title={t("biz.recent")} subtitle={sinceWhen ? t("biz.recent.since", { when: sinceWhen }) : t("biz.recent.week")} actions={<Link href="/activity" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("biz.changes.open")}</Link>}>
      {changes.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-changes-empty">
          {t("biz.changes.none")}
        </p>
      ) : (
        <div className="-my-1" data-testid="home-changes-list">
          <ul className="divide-y divide-line">{changes.slice(0, CHANGES_SHOWN).map(row)}</ul>
          {rest.length ? (
            <Disclosure summary={t("biz.showMore", { n: rest.length })} testId="home-changes-more" className="border-t border-line">
              <ul className="divide-y divide-line">{rest.map((c, i) => row(c, i + CHANGES_SHOWN))}</ul>
            </Disclosure>
          ) : null}
        </div>
      )}
    </Card>
  );
}

/** Who has not paid, and what comes in next, as rows: the buyer, then the amount. */
export function ReceivablesBlock({ r }: { r: HomeReceivables }) {
  const { t } = useI18n();
  const next = r.promised
    ? { buyer: r.promised.buyer_name, amount: r.promised.expected_display, when: r.promised.when ?? "" }
    : r.next_receipt
      ? { buyer: r.next_receipt.buyer_name, amount: r.next_receipt.face_display, when: r.next_receipt.due_when }
      : null;
  return (
    <Card id="home-receivables" title={t("biz.receivables")} subtitle={t("biz.receivables.sub", { total: r.open_total_display, n: r.open_count })} actions={<Link href="/receivables" className="text-xs font-medium text-brand-700 underline underline-offset-2">{t("biz.receivables.open")}</Link>}>
      <div className="-my-1 divide-y divide-line">
        {r.past_due.length ? (
          <ul className="divide-y divide-line" data-testid="home-late-list">
            {r.past_due.map((x) => (
              <li key={x.receivable_id}>
                <Row testId={`home-late-${x.receivable_id}`} avatar={<Avatar tone={toneFor(x.buyer_name)}>{initials(x.buyer_name)}</Avatar>} title={x.buyer_name} sub={daysLate(x.days_late, t)} tone="bad" right={x.face_display} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-2.5 text-sm text-ink-3" data-testid="home-late-none">
            {t("biz.late.none")}
          </p>
        )}
        {next ? (
          <Row testId="home-next-receipt" avatar={<Avatar tone={toneFor(next.buyer)}>{initials(next.buyer)}</Avatar>} title={next.buyer} sub={r.promised ? t("biz.promised.short") : t("biz.nextReceipt.short")} right={next.amount} rightSub={next.when} />
        ) : (
          <p className="py-2.5 text-sm text-ink-3" data-testid="home-next-receipt">
            {t("biz.nextReceipt.none")}
          </p>
        )}
      </div>
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
                  {t("biz.transit.lands", { amount: l.amount_display, when: l.arrival_when })} <span className="text-ink-3">· {l.facility_name}</span>
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
              <dd className="font-semibold tabular-nums" data-testid="home-dscr">{h.cash.dscr_text ?? t("common.none")}</dd>
              <dd className="text-xs text-ink-3">{t("home.position.limitMin", { limit: h.cash.min_dscr_display })}</dd>
            </div>
            <div>
              <dt className="text-xs text-ink-3">{t("biz.leverage")}</dt>
              <dd className="font-semibold tabular-nums" data-testid="home-leverage">{h.cash.leverage_text ?? t("common.none")}</dd>
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
