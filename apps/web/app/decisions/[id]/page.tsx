"use client";

import Link from "next/link";
import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { QuoteBlock } from "@/components/approval-card";
import { Badge, Button, ButtonLink, Callout, Card, EmptyState, ErrorState, LoadingBlock, PageHeader, textLinkClass, type Tone } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import { OpStatusBadge } from "@/components/badges";
import { ReceiptFacts } from "@/components/receipt-facts";
import { TrackerRecordLink } from "@/components/tracker/record-link"; // Deal tracker
import { useI18n } from "@/lib/i18n";
import type { DecisionView } from "@/lib/types";
import { useDecision } from "@/lib/use-decision";

/** A label above its value; the value is the server's own words. */
function Fact({ label, children, testId, figure = false }: { label: string; children: React.ReactNode; testId?: string; figure?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-meta font-medium text-ink-3">{label}</dt>
      <dd className={`break-words text-sm text-ink ${figure ? "font-semibold tabular-nums" : ""}`} data-testid={testId}>
        {children}
      </dd>
    </div>
  );
}

function RecordBody({ d }: { d: DecisionView }) {
  const { t } = useI18n();
  const sent = d.response?.sent ?? null;
  // A deal opens on its own negotiation in Deals (the record's id is the selection); a funding request opens Approvals.
  const dealHome = d.family === "DEAL" ? `/deals?decision=${encodeURIComponent(d.id)}` : "/approvals";
  // The server chooses the tone of the state; a state that waits for the owner, or leaves something short, is the warning tone, never a calm "done".
  const tone: Tone = d.state_tone ?? (d.residual ? "warn" : "neutral");
  const awaitsOwner = d.authorization?.status === "PENDING";
  return (
    <div className="space-y-6">
      <Card id="record-status" tone={tone === "bad" ? "bad" : tone === "warn" || d.residual || awaitsOwner ? "warn" : undefined}>
        <div className="flex flex-wrap items-center gap-3">
          <span data-testid="record-state" data-state={d.state} data-tone={tone}>
            <StateWord tone={tone}>{d.state_text}</StateWord>
          </span>
          <p className="min-w-0 flex-1 basis-64 text-sm text-ink" data-testid="record-waiting">
            {d.waiting_for.text}
          </p>
        </div>
        {/* Waiting for the owner: the one primary is the question to answer. */}
        {awaitsOwner && d.authorization ? (
          <p className="mt-3">
            <ButtonLink href={`/approvals#approval-${d.authorization.approval_id}`} variant="primary" data-testid="record-review">
              {t("biz.review")}
            </ButtonLink>
          </p>
        ) : null}
        <p className="mt-3 text-sm text-ink-2" data-testid="record-execution">
          {d.execution.summary_text}
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {d.counterparty_name ? <Fact label={t("rec.counterparty")}>{d.counterparty_name}</Fact> : null}
          {d.amount_display ? <Fact label={t("biz.amount")} figure>{d.amount_display}</Fact> : null}
          {d.opened_when ? <Fact label={t("rec.opened")}>{d.opened_when}</Fact> : null}
          {d.updated_when ? <Fact label={t("rec.updated")}>{d.updated_when}</Fact> : null}
        </dl>
        {d.residual || d.remaining_task.links.length ? (
          <div className="mt-4 border-t border-line pt-3" data-testid="record-remaining">
            <p className="text-meta font-medium text-ink-3">{t("rec.remaining")}</p>
            <p className="mt-0.5 text-sm text-ink">{d.residual?.text ?? d.remaining_task.text}</p>
            {d.remaining_task.links.length ? (
              <ul className="mt-2 flex flex-wrap gap-x-2 gap-y-1 text-sm">
                {d.remaining_task.links.map((l) => (
                  <li key={l.href}>
                    <Link href={l.href} className={textLinkClass}>
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </Card>

      {d.interpretation?.terms.length ? (
        <Card flat id="record-terms" title={t("rec.terms")} subtitle={t("rec.terms.sub")}>
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-ink" data-testid="record-terms">
            {d.interpretation.terms.map((x, i) => (
              <li key={i} className="break-words">
                {x}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {d.evaluation ? (
        <Card flat id="record-response" title={t("rec.response")} subtitle={t("rec.evaluated", { when: d.evaluation.evaluated_when })}>
          <p className="text-sm font-semibold text-ink" data-testid="record-action">
            {d.evaluation.business_action_text}
          </p>
          {d.evaluation.clarification ? <Clarification c={d.evaluation.clarification} /> : null}
          {d.response?.counters.length ? (
            <ul className="mt-3 divide-y divide-line text-sm">
              {d.response.counters.map((c) => (
                <li key={c.id} className="flex flex-wrap items-baseline justify-between gap-x-4 py-2">
                  <span className="font-medium text-ink">
                    {c.label_text ?? c.label}
                    {c.id === d.response?.recommended_counter_id ? <Badge tone="brand" className="ml-2">{t("biz.deals.option.recommended")}</Badge> : null}
                  </span>
                  <span className="tabular-nums text-ink-2">
                    {t("biz.deals.estCost")} {c.supplier_cost_display}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <div className="mt-3 border-t border-line pt-3" data-testid="record-sent">
            <p className="text-meta font-medium text-ink-3">{t("rec.sent")}</p>
            {sent === null ? (
              <p className="text-sm text-ink-2">{t("rec.sent.none")}</p>
            ) : sent.recorded ? (
              <div className="text-sm text-ink">
                <p>
                  {sent.chosen_label ? t("rec.sent.chosen", { label: sent.chosen_label_text ?? sent.chosen_label }) : t("rec.sent.unbound")} {t("rec.sent.simulated")}
                </p>
                {sent.economics ? (
                  <p className="mt-0.5 text-meta text-ink-2">
                    {t("biz.deals.netCost")} {sent.economics.net_display}
                    {sent.economics.basis_facility_name ? ` · ${sent.economics.basis_facility_name}` : ""}
                  </p>
                ) : null}
                {sent.funding_blocked ? <p className="mt-0.5 text-meta font-medium text-warn-fg">{sent.funding_blocked}</p> : null}
              </div>
            ) : (
              <p className="text-sm text-ink-2">{sent.text}</p>
            )}
          </div>
        </Card>
      ) : null}

      {d.quote ? (
        <Card flat id="record-quote" title={t("rec.quote")}>
          <div className="-mt-3">
            <QuoteBlock id={d.id} quote={d.quote} missing={d.quote.recorded ? null : d.quote.text} alwaysLines />
          </div>
        </Card>
      ) : null}

      {d.authorization || d.agreement ? (
        <Card flat id="record-standing" title={t("rec.standing")}>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
            {d.authorization ? (
              <>
                <Fact label={t("rec.approval")} testId="record-approval">
                  <Link href={`/approvals#approval-${d.authorization.approval_id}`} className={textLinkClass}>
                    {t(d.authorization.status === "PENDING" ? "rec.approval.pending" : d.authorization.status === "APPROVED" ? "rec.approval.approved" : "rec.approval.rejected")}
                  </Link>
                </Fact>
                {d.authorization.decided_when ? <Fact label={t("rec.decided")}>{d.authorization.decided_when}</Fact> : null}
              </>
            ) : null}
            {d.agreement ? (
              <>
                <Fact label={t("verdict.exec.agreement")} testId="record-agreement">
                  {d.agreement.status_text}
                </Fact>
                {d.agreement.expires_when ? <Fact label={t("deal.expires")}>{d.agreement.expires_when}</Fact> : null}
              </>
            ) : null}
          </dl>
        </Card>
      ) : null}

      {d.operations.length ? (
        <Card flat id="record-operations" title={t("rec.operations")}>
          <ol className="divide-y divide-line" data-testid="record-operations">
            {d.operations.map((o) => (
              <li key={o.op_id} className="flex flex-wrap items-start gap-x-3 gap-y-1 py-2.5 text-sm">
                <span className="min-w-0 flex-1 basis-64 break-words text-ink">{o.event_text ?? o.kind_text ?? o.kind}</span>
                {o.when ? <span className="text-meta text-ink-3">{o.when}</span> : null}
                <OpStatusBadge status={o.status} />
              </li>
            ))}
          </ol>
        </Card>
      ) : null}

      {d.settlement.length ? (
        <Card flat id="record-settlement" title={t("rec.settlement")}>
          <ul className="space-y-1.5 text-sm" data-testid="record-settlement">
            {d.settlement.map((l) => (
              <li key={l.lot_id} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-semibold tabular-nums text-ink">{l.principal_display}</span>
                <span className="text-ink-2">{l.facility_name}</span>
                <span className={`text-meta font-medium ${l.settled ? "text-ok-fg" : "text-ink-3"}`}>{l.settled ? t("deal.cashReceived", { when: l.arrival_when }) : t("deal.cashArrives", { when: l.arrival_when })}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {d.promises.length || d.receipts.length ? (
        <Card flat id="record-payments" title={t("rec.payments")}>
          <ul className="space-y-2 text-sm text-ink" data-testid="record-payments">
            {[...d.promises, ...d.receipts].map((x, i) => (
              <li key={i} className="break-words">
                {x.detail_when ?? x.detail}
                <ReceiptFacts facts={x as Record<string, string>} testId={`record-receipt-facts-${i}`} windowText={(x as { window_state_text?: string | null }).window_state_text} />
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {/* Deal tracker: shown only for a deal whose tracker read is available. */}
      {d.family === "DEAL" ? <TrackerRecordLink id={d.id} /> : null}

      <p className="text-meta text-ink-3">
        <Link href={dealHome} className={textLinkClass}>
          {d.family === "DEAL" ? t("rec.openDeals") : t("rec.openApprovals")}
        </Link>
      </p>
    </div>
  );
}

/**
 * One decision's record (ADR-0011): the state it is in, what it is waiting for, what was asked, what was recommended and sent, the quote, the
 * authorization, the agreement, what ran and what has landed. It is where a record with no page of its own is read (a funding request from
 * Home or Activity). Every sentence and figure is the server's, in the language on screen.
 */
/** Why the offer cannot be decided yet, in the server's words, and the question to send the buyer (copied, never sent from here). */
function Clarification({ c }: { c: NonNullable<DecisionView["evaluation"]>["clarification"] & object }) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);
  return (
    <div className="mt-3 space-y-3" data-testid="record-clarification">
      <Callout tone="warn">{c.text}</Callout>
      {c.ask_buyer_text ? (
        <div className="rounded-tile border border-line bg-surface p-3">
          <p className="text-meta font-medium text-ink-3">{t("rec.clarify.ask")}</p>
          <p className="mt-1 text-sm text-ink" data-testid="record-clarification-ask">
            {c.ask_buyer_text}
          </p>
          <Button
            size="sm"
            className="mt-2"
            onClick={() => {
              void navigator.clipboard?.writeText(c.ask_buyer_text ?? "").then(() => setCopied(true), () => setCopied(false));
            }}
          >
            {copied ? t("rec.clarify.copied") : t("rec.clarify.copy")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default function DecisionPage() {
  const { t } = useI18n();
  const params = useParams<{ id: string }>();
  // The id carries colons, which the address bar encodes; it is decoded once here and encoded again on the request.
  const raw = params.id ?? "";
  const id = (() => {
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  })();
  const record = useDecision(id);
  const router = useRouter();
  // Back goes where the owner came from (Home, Activity, an approval); a record opened on its own has no page behind it and falls back to Activity.
  const back = () => (typeof window !== "undefined" && window.history.length > 1 ? router.back() : router.push("/activity"));
  return (
    <>
      <PageHeader
        title={record.data ? record.data.headline : t("rec.title")}
        subtitle={record.data ? undefined : t("rec.subtitle")}
        actions={
          <Button size="sm" onClick={back} data-testid="record-back">
            {t("rec.back")}
          </Button>
        }
      />
      {record.error ? (
        <ErrorState error={record.error} onRetry={record.reload} />
      ) : record.data === undefined ? (
        <LoadingBlock rows={3} />
      ) : record.data === null ? (
        <EmptyState
          title={t("rec.missing")}
          body={t("rec.missing.body")}
          action={
            <ButtonLink href="/" variant="primary">
              {t("rec.home")}
            </ButtonLink>
          }
        />
      ) : (
        <RecordBody d={record.data} />
      )}
    </>
  );
}
