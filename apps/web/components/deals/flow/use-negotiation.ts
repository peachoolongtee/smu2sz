"use client";

import { getOffer, getOfferExposure, getOfferPicture } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { offerOf } from "@/lib/selection";
import type { DecisionView, ExposureView, OfferPictureView, OfferView } from "@/lib/types";
import { useEffect, useMemo, useRef } from "react";
import { useDemo } from "@/lib/demo-store";
import { useAsync } from "@/lib/use-async";
import { useDecision } from "@/lib/use-decision";

/**
 * The selected negotiation, hydrated from the server and nothing else (tickets #126 and #134; audit UX05): the offer (GET /offers/{id}), its decision record (GET /decisions/{id}:
 * where it stands), its cash picture (GET /offers/{id}/picture) and what it does to the exposure (GET /offers/{id}/exposure). A deep link in a fresh session reads the same
 * four as a click does; the session store decides nothing. Every answer is keyed by the offer it was read for, so another negotiation's answer is never shown while this one's is on its way.
 *   - `missing`: the server has no such offer (404), so the page asks which negotiation (never a sample).
 *   - `picture` null: the offer has not been evaluated yet (404 NO_VERDICT_YET) or the server has no picture; `undefined` is on its way.
 *   - `exposure` null: the server has the feature off or lacks the offer.
 */
export interface Negotiation {
  offerId: string | null;
  offer: OfferView | null;
  record: DecisionView | null | undefined;
  picture: OfferPictureView | null | undefined;
  exposure: ExposureView | null | undefined;
  loading: boolean;
  missing: boolean;
  error: Error | undefined;
  reload: () => void;
}

/** The record states of an agreement in force or one that is over: the deal tracker is its Overview. */
export const AGREED_RECORD_STATES: ReadonlySet<string> = new Set(["AGREED", "FULFILLED", "MISSED", "EXPIRED", "REVOKED"]);

const isMissing = (e: unknown) => e instanceof ApiError && e.status === 404;

export function useNegotiation(decision: string | null, opts: { agreedPicture?: boolean } = {}): Negotiation {
  const { lang } = useI18n();
  const offerId = offerOf(decision);
  const offerRead = useAsync(async () => (offerId ? { offerId, offer: await getOffer(offerId, lang).catch((e: unknown) => (isMissing(e) ? null : Promise.reject(e))) } : null), [offerId, lang]);
  const offerFor = offerRead.data && offerRead.data.offerId === offerId ? offerRead.data : undefined;
  const offer = offerFor?.offer ?? null;
  const record = useDecision(decision && offerId ? decision : null);
  const hasOffer = Boolean(offer);
  // The picture and the exposure are read only while the owner has a reply to read (RESPONSE_READY): a deal not yet checked has none (404), and once it has an outcome, or waits on the buyer
  // or the approval, the record says where it stands and the cash lines are history. They wait for the record, so no read is wasted.
  // An agreed deal's picture is read too (its Terms tab quotes the agreed response); a read that fails there is no picture, never an error on the page.
  // (Only while the Terms tab is open: an agreed deal's Overview is the tracker and reads no picture.)
  const agreedState = Boolean(opts.agreedPicture) && AGREED_RECORD_STATES.has(record.data?.state ?? "");
  const wantRead = hasOffer && record.data !== undefined && (record.data === null || record.data.state === "RESPONSE_READY" || agreedState);
  // After a write every read of the page is made again at once. The picture and the exposure are the server's slow ones (seconds on the busy books), and a server that answers one
  // request at a time would keep the deal's own record waiting behind them, so the owner would not see "Agreed" for as long as they take. They therefore wait here until the
  // record has been read again, and then read only if it still says there is a reply to read (an accepted deal needs neither). The page keeps showing the earlier ones meanwhile.
  const { version } = useDemo();
  const gate = useMemo(() => {
    const gate = { settled: Promise.resolve(), open: () => {} };
    gate.settled = new Promise<void>((resolve) => {
      gate.open = resolve;
    });
    return gate;
  }, [version, lang, decision]); // eslint-disable-line react-hooks/exhaustive-deps
  const wanted = useRef({ read: false, agreed: false });
  useEffect(() => {
    wanted.current = { read: wantRead, agreed: agreedState };
  });
  useEffect(() => {
    if (!record.loading) gate.open();
  }, [record.loading, gate]);
  const pictureRead = useAsync(
    async () => {
      if (!offerId || !wantRead) return null;
      await gate.settled;
      if (!wanted.current.read) return null;
      return { offerId, picture: await getOfferPicture(offerId, lang).catch((e: unknown) => (isMissing(e) || wanted.current.agreed ? null : Promise.reject(e))) };
    },
    [offerId, wantRead, lang, offerFor?.offer?.latest_verdict_id ?? null],
  );
  const exposureRead = useAsync(
    async () => {
      if (!offerId || !wantRead || agreedState) return null;
      await gate.settled;
      if (!wanted.current.read || wanted.current.agreed) return null;
      return { offerId, view: await getOfferExposure(offerId, lang) };
    },
    [offerId, wantRead, lang, offerFor?.offer?.latest_verdict_id ?? null],
  );
  const pictureFor = pictureRead.data && pictureRead.data.offerId === offerId ? pictureRead.data : undefined;
  const exposureFor = exposureRead.data && exposureRead.data.offerId === offerId ? exposureRead.data : undefined;
  const error = offerRead.error ?? pictureRead.error ?? exposureRead.error ?? record.error;
  const reload = () => {
    offerRead.reload();
    record.reload();
    pictureRead.reload();
    exposureRead.reload();
  };
  return {
    offerId,
    offer,
    record: !offerId ? null : record.data,
    // `undefined` is on its way; null is none (not read, not evaluated, or no longer wanted).
    picture: !offerId || !hasOffer || record.data === undefined ? null : !wantRead ? null : pictureFor === undefined ? undefined : pictureFor.picture,
    exposure: !offerId || !hasOffer || record.data === undefined ? null : !wantRead ? null : exposureFor === undefined ? undefined : exposureFor.view,
    loading: Boolean(offerId) && (offerFor === undefined || (hasOffer && record.data === undefined)),
    missing: Boolean(offerId) && offerFor !== undefined && offerFor.offer === null,
    error,
    reload,
  };
}
