"use client";

import { useSyncExternalStore } from "react";

export interface Store<T> {
  get: () => T;
  set: (next: T | ((prev: T) => T)) => void;
  useValue: () => T;
}

/**
 * A minimal external store with optional browser persistence. Reading storage lazily on the first client
 * `get()` keeps first paint identical to the server snapshot (`initial`) and avoids setState-in-effect.
 */
export function createStore<T>(
  initial: T,
  persist?: { storage: "session" | "local"; key: string; sanitize?: (v: T) => T },
): Store<T> {
  let value = initial;
  let loaded = typeof window === "undefined" || !persist;
  const listeners = new Set<() => void>();

  const area = () => (persist?.storage === "local" ? window.localStorage : window.sessionStorage);

  function ensureLoaded() {
    if (loaded) return;
    loaded = true;
    try {
      const raw = area().getItem(persist!.key);
      if (raw) value = { ...initial, ...(JSON.parse(raw) as T) };
    } catch {
      /* ignore corrupt or unavailable storage */
    }
  }

  const get = () => {
    ensureLoaded();
    return value;
  };

  const set: Store<T>["set"] = (next) => {
    ensureLoaded();
    value = typeof next === "function" ? (next as (p: T) => T)(value) : next;
    if (persist && typeof window !== "undefined") {
      try {
        area().setItem(persist.key, JSON.stringify(persist.sanitize ? persist.sanitize(value) : value));
      } catch {
        /* storage full: keep working in memory */
      }
    }
    listeners.forEach((l) => l());
  };

  const subscribe = (l: () => void) => {
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  };

  function useValue(): T {
    return useSyncExternalStore(subscribe, get, () => initial);
  }

  return { get, set, useValue };
}
