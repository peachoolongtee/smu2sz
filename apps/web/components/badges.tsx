"use client";

import { useI18n } from "@/lib/i18n";
import type { FacilityStatus, OperationStatus, Outcome, Tier, ViolationCode } from "@/lib/types";
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
      <span aria-hidden className="text-[0.7em]">
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

export function TierBadge({ tier }: { tier: Tier }) {
  const { te } = useI18n();
  const tone: Tone = tier === "TIER_1" ? "ok" : tier === "TIER_2" ? "warn" : "bad";
  return <Badge tone={tone}>{te("tier", tier)}</Badge>;
}

export function OpStatusBadge({ status }: { status: OperationStatus }) {
  const { te } = useI18n();
  const tone: Tone = status === "EXECUTED" ? "ok" : status === "REFUSED" ? "bad" : status === "PENDING_APPROVAL" ? "warn" : "neutral";
  return <Badge tone={tone}>{te("opstatus", status)}</Badge>;
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

export function YesNo({ value }: { value: boolean }) {
  const { t } = useI18n();
  return <Badge tone={value ? "ok" : "neutral"}>{value ? t("common.yes") : t("common.no")}</Badge>;
}
