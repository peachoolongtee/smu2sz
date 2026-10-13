import type { CustomerOverviewView, OfferPictureView } from "./types";

/**
 * The server's "no value" in the words it sends today. A term or a figure with nothing to say reaches the page as the literal string "None" (Python's `str(None)`); the server
 * branch for the slice-b fixes sends null instead. Until that branch is merged this one adapter turns the literal into null, so a null word omits its line on every page.
 * REMOVE this shim (and the two wrappers in api.ts that call it) once the server sends null: nothing else on the web reads the string.
 */
export function noWord(s: string | null | undefined): string | null {
  if (s === null || s === undefined) return null;
  const v = s.trim();
  return v === "" || v === "None" ? null : s;
}

/** The offer's picture with every path term whose value is the literal "None" read as no value. */
export function readPicture<T extends OfferPictureView | null | undefined>(picture: T): T {
  if (!picture?.paths) return picture;
  return { ...picture, paths: picture.paths.map((p) => ({ ...p, terms: (p.terms ?? []).map((x) => ({ ...x, value_text: noWord(x.value_text) })) })) } as T;
}

/** The customer overview with every figure whose value is the literal "None" read as no value. */
export function readOverview<T extends CustomerOverviewView>(view: T): T {
  if (!view?.figures) return view;
  return { ...view, figures: view.figures.map((f) => ({ ...f, value_display: noWord(f.value_display) })) } as T;
}
