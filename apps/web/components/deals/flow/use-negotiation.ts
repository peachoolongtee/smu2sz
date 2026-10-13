"use client";

import { getOffer, getOfferExposure, getOfferPicture } from "@/lib/api";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import { offerOf } from "@/lib/selection";
import type { DecisionView, ExposureView, OfferPictureView, OfferView } from "@/lib/types";
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

const isMissing = (e: unknown) => e instanceof ApiError && e.status === 404;

export function useNegotiation(decision: string | null): Negotiation {
  const { lang } = useI18n();
  const offerId = offerOf(decision);
  const offerRead = useAsync(async () => (offerId ? { offerId, offer: await getOffer(offerId).catch((e: unknown) => (isMissing(e) ? null : Promise.reject(e))) } : null), [offerId]);
  const offerFor = offerRead.data && offerRead.data.offerId === offerId ? offerRead.data : undefined;
  const offer = offerFor?.offer ?? null;
  const record = useDecision(decision && offerId ? decision : null);
  const hasOffer = Boolean(offer);
  const pictureRead = useAsync(
    async () => (offerId && hasOffer ? { offerId, picture: await getOfferPicture(offerId, lang).catch((e: unknown) => (isMissing(e) ? null : Promise.reject(e))) } : null),
    [offerId, hasOffer, lang, offerFor?.offer?.latest_verdict_id ?? null],
  );
  const exposureRead = useAsync(async () => (offerId && hasOffer ? { offerId, view: await getOfferExposure(offerId, lang) } : null), [offerId, hasOffer, lang, offerFor?.offer?.latest_verdict_id ?? null]);
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
    picture: !offerId || !hasOffer ? null : pictureFor === undefined ? undefined : pictureFor.picture,
    exposure: !offerId || !hasOffer ? null : exposureFor === undefined ? undefined : exposureFor.view,
    loading: Boolean(offerId) && (offerFor === undefined || (hasOffer && record.data === undefined)),
    missing: Boolean(offerId) && offerFor !== undefined && offerFor.offer === null,
    error,
    reload,
  };
}
