import type { HomeChange } from "./types";

/**
 * The Recent changes that are worth a row. A part-paid invoice is said twice by the server: once by the row that names the four facts
 * (received, cleared, discount, remaining) and once by the plain "still open" LATE row for the same invoice. The server names the
 * repeat with `superseded_by` (the `seq` or `decision_id` of the row that says it better), and the page drops it when that row is on the
 * page. Where the server named only the invoice (`receivable_id`), a LATE row with no facts of its own goes when another LATE row for the
 * same invoice carries them. Ids are compared, never shown; nothing is computed.
 */
export function withoutSuperseded(changes: HomeChange[]): HomeChange[] {
  const keys = (c: HomeChange): string[] => [c.seq !== null && c.seq !== undefined ? String(c.seq) : "", c.decision_id ?? ""].filter(Boolean);
  const factsOf = (c: HomeChange) => c.kind === "LATE" && Boolean(c.remaining_display);
  return changes.filter((c, i) => {
    const by = c.superseded_by;
    if (by !== null && by !== undefined && by !== "") {
      if (changes.some((o, j) => j !== i && keys(o).includes(String(by)))) return false;
    }
    if (c.kind === "LATE" && !factsOf(c) && c.receivable_id) {
      if (changes.some((o, j) => j !== i && factsOf(o) && o.receivable_id === c.receivable_id)) return false;
    }
    return true;
  });
}
