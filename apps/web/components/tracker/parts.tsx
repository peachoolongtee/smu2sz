import Link from "next/link";
import type { ReactNode } from "react";
import { textLinkClass } from "@/components/ui";
import { StateWord } from "@/components/ui/state-word";
import type { StateTone } from "@/components/ui/state-word-model";
import { useI18n } from "@/lib/i18n";
import type { TrackerTone } from "@/lib/tracker";

const FILL: Record<StateTone, string> = { neutral: "bg-subtle", ok: "bg-ok-bg", warn: "bg-warn-bg", bad: "bg-bad-bg", info: "bg-info-bg" };

/** A server word as a pill: the kit's `StateWord` (a mark, the word, the tone's ink) on the tone's fill. The word is the accessible name; colour is never alone. */
export function Pill({ tone, children, testId, ...data }: { tone: TrackerTone | "info"; children: ReactNode; testId?: string; [attr: `data-${string}`]: string | undefined }) {
  return (
    <span className={`inline-flex max-w-full rounded-pill px-2.5 py-1 ${FILL[tone]}`} data-testid={testId} {...data}>
      <StateWord tone={tone}>{children}</StateWord>
    </span>
  );
}

/** The quiet link to the evidence behind a line or a promise (the server's address). */
export function EvidenceLink({ href }: { href: string | null }) {
  const { t } = useI18n();
  if (!href) return null;
  return (
    <Link href={href} className={textLinkClass}>
      {t("tracker.evidence")}
    </Link>
  );
}

/** A section of the page: the scope's card with a section heading. */
export function Block({ id, title, children, className = "", testId }: { id: string; title: string; children: ReactNode; className?: string; testId?: string }) {
  return (
    <section aria-labelledby={`${id}-title`} data-testid={testId} className={`flow-card motion-reveal min-w-0 p-5 sm:p-7 ${className}`}>
      <h2 id={`${id}-title`} className="type-section text-balance text-ink">
        {title}
      </h2>
      {children}
    </section>
  );
}
