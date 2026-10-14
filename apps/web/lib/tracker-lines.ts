import type { TrackerLine } from "./tracker";

/**
 * Which cost line goes where (the server decides; nothing here is computed). The agreement's own components (the terms, the funding planned at
 * agreement) and the related funding that counts (or counts once approved) are the table and the bar; related funding the server will not count
 * (`counted` false with a `counted_note_text`) is shown apart, outside the deal's cost, with its own figure.
 */
export const isAgreementLine = (l: TrackerLine): boolean => !l.relation || l.relation === "none";
export const isOutside = (l: TrackerLine): boolean => !isAgreementLine(l) && !l.counted && !!l.counted_note_text;
export const tableLines = (lines: TrackerLine[]): TrackerLine[] => lines.filter((l) => !isOutside(l));
export const outsideLines = (lines: TrackerLine[]): TrackerLine[] => lines.filter(isOutside);
/** A line that has a figure in the total: it is a bar segment. */
export const inTotal = (l: TrackerLine): boolean => l.actual_fen !== null && l.actual_fen > 0;
