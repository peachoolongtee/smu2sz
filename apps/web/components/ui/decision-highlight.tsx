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
  children,
  testId,
  labelId,
}: {
  eyebrow: string;
  title: string;
  line?: string | null;
  facts?: { label: string; value: string }[];
  children?: ReactNode;
  testId?: string;
  labelId?: string;
}) {
  return (
    <section aria-labelledby={labelId} data-testid={testId} className="motion-reveal min-w-0 rounded-decision bg-canvas px-5 py-5 sm:px-7 sm:py-6">
      <p className="text-supporting font-bold text-brand-700" data-testid="home-action-eyebrow">
        {eyebrow}
      </p>
      <h2 id={labelId} className="mt-1.5 text-pretty font-display text-[19px] font-extrabold leading-tight tracking-[-0.02em] text-ink sm:text-[26px]" data-testid="home-action-title">
        {title}
      </h2>
      {line ? (
        <p className="mt-1.5 max-w-3xl text-pretty text-sm text-ink-2 max-sm:hidden" data-testid="home-action-text">
          {line}
        </p>
      ) : null}
      {facts?.length ? (
        <dl className="mt-4 grid gap-x-0 gap-y-3 border-t border-line-strong pt-3 sm:grid-cols-[auto_minmax(0,1.6fr)_auto]" data-testid="hv2-action-facts">
          {facts.map((f, i) => (
            <div key={f.label} className={`min-w-0 sm:pr-6 ${i > 0 ? "sm:border-l sm:border-line-strong sm:pl-6" : ""}`}>
              <dt className="text-supporting text-ink-3">{f.label}</dt>
              <dd className="mt-0.5 text-sm font-bold text-ink sm:text-[15px] tabular-nums">{f.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {children ? <div className="mt-4">{children}</div> : null}
    </section>
  );
}

/**
 * While a customer or a deal is the focus the recommendation collapses to one row on the canvas: a bad-tone dot, the label, the company's sentence, its cost, and an OUTLINED
 * button (never a text link: a decision level keeps a real button). The page's filled button belongs to the selection.
 */
export function HealthBand({ label, sentence, fact, children, testId }: { label: string; sentence: string; fact?: { label: string; value: string } | null; children?: ReactNode; testId?: string }) {
  return (
    <section aria-label={label} data-testid={testId} className="motion-reveal flex min-w-0 flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-card bg-canvas py-3 pl-4 pr-3">
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
