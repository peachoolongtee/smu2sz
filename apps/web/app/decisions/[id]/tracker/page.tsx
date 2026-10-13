"use client";

import { useParams, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { TrackerPage } from "@/components/tracker/tracker-page";
import { LoadingBlock } from "@/components/ui";
import { readSelection } from "@/lib/selection";

function Tracker() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  // The id carries colons, which the address bar encodes; it is decoded once here and encoded again on the request.
  const raw = params.id ?? "";
  const id = (() => {
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  })();
  return <TrackerPage id={id} selection={readSelection(search)} />;
}

/** The deal tracker of one agreed deal (map #148): what it was expected to cost, what it has cost, what each side promised, and the next step. */
export default function DecisionTrackerPage() {
  return (
    <Suspense fallback={<LoadingBlock rows={4} />}>
      <Tracker />
    </Suspense>
  );
}
