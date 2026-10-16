"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { Disclosure } from "@/components/business/kit";
import { Button, Callout, ErrorState, LoadingBlock, Segmented, SlowNotice } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { receiptLines } from "@/components/ui/commitment-receipt-model";
import { counterChanged, messageRefusal, negotiate } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { bump, recordNegotiation, useDemo } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { isTimeout } from "@/lib/errors";
import { CostTable } from "./cost-table";
import { StateWord } from "@/components/ui/state-word";
import { BuyerMessage, buyerMessageId } from "./buyer-message";
import { AUTH_TONE, quietLink } from "./flow-parts";
import { TermsTable } from "./terms-table";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import { receiptOfSend } from "@/lib/receipt";
import type { BuyerProfile, CommitmentReceiptView, CounterChangedDetail, NegotiationView, OfferedResult, OfferPictureView, PicturePath } from "@/lib/types";

/**
 * The commit area of a reply you may send (tickets #128, #129): one filled button in the whole region. "Review and send the counter" opens the commitment receipt (the server's
 * terms, in its order) above ONE commit button that names the action; the receipt on screen is the review, and Send keeps this one confirmation because it moves money at once.
 * The review is read from the evaluation the picture was drawn from (its `priced_response.receipt`, the terms of this very send): when this tab has not read it, opening the
 * review reads it (the same check as "Check again", asked for by the owner's own press), and the send carries exactly what was shown (that verdict's id and books version, and
 * the counter): if the books moved the API refuses (409) and nothing is sent; "Check again" asks for a new proposal, an explicit step and never a prerequisite to reading the deal. A send that ran out of time may have landed: Retry reads the
 * deal again and sends nothing. The page keys it by the reply, so another reply (or another deal) starts a fresh review. The buyer's reply is simulated in this environment: Business mode says so and sends with
 * the cooperative buyer; Demo mode also lets the owner choose how the simulated buyer leans.
 *
 * Round two (section 2): the review is three statements first (What you are authorizing, What happens immediately, What does not happen yet: the receipt's `authorizes_text`, `executes_now_text`,
 * `remaining_text`), then the terms and the cost of this very reply, then the one button that names the send; the rest of the receipt (who else must agree, the figures, the authority, the assumptions) is
 * one disclosure after it, with the record link as the audit evidence.
 *
 * The message to the buyer (ADR-0011 addendum, round two): the review IS the message FLOW prepared for this very reply, which the owner copies, sends themself and marks sent
 * (`BuyerMessage`: what they asked beside what the owner offers, then the letter). The simulated send is the Demo's only (the owner's choice): in Demo mode it keeps its receipt, the
 * buyer's lean and its button in a dashed "Demo only" row under the cards; Business mode has none. A simulated send the server refuses (409 NO_SIMULATED_BUYER for a buyer with no
 * simulated profile, OFFER_SENT_OUTSIDE once the owner sent a counter themself) says the server's sentence, with the way to the message.
 */
