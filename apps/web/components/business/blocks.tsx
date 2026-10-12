"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { AlertIcon, ArrowDownIcon, CheckIcon, ClockIcon, XIcon } from "@/components/icons";
import { approvalHref } from "@/components/operation-result";
import { Avatar, Disclosure, Row, initials, toneFor, type AvatarTone } from "@/components/business/kit";
import { Card, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { buttonClass, textLinkClass } from "@/components/ui";
import { daysLate } from "@/lib/when";
import type { HomeApproval, HomeChange, HomeReceivables, HomeView, ReceivablesWorthView } from "@/lib/types";

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
    <Card id="home-decisions" title={t("biz.decisions")} subtitle={t("biz.decisions.sub")} actions={<Link href="/approvals" className={textLinkClass}>{t("home.waiting.open")}</Link>}>
      {approvals.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-waiting-empty">
          {t("biz.decisions.none")}
        </p>
      ) : (
        <ul className="motion-rise -my-1 divide-y divide-line" data-testid="home-waiting-list">
          {approvals.map((a) => (
            <li key={a.id}>
              {/* The question and the button: side by side from the small breakpoint; on a phone the button sits under the text, full width, instead of squeezing it into a narrow column. */}
              <Link
                href={approvalHref(a.id)}
                className="motion-lift -mx-2 flex flex-col gap-3 rounded-tile px-2 py-3 hover:bg-subtle sm:flex-row sm:items-center"
                data-testid={`home-approval-${a.id}`}
              >
                <span className="flex min-w-0 flex-1 items-start gap-3">
                  <Avatar tone="warn"><ClockIcon /></Avatar>
                  <span className="min-w-0 flex-1">
                    <span className="block break-words text-sm font-medium text-ink">{a.headline}</span>
                    <span className="mt-0.5 block text-xs text-ink-3">
                      {[a.cost_display ? t("alerts.cost", { cost: a.cost_display }) : null, a.lands_day !== null ? t("biz.landsShort", { when: a.lands_when ?? "" }) : null, a.protects].filter(Boolean).join(" · ")}
                    </span>
                  </span>
                </span>
                {/* The page's one primary action while no plan waits to be run: the question is the thing to answer. */}
                {primary ? (
                  <span className={buttonClass("primary", "md", "w-full sm:w-auto")} data-testid="home-review-primary">
                    {t("biz.review")}
                  </span>
                ) : (
                  <span className="text-xs font-medium text-brand-700">{t("biz.review")}</span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/** Level 1 news: receipts, late payers, what ran, what waits, what landed. Server sentences, newest first; three show, the rest wait behind "Show more". */
export function ChangesBlock({ changes, sinceWhen, bare = false }: { changes: HomeChange[]; sinceWhen?: string | null; /** Inside a fold that already carries the title (Home's "What changed" under the cards): the list alone. */ bare?: boolean }) {
  const { t } = useI18n();
  const row = (c: HomeChange, i: number) => (
    <li key={`${c.day}-${c.seq}-${i}`}>
      <Row testId={`home-change-${c.kind}`} titleTestId="home-change-text" avatar={<Avatar tone={CHANGE_TONE[c.kind] ?? "neutral"}>{CHANGE_ICON[c.kind] ?? <CheckIcon />}</Avatar>} title={c.event_text ?? c.text} sub={c.when}>
      </Row>
    </li>
  );
  const rest = changes.slice(CHANGES_SHOWN);
  return (
    <Card flat id="home-changes" title={bare ? undefined : t("biz.recent")} subtitle={sinceWhen ? t("biz.recent.since", { when: sinceWhen }) : t("biz.recent.week")} actions={<Link href="/activity" className={textLinkClass}>{t("biz.changes.open")}</Link>}>
      {changes.length === 0 ? (
        <p className="text-sm text-ink-3" data-testid="home-changes-empty">
          {t("biz.changes.none")}
        </p>
      ) : (
        <div className="-my-1" data-testid="home-changes-list">
          <ul className="motion-rise divide-y divide-line">{changes.slice(0, CHANGES_SHOWN).map(row)}</ul>
          {rest.length ? (
            <Disclosure summary={t("biz.showMore", { n: rest.length })} testId="home-changes-more" className="border-t border-line">
              <ul className="divide-y divide-line">{rest.map((c, i) => row(c, i + CHANGES_SHOWN))}</ul>
            </Disclosure>
          ) : null}
        </div>
      )}
      {bare ? (
        <p className="mt-2">
          <Link href="/activity" className={`${textLinkClass} -ml-2`}>
            {t("biz.changes.open")}
          </Link>
        </p>
      ) : null}
    </Card>
  );
}

/**
 * Who has not paid, and what comes in next, as rows: the buyer, then the amount. With the strategy MVP's `worth` loaded,
 * one line more: what is best to do about the invoice that saves the most (the server's sentence).
 */
export function ReceivablesBlock({ r, worth }: { r: HomeReceivables; worth?: ReceivablesWorthView | null }) {
  const { t } = useI18n();
  const next = r.promised
    ? { buyer: r.promised.buyer_name, amount: r.promised.expected_display, when: r.promised.when ?? "" }
    : r.next_receipt
      ? { buyer: r.next_receipt.buyer_name, amount: r.next_receipt.face_display, when: r.next_receipt.due_when }
      : null;
  return (
    <Card flat id="home-receivables" title={t("biz.receivables")} subtitle={t("biz.receivables.sub", { total: r.open_total_display, n: r.open_count })} actions={<Link href="/receivables" className={textLinkClass}>{t("biz.receivables.open")}</Link>}>
      <div className="-my-1 divide-y divide-line">
        {r.past_due.length ? (
          <ul className="motion-rise divide-y divide-line" data-testid="home-late-list">
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
        {worth?.rows.length && worth.top_action ? (
          <div className="py-2.5 text-sm text-ink-2" data-testid="home-top-action">
            <p>{worth.top_action}</p>
            {worth.top_action_second ? <p className="mt-1" data-testid="home-top-action-second">{worth.top_action_second}</p> : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}

/**
 * Warnings and the details. The warnings are "Also on your radar", one quiet row of items above the fold (nothing is shown when there are none);
 * the fold keeps the facilities and the debt readings, closed by default. What is on its way is said once, in the headline's lines.
 */
export function DetailsBlock({ h, radarFold = false, afterRadar }: { h: HomeView; /** The warnings are a closed fold ("Also on your radar") instead of a section (Home under the cards). */ radarFold?: boolean; /** Another fold that sits between the warnings and the details (Home's "What changed"). */ afterRadar?: ReactNode }) {
  const { t } = useI18n();
  const warnings = (
    <ul className={`${radarFold ? "pt-1" : "mt-3"} flex flex-wrap gap-x-8 gap-y-3`}>
      {h.warnings.map((w) => (
        <li key={w.id} className="flex min-w-0 flex-[1_1_16rem] gap-3" data-testid={`home-warning-${w.kind}`}>
          <span aria-hidden className="grid size-8 shrink-0 place-items-center rounded-tile bg-warn-bg text-warn-fg">
            <AlertIcon width={16} height={16} />
          </span>
          <span className="min-w-0">
            <span className="block text-sm font-bold text-ink">{w.title}</span>
            <span className="block text-sm text-ink-2">{w.detail}</span>
          </span>
        </li>
      ))}
    </ul>
  );
  return (
    <>
      {h.warnings.length && radarFold ? (
        <Disclosure testId="home-radar" summary={t("biz.radar")} className="border-t border-line-strong pt-2">
          {warnings}
        </Disclosure>
      ) : null}
      {h.warnings.length && !radarFold ? (
        <section aria-labelledby="home-radar-title" className="motion-reveal" data-testid="home-radar">
          <h2 id="home-radar-title" className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("biz.radar")}
          </h2>
          {warnings}
        </section>
      ) : null}
      {afterRadar}
      <Disclosure testId="home-details" summary={t("biz.details")} className="border-t border-line-strong pt-2">
      <div className="space-y-5">
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
          <Link href="/cash" className={textLinkClass}>
            {t("biz.openCash")}
          </Link>
        </p>
      </div>
      </Disclosure>
    </>
  );
}
