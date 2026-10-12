"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "@/components/icons";
import { PartialRead } from "@/components/business/freshness";
import { Card, ButtonLink, PageHeader, textLinkClass } from "@/components/ui";
import { fromCustomer } from "@/lib/customer-href";
import { useI18n } from "@/lib/i18n";
import { contextQuery, type CustomerContext } from "@/lib/customer-href";
import type { CustomerOverviewView, OverviewAction, OverviewFigure, OverviewHistoryRow, OverviewRow, OverviewTone } from "@/lib/types";

/** The colour a tone gives a figure or a value; a status is always said in the server's words as well, so colour is never the only channel. */
const toneText: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

/** A quiet text link inside a sentence or a row: brand text, underlined, 14 px. */
const inlineLink = "font-bold text-brand-700 underline underline-offset-2 hover:text-brand-600";

function Figure({ figure }: { figure: OverviewFigure }) {
  return (
    <div className="min-w-0 lg:border-r lg:border-line lg:px-5 lg:first:pl-0 lg:last:border-r-0" data-testid={`customer-figure-${figure.key}`}>
      <dt className="text-supporting font-extrabold uppercase tracking-[0.08em] text-ink-3">{figure.label}</dt>
      <dd className={`mt-1 break-words type-value font-display ${toneText[figure.tone]}`} data-testid={`customer-figure-${figure.key}-value`}>
        {figure.value_display}
      </dd>
      <dd className="mt-0.5 break-words text-sm text-ink-2" data-testid={`customer-figure-${figure.key}-note`}>
        {figure.note}
      </dd>
    </div>
  );
}

/** The decision card: the one place on the page that asks the owner for something. A decision waiting leads with its primary; none waiting says so and keeps the other two links. */
function Decision({ view }: { view: CustomerOverviewView }) {
  const { t } = useI18n();
  const decision = view.decision;
  const rest: OverviewAction[] = decision ? decision.secondary : (view.actions ?? []);
  const links = rest.map((a) => (
    <ButtonLink key={a.key} href={a.key === "stress" ? fromCustomer(a.href, view.customer_id) : a.href} data-testid={`customer-action-${a.key}`}>
      {a.label}
    </ButtonLink>
  ));
  if (!decision) {
    if (!view.none_text && !rest.length) return null;
    return (
      <section aria-label={t("customer.decision")} className="motion-reveal flex flex-wrap items-center justify-between gap-x-8 gap-y-3" data-testid="customer-decision-none">
        {view.none_text ? <p className="min-w-0 flex-[2_1_20rem] text-pretty text-sm text-ink-2">{view.none_text}</p> : null}
        {links.length ? <div className="flex flex-wrap gap-2">{links}</div> : null}
      </section>
    );
  }
  // Source order is the reading and the tab order: the question, the actions, then what FLOW may do alone (so the actions stay in a phone's first screen).
  // From `lg` the actions sit beside the question and the authority line under it.
  return (
    <Card tone="warn" id="customer-decision" labelledBy="customer-decision-title">
      <div className="grid gap-x-8 gap-y-4 lg:grid-cols-[minmax(0,1fr)_auto]" data-testid="customer-decision">
        <div className="min-w-0 lg:col-start-1 lg:row-start-1">
          <h2 id="customer-decision-title" className="text-meta font-extrabold uppercase tracking-[0.08em] text-warn-fg">
            {decision.eyebrow}
          </h2>
          <p className="mt-1 text-pretty font-display text-lg font-extrabold leading-snug text-ink" data-testid="customer-decision-text">
            {decision.text}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:self-center">
          <ButtonLink href={decision.primary.href} variant="primary" data-testid="customer-decision-primary">
            {decision.primary.label}
          </ButtonLink>
          {links}
        </div>
        {decision.authority_text ? (
          <p className="border-l-2 border-line-strong pl-3 text-sm text-ink-2 lg:col-start-1 lg:row-start-2" data-testid="customer-decision-authority">
            {decision.authority_text}
          </p>
        ) : null}
      </div>
    </Card>
  );
}

/** A long value is a sentence, not a figure: only its first clause (to the first semicolon) is bold, the rest is regular weight; a long value with no clause is regular throughout. */
const LONG_VALUE = 40;
function splitValue(value: string): [string, string] {
  if (value.length <= LONG_VALUE) return [value, ""];
  const at = value.search(/[;；]/);
  return at > 0 ? [value.slice(0, at), value.slice(at)] : ["", value];
}

