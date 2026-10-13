"use client";

import { useEffect, useState } from "react";
import { whatIf } from "@/lib/api";
import type { WhatIfParams, WhatIfResult } from "@/lib/types";

/** Debounce for slider drags: short enough to feel live, long enough to skip intermediate stops. */
export const WHATIF_DEBOUNCE_MS = 150;

export const keyOf = (p: WhatIfParams): string =>
  `${p.terms_days}|${p.discount_bp}|${p.rebate_bp}|${p.price_adjustment_bp}|${p.settle_face_fen ?? "-"}`;

interface Settled {
  key: string;
  result?: WhatIfResult;
  error?: Error;
}

/**
 * Latest-wins request queue: at most one request in flight; while one runs, only the newest slider
 * position is kept and sent when it returns. Dragging never piles up requests on the server.
 */
class Queue {
  private inflight = false;
  private queued: WhatIfParams | null = null;

  constructor(
    private readonly publish: (update: (prev: Settled) => Settled) => void,
    private readonly scope: { customer?: string | null; decision?: string | null },
  ) {}

  send(p: WhatIfParams): void {
    if (this.inflight) {
      this.queued = p;
      return;
    }
    this.inflight = true;
    const key = keyOf(p);
    whatIf(p, this.scope)
      .then(
        (result) => this.publish(() => ({ key, result })),
        (e: unknown) =>
          this.publish((prev) => ({ key, result: prev.result, error: e instanceof Error ? e : new Error(String(e)) })),
      )
      .finally(() => {
        this.inflight = false;
        const next = this.queued;
        this.queued = null;
        if (next && keyOf(next) !== key) this.send(next);
      });
  }
}

export interface WhatIfState {
  /** The latest result received (kept while a newer one loads: stale-while-revalidate). */
  result: WhatIfResult | undefined;
  error: Error | undefined;
  /** True until the result for exactly these params has arrived. */
  loading: boolean;
  /** Send the current position again (after an error). */
  reload: () => void;
}

export function useWhatIf(params: WhatIfParams, scope: { customer?: string | null; decision?: string | null } = {}): WhatIfState {
  const [settled, setSettled] = useState<Settled>({ key: "" });
  const [queue] = useState(() => new Queue((update) => setSettled(update), scope));
  const [nonce, setNonce] = useState(0);
  const key = keyOf(params);

  useEffect(() => {
    const timer = setTimeout(() => queue.send(params), WHATIF_DEBOUNCE_MS);
    return () => clearTimeout(timer);
    // `key` encodes every field of `params`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, nonce, queue]);

  return {
    result: settled.result,
    error: settled.key === key ? settled.error : undefined,
    loading: settled.key !== key,
    reload: () => setNonce((n) => n + 1),
  };
}
