"use client";

import { useEffect, useRef, useState } from "react";
import { cancelPending, clearNotice, confirmPending, guardStore } from "@/lib/books-guard";
import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";

/**
 * The one confirmation dialog of every control that would reset, restore or replace the books while work stands on them (the Demo page's, the strip's and Operator tools'). It is a
 * native modal `dialog`: the page behind is inert, focus stays inside and Escape closes it. It lists what is lost in the server's words on the amber tone, says what a reset keeps,
 * and has one filled button, the confirmation, which is the only thing that sends `confirm_loss=1`. Focus starts on the safe choice (cancel), so Enter on open changes nothing, and
 * returns to the control that opened it. Beside it, a stale page's refusal (the books were another; nothing was reset) is said in the server's words.
 */
export function BooksDialog() {
  const { t } = useI18n();
  const { pending, notice } = guardStore.useValue();
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (pending && !d.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      d.showModal();
      // The safe choice takes the focus (React's autoFocus runs before the dialog is open, so it is set here).
      d.querySelector<HTMLElement>('[data-testid="books-dialog-cancel"]')?.focus();
    }
    if (!pending && d.open) {
      d.close();
      opener.current?.focus();
    }
  }, [pending]);

  const labels = pending?.labels;
  const books = pending?.books;
  return (
    <>
      <dialog
        ref={ref}
        aria-modal="true"
        aria-labelledby="books-dialog-title"
        data-testid="books-dialog"
        onCancel={(e) => {
          e.preventDefault();
          cancelPending();
        }}
        className="m-auto w-[min(34rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/40"
      >
        {pending && books ? (
          <>
            <h2 id="books-dialog-title" className="type-section text-balance text-ink">
              {labels?.title ?? books.reset_confirm_title_text}
            </h2>
            <div className="mt-3 space-y-4">
              <div className="rounded-tile border border-warn-line bg-warn-bg p-3 text-warn-fg" data-testid="books-dialog-loss">
                <h3 className="text-sm font-bold">{books.loss_title_text}</h3>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                  {pending.items.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <p className="text-sm text-ink-2">{labels?.keeps ?? books.reset_keeps_text}</p>
            </div>
            <div className="mt-5 flex flex-wrap items-center gap-2">
              <Button
                variant="primary"
                loading={busy}
                onClick={() => {
                  setBusy(true);
                  void confirmPending().finally(() => setBusy(false));
                }}
                data-testid="books-dialog-confirm"
              >
                {labels?.confirm ?? books.reset_confirm_label}
              </Button>
              {/* Focus starts here: the safe choice. */}
              <Button onClick={cancelPending} data-testid="books-dialog-cancel">
                {labels?.cancel ?? books.reset_cancel_label}
              </Button>
            </div>
          </>
        ) : null}
      </dialog>
      {notice ? (
        <div role="alert" className="fixed inset-x-4 top-4 z-[70] mx-auto flex max-w-xl items-start justify-between gap-3 rounded-card border border-warn-line bg-warn-bg px-4 py-3 text-sm text-warn-fg shadow-pop" data-testid="books-notice">
          <p className="min-w-0 flex-1">{notice}</p>
          <button type="button" onClick={clearNotice} className="hit shrink-0 rounded-pill px-2 font-semibold underline" aria-label={t("demo.notice.close")}>
            {t("demo.notice.close")}
          </button>
        </div>
      ) : null}
    </>
  );
}
