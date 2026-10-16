"use client";

import "@/app/flow-look.css";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { BOOKS, BooksCards, booksName, type BooksId } from "@/components/demo/books-cards";
import { TodayCard } from "@/components/home/today-card";
import { Disclosure } from "@/components/business/kit";
import { startTour } from "@/components/business/tour";
import { ArrowRightIcon } from "@/components/icons";
import { Badge, Button, ButtonLink, Callout, ErrorState, LoadingBlock, PageHeader } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { getDemoStory, restoreDemo } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { changeBooks, resetScenarioOf, resetTo } from "@/lib/books-guard";
import { goToMore, requestStart, runStoryAction, seenOf } from "@/lib/demo-control";
import { MORE, type MoreId } from "@/lib/demo";
import { reachedOf, resetSession, useDemo } from "@/lib/demo-store";
import { useI18n } from "@/lib/i18n";
import { useAsync } from "@/lib/use-async";
import type { DemoStoryView, StoryScene } from "@/lib/types";

const linkCls = "motion-press hit inline-flex min-h-8 items-center rounded-pill px-1 text-sm font-medium text-brand-700 underline underline-offset-2 hover:bg-brand-50 touch:min-h-11";

function SceneRow({ scene }: { scene: StoryScene }) {
  return (
    <li className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-start gap-x-3 py-3" data-testid={`demo-scene-${scene.id}`} data-state={scene.state}>
      <span className={`grid size-8 place-items-center rounded-pill text-sm font-bold ${scene.state === "done" ? "bg-f-green text-f-green-ink" : scene.state === "current" ? "bg-f-purple-soft text-f-purple-ink" : "bg-subtle text-ink-3"}`} aria-hidden>
        {scene.n}
      </span>
      <div className="min-w-0">
        <h3 className="text-base font-bold text-ink">{scene.label}</h3>
        {scene.state === "done" && scene.result_text ? (
          <p className="mt-0.5 break-words text-sm text-ink-2" data-testid={`demo-result-${scene.id}`}>
            {scene.result_text}
          </p>
        ) : null}
        {scene.state === "done" && scene.proof.length ? (
          <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-ink-3" data-testid={`demo-proof-${scene.id}`}>
            {scene.proof.map((p) => (
              <Link key={p.href} href={p.href} className={linkCls}>
                {p.label}
              </Link>
            ))}
          </p>
        ) : null}
      </div>
      <span className="pt-1 text-supporting font-medium text-ink-3" data-testid={`demo-scene-state-${scene.id}`}>
        {scene.state_text}
      </span>
    </li>
  );
}

