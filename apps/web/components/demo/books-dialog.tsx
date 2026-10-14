"use client";

import "@/app/flow-look.css";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { cancelPending, clearNotice, confirmPending, guardStore } from "@/lib/books-guard";
import { useI18n } from "@/lib/i18n";

/** How long the dialog has been open before its confirm button takes a click: a double click on the control that opened it must never land on the button under the pointer. */
const READY_MS = 400;

/**
 * The one confirmation dialog of every control that would reset, restore or replace the books (the Demo page's, the strip's and Operator tools'). It is a native modal `dialog`:
 * the page behind is inert, focus stays inside and Escape closes it. It lists what is lost, from a fresh read, in the server's words on the amber tone, says what a reset keeps, and
 * has one filled button, the confirmation, which is the only thing that sends the confirmation (the token of the list shown). Focus starts on the safe choice (cancel), so Enter on
 * open changes nothing, and returns to the control that opened it. The confirm acts only on a deliberate click: not before the dialog has been open for a moment (it says so with
 * `aria-disabled`) and never on the second click of a double click. Beside it, a stale page's refusal (the books were another; nothing was reset) is said in the server's words.
 */
export function BooksDialog() {
  const { t } = useI18n();
  const { pending, notice } = guardStore.useValue();
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const open = pending !== null;
  const prefix = pending?.options.prefix ?? "books-dialog";
  const id = (part: string) => (prefix === "demo-alternate" ? `demo-alternate-${part}` : part === "dialog" ? "books-dialog" : `books-dialog-${part}`);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      d.showModal();
      // The safe choice takes the focus (React's autoFocus runs before the dialog is open, so it is set here).
      d.querySelector<HTMLElement>("[data-cancel]")?.focus();
    }
    if (!open && d.open) {
      d.close();
      opener.current?.focus();
    }
  }, [open]);

  // The confirm is not ready until the dialog has been open for a moment; a list that was replaced under it needs a new, deliberate click too.
  const token = pending?.token ?? null;
  const note = pending?.note ?? null;
  useEffect(() => {
    if (!open) return;
    const off = window.setTimeout(() => setReady(true), READY_MS);
    return () => {
      window.clearTimeout(off);
      setReady(false);
    };
  }, [open, token, note]);

  const labels = pending?.options.labels;
  const books = pending?.books;
  return (
    <>
      <dialog
        ref={ref}
        aria-modal="true"
        aria-labelledby="books-dialog-title"
        data-testid={id("dialog")}
        onCancel={(e) => {
          e.preventDefault();
          cancelPending();
        }}
        className="flow-f m-auto w-[min(34rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/40"
      >
        {pending && books ? (
          <>
            <h2 id="books-dialog-title" className="type-section text-balance text-ink">
              {labels?.title ?? books.reset_confirm_title_text}
            </h2>
            <div className="mt-3 space-y-4">
              {pending.options.gives ? (
                <div>
                  <h3 className="text-sm font-bold text-ink">{pending.options.gives.heading}</h3>
                  <p className="mt-0.5 text-sm text-ink-2">{pending.options.gives.text}</p>
                </div>
              ) : null}
              {note ? (
                <p role="status" className="rounded-tile border border-warn-line px-3 py-2 text-sm font-medium text-ink" data-testid={id("note")}>
                  {note}
                </p>
              ) : null}
              <div className="rounded-tile border border-warn-line bg-warn-bg p-3 text-warn-fg" data-testid={id("loss")}>
                <h3 className="text-sm font-bold">{pending.lossTitle}</h3>
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
                aria-disabled={!ready || undefined}
                className={ready ? "" : "opacity-60"}
                onClick={(e) => {
                  // Only a deliberate click confirms: not the second click of a double click, and not before the dialog is ready.
                  if (e.detail > 1 || !ready) return;
                  setBusy(true);
                  void confirmPending().finally(() => setBusy(false));
                }}
                data-testid={id("confirm")}
              >
                {labels?.confirm ?? books.reset_confirm_label}
              </Button>
              {/* Focus starts here: the safe choice. */}
              <Button onClick={cancelPending} data-cancel data-testid={id("cancel")}>
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
