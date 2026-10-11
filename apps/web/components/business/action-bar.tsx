import type { HTMLAttributes } from "react";

/**
 * The page's one raised surface (DESIGN.md, The One Raised Surface Rule): a frosted bar for the action the page asks of the owner. In flow below
 * `lg`; from `lg` it is sticky at the bottom of the window until the reader reaches its place. Home's plan bar and Receivables' chase bar use it.
 */
export function ActionBar({ className = "", ...rest }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      {...rest}
      className={`motion-reveal z-10 flex flex-wrap items-center gap-x-8 gap-y-4 rounded-card border border-line-strong bg-surface/84 px-5 py-4 shadow-pop backdrop-blur-[18px] backdrop-saturate-150 max-sm:px-4 lg:sticky lg:bottom-4 short:py-3 ${className}`}
    />
  );
}
