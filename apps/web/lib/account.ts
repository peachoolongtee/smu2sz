"use client";

import { useSyncExternalStore } from "react";
import { getSetupStatus } from "./api";
import { rememberedSignedUp } from "./account-flag";
import { useAuth } from "./auth";
import { useI18n } from "./i18n";
import { useAsync } from "./use-async";

const subscribe = (onChange: () => void) => {
  window.addEventListener("storage", onChange);
  return () => window.removeEventListener("storage", onChange);
};

/**
 * Whether the visitor has signed up: their own books are open. When this tab is signed in the server says so (`GET /setup/status`);
 * otherwise the server is not asked at all (an unsigned read would be a refused credential, which the server records as a security
 * event) and this browser's memory of the setup opening the books decides. The landing page shows "Access FLOW" for a signed-up visitor
 * and "Join FLOW now!" for everyone else. Null while rendering on the server (not known yet), so no wrong button flashes. Call it once
 * per page and pass the answer down: each call is its own read.
 */
export function useSignedUp(): boolean | null {
  const { lang } = useI18n();
  const { token } = useAuth();
  const status = useAsync(() => (token ? getSetupStatus(lang).catch(() => null) : Promise.resolve(null)), [token, lang]);
  const remembered = useSyncExternalStore<boolean | null>(subscribe, rememberedSignedUp, () => null);
  if (remembered === null) return null;
  if (status.data) return status.data.books === "own";
  return remembered;
}
