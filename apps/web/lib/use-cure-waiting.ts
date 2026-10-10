"use client";

import { getApprovals } from "./api";
import { useDemo } from "./demo-store";
import { useAsync } from "./use-async";

/**
 * Whether the cure the story queued is still waiting for the owner. The approval card is where the owner decides, so while this is true the story's
 * controls only open it: a second "Approve" beside the card's would be two controls for one decision. Re-read whenever the session writes.
 */
export function useCureWaiting(): boolean {
  const demo = useDemo();
  const id = demo.cure?.approvalId ?? null;
  const rows = useAsync(() => (id ? getApprovals() : Promise.resolve([])), [id]);
  if (!id) return false;
  // Until the queue has been read the decision is treated as waiting: the owner's step is never offered as a plain "Next" in that instant.
  // (`data` keeps the answer of the read before: an empty one from before the cure was queued must not read as "decided".)
  if (rows.data === undefined || rows.loading) return true;
  return rows.data.some((a) => a.id === id && a.status === "PENDING");
}
