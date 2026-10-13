"use client";

import { Suspense } from "react";
import { DealsPage } from "@/components/deals/flow/deals-page";
import { LoadingBlock } from "@/components/ui";

/** Deals: the queue and the selected negotiation (components/deals/flow). The address is the selection; nothing is kept in a session store. */
export default function Page() {
  return (
    <Suspense fallback={<LoadingBlock rows={3} />}>
      <DealsPage />
    </Suspense>
  );
}
