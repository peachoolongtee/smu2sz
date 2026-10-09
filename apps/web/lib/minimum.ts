import type { DictKey } from "./dictionary";

/**
 * How far cash is from the owner's minimum, said in words ("¥100k above your minimum", "Lowest point: ¥300k below your minimum"). The figure is
 * the server's string; the browser only chooses "above" or "below" from the sign of the server's own integer and drops the minus sign from the
 * string it shows (no arithmetic on money; INVARIANT 13). An older recording without the integer reads the sign from the string.
 */
export function versusMinimum(short: string, fen: number | undefined, lowest: boolean, reserve = false): { key: DictKey; amount: string } {
  const below = fen !== undefined ? fen < 0 : /^[−-]/.test(short.trim());
  const amount = short.trim().replace(/^[−-]/, "");
  // Under the reserve tile the sentence is about the cash, so it cannot be read as the reserve itself ("Your cash is ¥100k above it").
  if (reserve) return { key: (below ? "biz.cashBelowIt" : "biz.cashAboveIt") as DictKey, amount };
  return { key: (lowest ? (below ? "biz.lowestBelow" : "biz.lowestAbove") : below ? "biz.below" : "biz.above") as DictKey, amount };
}
