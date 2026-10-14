"use client";

import { useEffect, useId, useState, type ReactNode } from "react";
import Link from "next/link";
import { Disclosure } from "@/components/business/kit";
import { Button, Callout, ErrorState, LoadingBlock, Segmented, SlowNotice } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { receiptLines } from "@/components/ui/commitment-receipt-model";
import { counterChanged, negotiate } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { bump, recordNegotiation, useDemo } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { isTimeout } from "@/lib/errors";
import { CostTable } from "./cost-table";
import { quietLink } from "./flow-parts";
import { TermsTable } from "./terms-table";
import { useI18n } from "@/lib/i18n";
import { useMode } from "@/lib/mode";
import { receiptOfSend } from "@/lib/receipt";
import type { BuyerProfile, CommitmentReceiptView, CounterChangedDetail, NegotiationView, OfferPictureView, PicturePath } from "@/lib/types";

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
 */
export function SendBlock({
  offerId,
  path,
  picture,
  buyer,
  recordHref,
  onSent,
  onBusy,
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
  /** Told whenever a send or a check is in flight: the page holds the selection then. */
  onBusy: (busy: boolean) => void;
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
  const inFlight = sending || checking || preparing;
  useEffect(() => {
    onBusy(inFlight);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [inFlight]);
  async function send() {
    setSending(true);
    setError(null);
    setSlow(false);
    setRechecked(false);
    try {
      if (!verdict) return;
      // What the owner was shown: the verdict's id and its books' version; if the books moved the API refuses and nothing is sent.
      const result = await negotiate(offerId, { buyer_profile: profile, verdict_id: verdict.id, counter_id: path.key, state_version: verdict.state_version });
      setChanged(null);
      recordNegotiation(result);
      onSent(result);
    } catch (e) {
      const moved = counterChanged(e);
      if (isTimeout(e)) {
        setSlow(true);
        bump();
      } else if (moved) setChanged(moved);
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
      <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
        {reviewing ? null : (
          <Button variant="primary" aria-expanded={false} aria-controls="counters" onClick={() => void open()} data-testid="queue-review-open">
            {t("dq.review")}
          </Button>
        )}
        {children}
      </ActionGroup>
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
          {receipt ? (
            <section aria-labelledby={`${uid}-receipt-title`} className="min-w-0 space-y-5" data-testid="commitment-receipt">
              <h3 id={`${uid}-receipt-title`} className="font-display text-base font-extrabold leading-snug text-ink">
                {t("receipt.title.send", { label: path.label })}
              </h3>
              <Statements receipt={receipt} />
              <div data-testid="send-terms">
                <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("deals.review.terms")}</h4>
                <TermsTable paths={[path]} heads={[path.label]} caption={t("deals.review.terms")} testId="send-terms-table" />
              </div>
              <div data-testid="send-cost">
                <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("deals.cost.title")}</h4>
                <CostTable paths={[path]} heads={[path.label]} caption={t("deals.cost.title")} testId="send-cost-table" />
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
              {/* The simulated buyer's lean is the Demo's control; Business sends with the cooperative buyer and says the reply is simulated. */}
              {mode === "demo" ? (
                <>
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
                </>
              ) : null}
            </div>
          )}
          <ActionGroup testId="deal-commit" label={t("deals.commit")}>
            {/* No server receipt for this reply: no Send (a send the owner cannot read first is not offered). */}
            {verdict && !receipt ? null : (
              <Button variant="primary" loading={sending} disabled={inFlight || !verdict} onClick={() => void send()} data-testid="deal-send">
                {sending ? t("biz.deals.sending") : t("deals.send.go", { label: path.label, buyer })}
              </Button>
            )}
            <button type="button" onClick={() => setReviewing(false)} disabled={inFlight} className={`${quietLink} disabled:opacity-50`} data-testid="queue-review-close">
              {t("dq.review.close")}
            </button>
          </ActionGroup>
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
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}

/** The three statements above the send button: what it authorizes, what happens immediately, what does not happen yet. The server's words, in this order; a statement it did not write is not drawn. */
function Statements({ receipt }: { receipt: CommitmentReceiptView }) {
  const { t } = useI18n();
  const wanted = new Set(["authorizes", "executes_now", "remaining"]);
  const label = { authorizes: "deals.review.authorizing", executes_now: "deals.review.now", remaining: "deals.review.later" } as const;
  const lines = receiptLines(receipt).filter((l) => wanted.has(l.key));
  if (!lines.length) return null;
  return (
    <dl className="divide-y divide-line border-y border-line" data-testid="send-statements">
      {lines.map((l, i) => (
        <div key={l.key} className="py-3" data-testid={`receipt-line-${l.key}`} data-line={i}>
          <dt className="text-supporting font-bold text-ink-3">{t(label[l.key as keyof typeof label])}</dt>
          <dd className="m-0 mt-0.5 min-w-0 whitespace-pre-line break-words text-[15px] leading-snug text-ink">{l.value}</dd>
        </div>
      ))}
    </dl>
  );
}
