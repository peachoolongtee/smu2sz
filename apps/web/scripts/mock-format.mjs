// Mock-authoring tooling ONLY. Not imported by the app.
// A faithful port of the server-side formatters (services/api/app/domain/money.py) so that the mock
// JSON carries the same display strings the real API will. The browser never formats money.

export function fmtYuan(fen) {
  const sign = fen < 0 ? "−" : "";
  const abs = Math.abs(fen);
  const y = Math.floor(abs / 100);
  const f = abs % 100;
  return `${sign}¥${y.toLocaleString("en-US")}.${String(f).padStart(2, "0")}`;
}

/** basis points -> "6.40%" (2 dp, half-up on integers). */
export function fmtPctBp(bp) {
  const sign = bp < 0 ? "-" : "";
  const abs = Math.abs(bp);
  return `${sign}${Math.floor(abs / 100)}.${String(abs % 100).padStart(2, "0")}%`;
}

/** basis points of a ratio -> "1.25×" (12500 -> 1.25x). */
export function fmtRatioBp(bp) {
  return `${Math.floor(bp / 10000)}.${String(Math.round((bp % 10000) / 100)).padStart(2, "0")}×`;
}

/** Exact ratio with `text`, two decimals half-up, mirroring Ratio.text. */
export function ratio(num, den) {
  const n = BigInt(num);
  const d = BigInt(den);
  const scaled = n * 100n;
  let q = scaled / d;
  if (2n * (scaled % d) >= d) q += 1n;
  return { num, den, text: `${q / 100n}.${String(q % 100n).padStart(2, "0")}` };
}

const isNum = (v) => typeof v === "number";

/**
 * Adds `<name>_display` next to every `<name>_fen` / `<name>_bp` number (and `display` next to a bare
 * `fen`), unless a hand-written display already exists. Mirrors the `Displayed<T>` type.
 */
export function annotate(node) {
  if (Array.isArray(node)) return node.map(annotate);
  if (node && typeof node === "object") {
    const out = {};
    for (const [k, v] of Object.entries(node)) out[k] = annotate(v);
    for (const [k, v] of Object.entries(node)) {
      if (!isNum(v) && v !== null) continue;
      let target = null;
      let text = null;
      if (k === "fen") {
        target = "display";
        text = isNum(v) ? fmtYuan(v) : null;
      } else if (k.endsWith("_fen")) {
        target = `${k.slice(0, -4)}_display`;
        text = isNum(v) ? fmtYuan(v) : null;
      } else if (k.endsWith("_bp")) {
        target = `${k.slice(0, -3)}_display`;
        if (isNum(v)) text = /dscr|leverage/.test(k) ? fmtRatioBp(v) : fmtPctBp(v);
      }
      if (target && !(target in node)) out[target] = text;
    }
    return out;
  }
  return node;
}
