import type { CommitmentStatus, DecisionView, OperationStatus } from "./types";

/**
 * What an offer has actually done, as the verdict page shows it above the (historical) verdict. The source is the decision record
 * (GET /decisions/{id}, ADR-0011): its `execution`, `agreement` and `settlement`. Every sentence and figure is the server's; this file
 * only picks which parts to show and which tone names the agreement. It reads no ledger, no cash position and no click.
 */

export type AgreementState = "agreed" | "settled" | "waiting" | "expired" | "revoked" | "none";

export interface ExecutedFunding {
  op_id: string;
  status: OperationStatus;
  /** The server's sentence for the operation (empty when the record has none; the page then names the kind). */
  text: string;
  kind: string;
}

export interface FundingLot {
  facility_name: string;
  amount_display: string;
  landed: boolean;
  arrival_when: string;
}

export interface ExecutionSummaryData {
  /** The server's one-sentence summary of what ran ("Agreement … recorded. Funding of ¥149,986.20 was requested and has landed."). */
  summary_text: string;
  agreement: AgreementState;
  /** The agreement's status in the server's words ("Agreed", "Expired", "Early payment did not arrive"); null when there is none. */
  agreement_text: string | null;
  /** The record's state in words, and what it is waiting for. */
  state_text: string;
  waiting_text: string;
  funding: ExecutedFunding[];
  /** The funding the decision created, landed or still arriving. */
  lots: FundingLot[];
}

const FUNDING_KINDS = new Set(["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);

/** The tone class of an agreement, by the commitment's status. The words are the server's. */
export function agreementState(status: CommitmentStatus | null | undefined): AgreementState {
  switch (status) {
    case "ACCEPTED":
    case "ACTIVE":
      return "agreed";
    case "FULFILLED":
      return "settled";
    case "PROPOSED":
      return "waiting";
    case "EXPIRED":
      return "expired";
    case "REVOKED":
      return "revoked";
    default:
      return "none";
  }
}

/**
 * The summary for one record, or null when it has done nothing (no agreement, no operation, no lot): evaluation alone.
 * A deal that went to NO_DEAL but still funded the gap has funding and no agreement, and says both.
 */
export function summaryFromRecord(d: DecisionView): ExecutionSummaryData | null {
  const funding = d.operations
    .filter((o) => FUNDING_KINDS.has(o.kind))
    .map((o) => ({ op_id: o.op_id, status: o.status, text: o.event_text ?? "", kind: o.kind }));
  if (!d.operations.length && !d.agreement && !d.settlement.length) return null;
  return {
    summary_text: d.execution.summary_text,
    agreement: agreementState(d.agreement?.status),
    agreement_text: d.agreement?.status_text ?? null,
    state_text: d.state_text,
    waiting_text: d.waiting_for.text,
    funding,
    lots: d.settlement.map((l) => ({ facility_name: l.facility_name, amount_display: l.principal_display, landed: l.settled, arrival_when: l.arrival_when })),
  };
}
