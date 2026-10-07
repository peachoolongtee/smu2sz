/**
 * Ids in a server sentence become the names on the books. An id is replaced only as a whole token, so "BUYER-1" inside
 * an invoice id such as "RI:BUYER-1:2" stays as it is (a plain split/join would turn it into "RI:Foshan Home Retail Co.:2").
 */
export function idsToNames(text: string, named: { id: string; name: string }[]): string {
  let out = text;
  for (const { id, name } of named) {
    if (!id || id === name) continue;
    const esc = id.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`(?<![\\w:-])${esc}(?![\\w:-])`, "g"), name);
  }
  return out;
}
