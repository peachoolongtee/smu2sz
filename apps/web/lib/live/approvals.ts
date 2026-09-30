/**
 * The Tier-2 queue. GET /approvals/queue returns raw approval records; the page wants a display row.
 * Decisions are owner actions. Like every live request they carry X-Owner-Token, and the server (not this file)
 * decides whether the caller really is the owner. A refusal from the executor is surfaced as an error.
 */

import { ApiError } from "../errors";
import type { Actor, ApprovalDecision, ApprovalStatus, ApprovalView, OperationResult, StateView } from "../types";
import { http } from "./http";

interface RawApproval {
  id: string;
  op_id: string | null;
  kind: string | null;
  reason: string;
  status: ApprovalStatus;
  decided_by: string | null;
  operation: { requested_by?: Actor; day?: number; amount_fen?: number | null } | null;
}

export async function getApprovals(): Promise<ApprovalView[]> {
  const { approvals } = await http<{ approvals: RawApproval[] }>("GET", "/approvals/queue");
  // The queue does not record the decision day; a decided row shows the simulated clock today.
  const decided = approvals.some((a) => a.status !== "PENDING");
  const today = decided ? (await http<StateView & { day: number }>("GET", "/state")).day : 0;
  return approvals.map(
    (a) =>
      ({
        id: a.id,
        subject: a.reason,
        status: a.status,
        // The queue holds Tier-2 operations by definition (docs/ARCHITECTURE.md, Operations and tiers).
        tier: "TIER_2",
        requested_by: a.operation?.requested_by ?? "AGENT",
        created_day: a.operation?.day ?? 0,
        operation_kind: a.kind ?? "",
        amount_fen: a.operation?.amount_fen ?? null,
        // INTERFACE_CHANGE_REQUEST: the queue has no amount_display; the amount is inside `reason`.
        amount_display: null,
        detail: a.op_id ? `Operation ${a.op_id}` : "",
        decided_day: a.status === "PENDING" ? null : today,
      }) as ApprovalView,
  );
}

export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  const { result } = await http<{ result: OperationResult }>("POST", `/approvals/${encodeURIComponent(id)}`, {
    body: { decision },
  });
  const notOwner = result.violations.some((v) => v.code === "INSUFFICIENT_AUTHORITY");
  if (notOwner || (decision === "APPROVE" && result.status === "REFUSED")) {
    throw new ApiError(403, result.message || "The executor refused this decision.");
  }
  const found = (await getApprovals()).find((a) => a.id === id);
  if (!found) throw new ApiError(404, `Approval ${id} not found.`);
  return found;
}
