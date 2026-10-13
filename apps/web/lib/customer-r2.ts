import type { CustomerOverviewView, ExposureComparison, FlowStep, OverviewTone, ReceivableFlow } from "./types";

/**
 * The customer overview's round-two reads as the page draws them: the receivable-to-cash flow (the server sends a list of steps, each with `amount_display` and `note`, or an object holding them)
 * and the exposure comparison (a row is its cells in the columns' order, or the server's `<column key>_text` fields). Nothing here is a word: it names the same fields one way.
 */
export function flowOf(view: Pick<CustomerOverviewView, "receivable_flow">): ReceivableFlow | null {
  const raw = view.receivable_flow;
  if (!raw) return null;
  const flow: ReceivableFlow = Array.isArray(raw) ? { steps: raw } : raw;
  const steps: FlowStep[] = (flow.steps ?? []).map((s) => ({ ...s, value_display: s.value_display ?? s.amount_display ?? null, text: s.text ?? s.note ?? null }));
  return steps.length ? { ...flow, steps } : null;
}

export interface ComparisonRow {
  key: string;
  label: string;
  cells: { text: string | null; tone: OverviewTone }[];
}

/** The comparison's rows with one cell per column; a cell the server has no word for is null (drawn as a dash). */
export function comparisonRows(c: ExposureComparison): ComparisonRow[] {
  return c.rows.map((r, i) => ({
    key: r.key ?? String(i),
    label: r.label,
    cells: c.columns.map((col, n) => {
      const cell = r.cells?.[n] ?? (r[`${col.key}_text` as `${string}_text`] as string | null | undefined) ?? null;
      return typeof cell === "object" && cell !== null ? { text: cell.text, tone: cell.tone ?? "neutral" } : { text: cell, tone: "neutral" };
    }),
  }));
}
