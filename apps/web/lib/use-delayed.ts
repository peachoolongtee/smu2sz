"use client";

import { useEffect, useState } from "react";

/** True once `active` has held for `ms` (false at once when it stops): a skeleton that appears only after a read has taken that long, so a quick one never flashes it. */
export function useDelayed(active: boolean, ms: number): boolean {
  const [late, setLate] = useState(false);
  useEffect(() => {
    if (!active) return;
    const id = window.setTimeout(() => setLate(true), ms);
    return () => {
      window.clearTimeout(id);
      setLate(false);
    };
  }, [active, ms]);
  return active && late;
}
