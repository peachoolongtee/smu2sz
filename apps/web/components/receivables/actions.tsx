"use client";

import { ChasePayment } from "@/components/business/chase-payment";
import { ButtonLink } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { CollectionActionKind, ReceivableRow } from "@/lib/types";

/** The invoice's actions in the server's order: `collection_action.primary` first, then the others. The words are the dictionary's, by the action's kind. */
export function actionsOf(row: ReceivableRow): CollectionActionKind[] {
  const a = row.collection_action;
  return a?.primary ? [a.primary, ...(a.others ?? []).map((o) => o.action)] : [];
}

/**
 * One action as a button at 44 px. View payment terms is a link to the customer; Prepare a reminder and Chase payment open the existing handoff
 * dialog (the server's facts and the request to copy). The invoice's FIRST action is the page's one filled primary; `primary` says whether this
 * instance is that one (on a phone it sits in the strip above the list, on a desktop in the detail, so exactly one is filled on screen).
 * `scope` keeps test ids and dialog ids unique where the same action appears twice.
 */
export function ActionButton({ row, action, primary, scope, customerHref, testId }: { row: ReceivableRow; action: CollectionActionKind; primary: boolean; scope: string; customerHref: string; testId?: string }) {
  const { t } = useI18n();
  const variant = primary ? "primary" : "secondary";
  if (action === "VIEW_TERMS") {
    return (
      <ButtonLink prefetch={false} href={customerHref} variant={variant} className="min-h-11" data-testid={testId}>
        {t("recv3.act.VIEW_TERMS")}
      </ButtonLink>
    );
  }
  return (
    <ChasePayment
      receivableId={row.receivable_id}
      buyer={row.buyer_name ?? ""}
      label={action === "CHASE" ? t("biz.chase.button") : t("recv3.act.PREPARE_REMINDER")}
      variant={variant}
      size="md"
      scope={`${scope}${action}-`}
      className="min-h-11"
    />
  );
}
