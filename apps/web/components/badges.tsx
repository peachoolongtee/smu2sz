"use client";

import { useI18n } from "@/lib/i18n";
import type { FacilityStatus, OperationStatus, Outcome, Tier, ViolationCode } from "@/lib/types";
import { OperationStatePill } from "./operation-result";
import { Badge, type Tone } from "./ui";

const outcomeTone: Record<Outcome | "NO_DEAL", Tone> = {
  ACCEPT: "ok",
  COUNTER: "warn",
  REJECT: "bad",
  NO_DEAL: "neutral",
  NEEDS_OWNER_APPROVAL: "info",
  NO_VERDICT: "neutral",
};

export function OutcomeBadge({ outcome, large = false }: { outcome: Outcome; large?: boolean }) {
  const { te } = useI18n();
  const tone = outcomeTone[outcome];
  const size = large ? "px-4 py-1.5 text-base font-bold tracking-wide" : "";
  return (
    <Badge tone={tone} className={size} title={outcome}>
      <span aria-hidden className="text-xs leading-none">
        {outcome === "ACCEPT" ? "●" : outcome === "REJECT" ? "■" : "◆"}
      </span>
      {te("outcome", outcome)}
    </Badge>
  );
}

/** A REJECT or NO_VERDICT executes nothing, so a tier-of-action badge on it would mislead. */
export function outcomeHasTier(outcome: Outcome | "NO_DEAL"): boolean {
  return outcome === "ACCEPT" || outcome === "COUNTER" || outcome === "NEEDS_OWNER_APPROVAL";
}

/** The tier badge; `explain` puts the plain sentence (tier.short) beside it for the engine views. */
export function TierBadge({ tier, explain = false }: { tier: Tier; explain?: boolean }) {
  const { te } = useI18n();
  const tone: Tone = tier === "TIER_1" ? "ok" : tier === "TIER_2" ? "warn" : "bad";
  const badge = <Badge tone={tone}>{te("tier", tier)}</Badge>;
  if (!explain) return badge;
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      {badge}
      <span className="text-xs text-ink-2">{te("tier.short", tier)}</span>
    </span>
  );
}

/** A ledger row's state: the shared presentation of an operation result (components/operation-result.tsx). */
export function OpStatusBadge({ status }: { status: OperationStatus }) {
  return <OperationStatePill status={status} />;
}

export function FacilityStatusBadge({ status }: { status: FacilityStatus }) {
  const { te } = useI18n();
  const tone: Tone = status === "COMMITTED" ? "ok" : status === "PENDING" ? "warn" : "neutral";
  return <Badge tone={tone}>{te("facstatus", status)}</Badge>;
}

export function CodeBadge({ code, tone = "neutral" }: { code: ViolationCode | string; tone?: Tone }) {
  const { te } = useI18n();
  return (
    <Badge tone={tone} title={te("violation", code)} className="font-mono">
      {code}
    </Badge>
  );
}

const codeText: Partial<Record<Tone, string>> = { bad: "text-bad-fg", warn: "text-warn-fg", ok: "text-ok-fg" };

/**
 * A reason code in plain words (violation.* or alertkind.*), with the code itself behind the same `<details>`
 * disclosure the Business pages use. A code with no plain name is shown as the code badge.
 */
export function PlainCode({ code, tone = "neutral", kind = "violation" }: { code: ViolationCode | string; tone?: Tone; kind?: "violation" | "alertkind" }) {
  const { t, te } = useI18n();
  const label = te(kind, code);
  if (label === code) return <CodeBadge code={code} tone={tone} />;
  return (
    <span className="inline-flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
      <span className={`min-w-0 break-words text-sm font-medium ${codeText[tone] ?? "text-ink"}`}>{label}</span>
      <details className="inline-block">
        <summary className="hit cursor-pointer text-xs text-ink-3">{t("common.code")}</summary>
        <CodeBadge code={code} tone={tone} />
      </details>
    </span>
  );
}

export function YesNo({ value }: { value: boolean }) {
  const { t } = useI18n();
  return <Badge tone={value ? "ok" : "neutral"}>{value ? t("common.yes") : t("common.no")}</Badge>;
}
