"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Avatar, BizCard, Disclosure, Row, SectionHead, initials, textLink, toneFor, type BizTone } from "@/components/business/kit";
import { AlertIcon, ArrowDownLeftIcon, CheckIcon, ClockIcon, XIcon } from "@/components/icons";
import { approvalHref } from "@/components/operation-result";
import { TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { localNames, plainDays } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import type { HomeApproval, HomeChange, HomeReceivables, HomeView } from "@/lib/types";

/** The names a Business sentence may carry ids for: the facilities and the buyers the home read names. */
export function homeNames(h: HomeView): { id: string; name: string }[] {
  const buyers = [...h.receivables.past_due, ...(h.receivables.next_receipt ? [h.receivables.next_receipt] : [])].map((r) => ({ id: r.buyer_id, name: r.buyer_name }));
  return [...h.facilities.map((f) => ({ id: f.id, name: f.name })), ...buyers];
}

/** Each kind of change has a round icon, tinted by what it means. */
const CHANGE_ICON: Record<string, { icon: ReactNode; tone: BizTone }> = {
  RECEIPT: { icon: <ArrowDownLeftIcon width={18} height={18} />, tone: "ok" },
  LANDED: { icon: <ArrowDownLeftIcon width={18} height={18} />, tone: "ok" },
  LATE: { icon: <AlertIcon width={18} height={18} />, tone: "bad" },
  WAITING: { icon: <ClockIcon width={18} height={18} />, tone: "warn" },
  REFUSED: { icon: <XIcon width={14} height={14} />, tone: "bad" },
  OPERATION: { icon: <CheckIcon width={14} height={14} />, tone: "brand" },
  AGREEMENT: { icon: <CheckIcon width={14} height={14} />, tone: "ok" },
};

/** How many recent changes show before "Show more". */
const CHANGES_SHOWN = 3;

/** Level 2: what requires the owner's decision, as questions. The buttons are on the approval card, never here. */
export function DecisionsBlock({ approvals }: { approvals: HomeApproval[] }) {
  const { t, lang } = useI18n();
  return (
    <section id="home-decisions" aria-labelledby="home-decisions-title">
      <SectionHead id="home-decisions-title" title={t("biz.decisions")} action={<Link href="/approvals" className={textLink}>{t("home.waiting.open")}</Link>} />
      <BizCard className="p-1.5">
        {approvals.length === 0 ? (
          <p className="px-4 py-3 text-sm text-ink-3" data-testid="home-waiting-empty">
            {t("biz.decisions.none")}
          </p>
        ) : (
          <ul data-testid="home-waiting-list">
            {approvals.map((a) => (
              <li key={a.id} data-testid={`home-approval-${a.id}`}>
                <Row
                  href={approvalHref(a.id)}
                  avatar={
                    <Avatar tone="warn">
                      <ClockIcon width={18} height={18} />
                    </Avatar>
                  }
                  title={localNames(a.headline, lang)}
                  sub={[a.cost_display ? t("alerts.cost", { cost: a.cost_display }) : null, a.lands_day !== null ? t("biz.landsShort", { when: a.lands_when ?? "" }) : null].filter(Boolean).join(" · ")}
                >
                  {a.protects ? <span className="mt-0.5 block text-xs text-ink-3">{a.protects}</span> : null}
                  <span className="sr-only">{t("biz.review")}</span>
                </Row>
              </li>
            ))}
          </ul>
        )}
      </BizCard>
    </section>
  );
}

/** Level 1 news: receipts, late payers, what ran, what waits, what landed. Server sentences, newest first; three shown. */
export function ChangesBlock({ changes, sinceWhen, today, anyPending }: { changes: HomeChange[]; sinceWhen?: string | null; today: number; anyPending: boolean }) {
  const { t, lang } = useI18n();
  const row = (c: HomeChange, i: number) => {
    // A request that waited is no longer waiting once nothing is pending: it was decided since.
    const kind = c.kind === "WAITING" && !anyPending ? "OPERATION" : c.kind;
    const look = CHANGE_ICON[kind] ?? CHANGE_ICON.OPERATION;
    return (
      <li key={`${c.day}-${c.seq}-${i}`} data-testid={`home-change-${c.kind}`}>
        <Row
          avatar={
            <Avatar tone={look.tone} size="sm">
              {look.icon}
            </Avatar>
          }
          title={<span className="line-clamp-2 text-sm font-medium">{localNames(plainDays(c.text, today, t), lang)}</span>}
          sub={`${c.when}${kind !== c.kind ? ` · ${t("biz.changes.decided")}` : ""}`}
        />
      </li>
    );
  };
  const first = changes.slice(0, CHANGES_SHOWN);
  const rest = changes.slice(CHANGES_SHOWN);
  return (
    <section id="home-changes" aria-labelledby="home-changes-title" className="min-w-0">
      <SectionHead id="home-changes-title" title={t("biz.recent")} sub={sinceWhen ? t("biz.recent.since", { when: sinceWhen }) : undefined} action={<Link href="/activity" className={textLink}>{t("biz.changes.open")}</Link>} />
      <BizCard className="p-1.5">
        {changes.length === 0 ? (
          <p className="px-4 py-3 text-sm text-ink-3" data-testid="home-changes-empty">
            {t("biz.changes.none")}
          </p>
        ) : (
          <>
            <ul data-testid="home-changes-list">{first.map(row)}</ul>
            {rest.length ? (
              <Disclosure summary={t("biz.showMore", { n: rest.length })} className="px-3">
                <ul>{rest.map((c, i) => row(c, i + CHANGES_SHOWN))}</ul>
              </Disclosure>
            ) : null}
          </>
        )}
      </BizCard>
    </section>
  );
}

/** Who has not paid, and what comes in next, as rows: the buyer, then the amount. */
export function ReceivablesBlock({ r }: { r: HomeReceivables }) {
  const { t } = useI18n();
  const next = r.promised
    ? { buyer: r.promised.buyer_name, amount: r.promised.expected_display, when: r.promised.when ?? "", text: t("biz.promised", { amount: r.promised.expected_display, buyer: r.promised.buyer_name, when: r.promised.when ?? "" }) }
    : r.next_receipt
      ? { buyer: r.next_receipt.buyer_name, amount: r.next_receipt.face_display, when: r.next_receipt.due_when, text: t("biz.nextReceipt", { amount: r.next_receipt.face_display, buyer: r.next_receipt.buyer_name, when: r.next_receipt.due_when }) }
      : null;
  return (
    <section id="home-receivables" aria-labelledby="home-receivables-title" className="min-w-0">
      <SectionHead
        id="home-receivables-title"
        title={t("biz.receivables")}
        sub={t("biz.receivables.sub", { total: r.open_total_display, n: r.open_count })}
        action={<Link href="/receivables" className={textLink}>{t("biz.receivables.open")}</Link>}
      />
      <BizCard className="p-1.5">
        {r.past_due.length ? (
          <ul data-testid="home-late-list">
            {r.past_due.map((x) => (
              <li key={x.receivable_id} data-testid={`home-late-${x.receivable_id}`}>
                <Row avatar={<Avatar tone={toneFor(x.buyer_name)}>{initials(x.buyer_name)}</Avatar>} title={x.buyer_name} sub={t("biz.late", { amount: x.face_display, days: x.days_late })} tone="bad" right={x.face_display} />
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 pt-3 text-sm text-ink-3" data-testid="home-late-none">
            {t("biz.late.none")}
          </p>
        )}
        {next ? (
          <div data-testid="home-next-receipt">
            <span className="sr-only">{next.text}</span>
            <Row avatar={<Avatar tone={toneFor(next.buyer)}>{initials(next.buyer)}</Avatar>} title={next.buyer} sub={t("biz.nextReceipt.short")} right={next.amount} rightSub={next.when} />
          </div>
        ) : (
          <p className="px-4 py-3 text-sm text-ink-3" data-testid="home-next-receipt">
            {t("biz.nextReceipt.none")}
          </p>
        )}
      </BizCard>
    </section>
  );
}

/** The warnings, open on the page as quiet rows: a thin headroom or an expiring mandate is worth reading without a click. */
export function WarningsBlock({ h }: { h: HomeView }) {
  const { t, lang } = useI18n();
  if (!h.warnings.length) return null;
  return (
    <BizCard className="p-1.5" testId="home-warnings">
      <h2 className="sr-only">{t("biz.warnings")}</h2>
      <ul>
        {h.warnings.map((w) => (
          <li key={w.id} data-testid={`home-warning-${w.kind}`}>
            <Row
              avatar={
                <Avatar tone="warn" size="sm">
                  <AlertIcon width={16} height={16} />
                </Avatar>
              }
              title={<span className="text-sm">{localNames(plainDays(w.title, h.day, t), lang)}</span>}
              sub={<span className="line-clamp-2">{localNames(plainDays(w.detail, h.day, t), lang)}</span>}
            />
          </li>
        ))}
      </ul>
    </BizCard>
  );
}

/** Levels 3 and 4, closed by default: what is on its way, the facilities and the debt readings. */
export function DetailsBlock({ h }: { h: HomeView }) {
  const { t, lang } = useI18n();
  return (
    <Disclosure card summary={t("biz.details.noWarnings")} testId="home-details">
      <div className="space-y-5">
        {h.cash.in_transit ? (
          <section>
            <h3 className="mb-1.5 text-sm font-semibold text-ink">{t("transit.title")}</h3>
            <ul className="text-sm">
              {h.cash.in_transit.lots.map((l, i) => (
                <li key={i} data-testid="in-transit-lot">
                  {t("biz.transit.lands", { amount: l.amount_display, when: l.arrival_when })} <span className="text-ink-3">· {localNames(l.facility_name, lang)}</span>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        <section>
          <h3 className="mb-1.5 text-sm font-semibold text-ink">{t("biz.facilities")}</h3>
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
                    <td className={tdCls}>{localNames(f.name, lang)}</td>
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
          <h3 className="mb-1.5 text-sm font-semibold text-ink">{t("biz.readings")}</h3>
          <dl className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-2xl bg-subtle px-4 py-3">
              <dt className="text-ink-3">{t("biz.dscr")}</dt>
              <dd className="figure text-lg font-semibold">{h.cash.dscr_text ?? t("common.none")}</dd>
              <dd className="text-xs text-ink-3">{t("home.position.limitMin", { limit: h.cash.min_dscr_display })}</dd>
            </div>
            <div className="rounded-2xl bg-subtle px-4 py-3">
              <dt className="text-ink-3">{t("biz.leverage")}</dt>
              <dd className="figure text-lg font-semibold">{h.cash.leverage_text ?? t("common.none")}</dd>
              <dd className="text-xs text-ink-3">{t("home.position.limitMax", { limit: h.cash.max_leverage_display })}</dd>
            </div>
          </dl>
          <p className="mt-2 text-xs text-ink-3">{t("biz.readings.note")}</p>
        </section>
        <p className="text-xs text-ink-3">
          {h.note_basis}{" "}
          <Link href="/cash" className="font-semibold text-brand-600 hover:text-brand-700">
            {t("biz.openCash")}
          </Link>
        </p>
      </div>
    </Disclosure>
  );
}
