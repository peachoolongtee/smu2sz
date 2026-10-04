"use client";

import { Badge, Card, EmptyState, ErrorState, LoadingBlock, type Tone } from "@/components/ui";
import { getLedger, getReconciliation, getState } from "@/lib/api";
import { useI18n, type I18n } from "@/lib/i18n";
import type { Commitment, CommitmentStatus, Displayed, Obligation, PromisedReceipt, PromiseStatus, Receivable } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { SectionLink } from "./today-card";

/**
 * The deals in force, in plain words: who, what was agreed, and how far along it is.
 * Reads GET /ledger (commitments), GET /state (buyer names, invoices carrying the new terms) and
 * GET /reconciliation (each promised early payment and what became of it). Every amount is a server
 * display string; the card only counts and arranges (INVARIANT 13).
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

const promiseTone: Record<PromiseStatus, Tone> = { AWAITED: "warn", RECEIVED: "ok", LAPSED: "bad", SETTLED_OTHERWISE: "neutral" };

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

function durationPhrase(o: Ob, t: I18n["t"]): string | null {
  const d = o.duration;
  if (d.kind === "ONE_OFF") return t("deal.dur.once");
  if (d.kind === "RECURRING_PERPETUAL") return t("deal.dur.forever");
  if (d.invoices !== null) return t("deal.dur.invoices", { n: d.invoices });
  if (d.end_day !== null) return t("deal.dur.until", { n: d.end_day });
  return null;
}

/** One agreed term as a sentence a non-accountant can read. Built from typed fields and display strings only. */
export function obligationSentence(o: Ob, t: I18n["t"], te: I18n["te"]): string {
  const base = basePhrase(o, t);
  const rate = o.rate_display ?? null;
  switch (o.type) {
    case "IMMEDIATE_DISCOUNT":
      return o.effective_day !== null
        ? t("deal.ob.discountBy", { rate: rate ?? "?", base, day: o.effective_day })
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

function invoicesChangedBy(commitmentId: string, receivables: Displayed<Receivable>[]) {
  return receivables.filter((r) => r.applied?.some((a) => a.startsWith(`${commitmentId}:`)));
}

function AgreementItem({
  c,
  buyer,
  promised,
  changed,
  today,
}: {
  c: Displayed<Commitment>;
  buyer: string;
  promised: PromisedReceipt[];
  changed: Displayed<Receivable>[];
  today: number | null;
}) {
  const { t, te } = useI18n();
  const done = promised.filter((p) => p.status === "RECEIVED" || p.status === "SETTLED_OTHERWISE").length;
  const live = LIVE.includes(c.status);
  const daysLeft = today !== null ? c.expires_day - today : null;

  return (
    <li className="rounded-lg border border-line px-4 py-3" data-testid={`agreement-${c.id}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-ink">{t("deal.with", { buyer })}</p>
        <Badge tone={statusTone[c.status]}>{te("deal.status", c.status)}</Badge>
      </div>

      <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("deal.agreed")}</h3>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink" data-testid="agreement-terms">
        {c.obligations.map((o) => {
          const dur = durationPhrase(o, t);
          return (
            <li key={o.id}>
              {obligationSentence(o, t, te)}
              {dur ? <span className="text-ink-3"> ({dur})</span> : null}
            </li>
          );
        })}
      </ul>

      <dl className="mt-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
        <div>
          <dt className="text-ink-3">{t("deal.giveaway")}</dt>
          <dd className="font-medium tabular-nums text-ink">{c.forward_value_display}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{t("deal.expires")}</dt>
          <dd className="font-medium text-ink">
            {t("common.dayN", { n: c.expires_day })}
            {live && daysLeft !== null && daysLeft >= 0 ? <span className="text-ink-3"> · {t("deal.daysLeft", { n: daysLeft })}</span> : null}
          </dd>
        </div>
      </dl>

      {promised.length || changed.length ? (
        <>
          <h3 className="mt-3 flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-ink-3">
            {t("deal.progress")}
            {promised.length ? (
              <span className="font-normal normal-case tracking-normal text-ink-2" data-testid="agreement-progress">
                {t("deal.progress.count", { done, total: promised.length })}
              </span>
            ) : null}
          </h3>
          {promised.length ? (
            <div className="mt-1.5 flex h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
              {promised.map((p) => (
                <span
                  key={`${p.obligation_id}-${p.receivable_id}`}
                  className={`flex-1 border-r-2 border-surface last:border-r-0 ${
                    p.status === "RECEIVED" || p.status === "SETTLED_OTHERWISE" ? "bg-ok-fg" : p.status === "LAPSED" ? "bg-bad-fg" : "bg-transparent"
                  }`}
                />
              ))}
            </div>
          ) : null}
          <ul className="mt-2 space-y-1.5 text-sm">
            {promised.map((p) => (
              <li key={`${p.obligation_id}-${p.receivable_id}`} className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-ink-2">
                  {p.promised_day !== null
                    ? t("deal.promise.by", { amount: p.expected_display, id: p.receivable_id, day: p.promised_day })
                    : t("deal.promise", { amount: p.expected_display, id: p.receivable_id })}
                </span>
                <Badge tone={promiseTone[p.status]}>{te("deal.promstatus", p.status)}</Badge>
              </li>
            ))}
            {changed.map((r) => (
              <li key={r.id} className="text-ink-2">
                {r.base_terms_days !== undefined && r.base_terms_days !== r.terms_days
                  ? t("deal.invoice.terms", { id: r.id, n: r.terms_days, base: r.base_terms_days })
                  : t("deal.invoice.updated", { id: r.id })}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {c.obligations.some((o) => o.spans.length) ? (
        <details className="mt-3 text-xs">
          <summary className="cursor-pointer font-medium text-brand-700">{t("deal.wording")}</summary>
          {c.obligations.flatMap((o) =>
            o.spans.map((s, i) => (
              <blockquote key={`${o.id}-${i}`} className="mt-2 border-l-2 border-line-strong pl-2.5 italic text-ink-2">
                &ldquo;{s.text}&rdquo;
              </blockquote>
            )),
          )}
        </details>
      ) : null}
    </li>
  );
}

/** The home page's contract summary: the agreements in force first, past ones folded away. */
export function AgreementsCard() {
  const { t } = useI18n();
  const view = useAsync(async () => {
    // Progress is a bonus: a refused or disabled reconciliation read must not hide what was agreed.
    const [ledger, state, recon] = await Promise.all([getLedger(), getState(), getReconciliation().catch(() => null)]);
    return { ledger, state, recon };
  }, []);
  const d = view.data;

  let body;
  if (view.error) body = <ErrorState error={view.error} onRetry={view.reload} />;
  else if (!d) body = <LoadingBlock rows={2} />;
  else {
    const names = new Map(d.state.state.counterparties.map((cp) => [cp.id, cp.name]));
    const today = d.state.day ?? d.state.state.as_of_day ?? null;
    const all = [...d.ledger.commitments].reverse();
    const live = all.filter((c) => LIVE.includes(c.status));
    const past = all.filter((c) => !LIVE.includes(c.status));
    const item = (c: Displayed<Commitment>) => (
      <AgreementItem
        key={c.id}
        c={c}
        buyer={names.get(c.counterparty_id) ?? c.counterparty_id}
        promised={d.recon?.promised?.filter((p) => p.commitment_id === c.id) ?? []}
        changed={invoicesChangedBy(c.id, d.state.state.receivables)}
        today={today}
      />
    );
    body =
      all.length === 0 ? (
        <EmptyState title={t("deal.empty.title")} body={t("deal.empty.body")} />
      ) : (
        <>
          {live.length ? (
            <ul className="space-y-3" data-testid="agreements-live">
              {live.map(item)}
            </ul>
          ) : (
            <p className="text-sm text-ink-3">{t("deal.noneLive")}</p>
          )}
          {past.length ? (
            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("deal.past", { n: past.length })}</summary>
              <ul className="mt-2 space-y-3">{past.map(item)}</ul>
            </details>
          ) : null}
        </>
      );
  }

  const count = d ? d.ledger.commitments.filter((c) => LIVE.includes(c.status)).length : null;
  return (
    <Card
      id="home-agreements"
      title={t("deal.title")}
      subtitle={t("deal.sub")}
      actions={
        <div className="flex items-center gap-2">
          {count !== null ? <Badge tone={count ? "ok" : "neutral"}>{t("deal.count", { n: count })}</Badge> : null}
          <SectionLink href="/ledger">{t("deal.open")}</SectionLink>
        </div>
      }
    >
      {body}
    </Card>
  );
}
