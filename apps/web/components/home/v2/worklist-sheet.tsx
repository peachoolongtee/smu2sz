"use client";

import { useEffect, useId, useRef, useState } from "react";
import { XIcon } from "@/components/icons";
import { Button } from "@/components/ui";
import { WorklistBody } from "@/components/home/v2/worklist";
import { useI18n } from "@/lib/i18n";
import type { CustomersView, WorklistView } from "@/lib/types";

/**
 * The phone's worklist: a "Worklist (N)" button under the chart that opens the same tabs, search and rows in a bottom sheet. A native modal dialog: the page behind is
 * inert, focus stays inside and Tab wraps, Escape closes it and focus returns to the button. It arrives by the expanded duration (`motion-reveal`).
 */
export function WorklistSheet({ read, customers }: { read: WorklistView; customers: CustomersView | null }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <>
      <Button className="w-full" aria-haspopup="dialog" onClick={() => setOpen(true)} data-testid="home-worklist-open">
        {t("hv2.sheet.open", { n: read.counts.needs_you })}
      </Button>
      <dialog
        ref={ref}
        aria-labelledby={titleId}
        data-testid="home-worklist-sheet"
        onClose={() => setOpen(false)}
        onClick={(e) => {
          if (e.target === e.currentTarget) setOpen(false);
        }}
        className="motion-reveal fixed inset-x-0 bottom-0 top-auto m-0 max-h-[85dvh] w-full max-w-none overflow-y-auto overscroll-contain rounded-b-none rounded-t-decision border border-line bg-surface p-0 pb-4 text-ink shadow-pop backdrop:bg-ink/40"
      >
        {open ? (
          <>
            <div className="sticky top-0 z-10 flex items-center justify-between gap-3 border-b border-line bg-surface px-4 py-3">
              <h2 id={titleId} className="type-card-title text-ink">
                {t("hv2.work.title")}
              </h2>
              <Button size="sm" onClick={() => setOpen(false)} aria-label={t("hv2.sheet.close")} data-testid="home-worklist-close">
                <XIcon className="size-4" />
                {t("hv2.sheet.close")}
              </Button>
            </div>
            <div className="pt-3">
              <WorklistBody read={read} customers={customers} onAlertGo={() => setOpen(false)} />
            </div>
          </>
        ) : null}
      </dialog>
    </>
  );
}
