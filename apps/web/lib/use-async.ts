"use client";

import { useEffect, useState } from "react";
import { useDemo } from "./demo-store";

export interface AsyncState<T> {
  data: T | undefined;
  error: Error | undefined;
  /** True while the latest request is in flight. Previous data stays in `data` (stale-while-revalidate). */
  loading: boolean;
  reload: () => void;
}

/**
 * Loads data through lib/api.ts. Refetches when `deps` change, when the demo session writes
 * (`version`), or when `reload()` is called. The setState calls happen only after the promise settles.
 */
export function useAsync<T>(load: () => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const { version } = useDemo();
  const [nonce, setNonce] = useState(0);
  const token = `${version}:${nonce}:${JSON.stringify(deps)}`;
  const [result, setResult] = useState<{ token: string; data?: T; error?: Error }>();

  useEffect(() => {
    let live = true;
    load().then(
      (data) => live && setResult({ token, data }),
      (e: unknown) => live && setResult({ token, error: e instanceof Error ? e : new Error(String(e)) }),
    );
    return () => {
      live = false;
    };
    // `load` is recreated each render; `token` already encodes every input that matters.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const settled = result?.token === token;
  return {
    data: result?.data,
    error: settled ? result?.error : undefined,
    loading: !settled,
    reload: () => setNonce((n) => n + 1),
  };
}
