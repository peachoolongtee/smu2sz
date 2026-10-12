"use client";

import type { ReactNode } from "react";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import type { ReceiptBasis } from "@/lib/types";

/**
 * The server's sentence about what a receipt rests on, with the state's glyph (owed, scheduled, agreed, pending) in front: the one place a basis is said (the Home
 * rail and tooltip rows, the Cash receipts, Receivables' due column). A basis the browser does not know (a newer server) is the sentence alone.
 */
export function BasisLine({ basis, children, testId, className = "" }: { basis?: ReceiptBasis | null; children: ReactNode; testId?: string; className?: string }) {
  const key = stateKey(basis);
  return key ? (
    <StateWord state={key} variant="line" testId={testId} data-basis={basis ?? undefined} className={className}>
      {children}
    </StateWord>
  ) : (
    <span className={`block text-[0.8125rem] leading-snug text-ink-2 ${className}`} data-testid={testId} data-basis={basis ?? undefined}>
      {children}
    </span>
  );
}

/**
 * What a receipt rests on, said under the picture (ticket #116). One row per receipt: its name, amount and distance on the first line, the server's basis
 * sentence under them at 13 px. A scheduled receipt is a shade quieter than an owed or agreed one (the "scheduled" word is the sentence's own); a pending
 * one sits in a dashed left rule, the same pattern as its line on the picture. Every word is the server's; `basis` only chooses the shade (INVARIANT 13).
 */
export interface BasisRow {
  key: string;
  label: string;
  amount?: string;
  when?: string;
  text: string;
  basis?: ReceiptBasis | null;
}

export function BasisRows({ rows, label, pending = false, testId }: { rows: BasisRow[]; label: string; pending?: boolean; testId: string }) {
  if (!rows.length) return null;
  return (
    <ul aria-label={label} className={`space-y-2 border-l-2 pl-3 ${pending ? "border-dashed border-brand-600/60" : "border-line-strong"}`} data-testid={testId}>
      {rows.map((r) => (
        <li key={r.key} data-testid={`${testId}-row`} data-basis={r.basis ?? undefined}>
          <p className="flex items-baseline justify-between gap-3 text-sm">
            <span className="min-w-0 break-words font-semibold text-ink first-letter:uppercase">
              {r.label}
              {r.when ? <span className="font-normal text-ink-3">{`, ${r.when}`}</span> : null}
            </span>
            {r.amount ? <span className="shrink-0 font-extrabold tabular-nums text-ink">{r.amount}</span> : null}
          </p>
          <BasisLine basis={r.basis} testId={`${testId}-text`}>
            {r.text}
          </BasisLine>
        </li>
      ))}
    </ul>
  );
}
