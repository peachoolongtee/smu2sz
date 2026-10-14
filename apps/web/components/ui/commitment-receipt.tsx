"use client";

import type { ReactNode } from "react";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { CommitmentReceiptView } from "@/lib/types";
import { receiptLines, type ReceiptLineKey } from "./commitment-receipt-model";

const LABEL: Record<ReceiptLineKey, DictKey> = {
  authorizes: "receipt.authorizes",
  executes_now: "receipt.executesNow",
  others_must_agree: "receipt.othersMustAgree",
  in_hand_vs_future: "receipt.inHandVsFuture",
  gross: "receipt.gross",
  fees: "receipt.fees",
  net: "receipt.net",
  when: "receipt.when",
  assumptions: "receipt.assumptions",
  authority: "receipt.authority",
  remaining: "receipt.remaining",
};

/** The three money lines carry a figure: they read at the body size in the display face, the sentences at 15 px. */
const FIGURE = new Set<ReceiptLineKey>(["gross", "fees", "net"]);

/**
 * The commitment receipt (ticket #128): one component for every action that authorizes or moves money, or sends on the owner's behalf. The server's block, drawn in its order, one
 * row per line it has a value for (a label at 13 px over the server's words at 15 px; a figure in the display face); a line it has no value for is not drawn, and nothing here is
 * composed. It is the terms the commit control follows: put it before the button in the reading order at every width. `children` is for what belongs to the same review (a
 * choice the commit needs, such as the simulated buyer's lean), drawn after the lines.
 */
export function CommitmentReceipt({
  receipt,
  title,
  id,
  testId = "commitment-receipt",
  className = "",
  omit,
  hideTitle = false,
  children,
}: {
  receipt: CommitmentReceiptView | null | undefined;
  title?: string;
  id?: string;
  testId?: string;
  className?: string;
  /** Lines said elsewhere (the send review states three of them above its button): left out here, never reworded. */
  omit?: ReceiptLineKey[];
  /** The title names the region for assistive tools and is not drawn (a fold that already says what it is). */
  hideTitle?: boolean;
  children?: ReactNode;
}) {
  const { t } = useI18n();
  const lines = receiptLines(receipt).filter((l) => !omit?.includes(l.key));
  if (!lines.length && !children) return null;
  const titleId = id ? `${id}-title` : undefined;
  return (
    <section id={id} role="region" aria-labelledby={titleId} aria-label={titleId ? undefined : (title ?? t("receipt.title"))} data-testid={testId} className={`min-w-0 ${className}`}>
      <h3 id={titleId} className={hideTitle ? "sr-only" : "font-display text-base font-extrabold leading-snug text-ink"}>
        {title ?? t("receipt.title")}
      </h3>
      <dl className={`${hideTitle ? "" : "mt-2 "}divide-y divide-line border-y border-line`} data-testid={`${testId}-lines`}>
        {lines.map((l, i) => (
          <div key={l.key} data-testid={`receipt-line-${l.key}`} data-line={i} className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(0,10.5rem)_minmax(0,1fr)]">
            <dt className="text-supporting font-bold text-ink-3">{t(LABEL[l.key])}</dt>
            {FIGURE.has(l.key) ? (
              // A figure, and under it (after a line break) the server's words for what it is: 13 px, never the figure's size.
              <dd className="m-0 min-w-0 break-words">
                <span className="block font-display text-base font-bold tabular-nums text-ink">{l.value.split("\n")[0]}</span>
                {l.value.includes("\n") ? <span className="block whitespace-pre-line text-supporting text-ink-2">{l.value.slice(l.value.indexOf("\n") + 1)}</span> : null}
              </dd>
            ) : (
              <dd className="m-0 min-w-0 whitespace-pre-line break-words text-[15px] leading-snug text-ink">{l.value}</dd>
            )}
          </div>
        ))}
      </dl>
      {children}
    </section>
  );
}
