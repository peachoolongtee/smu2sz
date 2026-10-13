/**
 * The Tier-2 queue. GET /approvals/queue returns raw approval records; the page wants a display row.
 * Decisions are owner actions. Like every live request they carry X-Owner-Token, and the server (not this file)
 * decides whether the caller really is the owner. Only "you are not the owner" is an error. An approval whose run the executor
 * refused is a completed decision: the row comes back APPROVED with the refusal, and the page shows the terminal outcome.
 */

import { ApiError } from "../errors";
import type { CommitmentReceiptView, StateTone, ApprovalLifecycleStage, ApprovalSummaryRow, ApprovalDecision, ApprovalExecutionStatus, ApprovalOperation, ApprovalPresentation, ApprovalQuote, ApprovalStatus, ApprovalView, DecisionState, OperationResult, Tier } from "../types";
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
  /** Business words for the card, written by the API. */
  presentation?: ApprovalPresentation;
  /** The decision record (ADR-0011): its id and state, the stored quote and what the decision run did. All the server's words. */
  decision_id?: string | null;
  decision_state?: DecisionState | null;
  quote?: ApprovalQuote | null;
  execution?: { status: ApprovalExecutionStatus; summary_text: string | null } | null;
  result_state_text?: string | null;
  result_tone?: StateTone | null;
  /** The commitment receipt of a pending approval (the server's words in its order); null for a decided one. */
  receipt?: CommitmentReceiptView | null;
  /** Round two: the exact-authorization words (the button's act, the first sentence, the terms state, the lifecycle, the summary and a real quote's terms). */
  commit_label?: string | null;
  authorize_text?: string | null;
  terms_state_text?: string | null;
  terms_rows?: ApprovalSummaryRow[] | null;
  lifecycle?: ApprovalLifecycleStage[] | null;
  summary_rows?: ApprovalSummaryRow[] | null;
}

export async function getApprovals(): Promise<ApprovalView[]> {
  return (await getApprovalsRead()).approvals;
}

/** The queue and when the books were last read for it (the server's words, absent from an older server). */
export async function getApprovalsRead(): Promise<{ approvals: ApprovalView[]; last_read_when: string | null }> {
  const raw = await http<{ approvals: RawApproval[]; last_read_when?: string | null }>("GET", "/approvals/queue");
  return { approvals: toViews(raw.approvals), last_read_when: raw.last_read_when ?? null };
}

function toViews(approvals: RawApproval[]): ApprovalView[] {
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
        result_message: a.result_message ?? null,
        presentation: a.presentation,
        decision_id: a.decision_id ?? null,
        decision_state: a.decision_state ?? null,
        quote: a.quote ?? null,
        execution: a.execution ?? null,
        result_state_text: a.result_state_text ?? a.presentation?.result_state_text ?? null,
        result_tone: a.result_tone ?? a.presentation?.result_tone ?? null,
        receipt: a.receipt ?? null,
        commit_label: a.commit_label ?? null,
        authorize_text: a.authorize_text ?? null,
        terms_state_text: a.terms_state_text ?? null,
        terms_rows: a.terms_rows ?? null,
        lifecycle: a.lifecycle ?? null,
        summary_rows: a.summary_rows ?? null,
      }) as ApprovalView,
  );
}

/** How the decision run ended, from the executor's result (the queue's `presentation.execution_status` wins once it is read). */
function executionStatusOf(decision: ApprovalDecision, status: OperationResult["status"]): ApprovalExecutionStatus {
  if (status === "REFUSED") return "REFUSED";
  if (status === "DUPLICATE") return "DUPLICATE";
  if (status === "PENDING_APPROVAL") return "PENDING";
  return decision === "REJECT" ? "DECLINED" : "EXECUTED";
}

export async function decideApproval(id: string, decision: ApprovalDecision): Promise<ApprovalView> {
  // A 404 (unknown id) or 409 (already decided) is thrown as an ApiError with that status; the page explains it.
  const { result } = await http<{ result: OperationResult }>("POST", `/approvals/${encodeURIComponent(id)}`, {
    body: { decision },
  });
  if (result.violations.some((v) => v.code === "INSUFFICIENT_AUTHORITY")) {
    throw new ApiError(403, result.message || "Only the owner can decide this.", undefined, result.message ? undefined : "executor_refused");
  }
  // The approval is APPROVED even when the executor then refused to run it (the authorization stands, the execution did not): read the queue again.
  const found = (await getApprovals()).find((a) => a.id === id);
  if (!found) throw new ApiError(404, `Approval ${id} not found.`, undefined, "approval_missing", { id });
  return { ...found, result_message: result.message, execution_status: found.presentation?.execution_status ?? executionStatusOf(decision, result.status) };
}
