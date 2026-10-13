"use client";

import { SecurityView } from "@/components/trust/security-view";

/** The engine's security audit. The same view is a destination of the evidence links, at /trust?view=security. */
export default function SecurityPage() {
  return <SecurityView />;
}
