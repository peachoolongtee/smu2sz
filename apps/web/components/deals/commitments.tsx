"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { CustomerSentence } from "@/components/customer-link";
import { ChevronRightIcon } from "@/components/icons";
import { DealSummary } from "@/components/deals/deal-summary";
import { Badge, Card, ErrorState, LoadingBlock, textLinkClass, type Tone } from "@/components/ui";
import { dealRecordId, getLedger } from "@/lib/api";
import { useI18n, type I18n } from "@/lib/i18n";
import type { Commitment, CommitmentStatus, DealView, Displayed, Obligation } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useDecisions } from "@/lib/use-decision";
import { whenText } from "@/lib/when";

/**
 * The agreements on the books, as plain sentences ported from `test/ui-ux` (`obligationSentence`): the ones in force first, then the
 * ones that ended (expired, revoked, completed) so a lapsed deal is never hidden. The terms come from GET /ledger; the status is the
 * deal's decision record (`deal:{offer_id}`, GET /decisions), in the server's words, with the commitment's own status as the fallback.
 * Every amount is a server display string (the commitment's `forward_value_display` is the future give-aways booked) and a day is said
 * as a distance from today; the card counts and arranges nothing (INVARIANT 13).
 *
 * The deal summary (the confirmed contract beside the books, `deal-summary.tsx`) is part of this section, not a card of its own: each
 * buyer's summary sits inside the agreement it describes, so the page says it once.
 */

const LIVE: CommitmentStatus[] = ["PROPOSED", "ACCEPTED", "ACTIVE"];

const statusTone: Record<CommitmentStatus, Tone> = {
  PROPOSED: "info",
  ACCEPTED: "ok",
  ACTIVE: "ok",
  FULFILLED: "neutral",
  EXPIRED: "neutral",
  REVOKED: "bad",
};

type Ob = Displayed<Obligation>;

/** What the base of an obligation is, in a phrase: "invoice RCV-A (¥257,200.00)", "future invoices". */
function basePhrase(o: Ob, t: I18n["t"]): string {
  const b = o.base;
  switch (b.kind) {
    case "INVOICE":
      return b.amount_display
        ? t("deal.base.invoiceAmt", { id: b.receivable_id ?? "?", amount: b.amount_display })
        : t("deal.base.invoice", { id: b.receivable_id ?? "?" });
    case "FUTURE_INVOICES":
      return t("deal.base.future");
    case "PERIOD_PURCHASES":
      return t("deal.base.period");
    case "PER_EVENT":
      return t("deal.base.event");
    default:
      return t("deal.base.unspecified");
  }
}

function durationPhrase(o: Ob, t: I18n["t"], today: number): string | null {
  const d = o.duration;
  if (d.kind === "ONE_OFF") return t("deal.dur.once");
  if (d.kind === "RECURRING_PERPETUAL") return t("deal.dur.forever");
  if (d.invoices !== null) return t("deal.dur.invoices", { n: d.invoices });
  // A past end date is said in the past tense ("ended 3 days ago"), never as a future one and never rewritten to "today".
  if (d.end_day !== null) return t(d.end_day < today ? "deal.dur.ended" : "deal.dur.until", { when: whenText(d.end_day, today, t) });
  return null;
}

/** One agreed term as a sentence a non-accountant can read. Built from typed fields and display strings only. */
export function obligationSentence(o: Ob, t: I18n["t"], te: I18n["te"], today: number): string {
  const base = basePhrase(o, t);
  const rate = o.rate_display ?? null;
  switch (o.type) {
    case "IMMEDIATE_DISCOUNT":
      return o.effective_day !== null
        ? t("deal.ob.discountBy", { rate: rate ?? "?", base, when: whenText(o.effective_day, today, t) })
        : t("deal.ob.discount", { rate: rate ?? "?", base });
    case "TERMS_EXTENSION":
      if (o.target_terms_days != null) return t("deal.ob.termsTo", { n: o.target_terms_days, base });
      if (o.days_delta !== null) return t("deal.ob.termsPlus", { n: o.days_delta, base });
      return t("deal.ob.terms", { base });
    case "PRICE_ADJUSTMENT":
      return t("deal.ob.price", { rate: rate ?? o.amount_display ?? "?", base });
    case "CONTINGENT_REBATE":
      return t("deal.ob.rebate", { rate: rate ?? o.amount_display ?? "?", base });
    case "VOLUME_COMMITMENT":
      return t("deal.ob.volume", { amount: o.amount_display ?? "?" });
    default:
      return `${te("obligation", o.type)}: ${base}`;
  }
}

/**
 * One agreement, folded to a row (who it is with, its status, how many terms and the give-aways booked); opening it shows the terms, the dates and the deal summary.
 * The list reads at a glance and only the agreement the owner picks takes the room.
 */
function AgreementRow({ testId, status, head, line, badge, children }: { testId?: string; status?: string; head: ReactNode; line?: ReactNode; badge?: ReactNode; children: ReactNode }) {
  return (
    <li className="border-t border-line first:border-t-0" data-testid={testId} data-status={status}>
      <details className="group">
        <summary className="motion-press flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 rounded-tile px-2 py-3 hover:bg-subtle [&::-webkit-details-marker]:hidden" data-testid="commitment-toggle">
          <ChevronRightIcon aria-hidden width={14} height={14} className="shrink-0 text-ink-3 transition-transform duration-(--dur-fast) group-open:rotate-90" />
          <span className="min-w-0 flex-1">
            <span className="block break-words text-sm font-semibold text-ink">{head}</span>
            {line ? <span className="block text-supporting text-ink-3">{line}</span> : null}
          </span>
          {badge}
        </summary>
        <div className="pb-4 pl-8 pr-2">{children}</div>
      </details>
    </li>
  );
}

