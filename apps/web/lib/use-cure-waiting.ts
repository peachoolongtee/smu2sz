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
  return Boolean(id && rows.data?.some((a) => a.id === id && a.status === "PENDING"));
}
