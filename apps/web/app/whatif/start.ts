import type { OfferView, StateView, WhatIfParams } from "@/lib/types";

/** The offer's terms as the sliders take them: the obligations' own numbers by type (nothing computed), and the customer's current payment terms from the books where the offer asks none. */
export function startOf(offer: OfferView, books: StateView): WhatIfParams {
  const obl = offer.offer.obligations;
  const rate = (type: string) => obl.find((o) => o.type === type)?.rate_bp ?? 0;
  const terms = obl.find((o) => o.type === "TERMS_EXTENSION")?.target_terms_days ?? books.state.recurring_invoices.find((r) => r.counterparty_id === offer.offer.counterparty_id)?.terms_days ?? 0;
  return { terms_days: terms, discount_bp: rate("IMMEDIATE_DISCOUNT"), rebate_bp: rate("CONTINGENT_REBATE"), price_adjustment_bp: rate("PRICE_ADJUSTMENT"), settle_face_fen: null };
}
