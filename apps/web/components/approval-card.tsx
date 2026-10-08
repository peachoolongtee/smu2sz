"use client";

import { TierBadge } from "@/components/badges";
import { Disclosure } from "@/components/business/kit";
import { Badge, Button, Callout, Card, KeyValueList, type Tone } from "@/components/ui";
import { approveDisabled, termsGate } from "@/lib/approval-terms";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalView } from "@/lib/types";

const statusTone: Record<ApprovalView["status"], Tone> = { PENDING: "warn", APPROVED: "ok", REJECTED: "bad" };

/**
 * One approval as a question the owner can answer: who with, what they would agree to, how much, what it costs, when the money
 * moves, why it needs them and what happens after. All of that sits above the buttons. A commercial approval whose terms the
 * server could not present cannot be approved (Decline stays). Ids, the tier and the operation id sit under "Audit details".
 */
export function ApprovalCard({
  a,
  busyId,
  resultMessage,
  onDecide,
  onRetry,
}: {
  a: ApprovalView;
  busyId: string | null;
  /** The executor's message for the decision the owner just made, kept by the page (the queue's own `result_message` is shown when this is absent, for example after a reload). */
  resultMessage?: string;
  onDecide: (id: string, decision: ApprovalDecision) => void;
  /** Reads the queue again: the way out of "terms unavailable". */
  onRetry?: () => void;
}) {
  const { t, te } = useI18n();
  const isPending = a.status === "PENDING";
  const p = a.presentation;
  // The queue's presentation says the result in business words (names, distances from today); the raw executor message
  // the page kept from the decision is the fallback until the queue has been read again.
  const shownResult = p?.result_message || resultMessage || a.result_message || null;
  const op = a.operation;
  const gate = termsGate(a);
  const execution = p?.execution_status ?? a.execution_status;
  // The owner approved and the executor then refused to run it: the authorization stands, the execution did not, and no money moved.
  const approvedButRefused = a.status === "APPROVED" && execution === "REFUSED";
  const refusedSentence = p?.result_message?.startsWith("You approved it") ? p.result_message : null;
  const refusedReason = a.result_message || resultMessage || "";

  const names: { k: string; v: React.ReactNode }[] = [];
  if (op?.facility_id) names.push({ k: t("appr.facility"), v: op.facility_id });
  if (op?.receivable_id) names.push({ k: t("appr.receivable"), v: op.receivable_id });
  if (op?.offer_id) names.push({ k: t("appr.offer"), v: `${op.offer_id} v${op.offer_version ?? "?"}` });
  if (op?.commitment_id) names.push({ k: t("appr.commitment"), v: op.commitment_id });
  if (op?.terms_hash) names.push({ k: t("neg.commitment.hash"), v: <span className="break-all font-mono text-xs">{op.terms_hash}</span> });

  const facts: { k: string; v: React.ReactNode }[] = [];
  const buyer = p?.counterparty_name || p?.buyer_name;
  if (gate.commercial && buyer) facts.push({ k: t("appr.buyer"), v: <span data-testid="approval-buyer">{buyer}</span> });
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
  if (gate.commercial && gate.available && (p?.forward_value_display || p?.economic_effect_text)) {
    // The figure when the agreement has one (the server sends null for zero), always with the server's sentence; nothing when it sent neither.
    facts.push({
      k: t("appr.forward"),
      v: (
        <span data-testid="approval-forward">
          {p.forward_value_display}
          {p.economic_effect_text ? <span className={`${p.forward_value_display ? "mt-0.5 block " : ""}font-normal text-ink-2`}>{p.economic_effect_text}</span> : null}
        </span>
      ),
    });
  }
  if (isPending && p?.lands_text) {
    // A waiting row's landing is a forecast, and the server says it as one ("If you approve today, the cash lands in 3 days.").
    facts.push({ k: t("appr.timing"), v: <span className="font-normal" data-testid="approval-lands">{p.lands_text}</span> });
  } else if (p?.lands_day !== null && p?.lands_day !== undefined) {
    facts.push({ k: t("biz.lands"), v: <span data-testid="approval-lands">{p.lands_when ?? t("common.dayN", { n: p.lands_day })}</span> });
  }
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
      {/* The facts in two columns: the label above its value. */}
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm" data-testid={`approval-facts-${a.id}`}>
        {facts.map((f, i) => (
          <div key={i} className="min-w-0">
            <dt className="text-xs font-medium text-ink-3">{f.k}</dt>
            <dd className="break-words font-semibold tabular-nums text-ink">{f.v}</dd>
          </div>
        ))}
      </dl>
      {gate.commercial && (gate.available || isPending) ? (
        <div className="mt-4 border-t border-line pt-3">
          {gate.available ? (
            <section aria-labelledby={`terms-${a.id}`} data-testid="approval-terms">
              <h3 id={`terms-${a.id}`} className="mb-1.5 text-xs font-medium text-ink-3">
                {isPending ? t("appr.agreeTo") : t("appr.agreedTo")}
              </h3>
              {p?.terms?.length ? (
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink marker:text-ink-3">
                  {p.terms.map((term, i) => (
                    <li key={i} className="text-pretty break-words">
                      {term}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-pretty break-words text-sm text-ink">{p?.what_you_agree_to}</p>
              )}
            </section>
          ) : (
            <div id={`terms-${a.id}`} data-testid="approval-terms-unavailable">
              <Callout tone="warn" title={t("appr.terms.unavailable.title")}>
                <p>{t("appr.terms.unavailable.body")}</p>
                {p?.terms_unavailable_reason ? <p className="mt-1 break-words font-medium text-ink">{p.terms_unavailable_reason}</p> : null}
                {onRetry ? (
                  <Button className="mt-2" size="sm" onClick={onRetry} data-testid="approval-terms-retry">
                    {t("appr.terms.retry")}
                  </Button>
                ) : null}
              </Callout>
            </div>
          )}
        </div>
      ) : null}
      <dl className="mt-4 space-y-3 border-t border-line pt-3 text-sm">
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
          <Button
            variant="primary"
            loading={busyId === `${a.id}:APPROVE`}
            disabled={approveDisabled(a, busyId !== null)}
            aria-describedby={gate.commercial && !gate.available ? `terms-${a.id}` : undefined}
            onClick={() => onDecide(a.id, "APPROVE")}
          >
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
      {approvedButRefused ? (
        <div className="mt-3" role="status" data-testid={`approval-refused-${a.id}`}>
          <Callout tone="bad" title={t("appr.refused.title")}>
            <p className="break-words" data-testid={`approval-result-${a.id}`}>
              {refusedSentence ?? t("appr.refused.sentence", { reason: refusedReason.replace(/[.\s]+$/, "") || t("appr.refused.noReason") })}
            </p>
          </Callout>
        </div>
      ) : shownResult ? (
        <p className="mt-2 text-sm font-medium text-ink" role="status" data-testid={`approval-result-${a.id}`}>
          {t("appr.result")}: {shownResult}
        </p>
      ) : null}

      <Disclosure className="mt-3 border-t border-line pt-1" testId={`approval-toggle-${a.id}`} summary={t("biz.auditDetails")}>
        <div className="space-y-4" data-testid={`approval-detail-${a.id}`}>
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
        </div>
      </Disclosure>
    </Card>
  );
}
