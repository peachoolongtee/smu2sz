"use client";

import Link from "next/link";
import { useState } from "react";
import { TierBadge } from "@/components/badges";
import { ChevronRightIcon } from "@/components/icons";
import { Badge, Button, Callout, Card, KeyValueList, type Tone } from "@/components/ui";
import { localNames, plainDays, sentenceCase } from "@/lib/business-words";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalOperation, ApprovalView, Commitment, Displayed } from "@/lib/types";

const statusTone: Record<ApprovalView["status"], Tone> = { PENDING: "warn", APPROVED: "ok", REJECTED: "bad" };

/** The commitment an ACCEPT_OFFER or RECORD_COMMITMENT operation names, found in GET /ledger. */
export function commitmentFor(op: ApprovalOperation | null, commitments: Displayed<Commitment>[] | undefined): Displayed<Commitment> | null {
  if (!op || !commitments) return null;
  if (op.kind === "RECORD_COMMITMENT") return commitments.find((c) => c.id === op.commitment_id) ?? null;
  if (op.kind === "ACCEPT_OFFER") {
    return commitments.find((c) => c.terms_hash === op.terms_hash && c.offer_id === op.offer_id && c.nonce === op.nonce) ?? null;
  }
  return null;
}

function Terms({ op, commitment, loaded }: { op: ApprovalOperation; commitment: Displayed<Commitment> | null; loaded: boolean }) {
  const { t, te } = useI18n();
  if (!commitment) {
    return (
      <div data-testid="approval-terms-missing">
        <Callout tone="neutral">
          {loaded ? t("appr.terms.none") : t("appr.terms.loading")}{" "}
          <span className="font-mono text-xs">
            {[op.offer_id ? `${op.offer_id} v${op.offer_version ?? "?"}` : null, op.commitment_id, op.terms_hash?.slice(0, 12)].filter(Boolean).join(" · ")}
          </span>
        </Callout>
      </div>
    );
  }
  return (
    <div data-testid="approval-terms" className="space-y-2">
      <p className="text-xs text-ink-3">
        <span className="font-mono">{commitment.id}</span> · {commitment.counterparty_id} · {t("appr.terms.forward", { v: commitment.forward_value_display })}
      </p>
      <ul className="space-y-2">
        {commitment.obligations.map((o) => {
          const rows: { k: string; v: string }[] = [];
          if (o.rate_bp !== null) rows.push({ k: t("item.rate"), v: o.rate_display ?? t("appr.rateBp", { n: o.rate_bp }) });
          if (o.amount_fen !== null && o.amount_display) rows.push({ k: t("item.amount"), v: o.amount_display });
          if (o.days_delta !== null) rows.push({ k: t("item.terms"), v: t("item.termsValue", { n: `${o.days_delta > 0 ? "+" : ""}${o.days_delta}` }) });
          rows.push({
            k: t("item.base"),
            v: [te("basekind", o.base.kind), o.base.amount_fen !== null ? o.base.amount_display : null, o.base.receivable_id].filter(Boolean).join(" · "),
          });
          rows.push({ k: t("item.effective"), v: o.effective_day !== null ? t("common.dayN", { n: o.effective_day }) : t("common.none") });
          const unformatted = (o.base.amount_fen !== null && !o.base.amount_display) || (o.amount_fen !== null && !o.amount_display);
          return (
            <li key={o.id} className="rounded-md border border-line px-3 py-2" data-testid={`approval-obligation-${o.type}`}>
              <p className="mb-1.5 text-sm font-semibold">{te("obligation", o.type)}</p>
              <KeyValueList items={rows} />
              {unformatted ? <p className="mt-1.5 text-xs text-ink-3">{t("appr.terms.noDisplay")}</p> : null}
              {o.spans.map((s, i) => (
                <blockquote key={i} className="mt-2 border-l-2 border-line-strong pl-2.5 text-xs italic text-ink-2" data-testid="approval-clause">
                  <span className="not-italic font-medium text-ink-3">{t("appr.terms.clause")}: </span>&ldquo;{s.text}&rdquo;
                </blockquote>
              ))}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * One approval as a question the owner can answer: what, how much, what it costs, when the money moves, why it needs them
 * and what happens after. Ids, the tier, the operation id and the terms sit under "Audit details".
 */
export function ApprovalCard({
  a,
  commitments,
  ledgerLoaded,
  busyId,
  today = null,
  resultMessage,
  onDecide,
}: {
  a: ApprovalView;
  commitments: Displayed<Commitment>[] | undefined;
  ledgerLoaded: boolean;
  busyId: string | null;
  /** Today on the books, for reasons that still carry day numbers; null leaves them as written. */
  today?: number | null;
  /** The executor's message for the decision the owner just made, kept by the page (the queue's own `result_message` is shown when this is absent, for example after a reload). */
  resultMessage?: string;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}) {
  const { t, te, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const isPending = a.status === "PENDING";
  const p = a.presentation;
  // The queue's presentation says the result in business words (names, distances from today); the raw executor message
  // the page kept from the decision is the fallback until the queue has been read again.
  const words = (text: string) => sentenceCase(today === null ? text : plainDays(text, today, t));
  const raw = p?.result_message || resultMessage || a.result_message || null;
  const shownResult = raw ? words(raw) : null;
  const op = a.operation;
  const detailId = `approval-${a.id}-detail`;
  const wantsTerms = op?.kind === "ACCEPT_OFFER" || op?.kind === "RECORD_COMMITMENT";

  const names: { k: string; v: string }[] = [];
  if (op?.facility_id) names.push({ k: t("appr.facility"), v: op.facility_id });
  if (op?.receivable_id) names.push({ k: t("appr.receivable"), v: op.receivable_id });
  if (op?.offer_id) names.push({ k: t("appr.offer"), v: `${op.offer_id} v${op.offer_version ?? "?"}` });
  if (op?.commitment_id) names.push({ k: t("appr.commitment"), v: op.commitment_id });

  // The decision in one glance: the amount large, then what it costs and when the money lands. The rest (the source, the
  // invoice, why it needs the owner, what happens after or if declined) waits behind "Why it needs you".
  const more: { k: string; v: React.ReactNode }[] = [];
  if (p?.facility_name) more.push({ k: t("biz.source"), v: localNames(p.facility_name, lang) });
  if (p?.invoice) more.push({ k: t("biz.invoice"), v: p.invoice });

  return (
    <Card
      id={`approval-${a.id}`}
      tone={isPending ? "warn" : undefined}
      title={<span data-testid="approval-headline">{p?.headline ?? a.subject}</span>}
      subtitle={p?.what ? localNames(p.what, lang) : `${a.id} · ${te("opkind", a.operation_kind)}`}
      actions={<Badge tone={statusTone[a.status]}>{te("apprstatus", a.status)}</Badge>}
    >
      {a.amount_display ? <p className="figure text-3xl font-semibold tracking-tight text-ink">{a.amount_display}</p> : null}
      <p className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-sm text-ink-2">
        {p?.cost_display ? (
          <span data-testid="approval-cost">
            {t("biz.cost")} <span className="figure font-semibold text-ink">{p.cost_display}</span>
            {p.rate_text ? <span className="ml-1 text-ink-3">{t("biz.costRateOnly", { rate: p.rate_text })}</span> : null}
          </span>
        ) : null}
        {p?.lands_day !== null && p?.lands_day !== undefined ? (
          <span>
            {t("biz.lands")} <span className="font-semibold text-ink" data-testid="approval-lands">{p.lands_when ?? t("common.dayN", { n: p.lands_day })}</span>
          </span>
        ) : null}
      </p>
      <details className="mt-3" data-testid="approval-why">
        <summary className="flex min-h-10 items-center text-sm font-semibold text-ink-2 hover:text-ink">{t("appr.why")}</summary>
        <div className="space-y-3 pb-1 pt-1 text-sm">
          {more.length ? <KeyValueList items={more} /> : null}
          <dl className="space-y-2">
            <div>
              <dt className="sr-only">{t("appr.why")}</dt>
              <dd className="text-ink" data-testid="approval-reason">
                {words(p?.reason || a.reason || a.detail || "")}
              </dd>
            </div>
            {p?.protects ? (
              <div>
                <dt className="text-xs font-medium text-ink-3">{t("biz.after")}</dt>
                <dd className="text-ink" data-testid="approval-after">
                  {p.protects}
                </dd>
              </div>
            ) : null}
            {isPending ? (
              <div>
                <dt className="text-xs font-medium text-ink-3">{t("biz.ifDecline")}</dt>
                <dd className="text-ink-2" data-testid="approval-if-decline">{p?.if_decline || t("biz.ifDecline.body")}</dd>
              </div>
            ) : null}
          </dl>
        </div>
      </details>

      {isPending ? (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button variant="primary" loading={busyId === `${a.id}:APPROVE`} disabled={busyId !== null} onClick={() => onDecide(a.id, "APPROVE")}>
            {a.amount_display ? t("appr.approveAmount", { amount: a.amount_display }) : t("appr.approve")}
          </Button>
          <Button variant="secondary" loading={busyId === `${a.id}:REJECT`} disabled={busyId !== null} onClick={() => onDecide(a.id, "REJECT")}>
            {t("appr.reject")}
          </Button>
        </div>
      ) : (
        // The day of a decision is shown only when the API recorded it for that decision.
        <p className="mt-3 text-xs text-ink-3" data-testid={`approval-decided-${a.id}`}>
          {p?.decided_when ? t("appr.decidedWhen", { when: p.decided_when }) : a.decided_day !== null && a.decided_day !== undefined ? t("appr.decidedOn", { day: a.decided_day }) : t("appr.decided")}
        </p>
      )}
      {shownResult ? (
        <p className="mt-2 text-sm font-medium text-ink" role="status" data-testid={`approval-result-${a.id}`}>
          {t("appr.result")}: {shownResult}
        </p>
      ) : null}
      {/* A decided capex application leads back to the purchase it belongs to. */}
      {!isPending && a.operation_kind === "APPLY_FOR_FACILITY" ? (
        <Link href="/capex" className="mt-2 inline-flex min-h-8 items-center text-sm font-semibold text-brand-700 hover:text-brand-600" data-testid={`approval-capex-${a.id}`}>
          {t("biz.appr.seeCapex")}
        </Link>
      ) : null}

      <button
        type="button"
        className="mt-3 inline-flex min-h-8 items-center gap-1.5 text-sm font-medium text-brand-700"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((v) => !v)}
        data-testid={`approval-toggle-${a.id}`}
      >
        <ChevronRightIcon className={`transition-transform duration-200 ${open ? "rotate-90" : ""}`} />
        {open ? t("appr.hide") : t("appr.show")}
      </button>

      {open ? (
        <div id={detailId} className="mt-3 space-y-4 border-t border-line pt-3" data-testid={`approval-detail-${a.id}`}>
          <section aria-label={t("appr.what")}>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("appr.what")}</h3>
            <KeyValueList
              items={[
                { k: t("common.id"), v: <span className="font-mono text-xs">{a.id}</span> },
                { k: t("appr.operation"), v: te("opkind", a.operation_kind) || a.operation_kind },
                ...names,
                ...(a.amount_display ? [{ k: t("item.amount"), v: a.amount_display }] : []),
                {
                  k: t("appr.requested"),
                  v: t("appr.requestedValue", { day: a.created_day, who: te("actor", op?.requested_by ?? a.requested_by) }),
                },
                { k: t("ledger.tier"), v: <span className="inline-flex items-center gap-2"><TierBadge tier={a.tier} /> <span className="text-xs text-ink-2">{te("tier.short", a.tier)}</span></span> },
                ...(a.op_id ? [{ k: t("appr.opId"), v: <span className="font-mono text-xs">{a.op_id}</span> }] : []),
              ]}
            />
          </section>
          {a.reason && p?.reason && a.reason !== p.reason ? (
            <section aria-label={t("appr.why")}>
              <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("biz.executorWords")}</h3>
              <p className="text-sm text-ink-2">{a.reason}</p>
            </section>
          ) : null}
          {wantsTerms && op ? (
            <section aria-label={t("appr.terms")}>
              <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("appr.terms")}</h3>
              <Terms op={op} commitment={commitmentFor(op, commitments)} loaded={ledgerLoaded} />
            </section>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}
