"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { textLinkClass } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { readSelection, selectionHref } from "@/lib/selection";
import { useTracker } from "@/lib/tracker";

function Link_({ id }: { id: string }) {
  const { t } = useI18n();
  const sel = readSelection(useSearchParams());
  const read = useTracker(id, sel);
  // Shown only when the server answers the tracker for this record and says it is available; an older API (404) or an unavailable deal shows nothing.
  if (!read.data?.available) return null;
  return (
    <p className="text-meta text-ink-3">
      <Link href={selectionHref(`/decisions/${encodeURIComponent(id)}/tracker`, sel)} className={textLinkClass} data-testid="decision-tracker-link">
        {t("tracker.link")}
      </Link>
    </p>
  );
}

/** Deal tracker: the quiet link from an agreed deal's record to its tracker; it carries the selection the record was opened with. */
export function TrackerRecordLink({ id }: { id: string }) {
  return (
    <Suspense fallback={null}>
      <Link_ id={id} />
    </Suspense>
  );
}
