"use client";

import Link from "next/link";
import { ArrowLeftIcon } from "@/components/icons";
import { PartialRead } from "@/components/business/freshness";
import { isNegotiation, lifecyclePill, rowPill } from "@/components/deals/flow/deal-model";
import type { PillTone } from "@/components/ui/status-pill";
import { useMode } from "@/lib/mode";
import { rowDecision, type Queue } from "@/components/deals/flow/queue-model";
import { ButtonLink, PageHeader, textLinkClass } from "@/components/ui";
import { StatusPill } from "@/components/ui/status-pill";
import { reviewHref, selectionHref } from "@/lib/selection";
import { flowOf } from "@/lib/customer-r2";
import { ExposureTable } from "./exposure-table";
import { ReceivableFlowCard } from "./receivable-flow";
import { ActionGroup } from "@/components/ui/action-group";
import { OpenSection } from "@/components/ui/open-section";
import { StateWord } from "@/components/ui/state-word";
import { stateKey } from "@/components/ui/state-word-model";
import { fromCustomer, contextQuery, type CustomerContext } from "@/lib/customer-href";
import { useI18n } from "@/lib/i18n";
import type { CustomerOverviewView, OverviewAction, OverviewFigure, OverviewHistoryRow, OverviewRow, OverviewTone } from "@/lib/types";
import { AllTasksLink, focusOf, OutstandingWork } from "./outstanding";
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
    <dd className="mt-1" data-testid={`customer-figure-${figure.key}-state`} data-state={key}>
      <StateWord state={key}>{figure.state_text}</StateWord>
    </dd>
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
  // A figure with no value, no note and no state has nothing to say: it is left out, not drawn as a bare label.
  if (!figure.value_display && !figure.note && !figure.state_text) return null;
  return (
    <div className="min-w-0 lg:border-r lg:border-line lg:px-5 lg:first:pl-0 lg:last:border-r-0" data-testid={`customer-figure-${figure.key}`}>
      <dt className="text-supporting font-bold text-ink-3">{contribution ? t("customer.fig.contribution") : figure.label}</dt>
      {figure.value_display ? (
        <dd className={`mt-1 break-words type-value font-display ${toneText[figure.tone]}`} data-testid={`customer-figure-${figure.key}-value`}>
          {figure.value_display}
        </dd>
      ) : null}
      <dd className="mt-0.5 break-words text-sm text-ink-2" data-testid={`customer-figure-${figure.key}-note`}>
        {figure.note}
      </dd>
      {typeof figure.proportion === "number" && figure.proportion >= 0 ? (
        <dd className="mt-1.5">
          <div className="h-1.5 overflow-hidden rounded-pill bg-track" role="img" aria-label={t("customer.share.bar", { label: figure.label })} data-testid={`customer-figure-${figure.key}-bar`}>
            <span className="block h-full rounded-pill bg-f-purple" style={{ width: `${Math.min(figure.proportion, 1) * 100}%` }} />
          </div>
        </dd>
      ) : null}
      {contribution && provenance ? (
        <dd className="mt-0.5 break-words text-supporting font-medium text-warn-fg" data-testid="customer-figure-value-provenance">
          {provenance}
        </dd>
      ) : null}
      <FigureState figure={figure} />
    </div>
  );
}

/**
 * Where the contribution comes from, said beside it: the figure's own word (`provenance_text`); else the weakest link of its economics (the margin's note, then the sales') unless
 * the figure's own note already says it ("a year, estimated contribution; margin assumed for the Demo, not confirmed by you"). The server's words as they are.
 */
function provenanceOf(view: CustomerOverviewView): string | null {
  const figure = view.figures?.find((f) => f.key === "value");
  if (figure?.provenance_text) return figure.provenance_text;
  const rows = view.economics ?? [];
  const word = rows.find((r) => r.key === "gross_margin")?.note ?? rows.find((r) => r.key === "annual_sales")?.note ?? null;
  return word && !(figure?.note ?? "").includes(word) ? word : null;
}

