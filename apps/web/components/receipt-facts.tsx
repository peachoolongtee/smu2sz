"use client";

import { Badge } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { ReceiptFacts as Facts } from "@/lib/types";

/**
 * The four facts of a part-paid invoice, named, under the server's sentence (which stays): what arrived, how much of the invoice it
 * cleared, the early-payment discount taken, what remains, and whether the early-payment window is still open. Every value is the
 * server's string. Renders nothing unless the server sent the facts.
 */
export function ReceiptFacts({ facts, testId }: { facts: Partial<Facts>; testId?: string }) {
  const { t } = useI18n();
  const { received_display, face_cleared_display, discount_display, remaining_display, window_state } = facts;
  if (!received_display || !face_cleared_display || !discount_display || !remaining_display) return null;
  const rows = [
    { k: t("biz.facts.received"), v: received_display, id: "received" },
    { k: t("biz.facts.cleared"), v: face_cleared_display, id: "cleared" },
    { k: t("biz.facts.discount"), v: discount_display, id: "discount" },
    { k: t("biz.facts.remaining"), v: remaining_display, id: "remaining" },
  ];
  return (
    <div className="mt-2" data-testid={testId}>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-4">
        {rows.map((r) => (
          <div key={r.id} className="min-w-0" data-testid={`${testId ?? "receipt-facts"}-${r.id}`}>
            <dt className="font-medium text-ink-3">{r.k}</dt>
            <dd className="break-words font-semibold tabular-nums text-ink">{r.v}</dd>
          </div>
        ))}
      </dl>
      {window_state ? (
        <p className="mt-1.5">
          <Badge tone={window_state === "ended" ? "warn" : "info"}>{window_state === "ended" ? t("biz.facts.window.ended") : t("biz.facts.window.open")}</Badge>
        </p>
      ) : null}
    </div>
  );
}
