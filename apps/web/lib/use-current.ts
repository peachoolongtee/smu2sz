"use client";

import { getOffer } from "./api";
import { useDemo } from "./demo-store";
import type { NegotiationView, OfferView, VerdictView } from "./types";
import { useAsync } from "./use-async";

export interface CurrentOffer {
  offerId: string | null;
  offer: OfferView | null;
  verdict: VerdictView | null;
  negotiation: NegotiationView | null;
  loading: boolean;
  error: Error | undefined;
  reload: () => void;
}

/** The offer the session is working on, with its cached verdict and negotiation (if any). */
export function useCurrentOffer(): CurrentOffer {
  const demo = useDemo();
  const id = demo.offerId;
  const cached = id ? (demo.offers[id] ?? null) : null;
  const fetched = useAsync<OfferView | null>(async () => (id && !cached ? await getOffer(id) : null), [id, Boolean(cached)]);
  const offer = cached ?? fetched.data ?? null;
  return {
    offerId: id,
    offer,
    verdict: id ? (demo.verdicts[id] ?? null) : null,
    negotiation: id ? (demo.negotiations[id] ?? null) : null,
    loading: Boolean(id) && !offer && fetched.loading,
    error: fetched.error,
    reload: fetched.reload,
  };
}
