"use client";

import Link from "next/link";
import { OpenSection } from "@/components/ui/open-section";
import { useI18n } from "@/lib/i18n";
import type { HomeV2 } from "@/lib/types";

/** Where the rest of the company's picture lives: the server's links on one line, in an open section (the one place that leaves for another page). */
export function HomeV2Links({ links }: { links: HomeV2["links"] }) {
  const { t } = useI18n();
  if (!links.length) return null;
  return (
    <OpenSection testId="hv2-links">
      <nav aria-label={t("hv2.links")} data-testid="home-v2-links">
        <ul className="flex flex-wrap gap-x-6 gap-y-2">
          {links.map((l) => (
            <li key={l.href + l.label}>
              <Link href={l.href} className="motion-press inline-flex min-h-8 items-center gap-1 text-sm font-bold text-brand-700 underline-offset-[3px] hover:underline">
                {l.label}
                <span aria-hidden>→</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </OpenSection>
  );
}
