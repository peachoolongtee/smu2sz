import Link from "next/link";
import type { ReactNode } from "react";
import { textLinkClass } from "@/components/ui";
import type { PillTone } from "@/components/ui/status-pill";
import { useI18n } from "@/lib/i18n";
import type { TrackerTone } from "@/lib/tracker";

/**
 * The server's tone on the kit's `StatusPill` (components/ui/status-pill.tsx): ok is green, warn amber, neutral the neutral fill. The pill has no
 * red of its own, so a `bad` tone takes the neutral pill with the kit's bad tint; the word is always shown, colour is never the only channel.
 */
export const PILL_TONE: Record<TrackerTone, PillTone> = { ok: "green", warn: "amber", bad: "neutral", neutral: "neutral" };
export const pillClass = (tone: TrackerTone): string => (tone === "bad" ? "bg-bad-bg! text-bad-fg!" : "");

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
