"use client";

import Link from "next/link";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, Segmented } from "@/components/ui";
import { negotiate } from "@/lib/api";
import { idsToNames, localNames, plainDays } from "@/lib/business-words";
import { recordNegotiation } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import type { Mode } from "@/lib/mode";
import type { BuyerProfile, CounterProposal, Displayed, NegotiationView, VerdictView } from "@/lib/types";

type Counter = Displayed<CounterProposal> & { text_when?: string; rationale_when?: string; outbound_blocked?: boolean };
/** Ids on the books with their names (facilities, buyers), so a funding sentence reads "Bank credit line", not "FAC-LINE". */
type Named = { id: string; name: string }[];

/**
 * One counter as a business card: what changes for the buyer (the counter's own wording), what it costs (the plain
 * cost, or the net economic cost with the funding cost and the offset beside it, never "¥0.00" alone), and the
 * reasoning behind "Details". Formulas stay in the calculation disclosure of the page.
 */
type CounterBadge = "recommended" | "accepted" | null;

function CounterBusinessCard({ c, badge, today, action }: { c: Counter; badge: CounterBadge; today: number; action?: React.ReactNode }) {
  const recommended = badge !== null;
  const { t, lang } = useI18n();
  const e = c.economics ?? null;
  return (
    <li className={`rounded-lg border p-4 ${recommended ? "border-brand-600 bg-brand-50/40" : "border-line"}`} data-testid={`deal-option-${c.label.replace(/\s+/g, "-")}`}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-base font-semibold text-ink">{c.label}</h3>
        {badge === "recommended" ? <Badge tone="brand">{t("biz.deals.option.recommended")}</Badge> : null}
        {badge === "accepted" ? <Badge tone="ok">{t("biz.deals.option.accepted")}</Badge> : null}
      </div>
      <p className="mt-2 text-sm text-ink" data-testid="deal-option-text">
        {localNames(c.text_when ?? plainDays(c.text, today, t), lang)}
      </p>
      <dl className="mt-3 text-sm">
        {e?.is_net ? (
          <>
            <div className="flex items-baseline justify-between gap-3">
              <dt className="text-ink-2">{t("biz.deals.netCost")}</dt>
              <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
                {/* The verifier floors a negative net at zero on purpose (the adjustment covers the cost); the card says so, never a gain. */}
                {e.net_fen <= 0 ? "≈ ¥0" : e.net_display}
              </dd>
            </div>
            <div className="mt-1 flex items-baseline justify-between gap-3 text-xs text-ink-3">
              <dt>{t("biz.deals.fundingCost")}</dt>
              <dd className="tabular-nums">{e.funding_cost_display}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-3 text-xs text-ink-3">
              <dt>{t("biz.deals.offset")}</dt>
              <dd className="tabular-nums">−{e.offset_display}</dd>
            </div>
          </>
        ) : (
          <div className="flex items-baseline justify-between gap-3">
            <dt className="text-ink-2">{t("biz.deals.estCost")}</dt>
            <dd className="text-lg font-semibold tabular-nums text-ink" data-testid="deal-option-cost">
              {c.supplier_cost_display}
            </dd>
          </div>
        )}
      </dl>
      {action ? <div className="mt-4">{action}</div> : null}
      <details className="mt-3 text-sm" data-testid="deal-option-details">
        <summary className="cursor-pointer text-xs font-medium text-brand-700">{t("biz.deals.details")}</summary>
        <p className="mt-1.5 text-ink-2">{localNames(c.rationale_when ?? plainDays(c.rationale, today, t), lang)}</p>
      </details>
    </li>
  );
}

/**
 * Send the recommended counter to the buyer. The reply comes from the demo's simulated buyer (`POST /negotiate`), and it
 * is not a dry run: if the buyer agrees, the agreement is booked and the remaining gap is funded, so the owner confirms
 * first, as with "Run funding plan". The API always opens with the first counter and offers the next one only after a
 * refusal, which is why only the recommended option carries the button.
 */
