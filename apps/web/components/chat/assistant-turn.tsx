"use client";

import Link from "next/link";
import { AnnualisedCompact, offerLegs } from "@/components/annualised";
import { AutonomyPanel } from "@/components/autonomy-panel";
import { CodeBadge, OutcomeBadge, TierBadge, outcomeHasTier } from "@/components/badges";
import { OperationResultBox } from "@/components/operation-result";
import { Disclosure } from "@/components/business/kit";
import { Badge, Button, Chip, Hash, type Tone } from "@/components/ui";
import { confirmWord } from "@/lib/confirm-word";
import { useBusinessShell } from "@/lib/use-business-today";
import { useI18n } from "@/lib/i18n";
import type { DictKey } from "@/lib/dictionary";
import type { NlOperation, NlPlanStatus, NlPlanStep, NlResponse, NlVerdict } from "@/lib/types";

const PLAN_TONE: Record<NlPlanStatus, Tone> = {
  PROPOSED: "info",
  EXECUTED: "ok",
  REFUSED: "bad",
  PENDING_APPROVAL: "warn",
  DUPLICATE: "neutral",
  SKIPPED: "neutral",
  DONE: "ok",
  INFO: "neutral",
};

/** A glyph beside the label, so status never relies on colour alone. */
const PLAN_GLYPH: Record<NlPlanStatus, string> = {
  PROPOSED: "○",
  EXECUTED: "✓",
  REFUSED: "✕",
  PENDING_APPROVAL: "…",
  DUPLICATE: "=",
  SKIPPED: "–",
  DONE: "✓",
  INFO: "i",
};

const LONG = 160;

/** Verification steps repeat the whole verdict sentence; show the start and let the reader expand it. */
function StepText({ text }: { text: string }) {
  const { t } = useI18n();
  if (text.length <= LONG) return <span className="break-words">{text}</span>;
  return (
    <Disclosure className="min-w-0" summary={<span className="break-words">{text.slice(0, LONG)}…<span className="sr-only"> {t("chat.plan.more")}</span></span>}>
      <span className="mt-1 block whitespace-pre-wrap break-words text-ink-2">{text}</span>
    </Disclosure>
  );
}

