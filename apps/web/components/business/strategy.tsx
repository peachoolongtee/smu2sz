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
 * What collecting the invoice is worth, as ONE figure: the dictionary word "Saves" beside the server's `net_saving_display`
 * (right-aligned, tabular, never wrapping). When the server says there is no saving (`no_saving`), its own short sentence
 * ("Saves nothing extra now") stands in. The full `worth_text` (the limit and the better rate) is the first line of the row's
 * details (`WorthSentence`). The gross saving stays in the payload; the page decides nothing from it and computes no money.
 */
export function WorthText({ row, testId, align = "left" }: { row: ReceivableWorth; testId: string; align?: "left" | "right" }) {
  const { t } = useI18n();
  return (
    <span className={`block whitespace-nowrap text-sm tabular-nums text-ink ${align === "right" ? "text-right" : ""}`} data-testid={testId}>
      {row.no_saving ? (
        row.worth_text
      ) : (
        <>
          <span className="text-ink-3">{t("biz.strategy.saves")}</span> <span className="font-semibold">{row.net_saving_display}</span>
        </>
      )}
    </span>
  );
}

/** The server's full worth sentence ("Saves ¥86.16 at the 0.85% limit; ¥1,250.06 if they take 0.40%"), shown where the cell is one figure. */
export function WorthSentence({ row, testId }: { row: ReceivableWorth; testId: string }) {
  return (
    <span className="block text-ink" data-testid={testId}>
      {row.worth_text}
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
