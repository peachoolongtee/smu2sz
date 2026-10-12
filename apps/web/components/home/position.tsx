"use client";

import { Disclosure } from "@/components/business/kit";
import { Stat, type Tone } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import type { HomeTone, HomeView } from "@/lib/types";

/** The dot beside the status word (green when the server calls it fine, amber, red) and the figure's colour: amber at zero room, red below, nothing at all when fine (status colour is for status). */
const DOT: Record<HomeTone, string> = { ok: "bg-ok-solid", warn: "bg-warn-solid", bad: "bg-bad-solid", neutral: "bg-ink-3" };
const FIGURE: Record<HomeTone, Tone> = { ok: "neutral", warn: "warn", bad: "bad", neutral: "neutral" };

/**
 * Section 1 of Home, the position: a tone dot and the status word in sentence case ("· read today" after it), the one `h1` (the heading that holds
 * while the forecast depends on landings and receipts, else the plain headline), the note under it with the assumptions behind a fold, and three
 * fact tiles (label, the figure, a note). The tone colours a tile's figure only. Every word and figure is the server's.
 */
export function HomePosition({ h }: { h: HomeView }) {
  const { t } = useI18n();
  const cash = h.cash;
  const tone = cash.status_tone ?? "neutral";
  const heading = cash.headline_conditional || h.headline;
  const facts = cash.facts ?? [];
  const assumptions = cash.assumptions ?? [];
  return (
    <header aria-labelledby="home-status-title" className="motion-reveal flex flex-col items-start gap-2 sm:gap-2.5 short:gap-2" data-testid="home-status" data-status={h.status}>
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm font-semibold text-ink-2">
        <span aria-hidden className={`size-2 shrink-0 rounded-pill ${DOT[tone]}`} data-testid="home-status-dot" />
        <span className="text-ink" data-testid="home-status-word">
          {cash.status_word}
        </span>
        {cash.last_read_when ? (
          <>
            <span aria-hidden className="font-normal text-ink-3">
              ·
            </span>
            <span className="font-normal text-ink-3" data-testid="home-read-when">
              {t("biz.readWhen", { when: cash.last_read_when })}
            </span>
          </>
        ) : null}
      </p>
      <h1 id="home-status-title" className="max-w-4xl text-balance font-display text-2xl font-extrabold leading-[1.15] tracking-[-0.025em] text-ink sm:text-[2.125rem]" data-testid="home-headline">
        {heading}
      </h1>
      {cash.headline_note ? (
        <p className="max-w-3xl text-pretty text-[0.9375rem] leading-snug text-ink-2 sm:leading-normal" data-testid="home-note">
          {cash.headline_note}
        </p>
      ) : null}
      {assumptions.length ? (
        <Disclosure testId="home-assumptions" summary={t("home.hy.assumptions")} className="max-w-3xl -mt-1">
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
            {assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </Disclosure>
      ) : null}
      {facts.length ? (
        <dl aria-label={t("home.hy.facts")} className="mt-1 grid w-full gap-1.5 sm:grid-cols-3 sm:gap-3" data-testid="home-facts">
          {facts.map((f) => (
            <Stat key={f.key} row size="lg" label={f.label} value={f.value_short} caption={f.note} tone={FIGURE[f.tone ?? "neutral"]} testId={`home-fact-${f.key}`} rootTestId={`home-fact-tile-${f.key}`} />
          ))}
        </dl>
      ) : null}
    </header>
  );
}
