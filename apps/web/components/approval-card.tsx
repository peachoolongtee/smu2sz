"use client";

import Link from "next/link";
import type { HTMLAttributes } from "react";
import { TierBadge } from "@/components/badges";
import { Disclosure } from "@/components/business/kit";
import { CashPicture } from "@/components/business/cash-picture";
import { Badge, Button, Callout, DecisionCard, KeyValueList, textLinkClass, type Tone } from "@/components/ui";
import { ApprovalLifecycle } from "@/components/approval-lifecycle";
import { CommitmentReceipt } from "@/components/ui/commitment-receipt";
import { StateWord } from "@/components/ui/state-word";
import { approveDisabled, termsGate } from "@/lib/approval-terms";
import { useI18n } from "@/lib/i18n";
import type { ApprovalDecision, ApprovalQuote, ApprovalView } from "@/lib/types";

/** Operations that carry a price. A quote that was never recorded is said for these only; an application or an agreement has no price to miss. */
const PRICED_KINDS = new Set(["DRAW_FACILITY", "SUBMIT_INVOICE_FOR_FINANCING"]);

/** What the cash picture needs beyond the approval's two lines: today, the minimum cash reserve (the server's figures) and the server's horizon. */
export interface ApprovalCash {
  day: number;
  floor_fen: number;
  floor_short: string;
  horizon_days: number;
}

const statusTone: Record<ApprovalView["status"], Tone> = { PENDING: "warn", APPROVED: "ok", REJECTED: "bad" };

/**
 * The price the owner was quoted when the request was made, as the server stored it: the legs when there is more than one (with the
 * total), how the rate is billed, and, once decided, what actually happened and how it differs from the quote. A quote that was never
 * stored says so in the server's words. Nothing here is computed: every line is a string from the decision record.
 */
