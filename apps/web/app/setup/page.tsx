"use client";

import { Suspense } from "react";
import { SetupWizard } from "@/components/setup/wizard";
import { LoadingBlock } from "@/components/ui";

/** Set up your books (ADR-0014): a new owner's own starting position, in six steps, signed and opened by the owner. */
export default function SetupPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <SetupWizard />
    </Suspense>
  );
}
