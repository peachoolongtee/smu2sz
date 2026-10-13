"use client";

import Link from "next/link";
import { buttonClass, Card, textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

/** The path of a decision's record page. The id carries colons, so it is encoded. */
export const decisionHref = (id: string): string => `/decisions/${encodeURIComponent(id)}`;

/**
 * What is left after a cure that did not restore the reserve (F17): the server's sentence and the supported routes it names, as links.
 * The page never invents a cure and never waives the reserve; this block only says it still needs the owner's decision and where to look.
 * With no approval waiting it is the page's one primary: its first route (the server lists them in order) is the filled button.
 */
export function RemainingTaskBlock({ text, links, decisionId, primary = false }: { text: string; links: { label: string; href: string }[]; decisionId?: string | null; primary?: boolean }) {
  const { t } = useI18n();
  return (
    <Card id="home-remaining" tone="warn" title={t("biz.remaining.title")} actions={decisionId ? <Link href={decisionHref(decisionId)} className={textLinkClass}>{t("biz.remaining.record")}</Link> : undefined}>
      <p className="text-sm text-ink" data-testid="home-remaining-text">
        {text}
      </p>
      {links.length ? (
        <ul className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1" data-testid="home-remaining-links" aria-label={t("biz.remaining.links")}>
          {links.map((l, i) => (
            <li key={l.href}>
              {/* The first route is the one primary (when nothing else is waiting); the others are text links. */}
              <Link href={l.href} className={primary && i === 0 ? buttonClass("primary", "md", "max-w-full whitespace-normal text-center") : textLinkClass}>
                {l.label}
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}
