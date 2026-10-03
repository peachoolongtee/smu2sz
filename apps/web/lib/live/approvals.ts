/**
 * The Tier-2 queue. GET /approvals/queue returns raw approval records; the page wants a display row.
 * Decisions are owner actions. Like every live request they carry X-Owner-Token, and the server (not this file)
 * decides whether the caller really is the owner. A refusal from the executor is surfaced as an error.
 */

import { ApiError } from "../errors";
import type { ApprovalDecision, ApprovalOperation, ApprovalStatus, ApprovalView, OperationResult, Tier } from "../types";
import { http } from "./http";

interface RawApproval {
  id: string;
  op_id: string | null;
  kind: string | null;
  reason: string;
  status: ApprovalStatus;
  decided_by: string | null;
  operation: (ApprovalOperation & { amount_fen?: number | null }) | null;
  /** Added by the API: the row is display-ready. */
  subject?: string;
  tier?: Tier;
  created_day?: number | null;
  /** The clock day the owner decided; null while pending (and on rows decided before the API kept it). */
  decided_day?: number | null;
  /** The executor's message for the decision run, when there is one. */
  result_message?: string | null;
  amount_fen?: number | null;
  amount_display?: string | null;
}

export async function getApprovals(): Promise<ApprovalView[]> {
  const { approvals } = await http<{ approvals: RawApproval[] }>("GET", "/approvals/queue");
  // `decided_day` is the API's, never the simulated clock today (that is not the day a past decision was made).
  return approvals.map(
    (a) =>
      ({
        id: a.id,
        // The API sends a short subject; `reason` (the executor's sentence) is the detail line.
        subject: a.subject || a.reason,
        status: a.status,
        // The queue holds Tier-2 operations by definition (docs/ARCHITECTURE.md, Operations and tiers).
        tier: a.tier ?? "TIER_2",
        requested_by: a.operation?.requested_by ?? "AGENT",
        created_day: a.created_day ?? a.operation?.day ?? 0,
        operation_kind: a.kind ?? "",
        reason: a.reason,
        op_id: a.op_id,
        operation: a.operation,
        amount_fen: a.amount_fen ?? a.operation?.amount_fen ?? null,
        amount_display: a.amount_display ?? null,
        detail: a.subject && a.reason ? a.reason : a.op_id ? `Operation ${a.op_id}` : "",
        decided_day: a.decided_day ?? null,
      }) as ApprovalView,
  );
}

export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  // A 404 (unknown id) or 409 (already decided) is thrown as an ApiError with that status; the page explains it.
  const { result } = await http<{ result: OperationResult }>("POST", `/approvals/${encodeURIComponent(id)}`, {
    body: { decision },
  });
  const notOwner = result.violations.some((v) => v.code === "INSUFFICIENT_AUTHORITY");
  if (notOwner || (decision === "APPROVE" && result.status === "REFUSED")) {
    throw new ApiError(403, result.message || "The executor refused this decision.");
  }
  const found = (await getApprovals()).find((a) => a.id === id);
  if (!found) throw new ApiError(404, `Approval ${id} not found.`);
  return { ...found, result_message: result.message };
}
