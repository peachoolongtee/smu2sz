"use client";

import { Badge, Card, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { dealRecordId, getLedger } from "@/lib/api";
import { useI18n, type I18n } from "@/lib/i18n";
import type { Commitment, CommitmentStatus, Displayed, Obligation } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { useDecisions } from "@/lib/use-decision";
import { whenText } from "@/lib/when";

/**
 * The agreements on the books, as plain sentences ported from `test/ui-ux` (`obligationSentence`): the ones in force first, then the
 * ones that ended (expired, revoked, completed) so a lapsed deal is never hidden. The terms come from GET /ledger; the status is the
 * deal's decision record (`deal:{offer_id}`, GET /decisions), in the server's words, with the commitment's own status as the fallback.
 * Every amount is a server display string (the commitment's `forward_value_display` is the future give-aways booked) and a day is said
 * as a distance from today; the card counts and arranges nothing (INVARIANT 13).
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

function CommitmentItem({ c, buyer, today, recordState }: { c: Displayed<Commitment>; buyer: string; today: number; recordState: string | null }) {
  const { t, te } = useI18n();
  return (
    <li className="rounded-tile border border-line px-4 py-3" data-testid={`commitment-${c.id}`} data-status={c.status}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 break-words text-sm font-semibold text-ink">{t("deal.with", { buyer })}</p>
        <Badge tone={statusTone[c.status]}>
          <span data-testid="commitment-state">{recordState ?? te("deal.status", c.status)}</span>
        </Badge>
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
          <dt className="text-ink-3">{t(c.expires_day < today ? "deal.expired" : "deal.expires")}</dt>
          <dd className="font-medium text-ink">{whenText(c.expires_day, today, t)}</dd>
        </div>
      </dl>
    </li>
  );
}

/** The ledger's commitments, newest first with the ones in force (proposed, accepted or active) ahead of the ones that ended. */
export function ActiveCommitments({ today, buyerName, hideEmpty = false }: { today: number; buyerName: (id: string) => string; hideEmpty?: boolean }) {
  const { t, lang } = useI18n();
  const ledger = useAsync(() => getLedger(lang), [lang]);
  // A failed record read only costs the server's wording of the status: the commitment's own status is then shown.
  const records = useDecisions({ family: "DEAL" });
  const stateText = new Map((records.data?.decisions ?? []).map((d) => [d.id, d.state_text]));
  const all = ledger.data ? [...ledger.data.commitments].reverse() : [];
  const live = [...all.filter((c) => LIVE.includes(c.status)), ...all.filter((c) => !LIVE.includes(c.status))];
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
            <CommitmentItem key={c.id} c={c} buyer={buyerName(c.counterparty_id)} today={today} recordState={stateText.get(dealRecordId(c.offer_id)) ?? null} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-ink-3">{t("biz.deals.commitments.empty")}</p>
      )}
    </Card>
  );
}
