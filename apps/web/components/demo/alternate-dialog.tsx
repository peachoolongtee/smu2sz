"use client";

import { Disclosure } from "@/components/business/kit";
import { Button } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { useNarrow } from "@/lib/use-narrow";
import type { DemoStoryView } from "@/lib/types";

/**
 * "Another set of books": the scope in a sentence and an outline button that opens the books dialog (components/demo/books-dialog.tsx, the one modal confirmation): what you
 * get, what the main books lose from a fresh read, what stays, one filled confirmation and "Keep the main books". Loading is the dialog's confirm and nothing else. On a phone the
 * block is one closed fold with its title.
 */
export function AlternateSection({ alt, busy, onOpen }: { alt: DemoStoryView["alternate"]; busy: boolean; onOpen: () => void }) {
  const { t } = useI18n();
  const narrow = useNarrow();
  const body = (
    <>
      <p className="text-sm text-ink-2" data-testid="demo-alternate-scope">
        {alt.scope_text}
      </p>
      {alt.loaded ? null : (
        <Button disabled={busy} onClick={onOpen} data-testid="demo-alternate-open" aria-haspopup="dialog">
          {alt.label}
        </Button>
      )}
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
