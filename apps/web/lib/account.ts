"use client";

import { useSyncExternalStore } from "react";
import { rememberedAccount } from "./account-flag";
import { useAuth } from "./auth";

const subscribe = (onChange: () => void) => {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};

/**
 * Whether the visitor has an account: signed in in this tab, or signed in (or set up their books) on this browser before. The landing
 * page shows "Access FLOW" for them and "Join FLOW now!" with "Preview" for everyone else. Nothing is asked of the server. Null while
 * rendering on the server (not known yet), so no wrong button flashes.
 */
export function useHasAccount(): boolean | null {
  const { token } = useAuth();
  const remembered = useSyncExternalStore<boolean | null>(subscribe, rememberedAccount, () => null);
  if (remembered === null) return null;
  return Boolean(token) || remembered;
}