export function SendBlock({
  offerId,
  path,
  picture,
  buyer,
  recordHref,
  onSent,
  onMarked,
  onBack,
  onBusy,
  openSignal = 0,
  hideTrigger = false,
  onReviewing,
  children,
}: {
  offerId: string;
  path: PicturePath;
  picture: OfferPictureView;
  buyer: string;
  /** The negotiation's decision record: the audit evidence's link. */
  recordHref?: string;
  /** Told with the answer when a send was accepted by the API (the page reads the deal again). */
  onSent: (n: NegotiationView) => void;
  /** Told with the server's answer once the owner marked the message to the buyer sent (the page reads the deal again). */
  onMarked?: (r: OfferedResult) => void;
  /** "Back to Deals": closes the deal (the page's list); without it the review closes in place. */
  onBack?: () => void;
  /** Told whenever a send or a check is in flight: the page holds the selection then. */
  onBusy: (busy: boolean) => void;
  /** The deal header's [Review the counter] opens the review from outside: each press raises this number. */
  openSignal?: number;
  /** The review button is the header's, not this block's. */
  hideTrigger?: boolean;
  /** Told whether the review is open (the header's button gives way to the commit button while it is). */
  onReviewing?: (open: boolean) => void;
  /** The other buttons of the decision level, beside the review button. */
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const uid = useId();
  const demo = useDemo();
  const mode = useMode();
  // The evaluation behind the picture, as this tab holds it: its id is the picture's, or it is not the one the owner is looking at.
  const cached = demo.verdicts[offerId];
  const verdict = cached && cached.id === picture.verdict_id ? cached : null;
  // The server's receipt for THIS reply (its own priced response); none means FLOW has not priced it, and nothing is sent for it.
  const receipt = verdict ? receiptOfSend(path, verdict) : null;
  const [reviewing, setReviewing] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [profile, setProfile] = useState<BuyerProfile>("cooperative");
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState<CounterChangedDetail | null>(null);
  const [slow, setSlow] = useState(false);
  const [rechecked, setRechecked] = useState(false);
  // The simulated send refused (a buyer FLOW has no simulated reply for; an offer the owner already sent outside FLOW): the server's sentence, beside the way to the message.
  const [sendRefused, setSendRefused] = useState<string | null>(null);
  const asked = (picture.paths ?? []).find((p) => p.kind === "asked") ?? null;
  const [marking, setMarking] = useState(false);
  const inFlight = sending || checking || preparing || marking;
  useEffect(() => {
    onReviewing?.(reviewing);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the state, not the callback
  }, [reviewing]);
  const lastSignal = useRef(openSignal);
  useEffect(() => {
    if (openSignal === lastSignal.current) return;
    lastSignal.current = openSignal;
    void open();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per press
  }, [openSignal]);
  useEffect(() => {
    onBusy(inFlight);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [inFlight]);
  async function send() {
    setSending(true);
    setError(null);
    setSlow(false);
    setRechecked(false);
    setSendRefused(null);
    try {
      if (!verdict) return;
      // What the owner was shown: the verdict's id and its books' version; if the books moved the API refuses and nothing is sent.
      const result = await negotiate(offerId, { buyer_profile: profile, verdict_id: verdict.id, counter_id: path.key, state_version: verdict.state_version });
      setChanged(null);
      recordNegotiation(result);
      onSent(result);
    } catch (e) {
      const moved = counterChanged(e);
      const refused = messageRefusal(e);
      if (isTimeout(e)) {
        setSlow(true);
        bump();
      } else if (moved) setChanged(moved);
      else if (refused?.code === "NO_SIMULATED_BUYER" || refused?.code === "OFFER_SENT_OUTSIDE") setSendRefused(refused.message_when ?? refused.message);
      else setError(errorText(e, t));
    } finally {
      setSending(false);
    }
  }

  async function open() {
    setReviewing(true);
    if (verdict) return;
    setPreparing(true);
    setError(null);
    try {
      await evaluateAndCache(offerId);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setPreparing(false);
    }
  }

  async function checkAgain() {
    setChecking(true);
    setError(null);
    try {
      await evaluateAndCache(offerId);
      setChanged(null);
      setReviewing(false);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setChecking(false);
    }
  }

  return (
    <div className="space-y-3">
      {hideTrigger ? null : (
        <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
          {reviewing ? null : (
            <Button variant="primary" aria-expanded={false} aria-controls="counters" onClick={() => void open()} data-testid="queue-review-open">
              {t("dq.review")}
            </Button>
          )}
          {children}
        </ActionGroup>
      )}
      {changed ? (
        <div role="alert" data-testid="deal-counter-changed" data-reason={changed.reason}>
          <Callout tone="warn" title={t("biz.deals.changed.title")}>
            <p>{t("biz.deals.changed.reevaluate")}</p>
            <Button className="mt-2" size="sm" variant="secondary" loading={checking} onClick={() => void checkAgain()} data-testid="deal-check-again">
              {t("biz.deals.checkAgain")}
            </Button>
          </Callout>
        </div>
      ) : null}
      {reviewing ? (
        <div id="counters" role="region" aria-label={t("dq.review.region")} className="space-y-5 pt-1" data-testid="queue-review">
          <BuyerMessage offerId={offerId} counterId={path.key} label={path.label} asked={asked} onMarked={(r) => onMarked?.(r)} onCounterChanged={setChanged} onBusy={setMarking} />
          {/* The simulated buyer is the Demo's (the owner's choice): Business sends the message itself, above; the Demo keeps the simulated send, its receipt and its buyer's lean in a row of its own. */}
          {mode === "demo" ? (
            <section aria-labelledby={`${uid}-demo`} className="space-y-5 rounded-[20px] border border-dashed border-line-ui p-5 sm:p-6" data-testid="deal-demo-send">
              <p id={`${uid}-demo`} className="m-0 inline-flex rounded-pill bg-subtle px-3 py-1 text-supporting font-bold uppercase tracking-wide text-ink-2">
                {t("bm.demoOnly")}
              </p>
              {receipt ? (
                <section aria-labelledby={`${uid}-receipt-title`} className="min-w-0 space-y-5" data-testid="commitment-receipt">
                  <h3 id={`${uid}-receipt-title`} className="font-display text-base font-extrabold leading-snug text-ink">
                    {t("receipt.title.send", { label: path.label })}
                  </h3>
                  {path.authority_short_text ? (
                    <p className="m-0" data-testid="send-authority" data-authority={path.authority ?? ""}>
                      <StateWord tone={AUTH_TONE[path.authority ?? ""] ?? "neutral"}>{path.authority_short_text}</StateWord>
                    </p>
                  ) : null}
                  {/* The cost comes before the statements: one of them points back to this total ("already inside the ... above"). */}
                  <div data-testid="send-cost">
                    <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("deals.cost.title")}</h4>
                    <CostTable paths={[path]} heads={[path.label]} caption={t("deals.cost.title")} testId="send-cost-table" />
                  </div>
                  <Statements receipt={receipt} />
                  <div data-testid="send-terms">
                    <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("deals.review.terms")}</h4>
                    <TermsTable paths={[path]} heads={[path.label]} caption={t("deals.review.terms")} testId="send-terms-table" />
                  </div>
                </section>
              ) : verdict ? (
                <p className="rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="deal-unpriced">
                  {t("receipt.unpriced")}
                </p>
              ) : preparing ? (
                <LoadingBlock rows={3} label={t("deals.review.reading")} />
              ) : null}
              {verdict && !receipt ? null : (
                <div className="space-y-2" data-testid="deal-send-confirm-box">
                  <p className="text-sm text-ink-2">{t("biz.deals.send.confirmBody")}</p>
                  {/* What happens if the buyer refuses this reply: the server's sentence, above the button that sends it (nothing is said when the server wrote none). */}
                  {path.if_refused_text ? (
                    <p className="max-w-[68ch] rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-[15px] leading-snug text-ink" data-testid="deal-if-refused">
                      {path.if_refused_text}
                    </p>
                  ) : null}
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-supporting font-medium text-ink-2">{t("biz.deals.send.profile")}</span>
                    <Segmented<BuyerProfile>
                      label={t("biz.deals.send.profile")}
                      name={`deal-buyer-profile-${uid}`}
                      value={profile}
                      onChange={setProfile}
                      options={[
                        { value: "cooperative", label: t("biz.deals.send.cooperative") },
                        { value: "hard_line", label: t("biz.deals.send.hardLine") },
                      ]}
                    />
                  </div>
                  {profile === "hard_line" ? (
                    <p className="text-sm text-ink-2" data-testid="deal-send-refusal">
                      {t("biz.deals.send.ifRefuseOne")}
                    </p>
                  ) : null}
                </div>
              )}
              {/* No server receipt for this reply: no Send (a send the owner cannot read first is not offered). */}
              {verdict && !receipt ? null : (
                <ActionGroup testId="deal-commit" label={t("deals.commit")}>
                  <Button loading={sending} disabled={inFlight || !verdict} onClick={() => void send()} data-testid="deal-send">
                    {sending ? t("biz.deals.sending") : t(path.needs_owner ? "deals.send.approve" : "deals.send.go", { label: path.label, buyer })}
                  </Button>
                </ActionGroup>
              )}
              {receipt ? (
                <Disclosure testId="send-fold" summary={t("deals.review.fold")} className="border-t border-line pt-1">
                  <div className="space-y-3 pt-2">
                    <CommitmentReceipt receipt={receipt} id={`${uid}-rest`} title={t("deals.review.fold")} hideTitle omit={["authorizes", "executes_now", "remaining"]} testId="send-fold-lines" />
                    {recordHref ? (
                      <p className="text-sm">
                        <span className="mr-2 text-supporting font-bold text-ink-3">{t("deals.review.audit")}</span>
                        <Link href={recordHref} className={quietLink} data-testid="send-record-link">
                          {t("deals.record")}
                        </Link>
                      </p>
                    ) : null}
                  </div>
                </Disclosure>
              ) : null}
            </section>
          ) : null}
          <p className="m-0 border-t border-line pt-4">
            {/* Round three: the way out of the send review is back to the deals (the review is not a page of its own to dismiss). */}
            <button type="button" onClick={() => (onBack ? onBack() : setReviewing(false))} disabled={inFlight} className={`${quietLink} disabled:opacity-50`} data-testid="queue-review-close">
              {t("ws.backToDeals")}
            </button>
          </p>
        </div>
      ) : null}
      {slow ? (
        <SlowNotice
          message={t("err.timeout_write")}
          onRetry={() => {
            setSlow(false);
            setRechecked(true);
            bump();
          }}
        />
      ) : rechecked && !error ? (
        <p className="rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink-2" role="status" data-testid="slow-checked">
          {t("biz.slow.checked")}
        </p>
      ) : null}
      {sendRefused ? (
        <div role="alert" data-testid="deal-no-simulated-buyer">
          <Callout tone="warn">
            <p>{sendRefused}</p>
            {reviewing ? (
              <Button
                className="mt-2"
                size="sm"
                onClick={() => {
                  const el = document.getElementById(buyerMessageId(offerId, path.key));
                  el?.scrollIntoView({ block: "start" });
                  el?.focus({ preventScroll: true });
                }}
                data-testid="deal-to-message"
              >
                {t("bm.toMessage")}
              </Button>
            ) : null}
          </Callout>
        </div>
      ) : null}
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}

/** The three statements above the send button: what it authorizes, what happens immediately, what does not happen yet. The server's words, in this order; a statement it did not write is not drawn. */
export function Statements({ receipt, cash }: { receipt: CommitmentReceiptView; /** A fourth statement under the three (accepting as asked: what it does to cash; null when the reserve holds): omitted when the server wrote none. */ cash?: string | null }) {
  const { t } = useI18n();
  const wanted = new Set(["authorizes", "executes_now", "remaining"]);
  const label = { authorizes: "deals.review.authorizing", executes_now: "deals.review.now", remaining: "deals.review.later" } as const;
  const lines: { key: string; value: string; label: string }[] = receiptLines(receipt)
    .filter((l) => wanted.has(l.key))
    .map((l) => ({ key: l.key, value: l.value, label: t(label[l.key as keyof typeof label]) }));
  if (cash && cash.trim()) lines.push({ key: "cash", value: cash, label: t("deals.review.cash") });
  if (!lines.length) return null;
  return (
    <dl className="divide-y divide-line border-y border-line" data-testid="send-statements">
      {lines.map((l, i) => (
        <div key={l.key} className="py-3" data-testid={`receipt-line-${l.key}`} data-line={i}>
          <dt className="text-supporting font-bold text-ink-3">{l.label}</dt>
          <dd className="m-0 mt-0.5 min-w-0 whitespace-pre-line break-words text-[15px] leading-snug text-ink">{l.value}</dd>
        </div>
      ))}
    </dl>
  );
}
