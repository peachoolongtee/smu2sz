"use client";

import Link from "next/link";
import { CheckIcon } from "@/components/icons";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useCurrentOffer } from "@/lib/use-current";

/**
 * Where the owner is in one buyer deal, as one quiet line: Received · Analysed · Respond · Agreed. The agent's own
 * stages (receiving and analysing) are done by the time the owner looks, so the line never dominates the page. The
 * state comes from the session's current offer only; it decides nothing.
 */
const STEPS: { key: DictKey; href: string }[] = [
  { key: "steps.received", href: "/deals" },
  { key: "steps.analysed", href: "/deals" },
  { key: "steps.respond", href: "/deals#counters" },
  { key: "steps.agreed", href: "/deals#commitments" },
];

export function DealSteps() {
  const { t } = useI18n();
  const cur = useCurrentOffer();
  const agreed = Boolean(cur.negotiation?.commitment) || cur.verdict?.outcome === "ACCEPT";
  const responded = Boolean(cur.negotiation) || cur.verdict?.outcome === "ACCEPT";
  // How many steps are complete; the next one is the current step.
  // A refused negotiation ends the deal too: the last step then reads "No deal" instead of waiting forever on "Agreed".
  const noDeal = cur.negotiation?.outcome === "NO_DEAL";
  const done = !cur.offer ? 0 : !cur.verdict ? 1 : !responded ? 2 : agreed || noDeal ? 4 : 3;
  return (
    <nav aria-label={t("steps.label")} className="mb-4" data-testid="deal-steps">
      <ol className="flex flex-wrap items-center gap-x-1 gap-y-1 text-xs">
        {STEPS.map((s, i) => {
          const state = i < done ? "done" : i === done ? "current" : "todo";
          const tone = state === "done" ? "text-ok-fg" : state === "current" ? "font-semibold text-brand-700" : "text-ink-3";
          return (
            <li key={s.key} className="flex items-center gap-1">
              {i > 0 ? <span className="text-ink-3">·</span> : null}
              <Link href={noDeal && s.key === "steps.agreed" ? "/deals#counters" : s.href} aria-current={state === "current" ? "step" : undefined} className={`inline-flex items-center gap-1 rounded px-1.5 py-1 ${tone}`}>
                {state === "done" ? <CheckIcon width={12} height={12} /> : null}
                {noDeal && s.key === "steps.agreed" ? t("steps.noDeal") : t(s.key)}
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
