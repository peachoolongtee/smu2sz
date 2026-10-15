/**
 * "This browser's owner has signed up": they opened their own books through Set up your books. Kept in localStorage, written when the
 * setup opens the books, read by the landing page when the server cannot be asked (nobody signed in in this tab). Every storage access
 * is in a try/catch: a blocked store means the visitor is treated as new.
 */
const KEY = "tl-flow-signed-up";

export function rememberSignedUp(): void {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    /* storage unavailable: nothing to remember */
  }
}

export function rememberedSignedUp(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
