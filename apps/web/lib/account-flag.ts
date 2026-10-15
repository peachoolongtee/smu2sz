/**
 * "This browser's owner has an account": they signed in here, or opened their own books through Set up your books. Kept in localStorage
 * (the owner token itself stays in sessionStorage only), read by the landing page for a visitor who is not signed in in this tab. Every
 * storage access is in a try/catch: a blocked store means the visitor is treated as new.
 */
const KEY = "tl-flow-account";

export function rememberAccount(): void {
  try {
    window.localStorage.setItem(KEY, "1");
  } catch {
    /* storage unavailable: nothing to remember */
  }
}

export function rememberedAccount(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}
