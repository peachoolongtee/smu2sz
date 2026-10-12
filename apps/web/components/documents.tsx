"use client";

import type { ReactNode } from "react";
import { Chip, type Tone } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import type { AnnotationKind } from "@/lib/annotation-style";
import { ApiError } from "@/lib/errors";
import { useI18n, type I18n } from "@/lib/i18n";
import type { ContractFieldName, DocumentStatus, DocumentSummary } from "@/lib/types";
import { whenText } from "@/lib/when";

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

// ------------------------------------------------------------------ the documents page and the deal summary

/** A section title inside a deal: 12 px uppercase, spaced, with room for a pill beside it. */
export function DealHeading({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h3 className={`mb-2 flex flex-wrap items-center gap-2 text-meta font-semibold uppercase tracking-wider text-ink-3 ${className}`}>{children}</h3>;
}

/** A clause label as the contract numbers it: "§4.2" for a numbered clause, "Schedule 1, 1" as written. */
export function ClauseLabel({ clause }: { clause: string }) {
  const { t } = useI18n();
  return <span className="font-mono text-meta text-new">{/^\d/.test(clause) ? t("deal.clause", { n: clause }) : clause}</span>;
}

/** A term's clause and its exact words in the document, under a purple rule. */
export function ClauseQuote({ clause, quote }: { clause: string | null; quote: string }) {
  return (
    <span className="mt-1 block border-l-2 border-new-line pl-2 text-meta font-normal text-ink-3">
      {clause ? (
        <span className="mr-1">
          <ClauseLabel clause={clause} />
        </span>
      ) : null}
      “{quote}”
    </span>
  );
}

/**
 * A "when" in words: the server's string (`*_when`) when it sent one, else the day said as a distance from today. The Business pages never say
 * "Day N"; with neither a server string nor a today to measure from, the sentence is left to say without a when.
 */
export function whenWords(server: string | null | undefined, day: number | null | undefined, today: number | null | undefined, t: I18n["t"]): string {
  if (server) return server;
  if (day === null || day === undefined || today === null || today === undefined) return "";
  return whenText(day, today, t);
}

/** The tone of a status when the server named none: the status word's own (waiting is a warning, confirmed is good, rejected is quiet). */
const STATUS_TONE: Record<DocumentStatus, Tone> = { PROPOSED: "warn", CONFIRMED: "ok", REJECTED: "neutral" };

/** Where a document stands in the server's words and tone: waiting for the owner (with the AI label), confirmed, rejected, or blocked by a flag. */
export function DocStatusBadge({ doc }: { doc: Pick<DocumentSummary, "status" | "blocked" | "status_text"> & Partial<Pick<DocumentSummary, "status_tone">> }) {
  const { t } = useI18n();
  // The server writes the whole sentence ("Confirmed by you 3 days ago", "Waiting for your review"); the page adds nothing to it.
  const text = doc.status_text;
  const tone: Tone = doc.status_tone ?? (doc.status === "PROPOSED" && doc.blocked ? "bad" : STATUS_TONE[doc.status]);
  return (
    <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
      <StateWord tone={tone}>{text}</StateWord>
      {doc.status === "PROPOSED" ? <Chip tone="info">{t("docs.aiLabel")}</Chip> : null}
    </span>
  );
}
