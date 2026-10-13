import type { CommitmentReceiptView } from "@/lib/types";

/** The eleven lines of the commitment receipt, in the order ticket #128 fixes: what it authorizes, what runs now, who else must agree, money in hand against future, gross, fees or concession, net, when, the assumptions, whose authority, what stays open. */
export const RECEIPT_LINES = [
  { key: "authorizes", field: "authorizes_text" },
  { key: "executes_now", field: "executes_now_text" },
  { key: "others_must_agree", field: "others_must_agree_text" },
  { key: "in_hand_vs_future", field: "in_hand_vs_future_text" },
  { key: "gross", field: "gross_display" },
  { key: "fees", field: "fees_display" },
  { key: "net", field: "net_display" },
  { key: "when", field: "when_text" },
  { key: "assumptions", field: "assumptions_text" },
  { key: "authority", field: "authority_text" },
  { key: "remaining", field: "remaining_text" },
] as const satisfies readonly { key: string; field: keyof CommitmentReceiptView }[];

export type ReceiptLineKey = (typeof RECEIPT_LINES)[number]["key"];

/** The lines the server has a value for, in order: a null, absent or blank line is omitted, never filled in. */
export function receiptLines(receipt: CommitmentReceiptView | null | undefined): { key: ReceiptLineKey; value: string }[] {
  if (!receipt) return [];
  const out: { key: ReceiptLineKey; value: string }[] = [];
  for (const l of RECEIPT_LINES) {
    const v = receipt[l.field];
    if (typeof v === "string" && v.trim()) out.push({ key: l.key, value: v });
  }
  return out;
}
