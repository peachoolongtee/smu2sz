import type { ApprovalView } from "./types";

/**
 * Whether the owner may approve. A commercial approval (accepting an offer, recording a commitment) puts the owner's name to an
 * agreement, so it is shown only when the server resolved the agreement and sent its terms. Anything else, including an older
 * answer that lacks the field, fails closed: Approve is disabled and the card says why. Funding approvals carry no terms.
 */
export type TermsGate = { commercial: false } | { commercial: true; available: true } | { commercial: true; available: false };

const COMMERCIAL_KINDS = new Set(["ACCEPT_OFFER", "RECORD_COMMITMENT"]);

export function isCommercial(a: Pick<ApprovalView, "operation" | "operation_kind">): boolean {
  return COMMERCIAL_KINDS.has(a.operation?.kind ?? a.operation_kind);
}

export function termsGate(a: Pick<ApprovalView, "operation" | "operation_kind" | "presentation">): TermsGate {
  if (!isCommercial(a)) return { commercial: false };
  const p = a.presentation;
  const shown = p?.terms_available === true && ((p.terms?.length ?? 0) > 0 || Boolean(p.what_you_agree_to));
  return shown ? { commercial: true, available: true } : { commercial: true, available: false };
}

/** The Approve button is disabled while another decision is running, or while the terms of a commercial approval cannot be shown. */
export function approveDisabled(a: Pick<ApprovalView, "operation" | "operation_kind" | "presentation">, busy: boolean): boolean {
  const gate = termsGate(a);
  return busy || (gate.commercial && !gate.available);
}
