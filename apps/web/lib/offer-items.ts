import type { Annotation } from "@/components/annotated-text";
import type { AnnotationKind } from "./annotation-style";
import type { Displayed, Obligation, CompiledOffer, SourceSpan } from "./types";

export type OfferItem =
  | { id: string; n: number; group: "obligation"; kind: AnnotationKind; spans: SourceSpan[]; obligation: Displayed<Obligation> }
  | { id: string; n: number; group: "funding"; kind: "FUNDING_CLAIM"; spans: SourceSpan[]; claim: Displayed<CompiledOffer>["funding_claims"][number] }
  | { id: string; n: number; group: "authority"; kind: "AUTHORITY_CLAIM"; spans: SourceSpan[]; claim: Displayed<CompiledOffer>["authority_claims"][number] }
  | { id: string; n: number; group: "data"; kind: "DATA_REQUEST"; spans: SourceSpan[]; claim: Displayed<CompiledOffer>["data_requests"][number] };

/** Flattens a compiled offer into numbered items: obligations first, then the flags. Order is stable. */
export function offerItems(offer: Displayed<CompiledOffer>): OfferItem[] {
  const items: OfferItem[] = [];
  let n = 0;
  for (const o of offer.obligations) {
    items.push({ id: `obl:${o.id}`, n: ++n, group: "obligation", kind: o.type, spans: o.spans, obligation: o });
  }
  offer.funding_claims.forEach((c, i) => {
    items.push({ id: `fund:${i}`, n: ++n, group: "funding", kind: "FUNDING_CLAIM", spans: [c.span], claim: c });
  });
  offer.authority_claims.forEach((c, i) => {
    items.push({ id: `auth:${i}`, n: ++n, group: "authority", kind: "AUTHORITY_CLAIM", spans: [c.span], claim: c });
  });
  offer.data_requests.forEach((c, i) => {
    items.push({ id: `data:${i}`, n: ++n, group: "data", kind: "DATA_REQUEST", spans: [c.span], claim: c });
  });
  return items;
}

/** Annotations for one document. `label` is resolved by the caller (translated). */
export function annotationsFor(items: OfferItem[], docId: string, label: (item: OfferItem) => string): Annotation[] {
  return items.flatMap((item) =>
    item.spans
      .filter((s) => s.doc_id === docId)
      .map((s, i) => ({
        id: item.id,
        kind: item.kind,
        start: s.start,
        end: s.end,
        n: item.n,
        label: label(item),
        key: `${item.id}:${i}`,
      })),
  );
}
