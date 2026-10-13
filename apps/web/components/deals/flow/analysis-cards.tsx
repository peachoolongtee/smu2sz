"use client";

import { useEffect, useId, type ReactNode } from "react";

export type CardKey = "cost" | "cash";
/** `none` is both cards folded to their headline (the address says `show=none`); absent means the default card is open. */
export type ShowKey = CardKey | "none";

export interface CardHeadline {
  label: string;
  value: string | null;
}

/** A card's headline figures on one line: "Buyer request ¥28,327 · Option A ¥3,028"; a path with no figure is left out. */
function Headline({ items, testId }: { items: CardHeadline[]; testId: string }) {
  const shown = items.filter((i) => i.value);
  if (!shown.length) return null;
  return (
    <span className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-supporting text-ink-2" data-testid={testId}>
      {shown.map((i, n) => (
        <span key={i.label} className="min-w-0">
          {n > 0 ? <span aria-hidden className="mr-2 text-ink-3">·</span> : null}
          {i.label} <b className="font-display text-base font-bold tabular-nums text-ink">{i.value}</b>
        </span>
      ))}
    </span>
  );
}

/**
 * Two cards under the timing diagram (round two, section 6): "What it costs you" and "Your cash", side by side, each with its headline figures for the two options. One is open, in place, to its full
 * table; the other is folded to its headline, and pressing a card swaps them. The open one is the address (`show=cost|cash`; `none` is both folded), Escape folds it (before it dismisses the
 * selection), and the default is the card the server's recommendation reason names (cost when it does not say). The cards are the page's own `flow-card`; nothing here is a figure or a word of
 * ours except the card titles.
 */
export function AnalysisCards({
  open,
  onShow,
  cost,
  cash,
  costTitle,
  cashTitle,
  costBody,
  cashBody,
}: {
  open: ShowKey;
  onShow: (k: ShowKey) => void;
  cost: CardHeadline[];
  cash: CardHeadline[];
  costTitle: string;
  cashTitle: string;
  costBody: ReactNode;
  cashBody: ReactNode;
}) {
  const uid = useId();
  // Escape folds the open card first; the next Escape is the page's (it dismisses the selection). This listener is added before the page's own (child effects run first) and says it handled the key.
  useEffect(() => {
    if (open === "none") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || e.defaultPrevented || document.querySelector("dialog[open]")) return;
      const el = e.target instanceof HTMLInputElement ? e.target : null;
      if (el && el.value) return;
      e.preventDefault();
      onShow("none");
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onShow]);
  const card = (key: CardKey, title: string, head: CardHeadline[], body: ReactNode) => {
    const on = open === key;
    return (
      <section key={key} className={`flow-card flow-card-white min-w-0 p-4 sm:p-5 ${on ? "lg:col-span-2" : ""}`} data-testid={`deal-card-${key}`} data-open={on ? "true" : "false"}>
        <h3 className="m-0">
          <button
            type="button"
            aria-expanded={on}
            aria-controls={`${uid}-${key}`}
            onClick={() => onShow(on ? "none" : key)}
            className="motion-press flex w-full items-start justify-between gap-3 rounded-[16px] text-left outline-offset-4 focus-visible:outline-2 focus-visible:outline-brand-600"
            data-testid={`deal-card-${key}-toggle`}
          >
            <span className="min-w-0">
              <span className="block font-display text-base font-extrabold leading-snug text-ink">{title}</span>
              <Headline items={head} testId={`deal-card-${key}-headline`} />
            </span>
            <svg aria-hidden viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" className={`mt-1 shrink-0 text-ink-3 transition-transform duration-(--dur) ${on ? "rotate-180" : ""}`}>
              <path d="m4 6 4 4 4-4" />
            </svg>
          </button>
        </h3>
        <div id={`${uid}-${key}`} hidden={!on} className="mt-4" data-testid={`deal-card-${key}-body`}>
          {on ? body : null}
        </div>
      </section>
    );
  };
  // The open card takes the full row (its table needs the width) and the folded one is a headline beside or under it; the order of the two never changes.
  return (
    <div className="grid gap-4 lg:grid-cols-2" role="group" data-testid="deal-cards">
      {card("cost", costTitle, cost, costBody)}
      {card("cash", cashTitle, cash, cashBody)}
    </div>
  );
}
