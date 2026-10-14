"use client";

import Link from "next/link";
import { Button } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { DemoStoryView } from "@/lib/types";

/** The three sets of books the Demo can stand on: the id the page names them by, the scenario the API knows them as, and their words. */
export const BOOKS = [
  { id: "golden", scenario: "golden_sme", name: "demo.card.golden", help: "story.scenario.golden.help" },
  { id: "busy", scenario: "busy", name: "demo.card.busy", help: "story.scenario.busy.help" },
  { id: "short", scenario: "short_facilities", name: "demo.card.short", help: "story.scenario.short.help" },
] as const satisfies readonly { id: string; scenario: string; name: DictKey; help: DictKey }[];

export type BooksId = (typeof BOOKS)[number]["id"];

/**
 * "Which books?": the Demo's first question, three cards (Golden story, Busy company, Short facilities), each with its one-line help and a Load button; the loaded one is marked
 * "Loaded" and has no button. Load goes through the guarded flow (lib/books-guard.ts): a straight reset on fresh books, the loss preview dialog (components/demo/books-dialog.tsx) when
 * the current books hold work. Below `sm` each card is one row (name and help, then the button) so the three sit inside the first screen; from `md` they are three columns.
 */
export function BooksCards({ view, busy, onLoad }: { view: DemoStoryView; busy: boolean; onLoad: (id: BooksId) => void }) {
  const { t } = useI18n();
  return (
    <section aria-labelledby="demo-which-title" className="mb-5" data-testid="demo-books">
      <h2 id="demo-which-title" className="type-card-title text-ink">
        {t("demo.which.title")}
      </h2>
      <p className="mt-0.5 text-sm text-ink-2 max-sm:sr-only">{t("demo.which.sub")}</p>
      <ul className="mt-3 grid gap-2 sm:gap-3 md:grid-cols-3">
        {BOOKS.map((b) => {
          const loaded = view.books.scenario === b.scenario;
          const name = t(b.name);
          return (
            <li
              key={b.id}
              className={`card-standard grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1 p-4 md:flex md:flex-col ${loaded ? "ring-2 ring-ink" : ""}`}
              data-testid={`demo-scenario-${b.id}`}
              data-loaded={loaded ? "true" : undefined}
              aria-current={loaded ? "true" : undefined}
            >
              <div className="min-w-0">
                <h3 className="text-base font-bold text-ink">{name}</h3>
                <p className="mt-0.5 text-sm text-ink-2" data-testid={`demo-scenario-help-${b.id}`}>
                  {t(b.help)}
                </p>
                {b.id === "busy" ? (
                  <Link href="/" className="motion-press hit mt-1 inline-flex min-h-8 items-center rounded-pill px-1 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11" data-testid="demo-busy-home">
                    {t("demo.card.home")}
                  </Link>
                ) : null}
              </div>
              <div className="md:mt-auto md:pt-3">
                {loaded ? (
                  <StatusPill tone="green" testId={`demo-scenario-loaded-${b.id}`}>
                    {t("demo.card.loaded")}
                  </StatusPill>
                ) : (
                  <Button disabled={busy} onClick={() => onLoad(b.id)} aria-label={`${t("demo.card.load")}: ${name}`} data-testid={`demo-scenario-load-${b.id}`}>
                    {t("demo.card.load")}
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
