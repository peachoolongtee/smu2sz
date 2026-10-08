"use client";

import Link from "next/link";
import { TierBadge } from "@/components/badges";
import { Disclosure } from "@/components/business/kit";
import { Badge, Button, Callout, Card, KeyValueList, type Tone } from "@/components/ui";
import { approveDisabled, termsGate } from "@/lib/approval-terms";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalQuote, ApprovalView } from "@/lib/types";

/** Operations that carry a price. A quote that was never recorded is said for these only; an application or an agreement has no price to miss. */
const PRICED_KINDS = new Set(["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);

const statusTone: Record<ApprovalView["status"], Tone> = { PENDING: "warn", APPROVED: "ok", REJECTED: "bad" };

/**
 * The price the owner was quoted when the request was made, as the server stored it: the legs when there is more than one (with the
 * total), how the rate is billed, and, once decided, what actually happened and how it differs from the quote. A quote that was never
 * stored says so in the server's words. Nothing here is computed: every line is a string from the decision record.
 */
export function QuoteBlock({ id, quote, missing, alwaysLines = false }: { id: string; quote: ApprovalQuote; missing: string | null; alwaysLines?: boolean }) {
  const { t } = useI18n();
  const lines = quote.lines ?? [];
  return (
    <section aria-labelledby={`quote-${id}`} className="mt-4 border-t border-line pt-3" data-testid="approval-quote">
      <h3 id={`quote-${id}`} className="mb-1.5 text-xs font-medium text-ink-3">
        {quote.recorded && quote.quoted_when ? t("appr.quote.when", { when: quote.quoted_when }) : t("appr.quote.title")}
      </h3>
      {missing ? (
        <p className="text-sm text-ink-2" data-testid="approval-quote-missing">
          {missing}
        </p>
      ) : (
        <div className="space-y-2 text-sm">
          {lines.length > 1 || (alwaysLines && lines.length) ? (
            <ul className="space-y-1.5" data-testid="approval-quote-lines">
              {lines.map((l) => (
                <li key={l.op_id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-0.5">
                  <span className="min-w-0 flex-1 basis-56 break-words text-ink">{l.label}</span>
                  <span className="font-semibold tabular-nums text-ink">
                    {l.cost_display ?? l.amount_display}
                    {l.rate_text ? <span className="ml-1 font-normal text-ink-3">{t("biz.costRateOnly", { rate: l.rate_text })}</span> : null}
                  </span>
                </li>
              ))}
              {quote.total_display ? (
                <li className="flex items-baseline justify-between gap-4 border-t border-line pt-1.5 font-semibold text-ink">
                  <span>{t("appr.quote.total")}</span>
                  <span className="tabular-nums">{quote.total_display}</span>
                </li>
              ) : null}
            </ul>
          ) : null}
          {quote.rate_basis ? <p className="text-xs text-ink-2">{quote.rate_basis}</p> : null}
          {quote.cost_note ? <p className="text-xs text-ink-2">{quote.cost_note}</p> : null}
          {quote.lands_when && !lines.length ? <p className="text-xs text-ink-2">{t("appr.quote.lands", { when: quote.lands_when })}</p> : null}
          {quote.actual?.length ? (
            <div data-testid="approval-quote-actual">
              <p className="text-xs font-medium text-ink-3">{t("appr.quote.actual")}</p>
              <ul className="mt-0.5 space-y-0.5">
                {quote.actual.map((x) => (
                  <li key={x.op_id} className="text-ink">
                    <span className="font-semibold tabular-nums">{x.amount_display}</span>{" "}
                    <span className="text-ink-2">{x.settled ? t("verdict.exec.landed") : t("verdict.exec.arriving", { when: x.arrival_when })}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
          {quote.difference_text ? (
            <p className="text-ink" data-testid="approval-quote-difference">
              {quote.difference_text}
            </p>
          ) : null}
        </div>
      )}
    </section>
  );
}

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
  // What the decision run did, in the server's words (the decision record's execution block); the older fields are the fallback.
  const execution = a.execution?.status ?? p?.execution_status ?? a.execution_status;
  const executionText = a.execution?.summary_text ?? null;
  // The queue's presentation says the result in business words (names, distances from today); the raw executor message
  // the page kept from the decision is the fallback until the queue has been read again.
  const shownResult = executionText || p?.result_message || resultMessage || a.result_message || null;
  const op = a.operation;
  const gate = termsGate(a);
  // The owner approved and the executor then refused to run it: the authorization stands, the execution did not, and no money moved.
  const approvedButRefused = a.status === "APPROVED" && execution === "REFUSED";
  const refusedSentence = executionText && approvedButRefused ? executionText : p?.result_message?.startsWith("You approved it") ? p.result_message : null;
  // The price as it was quoted when the request was made. Without a stored quote, the server says so ("The quoted cost was not recorded.").
  const quote = a.quote ?? null;
  const quoted = quote?.recorded ? quote : null;
  const quoteMissing = quote && !quote.recorded && quote.text && PRICED_KINDS.has(a.operation_kind) ? quote.text : null;
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
  if (!p?.cost_display && quoted?.total_display) {
    facts.push({ k: t("biz.cost"), v: <span data-testid="approval-cost">{quoted.total_display}</span> });
  }
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
      {quoted || quoteMissing ? (
        <QuoteBlock id={a.id} quote={quote as ApprovalQuote} missing={quoteMissing} />
      ) : null}
      <dl className="mt-4 space-y-3 border-t border-line pt-3 text-sm">
        <div>
          <dt className="text-xs font-medium text-ink-3">{t("appr.why")}</dt>
          <dd className="text-ink" data-testid="approval-reason">
            {p?.reason || a.reason || a.detail}
          </dd>
        </div>
        {/* The stored quote's after-state and what declining leaves win over today's recomputation: they are what the owner was quoted. */}
        {quoted?.after || p?.protects ? (
          <div>
            <dt className="text-xs font-medium text-ink-3">{t("biz.after")}</dt>
            <dd className="text-ink" data-testid="approval-after">
              {quoted?.after || p?.protects}
            </dd>
          </div>
        ) : null}
        {isPending ? (
          <div>
            <dt className="text-xs font-medium text-ink-3">{t("biz.ifDecline")}</dt>
            <dd className="text-ink-2" data-testid="approval-if-decline">{quoted?.if_declined || p?.if_decline || t("biz.ifDecline.body")}</dd>
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
        <p className="mt-2 text-sm font-medium text-ink" role="status" data-testid={`approval-result-${a.id}`} data-execution={execution ?? ""}>
          {t("appr.result")}: {shownResult}
        </p>
      ) : null}
      {a.decision_id ? (
        <p className="mt-2 text-xs">
          <Link href={`/decisions/${encodeURIComponent(a.decision_id)}`} className="font-medium text-brand-700 underline underline-offset-2" data-testid={`approval-record-${a.id}`}>
            {t("appr.record")}
          </Link>
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
