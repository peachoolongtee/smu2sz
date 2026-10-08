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

/** The net saving, with the gross beneath it when the discount that earns it makes them differ. */
export function WorthText({ row, testId }: { row: ReceivableWorth; testId: string }) {
  const { t } = useI18n();
  const showGross = row.gross_saving_fen > 0 && row.gross_saving_display !== row.net_saving_display;
  return (
    <span data-testid={testId}>
      <span className="font-semibold tabular-nums text-ink">{row.net_saving_text}</span>
      {showGross ? <span className="block text-xs text-ink-3">{t("biz.strategy.worth.gross", { gross: row.gross_saving_display })}</span> : null}
    </span>
  );
}

/** The server's sentence for the step, wrapping, in plain text. */
export function ActionText({ row, testId }: { row: ReceivableWorth; testId: string }) {
  return (
    <span className="block text-ink-2" data-testid={testId}>
      {row.action_sentence}
    </span>
  );
}
