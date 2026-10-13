"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "@/components/icons";
import { PartialRead } from "@/components/business/freshness";
import { ButtonLink, PageHeader, textLinkClass } from "@/components/ui";
import { ActionGroup } from "@/components/ui/action-group";
import { OpenSection } from "@/components/ui/open-section";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import { fromCustomer, contextQuery, type CustomerContext } from "@/lib/customer-href";
import { useI18n } from "@/lib/i18n";
import type { CustomerOverviewView, OverviewAction, OverviewFigure, OverviewHistoryRow, OverviewRow, OverviewTone } from "@/lib/types";
import { focusOf, OutstandingWork } from "./outstanding";
import type { Queue } from "@/components/deals/flow/queue-model";
import { rowsOfCustomer } from "./outstanding";

/** The colour a tone gives a figure or a value; a status is always said in the server's words as well, so colour is never the only channel. */
const toneText: Record<OverviewTone, string> = { neutral: "text-ink", ok: "text-ok-fg", warn: "text-warn-fg", bad: "text-bad-fg" };

/** A quiet text link inside a sentence or a row: brand text, underlined, 14 px. */
const inlineLink = "font-bold text-brand-700 underline underline-offset-2 hover:text-brand-600";

/** The figure's state, in the one vocabulary: the mark and the server's word (`state` is a key of the twelve; a word the browser does not know draws no state). */
function FigureState({ figure }: { figure: OverviewFigure }) {
  const key = stateKey(figure.state);
  if (!key || !figure.state_text) return null;
  return (
    <p className="mt-1" data-testid={`customer-figure-${figure.key}-state`} data-state={key}>
      <StateWord state={key}>{figure.state_text}</StateWord>
    </p>
  );
}

/**
 * One of the four figures. The first is a year's gross contribution, said as that ("Estimated annual gross contribution", never "relationship value") with where it comes from
 * right beside it (the figure's own `provenance_text`, else the economics rows' words: "projected from your books", "assumed for the Demo, not confirmed by you"); the others carry
 * their state in the state vocabulary (planned, arranged, received, overdue ...) beside the server's note.
 */
function Figure({ figure, provenance }: { figure: OverviewFigure; provenance: string | null }) {
  const { t } = useI18n();
  const contribution = figure.key === "value";
  return (
    <div className="min-w-0 lg:border-r lg:border-line lg:px-5 lg:first:pl-0 lg:last:border-r-0" data-testid={`customer-figure-${figure.key}`}>
      <dt className="text-supporting font-bold text-ink-3">{contribution ? t("customer.fig.contribution") : figure.label}</dt>
      <dd className={`mt-1 break-words type-value font-display ${toneText[figure.tone]}`} data-testid={`customer-figure-${figure.key}-value`}>
        {figure.value_display}
      </dd>
      <dd className="mt-0.5 break-words text-sm text-ink-2" data-testid={`customer-figure-${figure.key}-note`}>
        {figure.note}
      </dd>
      {contribution && provenance ? (
        <dd className="mt-0.5 break-words text-supporting font-medium text-warn-fg" data-testid="customer-figure-value-provenance">
          {provenance}
        </dd>
      ) : null}
      <FigureState figure={figure} />
    </div>
  );
}

/** Where the contribution comes from: the figure's own word, else the weakest link of its economics (the margin's note, then the sales'), the server's words as they are. */
function provenanceOf(view: CustomerOverviewView): string | null {
  const own = view.figures?.find((f) => f.key === "value")?.provenance_text;
  if (own) return own;
  const rows = view.economics ?? [];
  return rows.find((r) => r.key === "gross_margin")?.note ?? rows.find((r) => r.key === "annual_sales")?.note ?? null;
}

/**
 * The commercial decision in focus: what waits (the server's question), the one filled primary and the other two links, then who may do it. The primary is the page's only
 * filled button; none waiting says so and keeps the links as outlined buttons.
 */
function Focus({ view }: { view: CustomerOverviewView }) {
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
      <section aria-label={t("customer.decision")} className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3" data-testid="customer-decision-none">
        {view.none_text ? <p className="min-w-0 flex-[2_1_20rem] text-pretty text-sm text-ink-2">{view.none_text}</p> : null}
        {links.length ? <ActionGroup>{links}</ActionGroup> : null}
      </section>
    );
  }
  return (
    <section aria-labelledby="customer-decision-title" className="mt-4 border-t border-line pt-4" id="customer-decision" data-testid="customer-decision">
      <h3 id="customer-decision-title" className="text-supporting font-bold text-warn-fg">
        {decision.eyebrow}
      </h3>
      <p className="mt-1 text-pretty font-display text-lg font-extrabold leading-snug text-ink" data-testid="customer-decision-text">
        {decision.text}
      </p>
      <ActionGroup className="mt-3" label={t("customer.decision")}>
        <ButtonLink href={decision.primary.href} variant="primary" data-testid="customer-decision-primary">
          {decision.primary.label}
        </ButtonLink>
        {links}
      </ActionGroup>
      {decision.authority_text ? (
        <p className="mt-3 border-l-2 border-line-strong pl-3 text-sm text-ink-2" data-testid="customer-decision-authority">
          {decision.authority_text}
        </p>
      ) : null}
    </section>
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
            {r.note ? <span className="mt-0.5 block text-supporting text-ink-2">{r.note}</span> : null}
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
    <OpenSection first id="customer-economics" title={t("customer.economics")} testId="customer-economics">
      <Rows rows={rows} testId="customer-economics-rows" />
      {view.economics_note || (view.edit_href && view.edit_label) ? (
        <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-economics-note">
          {view.economics_note}
          {/* The inputs sheet is the edit route, and the server names it only while the economics are on (hidden otherwise). */}
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
    </OpenSection>
  );
}

/** A link that carries the context this page was opened with, so the page it opens can find its way back. */
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
    <OpenSection first id="customer-exposure" title={t("customer.exposure")} testId="customer-exposure">
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
    </OpenSection>
  );
}

