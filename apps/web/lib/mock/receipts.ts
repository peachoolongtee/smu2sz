/**
 * Mock for the owner's "Record a payment" (POST /operations, RECEIVE_PAYMENT as the owner): the real API's answers recorded by
 * `scripts/record-mocks.mjs --receipts` (mocks/receipts.json) at two points of the story, with the GET /receivables read taken after each.
 *
 *   day0     the opening books: the whole ¥420,000 (full), ¥100,000 (partial), ¥500,000 (refused: more than is open)
 *   settled  day 38 of the main walk: the whole of the financed invoice, so the lender is repaid first
 *
 * Nothing here computes money: an amount the recordings do not hold is answered with a plain error that says so, and after a recorded payment the
 * Receivables read is the one recorded after it (until the books are reset, or the story moves to another point). One payment per point.
 */

import { ApiError } from "../errors";
import type { ReceivablesRead, RecordReceiptRequest, RecordReceiptResult } from "../types";
import type { ReceivablesPoint } from "./home";

const KEY = "tl-mock-receipt";

interface Answer {
  variant: string;
  amount_fen: number;
  answer: { en: RecordReceiptResult; zh: RecordReceiptResult };
  after: { en: ReceivablesRead; zh: ReceivablesRead } | null;
}
type Recordings = Record<string, { receivable_id: string; answers: Answer[] }>;

const clone = <T>(v: unknown): T => JSON.parse(JSON.stringify(v)) as T;

async function recordings(): Promise<Recordings> {
  return (await import("../../mocks/receipts.json")).default as unknown as Recordings;
}

/** The payment recorded on these mock books: the point it was recorded at and which recording. */
function stored(): { point: string; variant: string } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as { point: string; variant: string }) : null;
  } catch {
    return null;
  }
}

export function resetReceipts(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(KEY);
  } catch {
    /* nothing stored */
  }
}

export async function mockRecordReceipt(point: ReceivablesPoint, req: RecordReceiptRequest, lang: "en" | "zh"): Promise<RecordReceiptResult> {
  const at = (await recordings())[point];
  if (!at || at.receivable_id !== req.receivable_id) {
    throw new ApiError(422, "The offline demo has no recorded payment for this invoice at this point of the story.", { code: "MOCK_NOT_RECORDED" });
  }
  const done = stored();
  if (done && done.point === point) {
    throw new ApiError(409, "The offline demo records one payment on these books; reset the demo to record another.", { code: "MOCK_NOT_RECORDED" });
  }
  const found = at.answers.find((a) => a.amount_fen === req.amount_fen);
  if (!found) {
    throw new ApiError(422, "The offline demo has recorded payments for the whole amount, and on the opening books for ¥100,000 and ¥500,000 only.", {
      code: "MOCK_NOT_RECORDED",
    });
  }
  if (found.after && typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(KEY, JSON.stringify({ point, variant: found.variant }));
    } catch {
      /* the answer still stands */
    }
  }
  return clone<RecordReceiptResult>(found.answer[lang]);
}

/** The Receivables read recorded after the payment made at this point, or null when none was made here. */
export async function receivablesAfterReceipt(point: ReceivablesPoint, lang: "en" | "zh"): Promise<ReceivablesRead | null> {
  const done = stored();
  if (!done || done.point !== point) return null;
  const found = (await recordings())[point]?.answers.find((a) => a.variant === done.variant);
  return found?.after ? clone<ReceivablesRead>(found.after[lang]) : null;
}