function SendToBuyer({ offerId, first, next, buyer }: { offerId: string; first: Counter; next: Counter | null; buyer: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [profile, setProfile] = useState<BuyerProfile>("cooperative");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  async function send() {
    setSending(true);
    setError(null);
    try {
      // Recording the answer re-renders the card as the agreed or the refused deal.
      recordNegotiation(await negotiate(offerId, { buyer_profile: profile }));
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
      setSending(false);
    }
  }

  if (!open) {
    return (
      <Button variant="primary" onClick={() => setOpen(true)} data-testid="deal-send-open">
        {t("biz.deals.send.open", { label: first.label })}
      </Button>
    );
  }
  // After a refusal the API offers the next counter, whichever way the simulated buyer leans.
  const fallback = next ? t("biz.deals.send.ifRefuse", { next: next.label }) : t("biz.deals.send.ifRefuseOne");
  return (
    <div className="space-y-3 rounded-xl border border-brand-600/30 bg-surface p-4" data-testid="deal-send-confirm">
      <p className="font-semibold text-ink">{t("biz.deals.send.title", { label: first.label, buyer })}</p>
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
        <li>{t("biz.deals.send.simulated")}</li>
        <li>{t("biz.deals.send.ifAgree")}</li>
        <li>{fallback}</li>
      </ul>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs font-medium text-ink-3">{t("biz.deals.send.profile")}</span>
        <Segmented<BuyerProfile>
          label={t("biz.deals.send.profile")}
          name="deal-buyer-profile"
          value={profile}
          onChange={setProfile}
          options={[
            { value: "cooperative", label: t("biz.deals.send.cooperative") },
            { value: "hard_line", label: t("biz.deals.send.hardLine") },
          ]}
        />
      </div>
      {error ? <ErrorState error={error} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" loading={sending} onClick={() => void send()} data-testid="deal-send">
          {sending ? t("biz.deals.send.sending") : t("biz.deals.send.confirm")}
        </Button>
        <Button variant="secondary" disabled={sending} onClick={() => setOpen(false)} data-testid="deal-send-cancel">
          {t("biz.deals.send.cancel")}
        </Button>
      </div>
    </div>
  );
}

/** Each counter sent and the buyer's answer, in the buyer's own words. */
function BuyerThread({ negotiation }: { negotiation: NegotiationView }) {
  const { t } = useI18n();
  return (
    <ol className="space-y-2" data-testid="deal-rounds">
      {negotiation.rounds.map((r) => (
        <li key={r.round} className={`rounded-xl px-4 py-3 text-sm ${r.buyer_response === "ACCEPT" ? "bg-ok-bg/60" : "bg-subtle"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold text-ink">{t("biz.deals.round", { n: r.round })}</span>
            {r.counter_label ? <span className="text-ink-2">{r.counter_label}</span> : null}
            <Badge tone={r.buyer_response === "ACCEPT" ? "ok" : "bad"}>{r.buyer_response === "ACCEPT" ? t("biz.deals.option.accepted") : t("biz.deals.refused")}</Badge>
          </div>
          {r.buyer_text ? <p className="mt-1 italic text-ink-3">&ldquo;{r.buyer_text}&rdquo;</p> : null}
        </li>
      ))}
    </ol>
  );
}

/** What the negotiation did on the books: the operations that ran, and any that wait for the owner. */
function RanOnBooks({ negotiation, today, lead, named }: { negotiation: NegotiationView; today: number; lead: string; named: Named }) {
  const { t, lang } = useI18n();
  const ran = negotiation.operations.filter((o) => o.status === "EXECUTED" && o.kind !== "ACCEPT_OFFER");
  const waiting = negotiation.operations.some((o) => o.status === "PENDING_APPROVAL");
  if (!ran.length && !waiting) return null;
  return (
    <div className="mt-2 space-y-2">
      {ran.length ? (
        <div className="rounded-xl bg-ok-bg/60 px-4 py-3 text-sm" data-testid="deal-gap-funded">
          <p className="font-medium text-ok-fg">{lead}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-2">
            {ran.map((o) => (
              <li key={`${o.seq}-${o.op_id}`}>{localNames(plainDays(idsToNames(o.summary || o.message, named), today, t), lang)}</li>
            ))}
          </ul>
          <Link href="/cash" className="mt-2 inline-block font-semibold text-brand-700 hover:text-brand-600">
            {t("biz.deals.seeCash")}
          </Link>
        </div>
      ) : null}
      {waiting ? (
        <p className="text-sm text-warn-fg" data-testid="deal-waiting">
          {t("biz.deals.send.waiting")}{" "}
          <Link href="/approvals" className="font-semibold underline underline-offset-2">
            {t("biz.deals.send.openApprovals")}
          </Link>
        </p>
      ) : null}
    </div>
  );
}

/**
 * "Recommended response": the first counter as the response to send, the next one behind "Compare another option",
 * and, once a counter was sent, the buyer's reply and what it changed. In Business mode the owner sends the
 * recommended counter from here; Demo mode keeps the stepper's negotiation. The counters are the verifier's, priced and
 * re-checked on the books; the card only shows them.
 */
export function RecommendedResponse({
  v,
  offerId,
  negotiation,
  today,
  mode,
  buyer,
  named,
}: {
  v: VerdictView;
  offerId: string | null;
  negotiation: NegotiationView | null;
  today: number;
  mode: Mode;
  buyer: string;
  named: Named;
}) {
  const { t } = useI18n();
  const [compare, setCompare] = useState(false);
  const counters = v.counters as Counter[];
  if (!counters.length) {
    return (
      <Card id="counters" title={t("biz.deals.response")}>
        <p className="text-sm text-ink-2" data-testid="deal-no-offer">
          {t("glance.offer.none")}
        </p>
      </Card>
    );
  }

  // The buyer accepted: the agreed counter, marked as such, the buyer's reply, and what was funded after it.
  if (negotiation?.outcome === "DEAL") {
    const acceptedId = negotiation.accepted_counter_id ?? negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_id ?? null;
    const agreed = counters.find((c) => c.id === acceptedId) ?? counters[0];
    return (
      <Card id="counters" title={t("biz.deals.agreedTitle")} subtitle={t("biz.deals.agreedSub")}>
        <ul className="space-y-3">
          <CounterBusinessCard c={agreed} badge="accepted" today={today} />
        </ul>
        <p className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.deals.send.replyTitle")}</p>
        <BuyerThread negotiation={negotiation} />
        <p className="mt-3 text-sm text-ink-2" data-testid="deal-negotiation">
          {t("biz.deals.dealDone", { counter: negotiation.rounds.find((r) => r.buyer_response === "ACCEPT")?.counter_label ?? agreed.label })}
        </p>
        <RanOnBooks negotiation={negotiation} today={today} lead={t("biz.deals.gapFundedDeal")} named={named} />
      </Card>
    );
  }

  // The buyer refused every counter: what was offered and what the buyer answered, and what still happened on the books.
  if (negotiation?.outcome === "NO_DEAL") {
    const ran = negotiation.operations.some((o) => o.status === "EXECUTED" || o.status === "PENDING_APPROVAL");
    return (
      <Card id="counters" title={t("biz.deals.offeredTitle")} subtitle={t("biz.deals.offeredSub")}>
        <BuyerThread negotiation={negotiation} />
        <p className="mt-3 text-sm font-medium text-ink" data-testid="deal-negotiation">
          {t("biz.deals.noDealPlain")}
        </p>
        {ran ? <RanOnBooks negotiation={negotiation} today={today} lead={t("biz.deals.gapFunded")} named={named} /> : <p className="mt-1 text-sm text-ink-2">{t("biz.deals.nothingChanged")}</p>}
      </Card>
    );
  }

  const [first, ...rest] = counters;
  const send = mode === "business" && offerId ? <SendToBuyer offerId={offerId} first={first} next={rest[0] ?? null} buyer={buyer} /> : undefined;
  return (
    <Card id="counters" title={t("biz.deals.response")} subtitle={t("biz.deals.counters.sub")}>
      <ul className="space-y-3">
        <CounterBusinessCard c={first} badge="recommended" today={today} action={send} />
        {compare ? rest.map((c) => <CounterBusinessCard key={c.id} c={c} badge={null} today={today} />) : null}
      </ul>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        {rest.length ? (
          <Button variant="secondary" onClick={() => setCompare((x) => !x)} data-testid="deal-compare">
            {compare ? t("biz.deals.hideCompare") : t("biz.deals.compare", { n: rest.length })}
          </Button>
        ) : null}
        {mode === "demo" ? (
          <p className="text-xs text-ink-3">
            {t("biz.deals.negotiateHint")}{" "}
            <Link href="/verdict#negotiation" className="font-medium text-brand-700 underline underline-offset-2">
              {t("biz.deals.negotiateLink")}
            </Link>
          </p>
        ) : null}
      </div>
    </Card>
  );
}
