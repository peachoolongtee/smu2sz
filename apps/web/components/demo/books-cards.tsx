"use client";

import Link from "next/link";
import { Button } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { API_MODE } from "@/lib/config";
import type { DictKey } from "@/lib/dictionary";
import { useI18n } from "@/lib/i18n";
import type { DemoStoryView } from "@/lib/types";

/** The sets of books the Demo can stand on: the id the page names them by, the scenario the API knows them as, and their words. */
export const BOOKS = [
  { id: "golden", scenario: "golden_sme", name: "demo.card.golden", help: "story.scenario.golden.help" },
  { id: "busy", scenario: "busy", name: "demo.card.busy", help: "story.scenario.busy.help" },
  { id: "short", scenario: "short_facilities", name: "demo.card.short", help: "story.scenario.short.help" },
  { id: "blank", scenario: "blank", name: "demo.card.blank", help: "demo.card.blank.help" },
] as const satisfies readonly { id: string; scenario: string; name: DictKey; help: DictKey }[];

export type BooksId = (typeof BOOKS)[number]["id"];

/** The owner's own books (opened through the setup) are never a demo scenario: they have their own name. */
export const OWN = "own";

/** The books the page offers: the blank books only where the setup can open them (the live API; the mock has no setup). */
export const offeredBooks = () => BOOKS.filter((b) => b.id !== "blank" || API_MODE === "live");

/** The name of the books loaded now, in the dictionary's words (the owner's own books by their own name). */
export function booksName(scenario: string): DictKey {
  if (scenario === OWN) return "demo.card.own";
  if (scenario === "blank") return "demo.card.blankTitle";
  return (BOOKS.find((b) => b.scenario === scenario) ?? BOOKS[0]).name;
}

/**
 * "Which books?": the Demo's first question, a card per set of books (Golden story, Busy company, Short facilities and, on the live API, blank books to set up as your own), each
 * with its one-line help and a Load button; the loaded one is marked "Loaded" and has no button. Load goes through the guarded flow (lib/books-guard.ts): a straight reset on fresh
 * books, the loss preview dialog (components/demo/books-dialog.tsx) when the current books hold work. The card being loaded shows its spinner while the books are replaced (the busy
 * company takes several seconds). The owner's own books are named as theirs, on the blank card. Below `sm` each card is one row (name and help, then the button) so they sit inside
 * the first screen; from `md` they are columns.
 */
export function BooksCards({ view, busy, loading, onLoad }: { view: DemoStoryView; busy: boolean; loading?: BooksId | null; onLoad: (id: BooksId) => void }) {
  const { t } = useI18n();
  const cards = offeredBooks();
  const own = view.books.scenario === OWN;
  return (
    <section aria-labelledby="demo-which-title" className="mb-5" data-testid="demo-books">
      <h2 id="demo-which-title" className="type-card-title text-ink">
        {t("demo.which.title")}
      </h2>
      <p className="mt-0.5 text-sm text-ink-2 max-sm:sr-only">{t("demo.which.sub")}</p>
      <ul className={`mt-3 grid gap-2 sm:gap-3 ${cards.length > 3 ? "md:grid-cols-2 xl:grid-cols-4" : "md:grid-cols-3"}`}>
        {cards.map((b) => {
          // The blank card stands for the owner's own books once they are open.
          const mine = b.id === "blank" && own;
          const loaded = view.books.scenario === b.scenario;
          const name = t(mine ? "demo.card.own" : b.name);
          return (
            <li
              key={b.id}
              className={`card-standard grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-3 gap-y-1 p-4 md:flex md:flex-col ${loaded || mine ? "ring-2 ring-ink" : ""}`}
              data-testid={`demo-scenario-${b.id}`}
              data-loaded={loaded || mine ? "true" : undefined}
              aria-current={loaded || mine ? "true" : undefined}
            >
              <div className="min-w-0">
                <h3 className="text-base font-bold text-ink">{name}</h3>
                <p className="mt-0.5 text-sm text-ink-2" data-testid={`demo-scenario-help-${b.id}`}>
                  {t(mine ? "demo.card.own.help" : b.help)}
                </p>
                {b.id === "busy" ? (
                  <Link href="/" className="motion-press hit mt-1 inline-flex min-h-8 items-center rounded-pill px-1 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11" data-testid="demo-busy-home">
                    {t("demo.card.home")}
                  </Link>
                ) : null}
                {b.id === "blank" && loaded ? (
                  <Link href="/setup" className="motion-press hit mt-1 inline-flex min-h-8 items-center rounded-pill px-1 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11" data-testid="demo-blank-setup">
                    {t("demo.card.setup")}
                  </Link>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center gap-2 md:mt-auto md:pt-3">
                {loaded || mine ? (
                  <StatusPill tone="green" testId={`demo-scenario-loaded-${b.id}`}>
                    {t(mine ? "demo.card.ownLoaded" : "demo.card.loaded")}
                  </StatusPill>
                ) : null}
                {!loaded ? (
                  <Button disabled={busy} loading={loading === b.id} onClick={() => onLoad(b.id)} aria-label={`${t(mine ? "demo.card.restart" : "demo.card.load")}: ${t(b.name)}`} data-testid={`demo-scenario-load-${b.id}`}>
                    {t(mine ? "demo.card.restart" : "demo.card.load")}
                  </Button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
