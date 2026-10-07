"use client";

import { useState } from "react";
import { TierBadge } from "@/components/badges";
import { Badge, Button, Callout, Card, KeyValueList, type Tone } from "@/components/ui";
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
            <li key={o.id} className="rounded-tile border border-line px-3 py-2" data-testid={`approval-obligation-${o.type}`}>
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
  resultMessage,
  onDecide,
}: {
  a: ApprovalView;
  commitments: Displayed<Commitment>[] | undefined;
  ledgerLoaded: boolean;
  busyId: string | null;
  /** The executor's message for the decision the owner just made, kept by the page (the queue's own `result_message` is shown when this is absent, for example after a reload). */
  resultMessage?: string;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}) {
  const { t, te } = useI18n();
  const [open, setOpen] = useState(false);
  const isPending = a.status === "PENDING";
  const p = a.presentation;
  // The queue's presentation says the result in business words (names, distances from today); the raw executor message
  // the page kept from the decision is the fallback until the queue has been read again.
  const shownResult = p?.result_message || resultMessage || a.result_message || null;
  const op = a.operation;
  const detailId = `approval-${a.id}-detail`;
  const wantsTerms = op?.kind === "ACCEPT_OFFER" || op?.kind === "RECORD_COMMITMENT";

  const names: { k: string; v: string }[] = [];
  if (op?.facility_id) names.push({ k: t("appr.facility"), v: op.facility_id });
  if (op?.receivable_id) names.push({ k: t("appr.receivable"), v: op.receivable_id });
  if (op?.offer_id) names.push({ k: t("appr.offer"), v: `${op.offer_id} v${op.offer_version ?? "?"}` });
  if (op?.commitment_id) names.push({ k: t("appr.commitment"), v: op.commitment_id });

  const facts: { k: string; v: React.ReactNode }[] = [];
  if (a.amount_display) facts.push({ k: t("biz.amount"), v: a.amount_display });
  if (p?.cost_display) {
    facts.push({
      k: t("biz.cost"),
      v: (
        <span data-testid="approval-cost">
          {p.cost_display}
          {p.rate_text ? <span className="ml-1 font-normal text-ink-3">{t("biz.costRateOnly", { rate: p.rate_text })}</span> : null}
        </span>
      ),
    });
  }
  if (p?.lands_day !== null && p?.lands_day !== undefined) facts.push({ k: t("biz.lands"), v: <span data-testid="approval-lands">{p.lands_when ?? t("common.dayN", { n: p.lands_day })}</span> });
  if (p?.facility_name) facts.push({ k: t("biz.source"), v: p.facility_name });
  if (p?.invoice) facts.push({ k: t("biz.invoice"), v: p.invoice });

  return (
    <Card
      id={`approval-${a.id}`}
      tone={isPending ? "warn" : undefined}
      title={<span data-testid="approval-headline">{p?.headline ?? a.subject}</span>}
      subtitle={p?.what ?? `${a.id} · ${te("opkind", a.operation_kind)}`}
      actions={<Badge tone={statusTone[a.status]}>{te("apprstatus", a.status)}</Badge>}
    >
      <KeyValueList items={facts} />
      <dl className="mt-3 space-y-2 text-sm">
        <div>
          <dt className="text-xs font-medium text-ink-3">{t("appr.why")}</dt>
          <dd className="text-ink" data-testid="approval-reason">
            {p?.reason || a.reason || a.detail}
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

      {isPending ? (
        <div className="mt-4 flex flex-wrap gap-2">
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

      <Button
        variant="ghost"
        size="sm"
        className="mt-3 -ml-3"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((v) => !v)}
        data-testid={`approval-toggle-${a.id}`}
      >
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        {open ? t("appr.hide") : t("appr.show")}
      </Button>

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
                  // The request day as the server says it from today ("today", "3 days ago"); an older recording keeps the day number.
                  v: p?.created_when
                    ? t("appr.requestedWhen", { when: p.created_when, who: te("actor", op?.requested_by ?? a.requested_by) })
                    : t("appr.requestedValue", { day: a.created_day, who: te("actor", op?.requested_by ?? a.requested_by) }),
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