function CommitmentItem({ c, buyer, buyerId, today, recordState, inForce, summary }: { c: Displayed<Commitment>; buyer: string; buyerId: string; today: number; recordState: string | null; inForce: boolean; summary?: ReactNode }) {
  const { t, te } = useI18n();
  return (
    <AgreementRow
      testId={`commitment-${c.id}`}
      status={c.status}
      head={<CustomerSentence id={buyerId} name={buyer} sentence={(b) => t("deal.with", { buyer: b })} />}
      line={t("deals.agreement.line", { n: c.obligations.length, amount: c.forward_value_display })}
      badge={
        <Badge tone={statusTone[c.status]}>
          <span data-testid="commitment-state">{recordState ?? te("deal.status", c.status)}</span>
        </Badge>
      }
    >
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink" data-testid="commitment-terms">
        {c.obligations.map((o) => {
          const dur = durationPhrase(o, t, today);
          return (
            <li key={o.id}>
              {obligationSentence(o, t, te, today)}
              {dur ? <span className="text-ink-3"> ({dur})</span> : null}
            </li>
          );
        })}
      </ul>
      <dl className="mt-3 grid grid-cols-1 gap-2 text-supporting sm:grid-cols-2">
        <div>
          <dt className="text-ink-3">{t("biz.deals.giveawaysBooked")}</dt>
          <dd className="font-medium tabular-nums text-ink">{c.forward_value_display}</dd>
        </div>
        {/* An agreement in force (the record's state is AGREED) does not expire: the server's record says "In force." and carries no expiry, so none is said here either. */}
        {inForce ? null : (
          <div>
            <dt className="text-ink-3">{t(c.expires_day < today ? "deal.expired" : "deal.expires")}</dt>
            <dd className="font-medium text-ink">{whenText(c.expires_day, today, t)}</dd>
          </div>
        )}
      </dl>
      {summary}
    </AgreementRow>
  );
}

/**
 * The ledger's commitments, newest first with the ones in force (proposed, accepted or active) ahead of the ones that ended. `agreed` is
 * GET /deals for the buyers whose deal both parties agreed: each one's summary opens inside that buyer's newest agreement in force. A failed
 * read of the summaries says so in the standard error state (`dealsError`); a server with contract reading off sends none.
 */
export function ActiveCommitments({
  today,
  buyerName,
  hideEmpty = false,
  agreed = [],
  dealsDay = null,
  dealsError,
  onRetryDeals,
}: {
  today: number;
  buyerName: (id: string) => string;
  hideEmpty?: boolean;
  agreed?: DealView[];
  dealsDay?: number | null;
  dealsError?: Error;
  onRetryDeals?: () => void;
}) {
  const { t, lang } = useI18n();
  const ledger = useAsync(() => getLedger(lang), [lang]);
  // A failed record read only costs the server's wording of the status: the commitment's own status is then shown.
  const records = useDecisions({ family: "DEAL" });
  const stateText = new Map((records.data?.decisions ?? []).map((d) => [d.id, d.state_text]));
  const inForce = new Set((records.data?.decisions ?? []).filter((d) => d.state === "AGREED").map((d) => d.id));
  const all = ledger.data ? [...ledger.data.commitments].reverse() : [];
  const live = [...all.filter((c) => LIVE.includes(c.status)), ...all.filter((c) => !LIVE.includes(c.status))];
  // An empty section is noise on the deal page: with `hideEmpty` the card appears only once a deal is on the books (or the summaries could not be read).
  if (hideEmpty && ledger.data && !ledger.error && !live.length && !agreed.length && !dealsError) return null;
  // A buyer's summary opens inside its first agreement in the list; a summary with no agreement on the ledger gets an entry of its own.
  const placed = new Set<string>();
  const summaryFor = (buyerId: string) => {
    const deal = agreed.find((d) => d.counterparty_id === buyerId);
    if (!deal || placed.has(buyerId)) return undefined;
    placed.add(buyerId);
    return <DealSummary deal={deal} today={dealsDay ?? today} />;
  };
  const items = live.map((c) => <CommitmentItem key={c.id} c={c} buyer={buyerName(c.counterparty_id)} buyerId={c.counterparty_id} today={today} recordState={stateText.get(dealRecordId(c.offer_id)) ?? null} inForce={inForce.has(dealRecordId(c.offer_id))} summary={summaryFor(c.counterparty_id)} />);
  const loose = agreed.filter((d) => !placed.has(d.counterparty_id) && ledger.data);
  return (
    <Card
      flat
      id="commitments"
      title={t("biz.deals.commitments")}
      subtitle={t("biz.deals.commitments.sub")}
      actions={
        agreed.length ? (
          <Link href="/documents" className={textLinkClass} data-testid="deal-documents-link">
            {t("deals.summary.documents")}
          </Link>
        ) : undefined
      }
    >
      {dealsError ? (
        <div className="mb-3" data-testid="deals-error">
          <ErrorState error={dealsError} onRetry={onRetryDeals} />
        </div>
      ) : null}
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !ledger.data ? (
        <LoadingBlock rows={2} />
      ) : items.length || loose.length ? (
        <ul data-testid="commitments-live">
          {items}
          {loose.map((d) => (
            <AgreementRow key={d.counterparty_id} head={<CustomerSentence id={d.counterparty_id} name={d.counterparty_name} sentence={(b) => t("deal.with", { buyer: b })} />}>
              <DealSummary deal={d} today={dealsDay ?? today} />
            </AgreementRow>
          ))}
        </ul>
      ) : dealsError ? null : (
        <p className="text-sm text-ink-3">{t("biz.deals.commitments.empty")}</p>
      )}
    </Card>
  );
}
