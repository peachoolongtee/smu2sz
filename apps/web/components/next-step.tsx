"use client";

import type { ReactNode } from "react";
import { ArrowRightIcon } from "./icons";
import { buttonClass } from "./ui";

/**
 * The one thing to do next in a multi-step task, at the top of the screen (design principle 5 in
 * docs/UI_UX_CHANGES.md). `action` is the button or link that does it.
 */
export function NextStep({ label, children, action, testId = "next-step" }: { label: string; children: ReactNode; action?: ReactNode; testId?: string }) {
  return (
    <div
      className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-brand-100 bg-brand-50 px-4 py-3"
      role="region"
      aria-label={label}
      data-testid={testId}
    >
      <div className="flex min-w-0 items-center gap-2 text-sm text-ink-2">
        <ArrowRightIcon className="shrink-0 text-brand-700" />
        <p className="min-w-0">
          <span className="font-semibold text-brand-700">{label}: </span>
          {children}
        </p>
      </div>
      {action ? <div className="flex flex-wrap items-center gap-3">{action}</div> : null}
    </div>
  );
}

/** The same link as a secondary button, for a page whose own card carries the primary action (a counter to send). */
export const nextLinkSecondaryCls = buttonClass("secondary");

/** A link styled as the primary button, for a next step that is a navigation. */
export const nextLinkCls = buttonClass("primary");
