"use client";

import Link from "next/link";
import { ChatIcon } from "@/components/icons";
import { SECTIONS, type Section } from "@/components/section";
import { setPanelOpen } from "@/lib/chat";
import { useI18n } from "@/lib/i18n";

/**
 * "Where to next", under the hero on a phone or tablet: four round chips, one per place the owner goes from here, each in its
 * section's hue with a white icon (the desktop has the nav pills in view, so the row is hidden there). The chips are
 * wayfinding: their colour says where the link goes, never how things are going.
 */
export function WhereNext() {
  const { t } = useI18n();
  const places: { section: Section; href: string; label: string }[] = [
    { section: "deals", href: "/deals", label: t("nav.deals") },
    { section: "cash", href: "/cash", label: t("nav.cash") },
    { section: "recv", href: "/receivables", label: t("nav.receivables") },
  ];
  const chip = "motion-press motion-lift flex flex-col items-center gap-1.5 rounded-tile px-1 py-2 text-center text-xs font-medium leading-tight text-ink";
  const disc = (section: Section) => `grid size-12 place-items-center rounded-pill text-white ${SECTIONS[section].solid}`;
  return (
    <nav aria-labelledby="home-where-title" className="motion-reveal lg:hidden" data-testid="home-where-next">
      <h2 id="home-where-title" className="mb-1 px-1 text-xs font-semibold uppercase tracking-wide text-ink-3">
        {t("home.whereNext")}
      </h2>
      <ul className="motion-rise grid grid-cols-4 gap-1">
        {places.map(({ section, href, label }) => {
          const Icon = SECTIONS[section].icon;
          return (
            <li key={section}>
              <Link href={href} className={chip} data-testid={`home-go-${section}`}>
                <span aria-hidden className={disc(section)}>
                  <Icon width={20} height={20} />
                </span>
                {label}
              </Link>
            </li>
          );
        })}
        <li>
          <button type="button" onClick={() => setPanelOpen(true)} className={`${chip} w-full`} aria-haspopup="dialog" data-testid="home-go-chat">
            <span aria-hidden className={disc("home")}>
              <ChatIcon width={20} height={20} />
            </span>
            {t("chat.open")}
          </button>
        </li>
      </ul>
    </nav>
  );
}
