import { receiptLines } from "@/components/ui/commitment-receipt-model";
import type { CommitmentReceiptView, PicturePath, VerdictView } from "./types";

/**
 * The commitment receipt for sending a reply (ticket #128): the server's block on the priced response of the evaluation the review was read from (`workspace.priced_response.receipt`),
 * for the very counter it prices. Any other reply (one the owner picked from the comparison) has no receipt of its own yet, and a server that sends none gives none: the words the
 * path already carries then stand (what the reply says, who decides, what it costs and on what basis, what it assumes). Nothing is computed; a line without a word is absent.
 */
export function receiptOfSend(path: PicturePath, verdict: VerdictView | null | undefined): CommitmentReceiptView {
  const priced = verdict?.workspace?.priced_response;
  if (priced && priced.counter_id === path.key && priced.receipt && receiptLines(priced.receipt).length) return priced.receipt;
  return {
    authorizes_text: path.reply_text ?? null,
    // The cost figure and, on the next line, the server's words for what it is (once, net over twelve months).
    fees_display: costWithBasis(path),
    assumptions_text: path.scenario_assumption_text ?? path.assumption_text ?? null,
    authority_text: path.decides_text || path.authority_text || null,
  };
}

/** A path's cost figure with the server's basis words after a line break (the receipt draws the second line quietly); null when the path has no cost figure. */
function costWithBasis(path: PicturePath): string | null {
  const figure = path.cost_once_display ?? path.cost_total_display ?? null;
  if (!figure) return null;
  const basis = path.cost_basis_text ?? path.cost_note;
  return basis ? `${figure}\n${basis}` : figure;
}