/** Labelled rows, a hairline between: the label quiet, the value in the row's tone, the server's note beneath it. */
function Rows({ rows, testId }: { rows: OverviewRow[]; testId: string }) {
  return (
    <dl className="divide-y divide-line" data-testid={testId}>
      {rows.map((r) => (
        <div key={r.key} className="grid gap-x-4 gap-y-0.5 py-2.5 sm:grid-cols-[minmax(0,9.5rem)_minmax(0,1fr)]" data-testid={`${testId}-${r.key}`}>
          <dt className="text-sm text-ink-3">{r.label}</dt>
          <dd className="min-w-0 break-words text-sm">
            <Value row={r} />
            {r.note ? <span className="mt-0.5 block text-ink-2">{r.note}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Value({ row }: { row: OverviewRow }) {
  const [lead, rest] = splitValue(row.value_display);
  return (
    <span className={`tabular-nums ${toneText[row.tone]}`}>
      {lead ? <span className="font-bold">{lead}</span> : null}
      {rest}
    </span>
  );
}

/** What the server says for a fact the owner has not entered, in both languages. */
const NOT_ENTERED = new Set(["not entered yet", "尚未填写"]);

/** The economics rows worth showing: with nowhere to enter a fact (`edit_href` is null) a row that only says "not entered yet" is a dead end and is left out. */
function shownEconomics(view: CustomerOverviewView): OverviewRow[] {
  const rows = view.economics ?? [];
  return view.edit_href ? rows : rows.filter((r) => !NOT_ENTERED.has(r.value_display.trim()));
}

function Economics({ view, ctx }: { view: CustomerOverviewView; ctx: CustomerContext }) {
  const { t } = useI18n();
  const rows = shownEconomics(view);
  if (!rows.length) return null;
  return (
    <Card flat id="customer-economics" title={t("customer.economics")}>
      <Rows rows={rows} testId="customer-economics-rows" />
      {view.economics_note || (view.edit_href && view.edit_label) ? (
        <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-economics-note">
          {view.economics_note}
          {view.edit_href && view.edit_label ? (
            <>
              {view.economics_note ? " " : null}
              <Link href={withContext(view.edit_href, ctx)} className={inlineLink} data-testid="customer-edit">
                {view.edit_label}
              </Link>
            </>
          ) : null}
        </p>
      ) : null}
    </Card>
  );
}

/** A link that carries the context this page was opened with (`decision`, `path`, `invoice`), so the page it opens can find its way back. */
function withContext(href: string, ctx: CustomerContext): string {
  const query = contextQuery(ctx);
  return query ? `${href}${href.includes("?") ? "&" : "?"}${query.slice(1)}` : href;
}

/** The exposure panel; while the read is off the server's `note` says why, in place of the rows. */
function Exposure({ view }: { view: CustomerOverviewView }) {
  const { t } = useI18n();
  const exposure = view.exposure;
  if (!exposure && !view.note) return null;
  return (
    <Card flat id="customer-exposure" title={t("customer.exposure")}>
      {exposure ? (
        <>
          <Rows rows={exposure.rows} testId="customer-exposure-rows" />
          {exposure.same_figures_note ? (
            <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-exposure-note">
              {exposure.same_figures_note}
            </p>
          ) : null}
        </>
      ) : (
        <p className="py-2.5 text-pretty text-sm text-ink-2" data-testid="customer-exposure-off">
          {view.note}
        </p>
      )}
    </Card>
  );
}

function History({ rows }: { rows: OverviewHistoryRow[] }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  return (
    <Card flat id="customer-history" title={t("customer.history")}>
      <ul className="divide-y divide-line" data-testid="customer-history-rows">
        {rows.map((h, i) => (
          <li key={i} className="grid gap-x-4 gap-y-0.5 py-2.5 text-sm sm:grid-cols-[7.5rem_minmax(0,1fr)_auto] sm:items-baseline" data-testid="customer-history-row">
            <span className="text-ink-3">{h.when_text}</span>
            <span className="min-w-0 break-words text-ink">{h.text}</span>
            {h.href ? (
              <Link href={h.href} className={`${textLinkClass} -ml-2 justify-self-start text-sm sm:ml-0 sm:justify-self-end`}>
                {h.link_label ?? t("customer.history.open")}
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * A customer's overview in the order of the board: the eyebrow and the server's back link, the name and one sentence, the four figures, the one
 * commercial decision (or the line that none waits, with the two other links), the economics and the exposure side by side, and the history. Each
 * section is drawn only when the server sent it. Every word, figure and link is the server's; the page decides nothing.
 */
export function CustomerOverview({ view, onRetry, ctx = {} }: { view: CustomerOverviewView; onRetry: () => void; ctx?: CustomerContext }) {
  const { t } = useI18n();
  const back = view.context?.back;
  return (
    <div className="space-y-6" data-testid="customer-overview">
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p className="text-meta font-extrabold uppercase tracking-[0.08em] text-ink-3">{t("customer.title")}</p>
          {back ? (
            <Link href={back.href} className="motion-press hit -mr-2 inline-flex min-h-8 items-center gap-1 rounded-pill px-2 text-sm font-bold text-brand-700 underline underline-offset-2 hover:bg-brand-50" data-testid="customer-back">
              <ArrowLeftIcon width={14} height={14} />
              {back.label}
            </Link>
          ) : null}
        </div>
        <PageHeader title={view.name} subtitle={view.summary_text} />
      </div>
      <PartialRead partial={view.partial} onRetry={onRetry} />
      {view.figures?.length ? (
        <section aria-label={t("customer.figures")} data-testid="customer-figures">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-y border-line py-3 lg:grid-cols-4 lg:gap-x-0 lg:gap-y-4 lg:py-4">
            {view.figures.map((f) => (
              <Figure key={f.key} figure={f} />
            ))}
          </dl>
        </section>
      ) : null}
      <Decision view={view} />
      <div className={`grid gap-x-10 gap-y-6 ${shownEconomics(view).length && (view.exposure || view.note) ? "lg:grid-cols-2" : ""}`}>
        <Economics view={view} ctx={ctx} />
        <Exposure view={view} />
      </div>
      <History rows={view.history ?? []} />
    </div>
  );
}
