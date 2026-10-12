import type { ReactNode } from "react";

/**
 * A row of the buttons of one decision level: primary first, an 8 px gap, left-aligned after the content they act on. One FILLED button per page; every other decision
 * level keeps a real, outlined button (`Button` / `ButtonLink` variant "secondary"); a text link only leaves the page without a decision. On a phone the buttons wrap to full
 * width. The buttons are the kit's own (40 px, 32 px for `size="sm"`): this is only their layout.
 */
export function ActionGroup({ children, className = "", testId, label }: { children: ReactNode; className?: string; testId?: string; label?: string }) {
  return (
    <div role="group" aria-label={label} data-testid={testId} className={`flex flex-wrap items-center gap-2 max-sm:[&>*]:flex-1 max-sm:[&>a]:justify-center ${className}`}>
      {children}
    </div>
  );
}
