"use client";

import { useEffect, useId, useState, type ReactNode } from "react";
import { Button, Callout, ErrorState, Segmented, SlowNotice, textLinkClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { counterChanged, getState, negotiate } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { bump, recordNegotiation } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { isTimeout } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import type { BuyerProfile, CommitmentReceiptView, CounterChangedDetail, NegotiationView, OfferPictureView, PicturePath } from "@/lib/types";

/**
 * The commit area of a reply you may send (tickets #128, #129): one filled button in the whole region. "Review and send the counter" opens the commitment receipt (the server's
 * terms, in its order) above ONE commit button that names the action; the receipt on screen is the review, and Send keeps this one confirmation because it moves money at once.
 * The send carries what the owner was shown (the picture's verdict id, the counter id and the books' version): if the books moved the API refuses (409) and nothing is
 * sent; "Check again" asks for a new proposal, an explicit step and never a prerequisite to reading the deal. A send that ran out of time may have landed: Retry reads the
 * deal again and sends nothing. The page keys it by the reply, so another reply (or another deal) starts a fresh review. The buyer's reply is simulated in this demo, and the owner says how the simulated buyer leans before sending.
 */
export function SendBlock({
  offerId,
  path,
  picture,
  receipt,
  buyer,
  onSent,
  onBusy,
  children,
}: {
  offerId: string;
  path: PicturePath;
  picture: OfferPictureView;
  receipt: CommitmentReceiptView;
  buyer: string;
  /** Told with the answer when a send was accepted by the API (the page reads the deal again). */
  onSent: (n: NegotiationView) => void;
  /** Told whenever a send or a check is in flight: the page holds the selection then. */
  onBusy: (busy: boolean) => void;
  /** The other buttons of the decision level, beside the review button. */
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const uid = useId();
  const [reviewing, setReviewing] = useState(false);
  const [profile, setProfile] = useState<BuyerProfile>("cooperative");
  const [sending, setSending] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changed, setChanged] = useState<CounterChangedDetail | null>(null);
  const [slow, setSlow] = useState(false);
  const [rechecked, setRechecked] = useState(false);
  const inFlight = sending || checking;
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
      // The books' version as they stand now: if it is not the verdict's, the API refuses and nothing is sent.
      const books = await getState();
      const result = await negotiate(offerId, { buyer_profile: profile, verdict_id: picture.verdict_id ?? undefined, counter_id: path.key, state_version: books.state.state_version });
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
          <Button variant="primary" aria-expanded={false} aria-controls={`${uid}-review`} onClick={() => setReviewing(true)} data-testid="queue-review-open">
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
        <div id={`${uid}-review`} role="region" aria-label={t("dq.review.region")} className="space-y-4 pt-1" data-testid="queue-review">
          <CommitmentReceipt receipt={receipt} id={`${uid}-receipt`} title={t("receipt.title.send", { label: path.label })} />
          <div className="space-y-2" data-testid="deal-send-confirm-box">
            <p className="text-sm text-ink-2">{t("biz.deals.send.confirmBody")}</p>
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
          <ActionGroup testId="deal-commit" label={t("deals.commit")}>
            <Button variant="primary" loading={sending} disabled={inFlight} onClick={() => void send()} data-testid="deal-send">
              {sending ? t("biz.deals.sending") : t("deals.send.go", { label: path.label, buyer })}
            </Button>
            <button type="button" onClick={() => setReviewing(false)} disabled={inFlight} className={`${textLinkClass} disabled:opacity-50`} data-testid="queue-review-close">
              {t("dq.review.close")}
            </button>
          </ActionGroup>
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
