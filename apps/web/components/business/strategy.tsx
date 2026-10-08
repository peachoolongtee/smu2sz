"use client";

import { Chip } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceivableWorth } from "@/lib/types";

/**
 * The strategy MVP's two receivable cells (behind STRATEGY_MVP): what collecting the invoice is worth and what to do about it.
 * Every figure and sentence is the server's string from GET /receivables/worth; nothing here parses or formats money. The action
 * word is a neutral pill (never a status colour: it names a step, not how things are going), the sentence beside it is plain text.
 */

/** The action as a small neutral pill, labelled from the dictionary by the server's action code. */
export function ActionChip({ action }: { action: ReceivableWorth["action"] }) {
  const { te } = useI18n();
  return <Chip>{te("biz.strategy.action", action)}</Chip>;
}

/**
 * What collecting the invoice is worth: the server's one string for the row (`worth_text`, "Saves ¥1,374.61"). A server that does not
 * send it yet is read through `net_saving_text`. The gross saving stays in the payload; the page decides nothing from it.
 */
export function WorthText({ row, testId }: { row: ReceivableWorth; testId: string }) {
  return (
    <span className="text-sm text-ink" data-testid={testId}>
      {row.worth_text ?? row.net_saving_text}
    </span>
  );
}

/** The server's sentence for the step, wrapping, with the reason beneath it in a smaller size. Both are plain text. */
export function ActionText({ row, testId }: { row: ReceivableWorth; testId: string }) {
  return (
    <span className="block" data-testid={testId}>
      <span className="block text-ink-2">{row.action_sentence}</span>
      {row.reason_sentence ? (
        <span className="mt-0.5 block text-xs text-ink-2" data-testid={`${testId}-reason`}>
          {row.reason_sentence}
        </span>
      ) : null}
    </span>
  );
}
