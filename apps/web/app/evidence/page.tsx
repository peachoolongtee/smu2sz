"use client";

import { EvidenceView } from "@/components/trust/evidence-view";

/** The engine's evidence file. The same view is a destination of the evidence links, at /trust?view=evidence. */
export default function EvidencePage() {
  return <EvidenceView />;
}
