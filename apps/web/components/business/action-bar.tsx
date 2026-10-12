import type { HTMLAttributes } from "react";
import { DecisionCard } from "@/components/ui";

/**
 * The page's one raised surface (DESIGN.md, The One Raised Surface Rule): a `DecisionCard` for the action the page asks of the owner. In flow below
 * `lg`; from `lg` it is sticky at the bottom of the window until the reader reaches its place. Home's attention card, the Deals reply bar and
 * Receivables' chase bar use it. Solid, with one soft shadow: no frost.
 */
export function ActionBar({ className = "", flow = false, ...rest }: HTMLAttributes<HTMLElement> & { /** Stays in the document's flow at every width (a page whose picture the sticky bar would cover). */ flow?: boolean }) {
  return (
    <DecisionCard
      {...rest}
      className={`z-10 flex flex-wrap items-center gap-x-8 gap-y-4 px-5 py-4 max-sm:px-4 ${flow ? "" : "lg:sticky lg:bottom-4"} short:py-3 ${className}`}
    />
  );
}