export function QuoteBlock({ id, quote, missing, alwaysLines = false, hideLands = false, bare = false }: { id: string; quote: ApprovalQuote; missing: string | null; alwaysLines?: boolean; hideLands?: boolean; /** Inside a fold that already names it: no rule and no heading of its own. */ bare?: boolean }) {
  const { t } = useI18n();
  const lines = quote.lines ?? [];
  return (
    <section aria-labelledby={bare ? undefined : `quote-${id}`} aria-label={bare ? t("appr.quote.title") : undefined} className={bare ? "mt-2" : "mt-4 border-t border-line pt-3"} data-testid="approval-quote">
      {bare ? null : (
        <h3 id={`quote-${id}`} className="mb-1.5 text-supporting font-medium text-ink-3">
          {quote.recorded && quote.quoted_when ? t("appr.quote.when", { when: quote.quoted_when }) : t("appr.quote.title")}
        </h3>
      )}
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
          {quote.rate_basis ? <p className="text-supporting text-ink-2">{quote.rate_basis}</p> : null}
          {quote.cost_note ? <p className="text-supporting text-ink-2">{quote.cost_note}</p> : null}
          {quote.lands_when && !lines.length && !hideLands ? <p className="text-supporting text-ink-2">{t("appr.quote.lands", { when: quote.lands_when })}</p> : null}
          {quote.actual?.length ? (
            <div data-testid="approval-quote-actual">
              <p className="text-supporting font-medium text-ink-3">{t("appr.quote.actual")}</p>
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
/** A standard card as a section (the approvals that are not the page's decision card). */
function StandardSection({ className = "", ...rest }: HTMLAttributes<HTMLElement>) {
  return <section {...rest} className={`motion-reveal card-standard min-w-0 ${className}`} />;
}

export function ApprovalCard({
  a,
  busyId,
  resultMessage,
  onDecide,
  onRetry,
  cash,
  headlineInPage = false,
  raised = true,
}: {
  a: ApprovalView;
  busyId: string | null;
  /** The executor's message for the decision the owner just made, kept by the page (the queue's own `result_message` is shown when this is absent, for example after a reload). */
  resultMessage?: string;
  onDecide: (id: string, decision: ApprovalDecision) => void;
  /** Reads the queue again: the way out of "terms unavailable". */
  onRetry?: () => void;
  /** The reserve and the day the cash picture is drawn against (from the home read); without it a waiting approval shows no picture. */
  cash?: ApprovalCash | null;
  /** The page's own `h1` is this approval's question (the only one waiting), so the card does not say it again. */
  headlineInPage?: boolean;
  /** The page's one decision card: the first waiting approval is raised, the others are standard cards (a page raises one surface). */
  raised?: boolean;
}) {
  const { t, te } = useI18n();
  const Wrap = raised ? DecisionCard : StandardSection;
  const isPending = a.status === "PENDING";
  const p = a.presentation;
  // What the decision run did, in the server's words (the decision record's execution block); the older fields are the fallback.
  const execution = a.execution?.status ?? p?.execution_status ?? a.execution_status;
  // A waiting row has run nothing, so it has no result to report ("Waiting for your approval. Nothing has run." is the question's, not an answer).
  const executionText = a.execution && a.execution.status !== "PENDING" ? a.execution.summary_text : null;
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
  // The one state word and its tone come from the server; the card never derives a colour from the status.
  const stateText = a.result_state_text ?? p?.result_state_text ?? null;
  const stateTone: Tone = (a.result_tone ?? p?.result_tone ?? "neutral") as Tone;

  // Round two's authorization words, from `presentation` or the row itself; a server that does not send them leaves each out.
  const words = {
    commit: p?.commit_label ?? a.commit_label ?? null,
    authorize: p?.authorize_text ?? a.authorize_text ?? null,
    termsState: p?.terms_state_text ?? a.terms_state_text ?? null,
    lifecycle: p?.lifecycle ?? a.lifecycle ?? [],
    summary: (p?.summary_rows ?? a.summary_rows ?? []).filter((r) => r.value_text),
    terms: (p?.terms_rows ?? a.terms_rows ?? []).filter((r) => r.value_text),
  };
  const names: { k: string; v: React.ReactNode }[] = [];
  if (op?.facility_id) names.push({ k: t("appr.facility"), v: op.facility_id });
  if (op?.receivable_id) names.push({ k: t("appr.receivable"), v: op.receivable_id });
  if (op?.offer_id) names.push({ k: t("appr.offer"), v: `${op.offer_id} v${op.offer_version ?? "?"}` });
  if (op?.commitment_id) names.push({ k: t("appr.commitment"), v: op.commitment_id });
  if (op?.terms_hash) names.push({ k: t("neg.commitment.hash"), v: <span className="break-all font-mono text-meta">{op.terms_hash}</span> });

  // The three the owner decides on (what you get, what it costs, when it lands) are the big ones; the rest are a quieter row under them.
  const priced = isPending && Boolean(p?.cost_display || quoted?.total_display);
  const facts: { k: string; v: React.ReactNode; key?: boolean }[] = [];
  const buyer = p?.counterparty_name || p?.buyer_name;
  if (gate.commercial && buyer) facts.push({ k: t("appr.buyer"), v: <span data-testid="approval-buyer">{buyer}</span> });
  if (a.amount_display) facts.push({ k: priced ? t("biz.appr.get") : t("biz.amount"), v: a.amount_display, key: priced });
  if (!p?.cost_display && quoted?.total_display) {
    facts.push({ k: priced ? t("biz.appr.cost") : t("biz.cost"), v: <span data-testid="approval-cost">{quoted.total_display}</span>, key: priced });
  }
  if (p?.cost_display) {
    facts.push({
      k: priced ? t("biz.appr.cost") : t("biz.cost"),
      key: priced,
      v: (
        <span data-testid="approval-cost">
          {p.cost_display}
          {p.rate_text ? <span className={`font-normal text-ink-3 ${priced ? "block text-supporting" : "ml-1"}`}>{t("biz.costRateOnly", { rate: p.rate_text })}</span> : null}
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
    facts.push({ k: priced ? t("biz.appr.lands") : t("appr.timing"), v: <span className={priced ? "font-sans text-base font-medium leading-snug tracking-normal" : "font-normal"} data-testid="approval-lands">{p.lands_text}</span>, key: priced });
  } else if (p?.lands_day !== null && p?.lands_day !== undefined) {
    facts.push({ k: t("biz.lands"), v: <span data-testid="approval-lands">{p.lands_when ?? t("common.dayN", { n: p.lands_day })}</span> });
  }
  const landsShown = (isPending && Boolean(p?.lands_text)) || (p?.lands_day !== null && p?.lands_day !== undefined);
  if (p?.facility_name) facts.push({ k: t("biz.source"), v: p.facility_name });
  if (p?.invoice) facts.push({ k: t("biz.invoice"), v: p.invoice });

  const keyFacts = facts.filter((f) => f.key);
  const otherFacts = facts.filter((f) => !f.key);
  const factsBlock = facts.length ? (
    <div className="space-y-3" data-testid={`approval-facts-${a.id}`}>
      {keyFacts.length ? (
        <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-3">
          {keyFacts.map((f, i) => (
            <div key={i} className="min-w-0">
              <dt className="text-supporting font-extrabold uppercase tracking-[0.08em] text-ink-3">{f.k}</dt>
              <dd className="mt-0.5 break-words font-display text-xl font-extrabold tabular-nums tracking-[-0.01em] text-ink">{f.v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {otherFacts.length ? (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          {otherFacts.map((f, i) => (
            <div key={i} className="min-w-0">
              <dt className="text-supporting font-medium text-ink-3">{f.k}</dt>
              <dd className="break-words font-semibold tabular-nums text-ink">{f.v}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  ) : null;

  const stateChip = stateText ? <StateWord tone={stateTone} testId={`approval-state-${a.id}`}>{stateText}</StateWord> : <Badge tone={statusTone[a.status]}>{te("apprstatus", a.status)}</Badge>;
  // The statement of what is authorized (`title_text`) while the request waits, what came of it (`decided_text`) once answered; the older question headline is the fallback.
  const headlineText = isPending ? (a.title_text ?? p?.title_text ?? p?.headline ?? a.subject) : (a.decided_text ?? p?.decided_text ?? p?.headline ?? a.subject);
  // The sentence under the question says what the request is; when the Source and Invoice facts say it already, it is not said twice.
  const whatText = p?.facility_name && p?.invoice ? undefined : (p?.what ?? `${a.id} · ${te("opkind", a.operation_kind)}`);

  // The agreement's terms (or why they cannot be shown), the same pending or decided.
  const termsBlock =
    gate.commercial && (gate.available || isPending) ? (
      <div className="border-t border-line pt-3">
        {gate.available ? (
          <section aria-labelledby={`terms-${a.id}`} data-testid="approval-terms">
            <h3 id={`terms-${a.id}`} className="mb-1.5 text-supporting font-extrabold uppercase tracking-[0.08em] text-ink-3">
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
    ) : null;

  // What was quoted, behind its own fold (waiting or decided); a decided row adds the after-state it promised.
  const quoteFold =
    quoted || quoteMissing ? (
      <Disclosure className="border-t border-line pt-1" testId={`approval-quoted-${a.id}`} summary={quoted?.quoted_when ? t("appr.quote.when", { when: quoted.quoted_when }) : t("appr.quote.title")}>
        <QuoteBlock id={a.id} quote={quote as ApprovalQuote} missing={quoteMissing} hideLands={landsShown} bare />
        {!isPending && (quoted?.after || p?.protects) ? (
          <p className="mt-2 text-sm text-ink-2">
            <span className="font-medium text-ink-3">{t("biz.after")}: </span>
            <span data-testid="approval-after">{quoted?.after || p?.protects}</span>
          </p>
        ) : null}
      </Disclosure>
    ) : null;

  const recordLink = a.decision_id ? (
    <p className="text-sm">
      <Link href={`/decisions/${encodeURIComponent(a.decision_id)}`} className={textLinkClass} data-testid={`approval-record-${a.id}`}>
        {t("appr.record")}
      </Link>
    </p>
  ) : null;

  const auditFold = (
    <Disclosure className="border-t border-line pt-1" testId={`approval-toggle-${a.id}`} summary={isPending ? t("deals.review.audit") : t("biz.auditDetails")}>
      <div className="space-y-4" data-testid={`approval-detail-${a.id}`}>
        <section aria-label={t("appr.what")}>
          <h3 className="mb-1.5 text-supporting font-semibold uppercase tracking-wide text-ink-3">{t("appr.what")}</h3>
          <KeyValueList
            items={[
              { k: t("common.id"), v: <span className="font-mono text-supporting">{a.id}</span> },
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
              { k: t("ledger.tier"), v: <span className="inline-flex items-center gap-2"><TierBadge tier={a.tier} /> <span className="text-supporting text-ink-2">{te("tier.short", a.tier)}</span></span> },
              ...(a.op_id ? [{ k: t("appr.opId"), v: <span className="font-mono text-supporting">{a.op_id}</span> }] : []),
            ]}
          />
        </section>
        {a.reason && p?.reason && a.reason !== p.reason ? (
          <section aria-label={t("appr.why")}>
            <h3 className="mb-1.5 text-supporting font-semibold uppercase tracking-wide text-ink-3">{t("biz.executorWords")}</h3>
            <p className="text-sm text-ink-2">{a.reason}</p>
          </section>
        ) : null}
      </div>
    </Disclosure>
  );

  const reasonText = p?.why_text || p?.reason || a.reason || a.detail;
  const afterText = quoted?.after || p?.protects;
  const declineText = quoted?.if_declined || p?.if_decline || t("biz.ifDecline.body");

  if (isPending) {
    // The picture: the cash line if the owner declines and if the owner approves, against the minimum; the server's two sentences are its captions.
    const picture = cash && p?.series_if_declined?.length && p?.series_if_approved?.length ? <ApprovalPicture a={a} cash={cash} after={afterText} decline={declineText} /> : null;
    // Round two, exact authorization: the button names the act, the first sentence says what approving does and does not mean, the lifecycle and a compact summary stand above the button,
    // and everything else (why it needs you, the cash picture, the terms, the receipt) is behind "View application details"; the authority and the audit evidence are folds of their own.
    const commitLabel = words.commit ?? p?.approve_label ?? (a.amount_display ? t("appr.approveAmount", { amount: a.amount_display }) : t("appr.approve"));
    const summary = words.summary.length ? (
      <dl className="divide-y divide-line border-y border-line" aria-label={t("appr.summary")} data-testid={`approval-summary-${a.id}`}>
        {words.summary.map((r, i) => (
          <div key={r.key ?? i} className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]" data-testid={`approval-summary-row-${r.key ?? i}`}>
            <dt className="text-supporting font-bold text-ink-3">{r.label}</dt>
            <dd className="m-0 min-w-0 break-words text-[15px] leading-snug text-ink">{r.value_text}</dd>
          </div>
        ))}
      </dl>
    ) : null;
    const decide = (
      <div className="flex flex-wrap gap-2">
        <Button
          variant="primary"
          loading={busyId === `${a.id}:APPROVE`}
          disabled={approveDisabled(a, busyId !== null)}
          aria-describedby={gate.commercial && !gate.available ? `terms-${a.id}` : undefined}
          onClick={() => onDecide(a.id, "APPROVE")}
          data-testid={`approval-approve-${a.id}`}
        >
          {commitLabel}
        </Button>
        <Button variant="secondary" loading={busyId === `${a.id}:REJECT`} disabled={busyId !== null} onClick={() => onDecide(a.id, "REJECT")} data-testid={`approval-decline-${a.id}`}>
          {t("appr.reject")}
        </Button>
      </div>
    );
    const authorityText = a.receipt?.authority_text ?? null;
    return (
      <Wrap
        id={`approval-${a.id}`}
        aria-labelledby={headlineInPage ? undefined : `approval-${a.id}-title`}
        aria-label={headlineInPage ? headlineText : undefined}
        className="space-y-4 p-5 max-sm:p-4"
        data-testid={`approval-card-${a.id}`}
        data-status={a.status}
      >
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="min-w-0">
            {headlineInPage ? null : (
              <h2 id={`approval-${a.id}-title`} className="text-balance text-lg font-extrabold text-ink" data-testid="approval-headline">
                {headlineText}
              </h2>
            )}
            {whatText ? <p className={`${headlineInPage ? "" : "mt-0.5"} text-pretty text-sm text-ink-2`}>{whatText}</p> : null}
          </div>
          {stateChip}
        </div>

        {words.authorize ? (
          <p className="text-pretty text-[15px] font-semibold leading-snug text-ink" data-testid={`approval-authorize-${a.id}`}>
            {words.authorize}
          </p>
        ) : null}
        {words.termsState ? (
          <p className="border-l-2 border-warn-solid py-0.5 pl-3 text-sm text-ink" data-testid={`approval-terms-state-${a.id}`}>
            {words.termsState}
          </p>
        ) : null}

        <dl className="border-t border-line pt-3">
          <dt className="text-supporting font-bold text-ink-3">{t("appr.why")}</dt>
          <dd className="mt-1 text-pretty text-ink" data-testid="approval-reason">
            {reasonText}
          </dd>
        </dl>

        <ApprovalLifecycle stages={words.lifecycle} id={a.id} />
        {/* A priced request keeps its three facts (what you get, what it costs, when it lands); the summary's six rows follow. */}
        {priced || !summary ? factsBlock : null}
        {summary}
        {/* A real quote's terms are shown while the request waits, not folded (the server's `terms_rows`); a stored quote with no terms of its own stays in the application details. */}
        {words.terms.length && !priced ? (
          <dl className="divide-y divide-line border-y border-line" aria-label={t("appr.quoted.title")} data-testid={`approval-terms-rows-${a.id}`}>
            {words.terms.map((r, i) => (
              <div key={i} className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]">
                <dt className="text-supporting font-bold text-ink-3">{r.label}</dt>
                <dd className="m-0 min-w-0 break-words text-[15px] leading-snug text-ink">{r.value_text}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        {/* An agreement's terms come first at every width, then the one button that names what it does (ticket #128, audit UX03): the summary on screen is the review, and the button asks nothing more. */}
        {termsBlock}
        {decide}

        <Disclosure className="border-t border-line pt-1" testId={`approval-details-${a.id}`} summary={t("appr.details")}>
          <div className="space-y-4 pt-2">
            {picture}
            {picture ? null : (
              // No cash line (an agreement's terms, or an older answer): the two sentences stand on their own.
              <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
                {afterText ? (
                  <div>
                    <dt className="text-supporting font-medium text-ink-3">{t("biz.after")}</dt>
                    <dd className="text-ink" data-testid="approval-after">
                      {afterText}
                    </dd>
                  </div>
                ) : null}
                <div>
                  <dt className="text-supporting font-medium text-ink-3">{t("biz.ifDecline")}</dt>
                  <dd className="text-ink-2" data-testid="approval-if-decline">
                    {declineText}
                  </dd>
                </div>
              </dl>
            )}
            {quoteFold}
            <CommitmentReceipt receipt={a.receipt} id={`approval-${a.id}-receipt`} title={t("receipt.title.approve")} omit={["authority"]} className="pt-1" />
          </div>
        </Disclosure>
        {authorityText || a.tier ? (
          <Disclosure className="border-t border-line pt-1" testId={`approval-authority-${a.id}`} summary={t("appr.authority")}>
            <div className="space-y-2 pt-2 text-sm">
              {authorityText ? <p className="text-pretty text-ink" data-testid={`approval-authority-text-${a.id}`}>{authorityText}</p> : null}
              <p className="inline-flex items-center gap-2">
                <TierBadge tier={a.tier} /> <span className="text-supporting text-ink-2">{te("tier.short", a.tier)}</span>
              </p>
            </div>
          </Disclosure>
        ) : null}
        {auditFold}
        {recordLink ? <div className="-mt-1">{recordLink}</div> : null}
      </Wrap>
    );
  }

  // Decided: an unboxed row on a hairline, the outcome first.
  return (
    <section id={`approval-${a.id}`} aria-labelledby={`approval-${a.id}-title`} className="motion-reveal min-w-0 space-y-3 border-b border-line py-5" data-testid={`approval-card-${a.id}`} data-status={a.status}>
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0">
          <h3 id={`approval-${a.id}-title`} className="text-balance text-base font-extrabold text-ink" data-testid="approval-headline">
            {headlineText}
          </h3>
          {whatText ? <p className="mt-0.5 text-pretty text-sm text-ink-2">{whatText}</p> : null}
        </div>
        {stateChip}
      </div>
      {/* Where the application stands once the owner has authorized it (the server's stages: You authorize done, Lender reviews current, Funding decision next). */}
      <ApprovalLifecycle stages={words.lifecycle} id={a.id} />
      <div className="space-y-1 text-sm" data-testid={`approval-outcome-${a.id}`} data-execution={execution ?? ""}>
        <p className="text-supporting font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("appr.result")}</p>
        {approvedButRefused ? (
          <div role="status" data-testid={`approval-refused-${a.id}`}>
            <p className="break-words text-ink" data-testid={`approval-result-${a.id}`}>
              {refusedSentence ?? t("appr.refused.sentence", { reason: refusedReason.replace(/[.\s]+$/, "") || t("appr.refused.noReason") })}
            </p>
          </div>
        ) : shownResult ? (
          <p className="break-words text-ink" role="status" data-testid={`approval-result-${a.id}`} data-execution={execution ?? ""}>
            {shownResult}
          </p>
        ) : null}
        {p?.residual ? (
          <p className="font-medium text-warn-fg" data-testid={`approval-residual-${a.id}`}>
            {/* The server's full sentence (the lowest point and today's gap apart); an older answer is composed from what it sent. */}
            {p.residual.text ?? t("appr.residual", { amount: p.residual.shortfall_display, when: p.residual.from_when })}
          </p>
        ) : null}
        {p?.next_step_text && p.next_step_href ? (
          <p>
            <Link href={p.next_step_href} className={textLinkClass} data-testid={`approval-next-${a.id}`}>
              {p.next_step_text}
            </Link>
          </p>
        ) : null}
        {/* The day of a decision is shown only when the API recorded it for that decision. */}
        <p className="text-supporting text-ink-3" data-testid={`approval-decided-${a.id}`}>
          {p?.decided_when ? t("appr.decidedWhen", { when: p.decided_when }) : a.decided_day !== null && a.decided_day !== undefined ? t("appr.decidedOn", { day: a.decided_day }) : t("appr.decided")}
        </p>
      </div>
      {factsBlock}
      {termsBlock}
      {quoteFold}
      <dl>
        <dt className="text-supporting font-medium text-ink-3">{t("appr.why")}</dt>
        <dd className="text-sm text-ink" data-testid="approval-reason">
          {reasonText}
        </dd>
      </dl>
      {recordLink}
      {auditFold}
    </section>
  );
}

/**
 * The picture of a waiting funding request: the cash line if the owner declines (the baseline) and if the owner approves, the minimum cash
 * reserve, and each line's lowest point named with the server's short string. Days and fen only place the marks; every word is the server's.
 */
function ApprovalPicture({ a, cash, after, decline }: { a: ApprovalView; cash: ApprovalCash; after: string | null | undefined; decline: string }) {
  const { t } = useI18n();
  const p = a.presentation!;
  const declined = p.series_if_declined ?? [];
  const approved = p.series_if_approved ?? [];
  const ahead = declined.filter((x) => x.day >= cash.day);
  const low = ahead.reduce<(typeof ahead)[number] | null>((m, x) => (m === null || x.closing_fen < m.closing_fen ? x : m), null);
  const breach = ahead.find((x) => x.closing_fen < cash.floor_fen)?.day ?? null;
  const declineLowest = p.lowest_if_declined_short ? t("biz.picture.lowest", { amount: p.lowest_if_declined_short }) : null;
  const approveLowest = p.lowest_if_approved_short ? t("biz.picture.lowest", { amount: p.lowest_if_approved_short }) : null;
  return (
    <CashPicture
      baseline={declined}
      alternative={approved}
      baselineLabel={t("biz.appr.pic.decline")}
      alternativeLabel={t("biz.appr.pic.approve")}
      floorFen={cash.floor_fen}
      floorLabel={t("biz.picture.reserve", { amount: cash.floor_short })}
      markers={{
        today: cash.day,
        breachDay: breach,
        lowestDay: low?.day ?? null,
        lowestLabel: declineLowest,
        lowestIsFloor: low?.closing_fen === cash.floor_fen,
        alternativeLowestLabel: approveLowest,
      }}
      horizonDays={cash.horizon_days}
      axis={p.series_axis}
      chips={false}
      ariaLabel={[t("biz.appr.pic.decline"), decline, t("biz.appr.pic.approve"), after].filter(Boolean).join(" ")}
      testIdPrefix="approval"
      viewLabel={t("biz.appr.pic.view")}
      labelledBy={`approval-${a.id}-picture-title`}
      header={
        <>
          <h3 id={`approval-${a.id}-picture-title`} className="text-supporting font-extrabold uppercase tracking-[0.08em] text-ink-3">
            {t("biz.appr.pic.title")}
          </h3>
          <dl className="mt-1 flex flex-wrap items-baseline gap-x-6 gap-y-1 text-sm">
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-3">{t("biz.appr.pic.decline")}</dt>
              <dd className="font-bold tabular-nums text-bad-fg" data-testid="approval-lowest-decline">
                {declineLowest}
                {p.lowest_if_declined_when ? <span className="ml-1 font-normal text-ink-3">{p.lowest_if_declined_when}</span> : null}
              </dd>
            </div>
            <div className="flex items-baseline gap-2">
              <dt className="text-ink-3">{t("biz.appr.pic.approve")}</dt>
              <dd className="font-bold tabular-nums text-ok-fg" data-testid="approval-lowest-approve">
                {approveLowest}
                {p.lowest_if_approved_when ? <span className="ml-1 font-normal text-ink-3">{p.lowest_if_approved_when}</span> : null}
              </dd>
            </div>
          </dl>
        </>
      }
      captions={
        <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-supporting font-medium text-ink-3">{t("biz.ifDecline")}</dt>
            <dd className="text-ink-2" data-testid="approval-if-decline">
              {decline}
            </dd>
          </div>
          {after ? (
            <div>
              <dt className="text-supporting font-medium text-ink-3">{t("biz.after")}</dt>
              <dd className="text-ink" data-testid="approval-after">
                {after}
              </dd>
            </div>
          ) : null}
        </dl>
      }
    />
  );
}
