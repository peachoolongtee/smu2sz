import type { ExposureContext } from "../api";

/** The query of the buyer exposure read: the language, the light read, and the page context (customer, invoice, decision, path, from) that asks for `context.back`. */
export function buyerExposureQuery(lang: "en" | "zh", context: ExposureContext = {}): string {
  const q = new URLSearchParams({ lang, spare: "0" });
  for (const k of ["customer", "invoice", "decision", "path", "from"] as const) if (context[k]) q.set(k, context[k]);
  return q.toString();
}
