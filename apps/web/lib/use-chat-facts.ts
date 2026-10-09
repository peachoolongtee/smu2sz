"use client";

import { getHome } from "./api";
import { useAuth } from "./auth";
import { dealFacts, NO_FACTS, type ChatFacts } from "./chat-context";
import { useDemo } from "./demo-store";
import { useI18n } from "./i18n";
import { useAsync } from "./use-async";

/**
 * What the pages hold, for choosing which questions to suggest: the evaluated deal (the session store, written by Deals), and
 * from GET /home whether a funding plan is recommended and whether an invoice is overdue. Nothing is computed here; a read that
 * has not arrived (or failed) leaves a fact false, so the prompts that need it stay hidden rather than failing when asked.
 * `refresh` changes after each turn, because an answer can change the books.
 */
export function useChatFacts(enabled: boolean, refresh: number): ChatFacts {
  const { lang } = useI18n();
  const { token } = useAuth();
  useDemo(); // a deal evaluated on another page changes the facts
  const live = enabled && Boolean(token);
  const home = useAsync(() => (live ? getHome(lang) : Promise.resolve(null)), [live, lang, refresh]).data;
  if (!live) return NO_FACTS;
  return { ...dealFacts(), plan: Boolean(home?.next_action), overdue: Boolean(home?.receivables.past_due.length) };
}
