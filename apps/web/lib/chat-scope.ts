"use client";

import { useEffect } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { chosenStore, pageStore, resolveScope, routeOf } from "./chat-scope-model";
import type { ChatScope, ScopeKind } from "./selection";

export { currentScope, toNlScope } from "./chat-scope-model";

/** The chip's state: the kinds on offer, the one in force and the scope it sends; `choose` narrows or widens the question for this route. */
export function useChatScope() {
  const pathname = usePathname();
  const params = useSearchParams();
  // Reading the stores here subscribes the chip to a page's registration and to the owner's choice.
  pageStore.useValue();
  chosenStore.useValue();
  const { choices, chosen } = resolveScope(pathname, params);
  const route = routeOf(pathname, params);
  return {
    kinds: choices.map((c) => c.kind),
    chosen,
    choose: (kind: ScopeKind) => chosenStore.set({ route, kind }),
  };
}

/**
 * A page whose selection is not in its address (Receivables selects its first invoice by default) names it here so Ask FLOW asks about the row the owner sees. Registered for
 * this route only and cleared when the page goes.
 */
export function usePageScope(scope: Omit<ChatScope, "kind"> & { kind?: ScopeKind } | null): void {
  const pathname = usePathname();
  const key = scope ? JSON.stringify(scope) : "";
  useEffect(() => {
    if (!scope) return;
    pageStore.set({ route: pathname, scope: { ...scope, kind: scope.kind ?? (scope.decision ? "decision" : scope.invoice ? "invoice" : "customer") } });
    return () => pageStore.set({ route: "", scope: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` encodes the scope
  }, [pathname, key]);
}
