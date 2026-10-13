import type { ReactNode } from "react";

/**
 * The page's one recommendation, as a tinted block (the canvas fill, radius 16, no border and no shadow): an eyebrow in the brand tone, a display title, one line, up to three
 * facts (a 13 px label over a 15 px value, hairlines between) and then its `ActionGroup`. It is the only decision surface on Home; there is one filled button on the page.
 */
export function DecisionHighlight({
  eyebrow,
  title,
  line,
  facts,
  hero,
  middle,
  stackMiddle = false,
  note,
  children,
  testId,
  labelId,
}: {
  eyebrow: string;
  title: string;
  line?: string | null;
  facts?: { label: string; value: string }[];
  /** The hero fact (the cost to the owner): a 13 px label, the figure at 28 px with a 2 px brand rule under it, and its basis word beside it in the quiet ink. */
  hero?: { label: string; value: string; basis?: string | null; testId?: string };
  /** Beside the hero fact: the funding, as a timeline or as text. */
  middle?: ReactNode;
  /** On a phone the middle goes under the hero fact (a list of rows) instead of beside it (a sentence). */
  stackMiddle?: boolean;
  /** One quiet line under the actions (who approves). */
  note?: ReactNode;
  children?: ReactNode;
  testId?: string;
  labelId?: string;
}) {
  return (
    <section aria-labelledby={labelId} data-testid={testId} className="motion-reveal min-w-0 rounded-decision bg-surface px-4 py-4 sm:px-7 sm:py-6">
      <p className="text-supporting font-bold leading-4 text-brand-700 sm:leading-normal" data-testid="home-action-eyebrow">
        {eyebrow}
      </p>
      <h2 id={labelId} className="mt-1.5 text-pretty font-display text-[18px] font-extrabold leading-tight tracking-[-0.02em] text-ink sm:text-[26px]" data-testid="home-action-title">
        {title}
      </h2>
      {line ? (
        <p className="mt-1.5 max-w-3xl text-pretty text-sm text-ink-2 max-sm:hidden" data-testid="home-action-text">
          {line}
        </p>
      ) : null}
      {hero ? (
        <div className={`mt-3 grid gap-x-5 gap-y-3 border-t border-line-strong pt-2.5 sm:mt-4 sm:grid-cols-[auto_minmax(0,1fr)] sm:gap-x-8 sm:gap-y-4 sm:pt-3 ${stackMiddle ? "" : "max-sm:grid-cols-[auto_minmax(0,1fr)]"}`} data-testid="hv2-action-facts">
          <div className="min-w-0">
            <p className="text-supporting text-ink-3">{hero.label}</p>
            <p className="mt-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
              <span className="inline-block border-b-2 border-brand-600 pb-1 font-display text-[24px] font-bold leading-none sm:text-[28px] tracking-[-0.02em] tabular-nums text-ink" data-testid={hero.testId ?? "hv2-hero-value"}>
                {hero.value}
              </span>
              {hero.basis ? <span className="text-supporting text-ink-2">{hero.basis}</span> : null}
            </p>
          </div>
          {middle ? <div className={`min-w-0 sm:border-l sm:border-line-strong sm:pl-8 ${stackMiddle ? "" : "max-sm:border-l max-sm:border-line-strong max-sm:pl-4"}`}>{middle}</div> : null}
        </div>
      ) : null}
      {!hero && facts?.length ? (
        <dl className="mt-3 grid grid-cols-2 gap-x-0 gap-y-2.5 border-t border-line-strong pt-2.5 sm:mt-4 sm:grid-cols-[auto_minmax(0,1.6fr)_auto] sm:gap-y-3 sm:pt-3" data-testid="hv2-action-facts">
          {facts.map((f, i) => (
            <div key={f.label} className={`min-w-0 sm:pr-6 ${i > 0 ? "sm:border-l sm:border-line-strong sm:pl-6" : ""} ${i === 1 ? "max-sm:order-last max-sm:col-span-2" : i === 2 ? "max-sm:border-l max-sm:border-line-strong max-sm:pl-4" : ""}`}>
              <dt className="text-supporting text-ink-3">{f.label}</dt>
              <dd className="mt-0.5 text-sm font-bold text-ink sm:text-[15px] tabular-nums">{f.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children ? <div className="mt-3 sm:mt-4">{children}</div> : null}
      {note ? <div className="mt-3 text-supporting text-ink-2">{note}</div> : null}
    </section>
  );
}

/**
 * While a customer or a deal is the focus the recommendation collapses to one row on the canvas: a bad-tone dot, the label, the company's sentence, its cost, and an OUTLINED
 * button (never a text link: a decision level keeps a real button). The page's filled button belongs to the selection.
 */
export function HealthBand({ label, sentence, fact, children, testId }: { label: string; sentence: string; fact?: { label: string; value: string } | null; children?: ReactNode; testId?: string }) {
  return (
    <section aria-label={label} data-testid={testId} className="motion-reveal flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-card bg-surface py-3 pl-4 pr-3">
      <div className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-3 gap-y-0.5 text-sm text-ink-2">
        <span aria-hidden className="size-2 shrink-0 translate-y-[-1px] rounded-pill bg-bad-solid" />
        <b className="font-bold text-ink">{label}</b>
        <span className="min-w-0" data-testid="home-action-title">
          {sentence}
        </span>
        {fact ? (
          <span className="whitespace-nowrap text-supporting text-ink-3">
            {fact.label} <b className="font-bold tabular-nums text-ink-2">{fact.value}</b>
          </span>
        ) : null}
      </div>
      {children}
    </section>
  );
}