function PlanList({ plan }: { plan: NlPlanStep[] }) {
  const { t, te } = useI18n();
  return (
    <section aria-label={t("chat.plan")} data-testid="chat-plan">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("chat.plan")}</h3>
      <ol className="space-y-1.5">
        {plan.map((s) => (
          <li key={s.step} className="flex items-start gap-2 text-sm" data-testid={`plan-step-${s.step}`} data-status={s.status}>
            <Badge tone={PLAN_TONE[s.status]} className="mt-0.5 shrink-0">
              <span aria-hidden>{PLAN_GLYPH[s.status]}</span>
              {t(`chat.plan.status.${s.status}` as DictKey)}
            </Badge>
            <div className="min-w-0">
              <span className="mr-1.5 text-xs font-medium text-ink-3">{te("opkind", s.kind) || s.kind}</span>
              <StepText text={s.description} />
              {s.condition ? <p className="text-xs text-ink-3">{t("chat.plan.condition", { c: s.condition })}</p> : null}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function VerdictBlock({ verdict }: { verdict: NlVerdict }) {
  const { t, te } = useI18n();
  const bad = verdict.outcome === "REJECT";
  return (
    <section aria-label={t("chat.verdict")} data-testid="chat-verdict" className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <span data-testid="chat-outcome">
          <OutcomeBadge outcome={verdict.outcome} />
        </span>
        {verdict.required_tier && verdict.required_tier !== "TIER_1" && outcomeHasTier(verdict.outcome) ? <TierBadge tier={verdict.required_tier} /> : null}
        {verdict.violations.map((v) => (
          <span key={v.code} data-testid={`chat-code-${v.code}`}>
            <CodeBadge code={v.code} tone={bad ? "bad" : "warn"} />
          </span>
        ))}
      </div>
      {verdict.violations.length ? (
        <Disclosure className="text-sm" summary={t("chat.verdict.why")}>
          <ul className="mt-1.5 space-y-2">
            {verdict.violations.map((v) => (
              <li key={v.code} className="rounded-tile border border-line bg-subtle px-2.5 py-2">
                <p className="font-mono text-xs font-semibold text-ink">{v.code}</p>
                <p className="mt-0.5 break-words text-ink-2">{v.message}</p>
                {v.observed || v.limit ? (
                  <p className="mt-0.5 text-xs text-ink-3">
                    {v.observed ? `${t("chat.verdict.observed")}: ${v.observed}` : null}
                    {v.observed && v.limit ? " · " : null}
                    {v.limit ? `${t("chat.verdict.limit")}: ${v.limit}` : null}
                  </p>
                ) : null}
                {v.curable && v.cure_cost_display ? (
                  <p className="mt-0.5 text-xs text-ok-fg">{t("chat.verdict.curable", { cost: v.cure_cost_display })}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </Disclosure>
      ) : (
        <p className="text-xs text-ink-3">{te("outcome", verdict.outcome)}</p>
      )}
    </section>
  );
}

/**
 * What the executor's operation is in audit terms: its own sentence, the operation id, the tier, the sequence and the
 * hash. Business pages keep these behind "Audit details" (the same disclosure as Activity); the Demo views show them in the row.
 */
function OperationAudit({ o }: { o: NlOperation }) {
  const { t, te } = useI18n();
  return (
    <Disclosure className="mt-1" testId="op-audit" summary={t("biz.auditDetails")}>
      <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
        <dt>{t("audit.executor")}</dt>
        <dd className="break-words" data-testid="op-raw">{o.message_when || o.message}</dd>
        <dt>{t("audit.opId")}</dt>
        <dd className="break-all font-mono">{te("opkind", o.kind) || o.kind} · {o.op_id}</dd>
        <dt>{t("ledger.seq")}</dt>
        <dd className="tabular-nums">{o.seq ?? t("common.none")}</dd>
        <dt>{t("ledger.tier")}</dt>
        <dd>
          <TierBadge tier={o.tier} />
        </dd>
        <dt>{t("ledger.hash")}</dt>
        <dd>
          <Hash value={o.entry_hash} />
        </dd>
      </dl>
    </Disclosure>
  );
}

/**
 * The operations an action ran. In `business` mode each row is the business sentence (`event_text`, else the
 * `message_when` twin, else the executor's sentence) and the status pill; the tier, sequence, operation id and hash
 * move behind "Audit details". The Demo views and the chat keep the full row.
 */
export function OperationList({ operations, business = false }: { operations: NlOperation[]; business?: boolean }) {
  const { t, te } = useI18n();
  return (
    <section aria-label={t("chat.ops")} data-testid="chat-ops">
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink-3">{t("chat.ops")}</h3>
      <ul className="space-y-2">
        {operations.map((o) => (
          <li key={`${o.op_id}-${o.seq ?? ""}-${o.status}`}>
            {business ? (
              <OperationResultBox status={o.status} message="" approvalId={o.approval_id} testId={`chat-op-${o.kind}`} kind={o.kind} details={<OperationAudit o={o} />} showId={false}>
                {/* A request that waits is said once, by the status and its link; the question is on the decision card and in the recent changes. */}
                {o.status === "PENDING_APPROVAL" ? null : (
                  <span className="min-w-0 break-words text-sm font-medium text-ink" data-testid="op-sentence">
                    {o.event_text || o.message_when || o.message}
                  </span>
                )}
              </OperationResultBox>
            ) : (
              <OperationResultBox status={o.status} message={o.message} approvalId={o.approval_id} testId={`chat-op-${o.kind}`} kind={o.kind}>
                <span className="text-sm font-medium text-ink">{te("opkind", o.kind) || o.kind}</span>
                <TierBadge tier={o.tier} />
                {o.seq !== null ? <span className="text-xs text-ink-3">{t("chat.ops.seq", { n: o.seq })}</span> : null}
                <Hash value={o.entry_hash} />
              </OperationResultBox>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function AssistantTurn({
  response: r,
  active,
  busy,
  restored = false,
  onSend,
}: {
  response: NlResponse;
  /** Read back from the browser after a refresh: its buttons are history, and what was pending lives on the Approvals page. */
  restored?: boolean;
  /** Only the latest turn can be answered: confirmations and clarifications on older turns are history. */
  active: boolean;
  busy: boolean;
  onSend: (text: string, display?: string) => void;
}) {
  const { t, te } = useI18n();
  // A Business page says one outcome line in the owner's words (the reply); the verdict panels, tiers and operation rows are the Demo views'.
  const business = useBusinessShell();
  const hasSecurity = r.security_events.length > 0;
  const ranNothing = r.operations.length === 0 && (hasSecurity || r.plan.length > 0);
  const zh = r.lang === "zh";
  // The Business button says the words the server asked for in its reply ("Yes, run it" for a plan, "Yes, do it" for an approval); the dictionary word is the fallback.
  const goLabel = business ? ((r.reply && confirmWord(r.reply)) ?? t("chat.goahead.business")) : t("chat.goahead");
  const refused = r.operations.some((o) => o.status === "REFUSED");
  const pendingAfterRefresh = restored && (r.awaiting_confirmation || r.operations.some((o) => o.status === "PENDING_APPROVAL"));

  return (
    <div
      className={`space-y-3 rounded-tile border bg-surface p-3 ${hasSecurity ? "border-bad-line" : "border-line"}`}
      data-testid="chat-turn"
      data-intent={r.intent}
    >
      {r.amended || r.replayed ? (
        <div className="flex flex-wrap items-center gap-2">
          {r.amended ? (
            <span data-testid="chat-corrected">
              <Badge tone="info" title={t("chat.corrected.hint")}>
                {t("chat.corrected")}
              </Badge>
            </span>
          ) : null}
          {r.replayed ? (
            <span data-testid="chat-replayed">
              <Badge tone="neutral" title={t("chat.replayed.hint")}>
                {t("chat.replayed")}
              </Badge>
            </span>
          ) : null}
        </div>
      ) : null}

      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-ink" data-testid="chat-reply">
        {r.reply}
      </p>

      {hasSecurity ? (
        <div role="alert" className="rounded-tile border border-bad-line bg-bad-bg px-3 py-2 text-sm text-bad-fg" data-testid="chat-security">
          <p className="font-semibold">{t("chat.security.title", { n: r.security_events.length })}</p>
          <p className="mt-0.5">{t("chat.security.body")}</p>
          <p className="mt-1 break-all font-mono text-xs">{r.security_events.join(", ")}</p>
          <Link href="/security" className="mt-1 inline-block text-xs font-medium underline">
            {t("chat.security.open")}
          </Link>
        </div>
      ) : null}

      {r.verdict && !business ? <VerdictBlock verdict={r.verdict} /> : null}
      {r.verdict?.annualised?.length && !business ? <AnnualisedCompact legs={offerLegs(r.verdict.annualised, r.verdict.counters)} /> : null}
      {r.verdict && !business ? (
        <AutonomyPanel
          outcome={r.verdict.outcome}
          tier={r.verdict.required_tier}
          summary={r.verdict.summary}
          passedChecks={r.verdict.passed_checks}
          autonomyEligible={r.verdict.autonomy_eligible}
          autonomyNotes={r.verdict.autonomy_notes}
          autonomy={r.verdict.autonomy}
          checksInReply={r.verdict.passed_checks !== undefined}
        />
      ) : null}

      {r.negotiation ? (
        <p className="text-sm text-ink-2" data-testid="chat-negotiation">
          {t("chat.negotiation", {
            outcome: r.negotiation.accepted_counter
              ? t("chat.negotiation.ACCEPT", { counter: r.negotiation.accepted_counter })
              : t("chat.negotiation.NO_DEAL"),
            rounds: r.negotiation.rounds,
          })}
        </p>
      ) : null}

      {r.clarification ? (
        <section aria-label={t("chat.clarify")} className="rounded-tile border border-info-line bg-info-bg px-3 py-2" data-testid="chat-clarify">
          <p className="text-sm font-medium text-info-fg">{r.clarification.question}</p>
          <div className="mt-2 flex flex-wrap gap-2" role="group" aria-label={t("chat.clarify.pick")}>
            {r.clarification.options.map((o) => (
              <Button
                key={o.id}
                size="sm"
                variant="secondary"
                disabled={!active || busy}
                onClick={() => onSend(o.id, o.label)}
                data-testid={`clarify-option-${o.id}`}
              >
                {o.label}
              </Button>
            ))}
          </div>
        </section>
      ) : null}

      {pendingAfterRefresh ? (
        <p className="rounded-tile border border-warn-line bg-warn-bg px-3 py-2 text-sm text-warn-fg" data-testid="chat-restored-pending">
          {t("chat.restored.pending")}{" "}
          <Link href="/approvals" className="font-medium underline">
            {t("chat.restored.open")}
          </Link>
        </p>
      ) : r.awaiting_confirmation ? (
        <section className="rounded-tile border border-warn-line bg-warn-bg px-3 py-2" data-testid="chat-awaiting" aria-label={t("chat.awaiting")}>
          <p className="text-sm font-medium text-warn-fg">{t("chat.awaiting")}</p>
          <p className="mt-0.5 text-xs text-warn-fg">{t("chat.awaiting.hint")}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Button variant="primary" size="sm" disabled={!active || busy} onClick={() => onSend(zh ? "执行" : "go ahead", goLabel)} data-testid="chat-goahead">
              {goLabel}
            </Button>
            <Button variant="secondary" size="sm" disabled={!active || busy} onClick={() => onSend(zh ? "取消" : "cancel", t("chat.cancelPlan"))} data-testid="chat-cancel">
              {t("chat.cancelPlan")}
            </Button>
          </div>
        </section>
      ) : null}

      <Disclosure className="rounded-tile border border-line px-3" defaultOpen={hasSecurity || refused} testId="chat-details" summary={t("chat.details")}>
        <div className="space-y-3">
          {business ? null : (
            <span data-testid="chat-intent" className="inline-block">
              <Chip>{te("nlintent", r.intent) || r.intent}</Chip>
            </span>
          )}
          {r.plan.length ? <PlanList plan={r.plan} /> : null}
          {r.operations.length ? <OperationList operations={r.operations} business={business} /> : null}
          {ranNothing ? (
            <p className="text-xs font-medium text-ink-2" data-testid="chat-nothing-executed">
              {t("chat.ops.none")}
            </p>
          ) : null}
        </div>
      </Disclosure>
    </div>
  );
}
