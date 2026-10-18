/**
 * The amount an owner types, read as whole fen: "100000", "100,000", "¥100,000.50", "100000.5". Thousands separators must group by threes, at most two
 * decimals; anything else is not an amount (null), and so is zero. This reads input; it never adds, rounds or formats money (INVARIANT 13): the digits
 * are joined as text and the server says what the amount comes to.
 */
export function yuanTextToFen(text: string): number | null {
  const s = text.trim().replace(/^[¥￥]\s*/, "").replace(/，/g, ",");
  const m = /^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?$/.exec(s);
  if (!m) return null;
  const digits = `${m[1].replace(/,/g, "")}${(m[2] ?? "").padEnd(2, "0")}`.replace(/^0+(?=\d)/, "");
  if (digits.length > 15) return null; // beyond any invoice and beyond exact integers
  const fen = Number(digits);
  return Number.isSafeInteger(fen) && fen > 0 ? fen : null;
}
