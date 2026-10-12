"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ChasePayment } from "@/components/business/chase-payment";
import { ButtonLink } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CollectionActionKind, ReceivableRow } from "@/lib/types";
import { isFinanced } from "./state";

/**
 * The chosen invoice, which replaces in place: the eyebrow with the customer link, the condition as the heading, the breakdown from the invoice to the
 * cash at collection, the recourse sentence the server writes when the receipt would fall short, who governs the invoice, the early payment and the
 * payment history, then the actions in the server's order (`collection_action.primary` first, the others after it). Every figure and sentence is the
 * server's; the dictionary supplies the labels and the glue words. The browser adds up nothing: each line of the breakdown is a field of its own.
 */
export function InvoiceDetail({
  row,
  customerHref,
  dealHref,
  history,
}: {
  row: ReceivableRow;
  customerHref: string;
  /** The deal the pending counter belongs to, when there is one. */
  dealHref: string | null;
  /** The buyer's payment history in the server's words (from the exposure read), when it has been read for this buyer. */
  history: string | null;
}) {
  const { t } = useI18n();
  const net = row.net ?? {};
  const buyer = row.buyer_name ?? "";
  const financed = isFinanced(row);
  const actions: { action: CollectionActionKind; label: string }[] = row.collection_action?.primary
    ? [{ action: row.collection_action.primary, label: row.collection_action.label ?? "" }, ...(row.collection_action.others ?? [])]
    : [];

  return (
    <div className="min-w-0 space-y-4" data-testid="recv3-detail" data-receivable={row.receivable_id}>
      <p className="text-xs font-extrabold uppercase tracking-[0.08em] text-ink-3">
        {t("recv3.detail.eyebrow")}
        {buyer ? (
          <>
            {" · "}
            <Link href={customerHref} className="rounded-pill font-extrabold text-brand-700 underline-offset-2 hover:underline" data-testid="recv3-detail-customer">
              {buyer} ›
            </Link>
          </>
        ) : null}
      </p>
      {net.condition_text && net.net_short ? (
        <h2 id="recv3-detail-title" className="text-balance font-display text-xl font-extrabold leading-snug tracking-[-0.02em] text-ink first-letter:uppercase sm:text-2xl" data-testid="recv3-detail-title">
          {t("recv3.detail.h2", { condition: net.condition_text, net: net.net_short })}
        </h2>
      ) : null}

      {net.net_display ? (
        <dl className="grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2.5 text-sm" data-testid="recv3-breakdown">
          <Line label={t("recv3.bd.invoice", { when: row.due_when ?? "" })} value={row.outstanding_display} testId="recv3-bd-invoice" />
          {financed ? (
            <>
              <Line
                less
                label={t("recv3.bd.repays")}
                note={net.financing_state_text ? <span data-testid="recv3-bd-state">{net.financing_state_text}</span> : undefined}
                value={net.advance_display}
                testId="recv3-bd-advance"
              />
              <Line less label={t("recv3.bd.charges")} note={net.per_period_text ? <span className="first-letter:uppercase">{net.per_period_text}</span> : undefined} value={net.charges_display} testId="recv3-bd-charges" />
            </>
          ) : null}
          <Line total label={t("recv3.bd.net")} value={net.net_display} testId="recv3-bd-net" />
        </dl>
      ) : null}
      {net.repays_text ? (
        <p className="text-sm text-ink-2" data-testid="recv3-repays">
          {net.repays_text}
          {financed ? t("recv3.sub.end") : ""}
        </p>
      ) : null}
      {net.owed_text ? (
        <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-2" data-testid="recv3-owed">
          {net.owed_text}
        </p>
      ) : null}

      <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-[max-content_minmax(0,1fr)]" data-testid="recv3-facts">
        {row.governed_by?.terms_text ? <Fact label={t("recv3.facts.terms")} testId="recv3-terms">{row.governed_by.terms_text}</Fact> : null}
        {row.early_payment?.text ? (
          <Fact label={t("recv3.facts.early")} testId="recv3-early">
            <span className="first-letter:uppercase">{row.early_payment.text}</span>
            {row.pending_counter?.text ? (
              <>
                <span className="font-normal text-ink-3"> · </span>
                {dealHref ? (
                  <Link href={dealHref} className="font-normal text-brand-700 underline underline-offset-2" data-testid="recv3-counter">
                    {row.pending_counter.text}
                  </Link>
                ) : (
                  <span className="font-normal text-ink-2" data-testid="recv3-counter">{row.pending_counter.text}</span>
                )}
              </>
            ) : null}
          </Fact>
        ) : null}
        {history ? <Fact label={t("recv3.facts.history")} testId="recv3-history">{history}</Fact> : null}
      </dl>

      {actions.length ? (
        <div className="space-y-2">
          <div role="group" aria-label={t("recv3.actions")} className="flex flex-wrap gap-2" data-testid="recv3-actions">
            {actions.map((a, i) =>
              a.action === "VIEW_TERMS" ? (
                <ButtonLink key={a.action} href={customerHref} className="min-h-11" data-testid={`recv3-action-${a.action}`} data-order={i}>
                  {a.label}
                </ButtonLink>
              ) : (
                <span key={a.action} className="contents" data-testid={`recv3-action-${a.action}`} data-order={i}>
                  <ChasePayment receivableId={row.receivable_id} buyer={buyer} label={a.label} size="md" scope="detail-" className="min-h-11" />
                </span>
              ),
            )}
          </div>
          <p className="text-sm text-ink-3">{t("recv3.actions.note", { chase: t("biz.chase.button") })}</p>
        </div>
      ) : null}
    </div>
  );
}

function Line({ label, note, value, less = false, total = false, testId }: { label: string; note?: ReactNode; value?: string; less?: boolean; total?: boolean; testId?: string }) {
  const { t } = useI18n();
  return (
    <>
      <dt className={total ? "border-t border-line-strong pt-2 font-extrabold text-ink" : less ? "text-ink-2" : "text-ink"}>
        {label}
        {note ? <span className="block text-sm font-normal text-ink-3">{note}</span> : null}
      </dt>
      <dd className={`text-right font-display font-bold tabular-nums ${total ? "border-t border-line-strong pt-2 font-extrabold text-ok-fg" : less ? "text-ink-2" : "text-ink"}`} data-testid={testId}>
        {less ? (
          <>
            <span aria-hidden>− </span>
            <span className="sr-only">{t("recv3.bd.less")} </span>
          </>
        ) : null}
        {value}
      </dd>
    </>
  );
}

function Fact({ label, children, testId }: { label: string; children: ReactNode; testId?: string }) {
  return (
    <>
      <dt className="text-ink-3">{label}</dt>
      <dd className="min-w-0 break-words font-semibold text-ink" data-testid={testId}>
        {children}
      </dd>
    </>
  );
}
