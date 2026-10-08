import type { Commitment, CommitmentStatus, Displayed, HomeView, LedgerView, NegotiationView, OperationStatus, OperationView } from "./types";

/**
 * What an offer has actually done, as the verdict page shows it above the (historical) verdict. Every sentence and figure is the
 * server's (`event_text`, `amount_display`, `arrival_when`); this file only chooses which rows belong to the offer and which
 * label names the agreement. Wave 2 replaces the source with the decision record and keeps these server-shaped props.
 */

export type AgreementState = "agreed" | "settled" | "waiting" | "expired" | "revoked" | "none";

export interface ExecutedFunding {
  op_id: string;
  status: OperationStatus;
  /** The server's sentence for the operation. */
  text: string;
}

export interface FundingLot {
  facility_name: string;
  amount_display: string;
  landed: boolean;
  arrival_when: string;
}

export interface ExecutionSummaryData {
  agreement: AgreementState;
  /** The commitment's status as the server sent it, for a screen reader or a test. */
  commitment_status: CommitmentStatus | null;
  funding: ExecutedFunding[];
  /** The funding on the books, landed or still arriving; empty unless a funding operation of this offer executed. */
  lots: FundingLot[];
  /** The agreement exists and has not been settled yet. */
  settlement_pending: boolean;
}

const FUNDING_KINDS = new Set(["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);

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

/** The server's sentence for an operation; the older recordings only have the executor's. */
export function operationText(op: Pick<OperationView, "event_text" | "message_when" | "summary" | "message">): string {
  return op.event_text || op.message_when || op.summary || op.message;
}

/**
 * The summary for one offer, or null when the offer has done nothing (no agreement and no operation): evaluation alone.
 * An operation belongs to the offer when the negotiation returned it, or when the ledger's operation id names the offer
 * (`fund-OFF-…`) or one of its commitments (`accept-CMT-…`).
 */
export function buildExecutionSummary(
  offerId: string,
  negotiation: Pick<NegotiationView, "operations" | "commitment"> | null,
  ledger: Pick<LedgerView, "commitments" | "operations"> | undefined,
  home: Pick<HomeView, "cash"> | undefined,
): ExecutionSummaryData | null {
  const commitments: Displayed<Commitment>[] = (ledger?.commitments ?? []).filter((c) => c.offer_id === offerId);
  // The latest commitment for the offer is the one the owner is looking at; the session's own is the fallback when the ledger is unread.
  const commitment = commitments[commitments.length - 1] ?? negotiation?.commitment ?? null;
  const ids = new Set<string>([...(negotiation?.operations ?? []).map((o) => o.op_id)]);
  const named = (opId: string) => opId.includes(offerId) || commitments.some((c) => opId.includes(c.id));
  // The ledger's row wins over the negotiation's copy of the same operation: it carries the business sentence.
  const byId = new Map<string, OperationView>();
  for (const o of negotiation?.operations ?? []) byId.set(o.op_id, o);
  for (const o of ledger?.operations ?? []) if (ids.has(o.op_id) || named(o.op_id)) byId.set(o.op_id, o);
  const ops = [...byId.values()];

  const funding = ops
    .filter((o) => FUNDING_KINDS.has(o.kind))
    .map((o) => ({ op_id: o.op_id, status: o.status, text: operationText(o) }));
  const agreement = agreementState(commitment?.status);
  if (!funding.length && agreement === "none" && !ops.length) return null;

  const executedFunding = funding.some((f) => f.status === "EXECUTED");
  const lots = executedFunding
    ? (home?.cash.funding_lots ?? [])
        .filter((l) => !l.opening)
        .map((l) => ({ facility_name: l.facility_name, amount_display: l.amount_display, landed: l.landed, arrival_when: l.arrival_when }))
    : [];

  return { agreement, commitment_status: commitment?.status ?? null, funding, lots, settlement_pending: agreement === "agreed" };
}
