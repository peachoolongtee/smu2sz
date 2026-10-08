"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { AnnotationKind } from "@/lib/annotation-style";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import type { ContractFieldName, DealTone, DocumentSummary } from "@/lib/types";

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

// ------------------------------------------------------------------ the brief-03 prototype's look (deal and documents cards)

const PILL: Record<DealTone, string> = {
  ok: "border-ok-line bg-ok-bg text-ok-fg",
  warn: "border-warn-line bg-warn-bg text-warn-fg",
  bad: "border-bad-line bg-bad-bg text-bad-fg",
  info: "border-info-line bg-info-bg text-info-fg",
  mute: "border-line bg-subtle text-ink-3",
};

/** The prototype's pill: 12px semibold on a tinted ground with a border, never wrapped. */
export function Pill({ tone = "mute", children }: { tone?: DealTone; children: ReactNode }) {
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-[9px] py-0.5 text-xs font-semibold ${PILL[tone]}`}>{children}</span>;
}

/** Marks the cards contract ingestion added, in the prototype's purple. */
export function NewTag() {
  const { t } = useI18n();
  return (
    <span className="rounded-full border border-new-line bg-new-bg px-2 py-px text-[11px] font-semibold uppercase tracking-[0.05em] text-new">
      {t("home.new")}
    </span>
  );
}

/** The prototype's header link: brand blue, 13px, no underline until hovered. */
export function CardLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link href={href} className="text-[13px] font-medium text-brand-600 hover:underline">
      {children}
    </Link>
  );
}

/**
 * The prototype's card: a 15px title with the "New" tag, a link or a note on the right, no rule under the header, and the
 * purple outline that marks the new cards. The title is an h2 of its own, so its accessible name is the title alone.
 */
export function ContractCard({ id, title, aside, children }: { id: string; title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="min-w-0 rounded-(--radius-card) border border-new-line bg-surface ring-3 ring-new-bg">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1.5 px-4 pt-3.5">
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 id={`${id}-title`} className="text-[15px] font-semibold text-ink">
            {title}
          </h2>
          <NewTag />
        </div>
        {aside}
      </div>
      <div className="px-4 pb-4 pt-3">{children}</div>
    </section>
  );
}

/** A section title inside a deal: 11px uppercase, spaced, with room for a pill beside it. */
export function DealHeading({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <h4 className={`mb-2 flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.06em] text-ink-3 ${className}`}>{children}</h4>;
}

/** A clause label as the contract numbers it: "§4.2" for a numbered clause, "Schedule 1, 1" as written. */
export function ClauseLabel({ clause }: { clause: string }) {
  const { t } = useI18n();
  return <span className="font-mono text-[11px] text-new">{/^\d/.test(clause) ? t("deal.clause", { n: clause }) : clause}</span>;
}

/** A term's clause and its exact words in the document, under a purple rule. */
export function ClauseQuote({ clause, quote }: { clause: string | null; quote: string }) {
  return (
    <span className="mt-[3px] block border-l-2 border-new-line pl-2 text-xs font-normal text-ink-3">
      {clause ? (
        <span className="mr-1">
          <ClauseLabel clause={clause} />
        </span>
      ) : null}
      “{quote}”
    </span>
  );
}

/** Where a document stands: waiting for the owner (with the AI label), confirmed, rejected, or blocked by a flag. */
export function DocStatusBadge({ doc }: { doc: Pick<DocumentSummary, "status" | "decided_day" | "blocked"> }) {
  const { t, te } = useI18n();
  if (doc.status === "CONFIRMED") {
    return (
      <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
        <Pill tone="ok">{t("docs.confirmedDay", { n: doc.decided_day ?? 0 })}</Pill>
      </span>
    );
  }
  if (doc.status === "REJECTED") {
    return (
      <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
        <Pill>{t("docs.rejectedDay", { n: doc.decided_day ?? 0 })}</Pill>
      </span>
    );
  }
  return (
    <span className="flex flex-wrap gap-1.5" data-testid="doc-status" data-status={doc.status}>
      {doc.blocked ? <Pill tone="bad">{t("docs.blocked")}</Pill> : <Pill tone="warn">{te("docstatus", doc.status)}</Pill>}
      <Pill tone="info">{t("docs.aiLabel")}</Pill>
    </span>
  );
}
