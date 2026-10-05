"use client";

import { Badge, type Tone } from "@/components/ui";
import type { AnnotationKind } from "@/lib/annotation-style";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import type { ContractFieldName, DealTone, DocumentSummary } from "@/lib/types";

/** The server's tones for the deal card, on the app's badge tones. */
export const DEAL_TONE: Record<DealTone, Tone> = { ok: "ok", warn: "warn", bad: "bad", info: "info", mute: "neutral" };

/** What a contract term is, for its highlight colour on the review screen. */
export const FIELD_KIND: Record<ContractFieldName, AnnotationKind> = {
  PARTY_SUPPLIER: "TERM_PARTY",
  PARTY_BUYER: "TERM_PARTY",
  CONTRACT_REFERENCE: "TERM_PARTY",
  AMENDMENT: "TERM_PARTY",
  SIGNED_DATE: "TERM_TIME",
  START_DATE: "TERM_TIME",
  END_DATE: "TERM_TIME",
  DURATION: "TERM_TIME",
  INVOICING: "TERM_TIME",
  PAYMENT_TERMS: "TERM_TIME",
  PRICE: "TERM_MONEY",
  SCHEDULED_INVOICE: "TERM_MONEY",
  EARLY_PAYMENT: "TERM_MONEY",
  MILESTONE: "TERM_MONEY",
  RETENTION: "TERM_MONEY",
  LATE_INTEREST: "TERM_MONEY",
  DELIVERABLE: "TERM_DUTY",
  REQUIRED_DOCUMENT: "TERM_DUTY",
};

/** The same for a lender agreement's clauses; a clause the agent may never act on (Tier 3) is marked as a flag. */
export const CLAUSE_KIND: Record<string, AnnotationKind> = {
  principal: "TERM_MONEY",
  rate: "TERM_MONEY",
  fee: "TERM_MONEY",
  advance_rate: "TERM_MONEY",
  tenor: "TERM_TIME",
  lead_time: "TERM_TIME",
  covenant: "TERM_DUTY",
  guarantee: "DOCUMENT_FLAG",
  collateral: "DOCUMENT_FLAG",
  equity: "DOCUMENT_FLAG",
};

/** True when the server has contract reading switched off (403 FEATURE_DISABLED): the card says so instead of an error. */
export function contractsOff(e: Error | undefined): boolean {
  return e instanceof ApiError && e.status === 403 && JSON.stringify(e.detail ?? "").includes("FEATURE_DISABLED");
}

/** A term's clause and its exact words in the document. */
export function ClauseQuote({ clause, quote }: { clause: string | null; quote: string }) {
  const { t } = useI18n();
  return (
    <span className="mt-1 block border-l-2 border-brand-100 pl-2 text-xs font-normal text-ink-3">
      {clause ? <span className="mr-1 font-mono text-[11px] text-brand-700">{t("deal.clause", { n: clause })}</span> : null}“{quote}”
    </span>
  );
}

/** Where a document stands: waiting for the owner (with the AI label), confirmed, rejected, or blocked by a flag. */
export function DocStatusBadge({ doc }: { doc: Pick<DocumentSummary, "status" | "decided_day" | "blocked"> }) {
  const { t, te } = useI18n();
  if (doc.status === "CONFIRMED") {
    return (
      <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
        <Badge tone="ok">{t("docs.confirmedDay", { n: doc.decided_day ?? 0 })}</Badge>
      </span>
    );
  }
  if (doc.status === "REJECTED") {
    return (
      <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
        <Badge>{t("docs.rejectedDay", { n: doc.decided_day ?? 0 })}</Badge>
      </span>
    );
  }
  return (
    <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
      {doc.blocked ? <Badge tone="bad">{t("docs.blocked")}</Badge> : <Badge tone="warn">{te("docstatus", doc.status)}</Badge>}
      <Badge tone="info">{t("docs.aiLabel")}</Badge>
    </span>
  );
}
