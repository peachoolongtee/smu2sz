"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { Disclosure } from "@/components/business/kit";
import { Button, Callout, ErrorState, LoadingBlock } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { receiptLines } from "@/components/ui/commitment-receipt-model";
import { acceptOffer, declineOffer } from "@/lib/api";
import { evaluate as evaluateAndCache } from "@/lib/demo";
import { bump, useDemo } from "@/lib/demo-store";
import { errorText } from "@/lib/error-text";
import { acceptRefusal } from "@/lib/accept";
import { useI18n } from "@/lib/i18n";
import type { AcceptBlock as AcceptView, OfferPictureView, PicturePath } from "@/lib/types";
import { CostTable } from "./cost-table";
import { quietLink } from "./flow-parts";
import { Statements } from "./send-block";
import { TermsTable } from "./terms-table";

/** What the owner's accept or decline came to, told to the page so it can show it beside the record once the record has moved on (the review itself is gone by then). */
export type AcceptOutcome =
  | { kind: "accepted"; text: string | null }
  | { kind: "declined" }
  | { kind: "refused"; text: string };

/**
 * The commit area of a request that needs the owner's review and has no counter FLOW can send (map #121, "Accept as asked"): the owner can accept it as asked or decline it. The
 * sibling of the send review (`send-block.tsx`) and built the same way. "Review the request" (an outline button) opens, in place, the server's `accept.receipt` as three statements
 * (what you are authorizing, what happens immediately, what does not happen yet), then the terms and the cost of the ask, then ONE filled button that names the act (`commit_label`)
 * with a quiet decline beside it; the rest of the receipt is one fold after the buttons. Declining asks once, in one line, because it closes the request. When the server says the
 * request cannot be accepted (`available` false: over the mandate) the review shows its reason and no button. A 409 (the books moved, the offer lapsed, the mandate is exceeded) shows
 * the server's sentence in place and moved nothing. Every word of the sentences, labels and figures is the server's; the dictionary supplies only headings.
 *
 * What the owner was shown is sent back (the verdict's id and the books' version, from the accept block or else from the evaluation the picture was drawn from), so the API
 * refuses an accept the books have outgrown. The page keys this by the offer, so another negotiation starts a fresh review; `initialOpen` is the address's `review=1`.
 */
