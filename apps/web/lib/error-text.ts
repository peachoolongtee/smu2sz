import { ApiError } from "./errors";
import { en, type DictKey } from "./dictionary";
import { tNow } from "./i18n";

type Translate = (key: DictKey, vars?: Record<string, string | number>) => string;

/**
 * What an error says on screen. A failure the client recognised by code is said from the dictionary (`err.<code>`, English and Chinese);
 * anything else keeps its own message (the server's words, or a runtime error's).
 */
export function errorText(e: unknown, t: Translate): string {
  if (e instanceof ApiError && e.code) {
    const key = `err.${e.code}`;
    if (key in en) return t(key as DictKey, e.vars);
  }
  return e instanceof Error ? e.message : String(e);
}

/** The same for code that is not a component (the stores): in the language chosen when the error is read. */
export const errorMessage = (e: unknown): string => errorText(e, tNow);