/** What the action block is about: the selected negotiation's own words (its subject, its lifecycle pill, what FLOW recommends), where "Review decision" leads and whether the owner's turn is next. */
interface Selected {
  key: string;
  subject: string;
  pill: { tone: PillTone; text: string; lifecycle: string | null };
  recommends: string | null;
  href: string;
  /** The server's label for the button when it speaks for this negotiation ("Review the counter", "Read the offer"); null is the dictionary's "Review decision". */
  label: string | null;
  closed: boolean;
}

/**
 * The primary action block (round two): the SELECTED negotiation's heading, lifecycle status and recommendation (the one the address names, else the first that needs the owner, never the
 * highest-priority one in its place), the one filled button to review it in Deals, then who may do it. The sentence over it is the server's (`primary_decision.text`, "Foshan has one commercial
 * decision requiring your response."), the recommendation is the server's (`recommends_text`) when the selection is the primary decision and the queue row's own consequence otherwise. Nothing waiting says
 * so (the server's `none_text`) and the other links stand as outlined buttons, so there is no filled primary.
 */
function ActionBlock({ view, selected }: { view: CustomerOverviewView; selected: Selected | null }) {
  const { t } = useI18n();
  const decision = view.decision;
  const rest: OverviewAction[] = decision ? decision.secondary : (view.actions ?? []);
  const links = rest.map((a) => (
    <ButtonLink key={a.key} href={a.key === "stress" ? fromCustomer(a.href, view.customer_id) : a.href} data-testid={`customer-action-${a.key}`}>
      {a.label}
    </ButtonLink>
  ));
  if (!decision && !selected) {
    if (!view.none_text && !rest.length) return null;
    return (
      <section aria-label={t("customer.decision")} className="flex flex-wrap items-center justify-between gap-x-8 gap-y-3" data-testid="customer-decision-none">
        {view.none_text ? <p className="min-w-0 flex-[2_1_20rem] text-pretty text-sm text-ink-2">{view.none_text}</p> : null}
        {links.length ? <ActionGroup>{links}</ActionGroup> : null}
      </section>
    );
  }
  const title = view.primary_decision?.text ?? decision?.eyebrow ?? t("customer.decision");
  const heading = selected?.subject ?? decision?.headline_short ?? decision?.text ?? "";
  const pill = selected?.pill ?? { tone: "amber" as PillTone, text: decision?.eyebrow ?? "", lifecycle: null };
  const closed = selected ? selected.closed : decision?.kind === "awaiting_buyer" || decision?.kind === "lapsed";
  // The server's recommendation speaks for the primary decision; the older long sentence is the fallback for a server that does not send it.
  const body = selected ? selected.recommends : (decision?.text ?? null);
  // A request that needs the owner's review opens its accept review on arrival (`review=1`).
  const reviewing = selected ? selected.pill.lifecycle === "owner_review" : decision?.kind === "request";
  const rawHref = selected?.href ?? decision?.primary.href ?? "/deals";
  const href = reviewing ? reviewHref(rawHref) : rawHref;
  const label = selected ? (selected.label ?? t("customer.review")) : (decision?.primary.label ?? t("customer.review"));
  return (
    <section aria-labelledby="customer-decision-title" className="flow-card p-4 sm:p-6" id="customer-decision" data-testid="customer-decision" data-focus={selected?.key ?? undefined}>
      {/* The server's own sentence for what waits names the region; with no server decision it is the plain title. */}
      <h2 id="customer-decision-title" className="type-section text-ink" data-kind={decision?.kind ?? ""}>
        {title}
      </h2>
      <p className="mt-3" data-testid="customer-decision-status">
        <StatusPill tone={pill.tone}>{pill.text}</StatusPill>
      </p>
      <p className="mt-2 text-pretty font-display text-base font-extrabold leading-snug text-ink sm:text-lg" data-testid="customer-decision-heading">
        {heading}
      </p>
      {body ? (
        <p className="mt-1 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-decision-text">
          {body}
        </p>
      ) : null}
      <ActionGroup className="mt-4" label={t("customer.decision")}>
        <ButtonLink href={href} variant={closed ? "secondary" : "primary"} data-testid="customer-decision-primary">
          {label}
        </ButtonLink>
        {links}
      </ActionGroup>
      {decision?.authority_text && (!selected || selected.key === view.primary_decision?.decision_id || !view.primary_decision) ? (
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
  const comparison = view.exposure_comparison;
  if (!exposure && !comparison && !view.note) return null;
  // The server's comparison (expected payment against paid late) replaces the rows; the link to the late-payment test is its own, else the action the overview already carries.
  const stress = (view.actions ?? view.decision?.secondary ?? []).find((a) => a.key === "stress");
  const explore = comparison?.explore ?? (stress ? { label: t("customer.explore"), href: fromCustomer(stress.href, view.customer_id) } : null);
  return (
    <OpenSection first id="customer-exposure" title={t("customer.exposure")} testId="customer-exposure">
      {comparison ? (
        <>
          <ExposureTable comparison={comparison} explore={explore} />
          {/* What the comparison does not say (how the customer pays, the financing, the room left) stays as rows beneath it; the late-payment row is the comparison's own. */}
          {exposure && exposure.rows.some((r) => r.key !== "stress") ? (
            <div className="mt-5 border-t border-line pt-2">
              <Rows rows={exposure.rows.filter((r) => r.key !== "stress")} testId="customer-exposure-rows" />
              {exposure.same_figures_note ? (
                <p className="mt-3 text-pretty text-sm leading-relaxed text-ink-2" data-testid="customer-exposure-note">
                  {exposure.same_figures_note}
                </p>
              ) : null}
            </div>
          ) : null}
        </>
      ) : exposure ? (
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
  const mode = useMode();
  const tasks = rowsOfCustomer(queue, view.customer_id);
  const wanted = ctx.decision ?? view.context?.deal ?? null;
  const focus = focusOf(tasks, wanted);
  // The selected negotiation: from the server's list of this customer's open negotiations (the address's, else the primary, else the first), else from the queue's rows.
  const negs = view.open_negotiations ?? [];
  const serverSel = negs.find((n) => n.decision_id === wanted) ?? negs.find((n) => n.is_primary) ?? negs[0] ?? null;
  const subjectOf = (n: { subject_text: string; subject_demo_text?: string | null }) => (mode === "demo" ? (n.subject_demo_text ?? n.subject_text) : n.subject_text);
  const selected: Selected | null = serverSel
    ? (() => {
        const pill = lifecyclePill(serverSel.lifecycle, serverSel.status_text);
        const primary = view.primary_decision?.decision_id === serverSel.decision_id;
        return {
          key: serverSel.decision_id,
          subject: subjectOf(serverSel),
          pill,
          recommends: primary ? (view.primary_decision?.recommends_text ?? null) : (focus && rowDecision(focus.row) === serverSel.decision_id ? focus.row.consequence_text : null),
          href: primary && view.primary_decision ? view.primary_decision.href : selectionHref("/deals", { customer: view.customer_id, decision: serverSel.decision_id, invoice: null, from: "customer" }),
          label: primary ? (view.decision?.primary.label ?? null) : null,
          closed: pill.lifecycle === "awaiting_buyer" || pill.lifecycle === "agreed" || pill.lifecycle === "lapsed" || pill.lifecycle === "declined",
        };
      })()
    : focus && isNegotiation(focus.row)
      ? (() => {
          const pill = rowPill(focus.tier, focus.row);
          const dec = rowDecision(focus.row);
          const speaks = Boolean(view.decision && dec && view.decision.primary.href.includes(encodeURIComponent(dec)));
          return {
            key: focus.row.key,
            subject: mode === "demo" ? (focus.row.subject_demo_text ?? focus.row.subject_text) : focus.row.subject_text,
            pill,
            recommends: speaks && view.decision ? view.decision.text : focus.row.consequence_text,
            // The server's decision speaks for this negotiation when its link names it: its own link (with the path) and its own label.
            href: speaks && view.decision ? view.decision.primary.href : dec ? selectionHref("/deals", { customer: view.customer_id, decision: dec, invoice: null, from: "customer" }) : (view.decision?.primary.href ?? "/deals"),
            label: speaks && view.decision ? view.decision.primary.label : null,
            closed: pill.lifecycle === "awaiting_buyer" || focus.tier === "waiting" || focus.tier === "agreements" || pill.lifecycle === "lapsed",
          };
        })()
      : null;
  const hasEconomics = shownEconomics(view).length > 0;
  const hasExposure = Boolean(view.exposure || view.exposure_comparison || view.note);
  const flow = flowOf(view);
  const hasFlow = Boolean(flow);
  const hasWork = Boolean(tasks.length || view.decision || view.none_text || (view.actions ?? []).length);
  const sentence = view.relationship_text ?? view.summary_text ?? null;
  return (
    <div className="flow-f flex flex-col gap-6" data-testid="customer-overview">
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
        <PageHeader title={view.name} subtitle={sentence ? <span data-testid="customer-relationship">{sentence}</span> : undefined} />
      </div>
      <PartialRead partial={view.partial} onRetry={onRetry} />
      {view.context?.irrelevant_text ? (
        <p className="rounded-tile border border-line bg-subtle px-4 py-3 text-sm text-ink-2" role="status" data-testid="customer-irrelevant">
          {view.context.irrelevant_text}
        </p>
      ) : null}
      {view.figures?.length ? (
        // On a phone the action comes before the four figures (they are not interactive, so no focus order changes): its button is inside the first screen.
        <section aria-label={t("customer.figures")} className="flow-card p-4 max-lg:order-2 sm:p-6" data-testid="customer-figures">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 lg:grid-cols-4 lg:gap-x-0 lg:gap-y-4">
            {view.figures.map((f) => (
              <Figure key={f.key} figure={f} provenance={provenanceOf(view)} />
            ))}
          </dl>
        </section>
      ) : null}
      {hasWork || hasFlow ? (
        <div className={`grid gap-6 max-lg:order-1 ${hasWork && hasFlow ? "lg:grid-cols-2 lg:items-start" : ""}`}>
          {/* The action comes first in the reading order (on a phone its button is in the first screen); the receivable-to-cash flow is beside it from `lg`. */}
          {hasWork ? (
            <div className="min-w-0 space-y-6" data-testid="customer-work">
              <ActionBlock view={view} selected={selected} />
              {(tasks.length || negs.length) && !(tasks.some((x) => x.row.key !== focus?.row.key) || negs.length > 1) ? <AllTasksLink customerId={view.customer_id} name={view.name} /> : null}
              {tasks.some((x) => x.row.key !== focus?.row.key) || negs.length > 1 ? (
                <section aria-label={t("customer.outstanding", { name: view.name })} className="flow-card p-4 sm:p-6">
                  <OutstandingWork customerId={view.customer_id} rows={tasks} focusKey={focus?.row.key ?? null} name={view.name} negotiations={negs.length ? negs.filter((n) => n.decision_id !== selected?.key).map((n) => ({ key: n.decision_id, href: selectionHref("/deals", { customer: view.customer_id, decision: n.decision_id, invoice: null, from: "customer" }), subject: subjectOf(n), pill: lifecyclePill(n.lifecycle, n.status_text) })) : undefined} />
                </section>
              ) : null}
            </div>
          ) : null}
          {flow ? <ReceivableFlowCard flow={flow} /> : null}
        </div>
      ) : null}
      {hasEconomics || hasExposure ? (
        <div className={`grid gap-6 max-lg:order-3 ${hasEconomics && hasExposure ? "lg:grid-cols-2" : ""}`}>
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
        <div className="flow-card p-5 max-lg:order-3 sm:p-6">
          <History rows={view.history} />
        </div>
      ) : null}
    </div>
  );
}
