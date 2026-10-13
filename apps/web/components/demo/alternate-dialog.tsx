"use client";

import { useRef } from "react";
import { Disclosure } from "@/components/business/kit";
import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { useNarrow } from "@/lib/use-narrow";
import type { DemoStoryView } from "@/lib/types";

/**
 * "Another set of books": the scope in a sentence and an outline button that opens a modal dialog. The dialog says what you get, what the main books lose (the loss
 * preview, on the amber tone) and what stays, and has one filled button, the confirmation. It is a native modal `dialog`: the page behind is inert, focus stays inside,
 * Escape closes it and focus returns to the button that opened it. Cancelling changes nothing; confirming is the caller's call.
 */
export function AlternateSection({ alt, busy, onConfirm }: { alt: DemoStoryView["alternate"]; busy: boolean; onConfirm: () => void }) {
  const { t } = useI18n();
  const narrow = useNarrow();
  const dialog = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLButtonElement>(null);
  const close = () => {
    dialog.current?.close();
    opener.current?.focus();
  };

  const body = (
    <>
      <p className="text-sm text-ink-2" data-testid="demo-alternate-scope">
        {alt.scope_text}
      </p>
      {alt.loaded ? null : (
        <Button ref={opener} disabled={busy} onClick={() => {
            dialog.current?.showModal();
            // The safe choice takes the focus: Enter on open keeps the main books.
            dialog.current?.querySelector<HTMLElement>('[data-testid="demo-alternate-cancel"]')?.focus();
          }} data-testid="demo-alternate-open" aria-haspopup="dialog">
          {alt.label}
        </Button>
      )}
      <dialog
        ref={dialog}
        aria-modal="true"
        aria-labelledby="demo-alt-dialog-title"
        data-testid="demo-alternate-dialog"
        onClose={() => opener.current?.focus()}
        className="m-auto w-[min(34rem,calc(100vw-2rem))] rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/40"
      >
        <h2 id="demo-alt-dialog-title" className="type-section text-balance text-ink">
          {alt.confirm_title_text}
        </h2>
        <div className="mt-3 space-y-4">
          <div>
            <h3 className="text-sm font-bold text-ink">{t("demo.alt.get")}</h3>
            <p className="mt-0.5 text-sm text-ink-2">{alt.scope_text}</p>
          </div>
          <div className="rounded-tile border border-warn-line bg-warn-bg p-3 text-warn-fg" data-testid="demo-alternate-loss">
            <h3 className="text-sm font-bold">{alt.loss_title_text}</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
              {alt.loss_items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <p className="text-sm text-ink-2">{alt.keeps_text}</p>
        </div>
        <div className="mt-5 flex flex-wrap items-center gap-2">
          <Button variant="primary" loading={busy} onClick={onConfirm} data-testid="demo-alternate-confirm">
            {alt.confirm_label}
          </Button>
          {/* Focus starts on the safe choice: Enter on open changes nothing. */}
          <Button onClick={close} data-testid="demo-alternate-cancel">
            {alt.cancel_label}
          </Button>
        </div>
      </dialog>
    </>
  );

  // On a phone the block is one closed fold with its title (the story is the page); the dialog opens from inside it.
  if (narrow) {
    return (
      <div data-testid="demo-alternate">
        <Disclosure card testId="demo-alternate-fold" summary={t("demo.alt.heading")}>
          <div className="space-y-3">{body}</div>
        </Disclosure>
      </div>
    );
  }
  return (
    <section aria-labelledby="demo-alt-title" className="card-standard space-y-3 p-5" data-testid="demo-alternate">
      <h2 id="demo-alt-title" className="type-card-title text-ink">
        {t("demo.alt.heading")}
      </h2>
      {body}
    </section>
  );
}
