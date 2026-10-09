/**
 * The cash price sentence (the server's words, GET /cash/price-curve) as a first line and the rest: the page shows the first clause on one
 * line and keeps the continuation under a Disclosure. The cut is at the sentence's own first break outside any bracket (";", a comma
 * followed by a space, or their Chinese forms); a comma inside a figure ("¥10,000") has no space after it, so it never cuts. Nothing is
 * added, reworded or computed: `first + sep + rest` is the server's sentence. A sentence with no break is all `first`.
 */
export function splitSentence(sentence: string): { first: string; rest: string } {
  let depth = 0;
  for (let i = 0; i < sentence.length; i++) {
    const ch = sentence[i];
    if (ch === "(" || ch === "（") depth++;
    else if (ch === ")" || ch === "）") depth = Math.max(0, depth - 1);
    else if (depth === 0 && (ch === ";" || ch === "；" || ch === "，" || (ch === "," && sentence[i + 1] === " "))) {
      const first = sentence.slice(0, i).trim();
      const rest = sentence.slice(i + 1).trim();
      // A cut that leaves nothing on either side, or a stub of a first line, is not a cut.
      if (first.length >= 12 && rest.length > 0) return { first, rest };
    }
  }
  return { first: sentence, rest: "" };
}