export function AcceptBlock({
  offerId,
  accept,
  asked,
  picture,
  buyer,
  recordHref,
  initialOpen,
  onDone,
  onBusy,
  openSignal = 0,
  hideTrigger = false,
  onReviewing,
}: {
  offerId: string;
  accept: AcceptView;
  /** The ask as a path: its terms and its cost with the basis. */
  asked: PicturePath | null;
  picture: OfferPictureView;
  buyer: string;
  recordHref?: string;
  initialOpen: boolean;
  onDone: (outcome: AcceptOutcome) => void;
  onBusy: (busy: boolean) => void;
  /** The header's [Review the request] opens the review from outside: each press raises this number. */
  openSignal?: number;
  /** The open button is the header's (or the comparison's), not this block's. */
  hideTrigger?: boolean;
  /** Told whether the review is open. */
  onReviewing?: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const uid = useId();
  const demo = useDemo();
  const [reviewing, setReviewing] = useState(initialOpen);
  const [preparing, setPreparing] = useState(false);
  const [accepting, setAccepting] = useState(false);
  const [declining, setDeclining] = useState(false);
  const [checking, setChecking] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [refusal, setRefusal] = useState<{ code: string; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const openRef = useRef<HTMLButtonElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const regionRef = useRef<HTMLDivElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const inFlight = accepting || declining || checking || preparing;
  useEffect(() => {
    onBusy(inFlight);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the flight, not the callback
  }, [inFlight]);

  // What the owner is shown: the server's block says which verdict and books version it was drawn from, else the evaluation the picture came from does.
  const cached = demo.verdicts[offerId];
  const verdict = cached && cached.id === picture.verdict_id ? cached : null;
  const verdictId = accept.verdict_id ?? verdict?.id ?? null;
  const stateVersion = accept.state_version ?? verdict?.state_version ?? null;
  const ready = verdictId !== null && stateVersion !== null;
  const lines = receiptLines(accept.receipt);
  const canCommit = accept.available && Boolean(accept.commit_label) && lines.length > 0;
  // A request can be declined whatever its verdict (the server says when it cannot: lapsed, or already answered), so an over-the-mandate request still offers the quiet decline.
  const canDecline = Boolean(accept.decline_label) && accept.decline_available !== false;

  async function prepare() {
    if (ready || !(accept.available || canDecline)) return;
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

  function open() {
    setReviewing(true);
    void prepare();
    requestAnimationFrame(() => (titleRef.current ?? regionRef.current)?.focus({ preventScroll: false }));
  }

  const lastSignal = useRef(openSignal);
  useEffect(() => {
    if (openSignal === lastSignal.current) return;
    lastSignal.current = openSignal;
    open();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per press
  }, [openSignal]);
  useEffect(() => {
    onReviewing?.(reviewing);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reports the state, not the callback
  }, [reviewing]);

  // Arrived with `review=1`: the review is open already, and its version is read once.
  useEffect(() => {
    if (!initialOpen) return;
    const id = window.setTimeout(() => void prepare(), 0);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, []);

  function close() {
    setReviewing(false);
    setConfirming(false);
    setRefusal(null);
    requestAnimationFrame(() => openRef.current?.focus());
  }

  async function run(act: "accept" | "decline") {
    if (!verdictId || stateVersion === null) return;
    (act === "accept" ? setAccepting : setDeclining)(true);
    setError(null);
    setRefusal(null);
    try {
      if (act === "accept") {
        const result = await acceptOffer(offerId, { verdict_id: verdictId, state_version: stateVersion });
        onDone({ kind: "accepted", text: result.execution?.summary_text || null });
      } else {
        await declineOffer(offerId, { verdict_id: verdictId, state_version: stateVersion });
        onDone({ kind: "declined" });
      }
      bump();
    } catch (e) {
      const refused = acceptRefusal(e);
      if (refused) {
        setRefusal(refused);
        setConfirming(false);
        onDone({ kind: "refused", text: refused.text });
        bump();
      } else setError(errorText(e, t));
    } finally {
      (act === "accept" ? setAccepting : setDeclining)(false);
    }
  }

  async function checkAgain() {
    setChecking(true);
    setError(null);
    try {
      await evaluateAndCache(offerId);
      setRefusal(null);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setChecking(false);
    }
  }

  // Nothing the server wrote, nothing to review.
  if (!accept.available && !accept.reason_text && !canDecline) return null;

  return (
    <div className="space-y-3">
      {reviewing || hideTrigger ? null : (
        <ActionGroup className="mt-4" testId="deal-actions" label={t("deals.actions")}>
          <Button ref={openRef} variant="secondary" aria-expanded={false} aria-controls={`${uid}-review`} onClick={open} data-testid="accept-review-open">
            {t("accept.review")}
          </Button>
        </ActionGroup>
      )}
      {reviewing ? (
        <div id={`${uid}-review`} ref={regionRef} tabIndex={-1} role="region" aria-label={t("accept.review.region")} className="space-y-5 pt-1 outline-none" data-testid="accept-review" data-available={accept.available ? "1" : "0"}>
          {accept.available ? (
            <>
              {lines.length ? (
                <section aria-labelledby={`${uid}-title`} className="min-w-0 space-y-5" data-testid="commitment-receipt">
                  <h3 id={`${uid}-title`} ref={titleRef} tabIndex={-1} className="font-display text-base font-extrabold leading-snug text-ink outline-none">
                    {t("receipt.title.accept", { buyer })}
                  </h3>
                  <Statements receipt={accept.receipt!} cash={accept.receipt?.cash_text} />
                  {asked ? (
                    <>
                      <div data-testid="accept-terms">
                        <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("accept.terms")}</h4>
                        <TermsTable paths={[asked]} heads={[t("deals.terms.col.asked")]} caption={t("accept.terms")} testId="accept-terms-table" />
                      </div>
                      <div data-testid="accept-cost">
                        <h4 className="mb-1 text-supporting font-bold text-ink-2">{t("deals.cost.title")}</h4>
                        <CostTable paths={[asked]} heads={[t("deals.cost.col.asked")]} caption={t("deals.cost.title")} testId="accept-cost-table" />
                      </div>
                    </>
                  ) : null}
                </section>
              ) : preparing ? (
                <LoadingBlock rows={3} label={t("accept.reading")} />
              ) : null}
            </>
          ) : (
            // The request cannot be accepted as asked: the server says why ("only a new mandate changes that"), and there is nothing to press.
            <p className="rounded-tile border border-line bg-subtle px-3.5 py-2.5 text-sm text-ink" role="status" data-testid="accept-reason">
              {accept.reason_text}
            </p>
          )}
          {refusal ? (
            <div role="alert" data-testid="accept-refused" data-code={refusal.code}>
              <Callout tone="warn">
                <p className="text-ink">{refusal.text}</p>
                {refusal.code === "COUNTER_CHANGED" ? (
                  <Button className="mt-2" size="sm" loading={checking} onClick={() => void checkAgain()} data-testid="accept-check-again">
                    {t("biz.deals.checkAgain")}
                  </Button>
                ) : null}
              </Callout>
            </div>
          ) : null}
          {error ? <ErrorState error={error} /> : null}
          <ActionGroup testId="deal-commit" label={t("deals.commit")}>
            {canCommit ? (
              <Button variant="primary" loading={accepting} disabled={inFlight || !ready} onClick={() => void run("accept")} data-testid="accept-go">
                {accept.commit_label}
              </Button>
            ) : null}
            {canDecline ? (
              <button
                type="button"
                aria-expanded={confirming}
                aria-controls={`${uid}-decline`}
                disabled={inFlight || !ready}
                onClick={() => {
                  setConfirming(true);
                  requestAnimationFrame(() => confirmRef.current?.focus());
                }}
                className={`${quietLink} whitespace-nowrap disabled:opacity-50`}
                data-testid="accept-decline"
              >
                {accept.decline_label}
              </button>
            ) : null}
            <button type="button" onClick={close} disabled={inFlight} className={`${quietLink} whitespace-nowrap disabled:opacity-50`} data-testid="accept-review-close">
              {t("accept.review.close")}
            </button>
          </ActionGroup>
          {confirming && canDecline ? (
            <div
              id={`${uid}-decline`}
              role="group"
              aria-label={accept.decline_label ?? undefined}
              className="space-y-2 rounded-tile border border-line bg-subtle px-3.5 py-3"
              data-testid="accept-decline-confirm"
              onKeyDown={(e) => {
                if (e.key === "Escape" && !inFlight) {
                  e.preventDefault();
                  e.stopPropagation();
                  setConfirming(false);
                }
              }}
            >
              <p className="text-sm text-ink-2">{t("accept.decline.confirm")}</p>
              <ActionGroup label={accept.decline_label ?? undefined}>
                <Button ref={confirmRef} variant="secondary" loading={declining} disabled={inFlight} onClick={() => void run("decline")} data-testid="accept-decline-go">
                  {accept.decline_label}
                </Button>
                <button type="button" onClick={() => setConfirming(false)} disabled={inFlight} className={`${quietLink} disabled:opacity-50`} data-testid="accept-decline-cancel">
                  {t("accept.review.close")}
                </button>
              </ActionGroup>
            </div>
          ) : null}
          {accept.available && lines.length ? (
            <Disclosure testId="accept-fold" summary={t("deals.review.fold")} className="border-t border-line pt-1">
              <div className="space-y-3 pt-2">
                <CommitmentReceipt receipt={accept.receipt} id={`${uid}-rest`} title={t("deals.review.fold")} hideTitle omit={["authorizes", "executes_now", "remaining"]} testId="accept-fold-lines" />
                {recordHref ? (
                  <p className="text-sm">
                    <span className="mr-2 text-supporting font-bold text-ink-3">{t("deals.review.audit")}</span>
                    <Link href={recordHref} className={quietLink} data-testid="accept-record-link">
                      {t("deals.record")}
                    </Link>
                  </p>
                ) : null}
              </div>
            </Disclosure>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
