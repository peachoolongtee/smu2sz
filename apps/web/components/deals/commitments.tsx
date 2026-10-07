"use client";

import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { getLedger } from "@/lib/api";
import { useI18n, type I18n } from "@/lib/i18n";
import type { Commitment, CommitmentStatus, Displayed, Obligation } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { whenText } from "@/lib/when";

/**
 * Active commitments: the deals in force, as plain sentences ported from `test/ui-ux` (`obligationSentence`). Reads
 * GET /ledger. Every amount is a server display string (the commitment's `forward_value_display` is the future
 * give-aways booked) and a day is said as a distance from today; the card counts and arranges nothing (INVARIANT 13).
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
  if (d.end_day !== null) return t("deal.dur.until", { when: whenText(d.end_day, today, t) });
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

function CommitmentItem({ c, buyer, today }: { c: Displayed<Commitment>; buyer: string; today: number }) {
  const { t, te } = useI18n();
  return (
    <li className="rounded-tile border border-line px-4 py-3" data-testid={`commitment-${c.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 break-words text-sm font-semibold text-ink">{t("deal.with", { buyer })}</p>
        <Badge tone={statusTone[c.status]}>{te("deal.status", c.status)}</Badge>
      </div>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="commitment-terms">
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
      <dl className="mt-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-ink-3">{t("biz.deals.giveawaysBooked")}</dt>
          <dd className="font-medium tabular-nums text-ink">{c.forward_value_display}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{t("deal.expires")}</dt>
          <dd className="font-medium text-ink">{whenText(c.expires_day, today, t)}</dd>
        </div>
      </dl>
    </li>
  );
}

/** The ledger's live commitments (proposed, accepted or active), newest first. */
export function ActiveCommitments({ today, buyerName, hideEmpty = false }: { today: number; buyerName: (id: string) => string; hideEmpty?: boolean }) {
  const { t } = useI18n();
  const ledger = useAsync(getLedger, []);
  const live = ledger.data ? [...ledger.data.commitments].reverse().filter((c) => LIVE.includes(c.status)) : [];
  // An empty section is noise on the deal page: with `hideEmpty` the card appears only once a deal is on the books.
  if (hideEmpty && ledger.data && !ledger.error && !live.length) return null;
  return (
    <Card id="commitments" title={t("biz.deals.commitments")} subtitle={t("biz.deals.commitments.sub")}>
      {ledger.error ? (
        <ErrorState error={ledger.error} onRetry={ledger.reload} />
      ) : !ledger.data ? (
        <LoadingBlock rows={2} />
      ) : live.length ? (
        <ul className="space-y-3" data-testid="commitments-live">
          {live.map((c) => (
            <CommitmentItem key={c.id} c={c} buyer={buyerName(c.counterparty_id)} today={today} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-3">{t("biz.deals.commitments.empty")}</p>
      )}
    </Card>
  );
}
