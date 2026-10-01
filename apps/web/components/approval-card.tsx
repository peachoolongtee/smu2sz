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

/** One Tier-2 queue row: collapsed it shows subject, amount, tier and reason; expanded, everything the server sent about it. */
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
  /** The executor's message for the decision the owner just made, kept by the page (the queue does not repeat it). */
  resultMessage?: string;
  onDecide: (id: string, decision: ApprovalDecision) => void;
}) {
  const { t, te } = useI18n();
  const [open, setOpen] = useState(false);
  const isPending = a.status === "PENDING";
  const op = a.operation;
  const detailId = `approval-${a.id}-detail`;
  const wantsTerms = op?.kind === "ACCEPT_OFFER" || op?.kind === "RECORD_COMMITMENT";

  const names: { k: string; v: string }[] = [];
  if (op?.facility_id) names.push({ k: t("appr.facility"), v: op.facility_id });
  if (op?.receivable_id) names.push({ k: t("appr.receivable"), v: op.receivable_id });
  if (op?.offer_id) names.push({ k: t("appr.offer"), v: `${op.offer_id} v${op.offer_version ?? "?"}` });
  if (op?.commitment_id) names.push({ k: t("appr.commitment"), v: op.commitment_id });

  return (
    <Card
      id={`approval-${a.id}`}
      tone={isPending ? "warn" : undefined}
      title={a.subject}
      subtitle={`${a.id} · ${te("opkind", a.operation_kind)} · ${te("actor", a.requested_by)} · ${t("appr.created", { day: a.created_day })}`}
      actions={<Badge tone={statusTone[a.status]}>{te("apprstatus", a.status)}</Badge>}
    >
      <div className="flex flex-wrap items-center gap-2">
        <TierBadge tier={a.tier} />
        {a.amount_display ? <span className="text-lg font-semibold tabular-nums">{a.amount_display}</span> : null}
      </div>
      <p className="mt-2 text-sm text-ink-2" data-testid="approval-reason">
        {a.reason || a.detail}
      </p>

      <button
        type="button"
        className="mt-3 inline-flex min-h-8 items-center gap-1 text-sm font-medium text-brand-700 underline underline-offset-2"
        aria-expanded={open}
        aria-controls={detailId}
        onClick={() => setOpen((v) => !v)}
        data-testid={`approval-toggle-${a.id}`}
      >
        <span aria-hidden>{open ? "▾" : "▸"}</span>
        {open ? t("appr.hide") : t("appr.show")}
      </button>

      {open ? (
        <div id={detailId} className="mt-3 space-y-4 border-t border-line pt-3" data-testid={`approval-detail-${a.id}`}>
          <section aria-label={t("appr.what")}>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("appr.what")}</h3>
            <KeyValueList
              items={[
                { k: t("appr.operation"), v: te("opkind", a.operation_kind) || a.operation_kind },
                ...names,
                ...(a.amount_display ? [{ k: t("item.amount"), v: a.amount_display }] : []),
                {
                  k: t("appr.requested"),
                  v: t("appr.requestedValue", { day: a.created_day, who: te("actor", op?.requested_by ?? a.requested_by) }),
                },
                ...(a.op_id ? [{ k: t("appr.opId"), v: <span className="font-mono text-xs">{a.op_id}</span> }] : []),
              ]}
            />
          </section>

          <section aria-label={t("appr.why")}>
            <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("appr.why")}</h3>
            <p className="text-sm">{a.reason}</p>
            <p className="mt-1 text-xs text-ink-2">
              {te("tier", a.tier)} · {te("tier.short", a.tier)}
            </p>
          </section>

          {wantsTerms && op ? (
            <section aria-label={t("appr.terms")}>
              <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("appr.terms")}</h3>
              <Terms op={op} commitment={commitmentFor(op, commitments)} loaded={ledgerLoaded} />
            </section>
          ) : null}
        </div>
      ) : null}

      {isPending ? (
        <div className="mt-4 flex flex-wrap gap-2">
          <Button variant="primary" loading={busyId === `${a.id}:APPROVE`} disabled={busyId !== null} onClick={() => onDecide(a.id, "APPROVE")}>
            {t("appr.approve")}
          </Button>
          <Button variant="secondary" loading={busyId === `${a.id}:REJECT`} disabled={busyId !== null} onClick={() => onDecide(a.id, "REJECT")}>
            {t("appr.reject")}
          </Button>
        </div>
      ) : (
        <p className="mt-3 text-xs text-ink-3">{t("appr.decided", { day: a.decided_day ?? 0 })}</p>
      )}
      {resultMessage ? (
        <p className="mt-2 text-sm font-medium text-ink" role="status" data-testid={`approval-result-${a.id}`}>
          {t("appr.result")}: {resultMessage}
        </p>
      ) : null}
    </Card>
  );
}
