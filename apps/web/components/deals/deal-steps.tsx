"use client";

import Link from "next/link";
import { CheckIcon } from "@/components/icons";
import { Button } from "@/components/ui";
import { dealRecordId } from "@/lib/api";
import { dealProgress } from "@/lib/decision";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useCurrentOffer } from "@/lib/use-current";
import { useDecision } from "@/lib/use-decision";

/**
 * Where the owner is in one buyer deal, as one quiet line: Received · Analysed · Response ready · Sent · the outcome. Every step and the
 * outcome's words come from the deal's decision record (`deal:{offer_id}`), read again whenever the books or the clock move; the line
 * never reads the verdict's outcome, the session cache or a clicked button. While the record loads the line waits rather than guess.
 */
const STEPS: { key: DictKey; href: string }[] = [
  { key: "steps.received", href: "/deals" },
  { key: "steps.analysed", href: "/deals" },
  { key: "steps.ready", href: "/deals#counters" },
  { key: "steps.sent", href: "/deals#counters" },
];

export function DealSteps() {
  const { t } = useI18n();
  const cur = useCurrentOffer();
  const record = useDecision(cur.offerId ? dealRecordId(cur.offerId) : null);
  if (record.error) {
    return (
      <nav aria-label={t("steps.label")} className="mb-4 flex flex-wrap items-center gap-2 text-xs text-ink-2" data-testid="deal-steps">
        <span>{t("steps.unavailable")}</span>
        <Button size="sm" onClick={record.reload}>
          {t("common.retry")}
        </Button>
      </nav>
    );
  }
  const d = record.data;
  if (!d) return <nav aria-label={t("steps.label")} className="mb-4 min-h-6" data-testid="deal-steps" aria-busy={record.loading} />;
  const p = dealProgress(d.state);
  const outcomeTone =
    p.tone === "bad" ? "font-semibold text-bad-fg" : p.tone === "closed" ? "font-semibold text-ink-2" : p.tone === "good" ? "text-ok-fg" : "font-semibold text-brand-700";
  return (
    <nav aria-label={t("steps.label")} className="mb-4" data-testid="deal-steps" data-state={d.state} aria-busy={record.loading}>
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs">
        {STEPS.map((s, i) => {
          const state = i < p.done ? "done" : i === p.done ? "current" : "todo";
          const tone = state === "done" ? "text-ok-fg" : state === "current" ? "font-semibold text-brand-700" : "text-ink-3";
          // A deal that waits on the buyer (needs clarification) says so in the step it is stuck on.
          const label =
            state === "current" && p.stalled
              ? d.state_text
              : // The response that is ready says what it is ("Counter recommended", "Acceptable, awaiting agreement") until it has been sent.
                s.key === "steps.ready" && d.state === "RESPONSE_READY"
                ? t("steps.ready.with", { action: d.state_text })
                : t(s.key);
          return (
            <li key={s.key} className="flex items-center gap-1">
              {i > 0 ? <span className="text-ink-3">·</span> : null}
              <Link href={s.href} aria-current={state === "current" ? "step" : undefined} className={`inline-flex items-center gap-1 rounded-pill px-2 py-1 ${tone}`}>
                {state === "done" ? <CheckIcon /> : null}
                {label}
              </Link>
            </li>
          );
        })}
        <li className="flex items-center gap-1">
          <span className="text-ink-3">·</span>
          {p.reached ? (
            <Link
              href={p.tone === "open" ? "/approvals" : "/deals#commitments"}
              aria-current={p.tone === "open" ? "step" : undefined}
              className={`inline-flex items-center gap-1 rounded-pill px-2 py-1 ${outcomeTone}`}
              data-testid="deal-steps-outcome"
            >
              {p.tone === "good" ? <CheckIcon /> : null}
              {d.state_text}
            </Link>
          ) : (
            <span className="inline-flex items-center rounded-pill px-2 py-1 text-ink-3" data-testid="deal-steps-outcome">
              {t("steps.agreement")}
            </span>
          )}
        </li>
      </ol>
    </nav>
  );
}
