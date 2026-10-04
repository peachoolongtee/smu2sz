"use client";

import Link from "next/link";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import { useCurrentOffer } from "@/lib/use-current";
import { CheckIcon } from "./icons";

/**
 * Where the owner is in one buyer deal: read the offer, check it against the limits, respond, agreed.
 * Shown on the offer and decision screens so the four steps read as one journey, not four modules.
 * The state comes from the session's current offer only; it decides nothing.
 */
const STEPS: { key: DictKey; hint: DictKey; href: string }[] = [
  { key: "steps.read", hint: "steps.read.hint", href: "/inbox" },
  { key: "steps.check", hint: "steps.check.hint", href: "/verdict" },
  { key: "steps.respond", hint: "steps.respond.hint", href: "/verdict#counters-title" },
  { key: "steps.agreed", hint: "steps.agreed.hint", href: "/#home-agreements" },
];

export function DealSteps() {
  const { t } = useI18n();
  const cur = useCurrentOffer();
  const agreed = Boolean(cur.negotiation?.commitment) || cur.verdict?.outcome === "ACCEPT";
  const responded = Boolean(cur.negotiation) || cur.verdict?.outcome === "ACCEPT";
  // How many steps are complete; the next one is the current step.
  const done = !cur.offer ? 0 : !cur.verdict ? 1 : !responded ? 2 : agreed ? 4 : 3;

  return (
    <nav aria-label={t("steps.label")} className="mb-5" data-testid="deal-steps">
      <ol className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {STEPS.map((s, i) => {
          const state = i < done ? "done" : i === done ? "current" : "todo";
          const tone =
            state === "done"
              ? "border-ok-line bg-ok-bg text-ok-fg"
              : state === "current"
                ? "border-brand-600 bg-brand-50 text-brand-700 ring-1 ring-brand-600"
                : "border-line bg-surface text-ink-3";
          return (
            <li key={s.key}>
              <Link
                href={s.href}
                aria-current={state === "current" ? "step" : undefined}
                className={`flex h-full items-start gap-2 rounded-lg border px-3 py-2 ${tone}`}
              >
                <span className="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border border-current text-[0.7rem] font-semibold">
                  {state === "done" ? <CheckIcon /> : i + 1}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">{t(s.key)}</span>
                  <span className="block text-xs opacity-80">{t(s.hint)}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
