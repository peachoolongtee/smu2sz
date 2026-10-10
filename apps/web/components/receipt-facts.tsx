"use client";

import { useI18n } from "@/lib/i18n";
import type { ReceiptFacts as Facts } from "@/lib/types";

/**
 * The four facts of a part-paid invoice, named: what arrived, how much of the invoice it cleared, the early-payment discount taken, and what
 * remains (the one to act on, so it is larger). 14 px; every value is the server's string. The window's state is the server's own words
 * (`windowText`, a line of text, not a badge) and is shown only where no sentence beside the facts already says it. Renders nothing unless
 * the server sent the facts.
 */
export function ReceiptFacts({ facts, testId, windowText = null }: { facts: Partial<Facts>; testId?: string; windowText?: string | null }) {
  const { t } = useI18n();
  const { received_display, face_cleared_display, discount_display, remaining_display } = facts;
  if (!received_display || !face_cleared_display || !discount_display || !remaining_display) return null;
  const rows = [
    { k: t("biz.facts.received"), v: received_display, id: "received", key: false },
    { k: t("biz.facts.cleared"), v: face_cleared_display, id: "cleared", key: false },
    { k: t("biz.facts.discount"), v: discount_display, id: "discount", key: false },
    { k: t("biz.facts.remaining"), v: remaining_display, id: "remaining", key: true },
  ];
  return (
    <div className="mt-2" data-testid={testId}>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm sm:grid-cols-4">
        {rows.map((r) => (
          <div key={r.id} className="min-w-0" data-testid={`${testId ?? "receipt-facts"}-${r.id}`}>
            <dt className="font-medium text-ink-3">{r.k}</dt>
            <dd className={`break-words tabular-nums text-ink ${r.key ? "text-base font-bold" : "font-semibold"}`}>{r.v}</dd>
          </div>
        ))}
      </dl>
      {windowText ? (
        <p className="mt-1.5 text-sm text-ink-2" data-testid={`${testId ?? "receipt-facts"}-window`}>
          {windowText}
        </p>
      ) : null}
    </div>
  );
}
