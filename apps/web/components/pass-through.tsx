import type { ReactNode } from "react";

/** A route segment's layout that only exists to carry that segment's `metadata` (lib/route-title.ts). */
export default function PassThrough({ children }: { children: ReactNode }) {
  return children;
}