function History({ rows }: { rows: OverviewHistoryRow[] }) {
  const { t } = useI18n();
  if (!rows.length) return null;
  return (
    <OpenSection first id="customer-history" title={t("customer.history")} testId="customer-history">
      <ul className="divide-y divide-line" data-testid="customer-history-rows">
        {rows.map((h, i) => {
          const key = stateKey(h.state);
          return (
            <li key={i} className="grid gap-x-4 gap-y-0.5 py-2.5 text-sm sm:grid-cols-[7.5rem_minmax(0,1fr)_auto] sm:items-baseline" data-testid="customer-history-row">
              <span className="text-ink-3">{h.when_text}</span>
              <span className="min-w-0 break-words text-ink">
                {h.text}
                {key && h.state_text ? (
                  <span className="mt-0.5 block" data-testid="customer-history-state" data-state={key}>
                    <StateWord state={key}>{h.state_text}</StateWord>
                  </span>
                ) : null}
              </span>
              {h.href ? (
                <Link href={h.href} className={`${textLinkClass} -ml-2 justify-self-start text-sm sm:ml-0 sm:justify-self-end`}>
                  {h.link_label ?? t("customer.history.open")}
                </Link>
              ) : null}
            </li>
          );
        })}
      </ul>
    </OpenSection>
  );
}

/**
 * A customer's overview (tickets #126, #134): the eyebrow and the server's back link (written from the origin the owner came from), the name and one sentence, the four figures
 * (the first a year's estimated gross contribution with its provenance beside it, the others with their state), what is outstanding with this customer as a short list from the queue
 * with one task in focus and the commercial decision's one filled primary, the economics and the exposure, and the history. Each section is drawn only when the server sent it.
 * Every word, figure and link is the server's; the page decides nothing.
 */
export function CustomerOverview({ view, onRetry, ctx = {}, queue }: { view: CustomerOverviewView; onRetry: () => void; ctx?: CustomerContext; queue?: Queue | null }) {
  const { t } = useI18n();
  const back = view.context?.back;
  const tasks = rowsOfCustomer(queue, view.customer_id);
  const focus = focusOf(tasks, ctx.decision ?? view.context?.deal ?? null);
  const hasEconomics = shownEconomics(view).length > 0;
  const hasExposure = Boolean(view.exposure || view.note);
  return (
    <div className="flow-f space-y-5" data-testid="customer-overview">
      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
          <p className="text-supporting font-bold text-ink-3">{t("customer.title")}</p>
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
        <section aria-label={t("customer.figures")} className="flow-card p-5 sm:p-6" data-testid="customer-figures">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 lg:grid-cols-4 lg:gap-x-0">
            {view.figures.map((f) => (
              <Figure key={f.key} figure={f} provenance={provenanceOf(view)} />
            ))}
          </dl>
        </section>
      ) : null}
      {tasks.length || view.decision || view.none_text || (view.actions ?? []).length ? (
        <section aria-labelledby="customer-work-title" className="flow-card p-5 sm:p-6" data-testid="customer-work">
          <h2 id="customer-work-title" className="type-section mb-3 text-ink">
            {t("customer.outstanding", { name: view.name })}
          </h2>
          <OutstandingWork customerId={view.customer_id} rows={tasks} focusKey={focus?.row.key ?? null} name={view.name} />
          <Focus view={view} />
        </section>
      ) : null}
      {hasEconomics || hasExposure ? (
        <div className={`grid gap-5 ${hasEconomics && hasExposure ? "lg:grid-cols-2" : ""}`}>
          {hasEconomics ? (
            <div className="flow-card p-5 sm:p-6">
              <Economics view={view} ctx={ctx} />
            </div>
          ) : null}
          {hasExposure ? (
            <div className="flow-card p-5 sm:p-6">
              <Exposure view={view} />
            </div>
          ) : null}
        </div>
      ) : null}
      {view.history?.length ? (
        <div className="flow-card p-5 sm:p-6">
          <History rows={view.history} />
        </div>
      ) : null}
    </div>
  );
}
