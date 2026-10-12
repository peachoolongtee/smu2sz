"use client";

import Link from "next/link";
import { Card } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeV2 } from "@/lib/types";

/** Where the rest of the company's picture lives: the server's links, one line, thin dividers (two columns on a phone). */
export function HomeV2Links({ links }: { links: HomeV2["links"] }) {
  const { t } = useI18n();
  if (!links.length) return null;
  return (
    <Card className="[&>div]:p-0">
      <nav aria-label={t("hv2.links")} data-testid="home-v2-links">
        <ul className="grid grid-cols-2 md:flex md:flex-wrap">
          {links.map((l) => (
            <li key={l.href + l.label} className="min-w-0 border-line max-md:nth-[even]:border-l max-md:nth-[n+3]:border-t md:border-l md:first:border-l-0">
              <Link href={l.href} className="motion-press flex min-h-11 items-center gap-1 px-4 py-2 text-sm font-bold text-brand-700 hover:bg-brand-50">
                {l.label}
                <span aria-hidden>›</span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </Card>
  );
}
