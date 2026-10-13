"use client";

import { getHome } from "./api";
import { useAuth } from "./auth";
import { NO_FACTS, type ChatFacts } from "./chat-context";
import { useChatScope } from "./chat-scope";
import { useI18n } from "./i18n";
import { useAsync } from "./use-async";
import { useDecision } from "./use-decision";

/**
 * What the pages hold, for choosing which questions to suggest: the evaluated deal of the scope's decision (its decision record, read from the server: evaluated, and with
 * counters), and from GET /home whether a funding plan is recommended and whether an invoice is overdue. Nothing is computed here, and nothing is read from what this tab did: a
 * read that has not arrived (or failed) leaves a fact false, so the prompts that need it stay hidden rather than failing when asked. `refresh` changes after each turn, because an
 * answer can change the books.
 */
export function useChatFacts(enabled: boolean, refresh: number): ChatFacts {
  const { lang } = useI18n();
  const { token } = useAuth();
  const live = enabled && Boolean(token);
  const { chosen } = useChatScope();
  const record = useDecision(live && chosen.decision ? chosen.decision : null).data;
  const home = useAsync(() => (live ? getHome(lang) : Promise.resolve(null)), [live, lang, refresh]).data;
  if (!live) return NO_FACTS;
  return {
    verdict: Boolean(record?.evaluation),
    counters: Boolean(record?.response?.counters.length),
    plan: Boolean(home?.next_action),
    overdue: Boolean(home?.receivables.past_due.length),
  };
}
