import { receiptLines } from "@/components/ui/commitment-receipt-model";
import type { CommitmentReceiptView, PicturePath, VerdictView } from "./types";

/**
 * The commitment receipt for sending a reply (ticket #128). The server's `receipt` on the path is the source. A server that does not send it yet is read as today's words:
 * when the session holds the evaluation this very picture was drawn from (the same verdict id) its three "This will" lines (the agreement it records, the funding it draws, the
 * funding cost) stand as the first lines; every receipt also takes the words the path already carries (what the reply says, who decides, what it costs, what it assumes).
 * Nothing is computed: a line the path has no word for is absent, and the page never invents one.
 */
export function receiptOfPath(path: PicturePath, verdict: VerdictView | null | undefined, pictureVerdictId: string | null | undefined): CommitmentReceiptView {
  if (path.receipt && receiptLines(path.receipt).length) return path.receipt;
  const priced = verdict && pictureVerdictId && verdict.id === pictureVerdictId ? verdict.workspace?.priced_response : null;
  const lines = priced && priced.counter_id === path.key ? (priced.send_scope_lines ?? []) : [];
  return {
    authorizes_text: lines[0] ?? path.reply_text ?? null,
    executes_now_text: lines.length > 1 ? lines.slice(1).join("\n") : null,
    // The cost figure and, on the next line, the server's words for what it is (once, net over twelve months); omitted when the three lines above already say it.
    fees_display: lines.length > 1 ? null : costWithBasis(path),
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