/** The operator tools, as the server lists them (the clock, the books, the engine views) plus the optional scenes the page can still run. */
function OperatorTools({ view, busy }: { view: DemoStoryView; busy: boolean }) {
  const { t, te } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const tools = view.operator_tools;
  const act = async (action: string) => {
    // The owner's own books are not a scenario the server resets to: resetting them starts blank books, and the setup opens.
    if (action === "reset") await changeBooks(view.books, resetTo(resetScenarioOf(view.books), router.push, view.books.scenario === "own" ? "/setup" : "/demo"));
  };
  return (
    <Disclosure card testId="demo-operator-tools" summary={<span>{tools.label} <span className="text-supporting font-normal text-ink-3">{tools.hint_text}</span></span>}>
      <div className="space-y-4">
        {tools.groups.map((g) => (
          <div key={g.key} data-testid={`demo-tools-${g.key}`}>
            <p className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{g.label}</p>
            <div className="flex flex-wrap gap-2">
              {g.items.map((item) =>
                item.href ? (
                  <Link key={item.label} href={item.href} className={linkCls}>
                    {item.label}
                  </Link>
                ) : (
                  <Button key={item.label} size="sm" disabled={busy} onClick={() => void act(item.action ?? "")}>
                    {item.label}
                  </Button>
                ),
              )}
            </div>
            {g.note_text ? <p className="mt-1 text-supporting text-ink-3">{g.note_text}</p> : null}
            {/* The day, and any number of days to move it by: the clock group's own control (its fields keep their ids). */}
            {g.key === "clock" ? (
              <fieldset disabled={busy} className="mt-3 min-w-0">
                <TodayCard onAdvanced={() => undefined} folded />
              </fieldset>
            ) : null}
          </div>
        ))}
        {view.main ? (
          <div data-testid="demo-tools-more">
            <p className="mb-1.5 text-meta font-semibold uppercase tracking-wide text-ink-3">{t("demo.tools.more")}</p>
            <ul className="space-y-2">
              {MORE.map((m) => (
                <li key={m.id} className="flex flex-wrap items-center gap-x-3 gap-y-1" data-testid={`more-${m.id}`}>
                  <span className="min-w-0 flex-1 basis-48">
                    <span className="block text-sm font-medium text-ink">{te("more.title", m.id)}</span>
                    <span className="block text-supporting text-ink-3">{te("more.desc", m.id)}</span>
                    {m.replacesBooks ? <span className="block text-supporting font-medium text-warn-fg">{t("more.replaces")}</span> : null}
                  </span>
                  <Button size="sm" disabled={busy || Boolean(m.needsWalk && !demo.rewordedId)} onClick={() => void goToMore(m.id as MoreId, router.push, view.books)} aria-label={`${t("story.show")}: ${te("more.title", m.id)}`} data-testid={`more-run-${m.id}`}>
                    {t("story.show")}
                  </Button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Disclosure>
  );
}

/**
 * The story, read from GET /demo/story: "Which books?" first (three cards, each loaded through the guard), one current scene with the page's only filled button, the six scenes as
 * a list, the one-click restore of the main books while others are loaded, the operator tools folded away and the proof appendix. Every sentence is the server's. The owner's step only opens the approval: nothing here
 * presses it, and the stepper never runs it.
 */
export default function DemoPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const demo = useDemo();
  const reached = reachedOf(demo);
  const seen = seenOf(reached);
  // No page asks for the owner's sign-in by itself: the story is read only for a signed-in owner (a visitor sees "Start demo", whose click asks).
  const signedIn = useAuth().token !== null;
  const story = useAsync(() => (signedIn ? getDemoStory(lang, seen) : Promise.resolve(null)), [lang, seen, signedIn]);
  const [working, setWorking] = useState(false);
  const [restored, setRestored] = useState<string | null>(null);
  // The card whose Load is running: loading the busy company takes several seconds, and the button says it is working.
  const [loading, setLoading] = useState<BooksId | null>(null);
  const busy = demo.busy || working || loading !== null;
  const view = signedIn ? (story.data ?? null) : null;

  // Every card's Load goes through the guard (lib/books-guard.ts): a straight reset on fresh books, else the books dialog (the one every reset uses) lists what the current books lose from
  // a fresh read, and its confirm button is the one thing that replaces them. The server writes the busy company's words while the main books are the ones replaced.
  async function load(id: BooksId) {
    if (!view) return;
    setRestored(null);
    const card = BOOKS.find((b) => b.id === id)!;
    const alt = view.alternate;
    const blank = id === "blank";
    const name = t(blank ? "demo.card.blankTitle" : card.name);
    const server = id === "busy" && view.main;
    setLoading(id);
    try {
      await changeBooks(view.books, resetTo(id === "golden" ? undefined : card.scenario, router.push, blank ? "/setup" : "/demo"), {
        alternate: server,
        prefix: "demo-alternate",
        labels: server
          ? { title: alt.confirm_title_text, confirm: alt.confirm_label, cancel: alt.cancel_label, keeps: alt.keeps_text }
          : { title: t("demo.load.title", { name }), confirm: t("demo.load.confirm", { name }), cancel: t("demo.load.cancel"), keeps: view.books.reset_keeps_text },
        // What the TARGET books are. The server's `alternate.scope_text` describes the busy company only while the main books are loaded; on any other books it counts the
        // books loaded now, so there the card's own help says what the busy company is.
        gives: { heading: t("demo.alt.get"), text: server ? alt.scope_text : t(card.help) },
      });
    } finally {
      setLoading(null);
    }
  }

  async function restore() {
    if (!view) return;
    const alt = view.alternate;
    setWorking(true);
    try {
      await changeBooks(
        view.books,
        async (guard) => {
          const r = await restoreDemo(lang, guard);
          resetSession();
          setRestored(r.restored_text);
        },
        { labels: { title: alt.restore_label, confirm: alt.restore_label, cancel: alt.cancel_label, keeps: alt.restore_text } },
      );
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="flow-f min-w-0" data-testid="demo-page">
      {view?.alternate.loaded ? (
        <div role="status" className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-card border border-warn-line bg-warn-bg px-4 py-3 text-warn-fg" data-testid="demo-loaded-banner">
          <p className="min-w-0 flex-1 basis-64 text-sm font-medium">{view.alternate.loaded_text}</p>
          <Button loading={working} onClick={() => void restore()} data-testid="demo-restore">
            {view.alternate.restore_label}
          </Button>
        </div>
      ) : restored ? (
        <p role="status" className="mb-4 text-sm font-medium text-ok-fg" data-testid="demo-restored">
          {restored}
        </p>
      ) : null}

      <PageHeader
        title={view?.title_text ?? t("story.title")}
        subtitle={view ? <span className="max-sm:sr-only">{view.subtitle_text}</span> : undefined}
        actions={
          <Button variant="ghost" size="sm" onClick={startTour} data-testid="demo-tour">
            {t("tour.replay")}
          </Button>
        }
      />

      {!signedIn ? (
        <section aria-label={t("demo.scene.aria")} className="card-standard p-5" data-testid="demo-current">
          <p className="text-body-lg text-ink-2">{t("demo.idle")}</p>
          <div className="mt-4">
            <Button variant="primary" onClick={requestStart} data-testid="demo-next">
              {t("demo.start")}
              <ArrowRightIcon />
            </Button>
          </div>
        </section>
      ) : story.error ? (
        <ErrorState error={story.error} onRetry={story.reload} />
      ) : !view ? (
        <LoadingBlock rows={4} />
      ) : (
        <>
        <BooksCards view={view} busy={busy} loading={loading} onLoad={(id) => void load(id)} />
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-6">
            <section aria-label={t("demo.scene.aria")} className="card-standard p-5" data-testid="demo-current">
              {view.current ? (
                <>
                  <StatusPill tone="lavender" testId="demo-progress">
                    {view.progress_text}
                  </StatusPill>
                  <h2 className="type-section mt-2 text-balance text-ink">{view.current.title_text}</h2>
                  <p className="mt-1 text-body-lg text-ink-2">{view.current.text}</p>
                  {view.current.owner_text ? (
                    <p className="mt-2 text-sm font-medium text-ink" data-testid="demo-owner-text">
                      {view.current.owner_text}
                    </p>
                  ) : null}
                </>
              ) : (
                <>
                  <StatusPill tone="lavender" testId="demo-progress">
                    {view.progress_text}
                  </StatusPill>
                  {/* All six scenes done: the story says so (never the other books' name). On the other books there is no story: the card names the books loaded. */}
                  <h2 className="type-section mt-2 text-balance text-ink" data-testid="demo-current-title">
                    {view.complete ? t("demo.complete.title") : t(booksName(view.books.scenario))}
                  </h2>
                </>
              )}
              <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2">
                {view.next.href ? (
                  <ButtonLink href={view.next.href} variant="primary" data-testid="demo-next" data-owner={view.next.owner ? "true" : undefined}>
                    {view.next.label}
                    <ArrowRightIcon />
                  </ButtonLink>
                ) : (
                  <Button variant="primary" loading={busy} onClick={() => void runStoryAction(view.next.action ?? "", router.push, view.books)} data-testid="demo-next">
                    {view.complete && view.next.action === "restart" ? t("demo.startAgain") : view.next.label}
                    <ArrowRightIcon />
                  </Button>
                )}
                <p className="min-w-0 flex-1 basis-48 text-sm text-ink-3" data-testid="demo-next-hint">
                  {view.next.hint_text}
                </p>
              </div>
              {demo.error ? (
                <p role="alert" className="mt-3 rounded-tile border border-bad-line bg-bad-bg px-2.5 py-1.5 text-sm text-bad-fg">
                  {demo.error}
                </p>
              ) : null}
              {!demo.busy && demo.running !== null ? (
                <p role="status" className="mt-3 rounded-tile border border-warn-line bg-warn-bg px-2.5 py-1.5 text-sm text-warn-fg" data-testid="story-interrupted">
                  {t("demo.interrupted", { n: demo.running + 1 })}
                </p>
              ) : null}
            </section>

            {view.story_available ? (
              <section aria-label={t("demo.scenes.aria")} data-testid="story">
                <ol className="divide-y divide-line">
                  {view.scenes.map((s) => (
                    <SceneRow key={s.id} scene={s} />
                  ))}
                </ol>
              </section>
            ) : null}

            <section aria-labelledby="demo-proof-title" className="border-t border-line pt-4" data-testid="demo-proof">
              <h2 id="demo-proof-title" className="type-card-title text-ink">
                {view.proof.title_text}
              </h2>
              <p className="mt-1 text-sm text-ink-2">{view.proof.text}</p>
              <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5">
                {view.proof.links.map((l) => (
                  <Link key={l.href} href={l.href} className={linkCls}>
                    {l.label}
                  </Link>
                ))}
              </p>
              {view.proof.chain.chain_text ? (
                <div className="mt-1">
                  <span data-testid="demo-chain" data-valid={view.proof.chain.chain_valid ? "true" : "false"}>
                    <Badge tone={view.proof.chain.chain_valid ? "ok" : "bad"}>{view.proof.chain.chain_text}</Badge>
                  </span>
                  <p className="mt-1 text-sm text-ink-3" data-testid="demo-chain-scope">
                    {view.proof.chain.chain_scope_text}
                  </p>
                </div>
              ) : null}
            </section>
          </div>

          <div className="min-w-0 space-y-6">
            <OperatorTools view={view} busy={busy} />
            <Callout tone="info">
              <p>{view.simulation_text}</p>
            </Callout>
          </div>
        </div>
        </>
      )}
    </div>
  );
}
