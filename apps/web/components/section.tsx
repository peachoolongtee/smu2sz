"use client";

import type { ComponentType, SVGProps } from "react";
import { ActivityIcon, DealsIcon, HomeIcon, InboxInIcon, WalletIcon } from "./icons";

/**
 * Where you are, in colour: the five Business sections each own a hue (globals.css, `sec-*`). A hue only ever answers
 * "which part of the product is this?" (a page's icon chip, a tab, a shortcut, an avatar); it never says how things are
 * going, which is the job of the status tones. The class names are written out so Tailwind sees them.
 */
export type Section = "home" | "deals" | "cash" | "recv" | "activity";

export type SectionIcon = ComponentType<SVGProps<SVGSVGElement>>;
type Icon = SectionIcon;

export const SECTIONS: Record<Section, { icon: Icon; solid: string; solidText: string; tint: string }> = {
  home: { icon: HomeIcon, solid: "bg-sec-home-solid", solidText: "text-sec-home-solid", tint: "bg-sec-home-bg text-sec-home-fg" },
  deals: { icon: DealsIcon, solid: "bg-sec-deals-solid", solidText: "text-sec-deals-solid", tint: "bg-sec-deals-bg text-sec-deals-fg" },
  cash: { icon: WalletIcon, solid: "bg-sec-cash-solid", solidText: "text-sec-cash-solid", tint: "bg-sec-cash-bg text-sec-cash-fg" },
  recv: { icon: InboxInIcon, solid: "bg-sec-recv-solid", solidText: "text-sec-recv-solid", tint: "bg-sec-recv-bg text-sec-recv-fg" },
  activity: { icon: ActivityIcon, solid: "bg-sec-activity-solid", solidText: "text-sec-activity-solid", tint: "bg-sec-activity-bg text-sec-activity-fg" },
};

/** The section's mark: a round chip, a white icon on the section's solid (3:1 and better). `icon` overrides the section's own glyph. */
export function PageIcon({ section, icon: Glyph, size = "md" }: { section: Section; icon?: Icon; size?: "md" | "lg" }) {
  const Icon = Glyph ?? SECTIONS[section].icon;
  return (
    <span aria-hidden className={`grid shrink-0 place-items-center rounded-pill text-white ${SECTIONS[section].solid} ${size === "lg" ? "size-12" : "size-10"}`}>
      <Icon width={20} height={20} />
    </span>
  );
}
