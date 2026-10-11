"use client";

import { useId, useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { Disclosure } from "@/components/business/kit";
import { CLAUSE_KIND, ClauseQuote, DocStatusBadge, FIELD_KIND, whenWords } from "@/components/documents";
import { OperationResultBox } from "@/components/operation-result";
import { Badge, Button, Callout, Card, Chip, ErrorState, LoadingBlock, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { ANNOTATION_STYLE, type AnnotationKind } from "@/lib/annotation-style";
import { decideDocument, getDocument } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { ApiError } from "@/lib/errors";
import { useI18n, type I18n } from "@/lib/i18n";
import type { DocumentDecision, DocumentView, TextSpan } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/** One numbered thing the reading points at in the text: a term, a lender agreement's clause, or a flag. */
interface Item {
  id: string;
  n: number;
  kind: AnnotationKind;
  span: TextSpan;
  label: string;
  value: string;
  clause: string | null;
  quote: string;
}

/** A flag's kind in words: the server's (`kind_text`), else the dictionary's for the kind before any ":" ("DATA_REQUEST:…"), else "Flag"; never the code. */
function flagLabel(f: DocumentView["flags"][number], t: I18n["t"], te: I18n["te"]): string {
  if (f.kind_text) return f.kind_text;
  const base = f.kind.split(":")[0];
  const word = te("flagkind", base);
  return word && word !== base ? word : t("docs.flag");
}

function itemsOf(d: DocumentView, t: I18n["t"], te: I18n["te"]): { read: Item[]; flags: Item[] } {
  const read: Item[] = [];
  let n = 0;
  (d.terms ?? []).forEach((x, i) =>
    read.push({ id: `term:${i}`, n: ++n, kind: FIELD_KIND[x.field], span: x.span, label: te("contractfield", x.field) || x.label, value: x.value_display, clause: x.clause, quote: x.quote }),
  );
  (d.clauses ?? []).forEach((x, i) =>
    read.push({ id: `clause:${i}`, n: ++n, kind: CLAUSE_KIND[x.field] ?? "TERM_DUTY", span: x.span, label: te("clausefield", x.field), value: x.value_text, clause: null, quote: x.quote }),
  );
  const flags = d.flags.map((f, i) => ({ id: `flag:${i}`, n: ++n, kind: "DOCUMENT_FLAG" as const, span: f.span, label: flagLabel(f, t, te), value: f.note, clause: null, quote: f.quote }));
  return { read, flags };
}

/** Brings the highlighted clause into view inside the document pane (keyboard focus on a term). */
function reveal(id: string): void {
  if (typeof document === "undefined") return;
  document.querySelector(`mark[data-annotation~="${id}"]`)?.scrollIntoView({ block: "nearest" });
}

/** What went wrong with a decision, in the owner's words: the text changed, it was already decided, the server refused, or the call failed. */
type Problem = { kind: "changed" | "decided" | "refused" | "generic" } | { kind: "error"; error: Error };

/** Reads the failure of a decision: a 409 carries the server's code (`TERMS_CHANGED`, `ALREADY_DECIDED`); a signed-out or coded failure keeps the app's own sentence. */
function problemOf(e: unknown): Problem {
  if (e instanceof ApiError) {
    const code = (e.detail as { code?: unknown } | undefined)?.code;
    if (e.status === 409 && code === "TERMS_CHANGED") return { kind: "changed" };
    if (e.status === 409 && code === "ALREADY_DECIDED") return { kind: "decided" };
    if (e.status === 401 || e.status === 403 || e.code) return { kind: "error", error: e };
  }
  return { kind: "generic" };
}

/**
 * The review screen for one document: the text with every clause the agent read highlighted, each term beside its quote,
 * the fields left blank and why, the flags, and for a lender agreement the facility it describes against the one on the books.
 * Until the owner confirms it, the reading is labelled "AI-generated, for reference". Confirming is logged in the hash chain
 * and bound to the hash of this exact text; it never changes the books. The decision cannot be undone, so its controls say so,
 * stay reachable on a phone (a bar at the foot of the screen below the desktop layout), and answer a changed text or an earlier
 * decision in words with the way forward. Ids, the entry number, the reader and the hash are behind the Audit details fold.
 */
export function DocumentReview({ id, today = null }: { id: string; today?: number | null }) {
  const { t, te, lang } = useI18n();
  const doc = useAsync(() => getDocument(id, lang), [id, lang]);
  const [active, setActive] = useState<string | null>(null);
  // Linking a lender agreement to a facility on the books starts off: the owner chooses it.
  const [link, setLink] = useState(false);
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [decision, setDecision] = useState<DocumentDecision | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const reasonId = useId();
  const hintId = useId();
  const linkHintId = useId();

  if (doc.error) return <ErrorState error={doc.error} onRetry={doc.reload} />;
  if (!doc.data) return <LoadingBlock rows={3} />;
  const d = doc.data;
  const { read, flags } = itemsOf(d, t, te);
  const all = [...read, ...flags];
  const kinds = [...new Set(all.map((i) => i.kind))];
  const lender = d.kind === "LENDER_AGREEMENT";
  const linkTo = lender && link ? (d.suggested_facility_id ?? null) : null;
  const facility = d.suggested_facility_name ?? null;
  const uploaded = whenWords(d.uploaded_when, d.uploaded_day, today, t);
  const decidedWhen = whenWords(d.decided_when, d.decided_day, today, t);
  const proposed = d.status === "PROPOSED";

  function reload() {
    setProblem(null);
    doc.reload();
  }

  async function decide(which: "confirm" | "reject", view: DocumentView) {
    if (busy) return;
    setBusy(which);
    setProblem(null);
    try {
      const res = await decideDocument(view.id, which, view.doc_hash, which === "confirm" ? linkTo : null);
      // The executor can refuse in an answer of its own: the text changed under the owner's eyes, or something else stopped it.
      if (res.result.status === "REFUSED") setProblem({ kind: res.result.violations.some((v) => v.code === "TERMS_CHANGED") ? "changed" : "refused" });
      else setDecision(res);
      bump();
    } catch (e) {
      const found = problemOf(e);
      setProblem(found);
      // Decided already, here or in another window: read it again so the screen shows what is true.
      if (found.kind === "decided") doc.reload();
    } finally {
      setBusy(null);
    }
  }

  const itemRow = (it: Item) => (
    <li
      key={it.id}
      tabIndex={0}
      data-testid={`doc-item-${it.id}`}
      onMouseEnter={() => setActive(it.id)}
      onMouseLeave={() => setActive(null)}
      onFocus={() => {
        setActive(it.id);
        reveal(it.id);
      }}
      onBlur={() => setActive(null)}
      className={`rounded-tile border px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${active === it.id ? "border-brand-600 bg-brand-50" : "border-line"}`}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="inline-grid min-w-5 place-items-center rounded-pill bg-ink px-1.5 text-xs font-bold leading-5 text-white">{it.n}</span>
        <span className="text-xs font-medium text-ink-3">{it.label}</span>
        <span className={`ml-auto rounded-pill border px-2 text-xs font-medium ${ANNOTATION_STYLE[it.kind].chip}`}>{te("termkind", it.kind)}</span>
      </div>
      <p className="mt-1 break-words text-sm font-medium text-ink">{it.value}</p>
      <ClauseQuote clause={it.clause} quote={it.quote} />
    </li>
  );

  const subtitle = [d.counterparty_name, te("dockind", d.kind), uploaded ? t("docs.readWhen", { when: uploaded }) : null].filter(Boolean).join(" · ");

  return (
    <>
      <div className="space-y-6" data-testid="doc-review" data-id={d.id} data-status={d.status} data-kind={d.kind}>
        <Card id="doc-review" title={d.title} subtitle={subtitle} actions={<DocStatusBadge doc={d} today={today} />}>
          <div className="flex flex-wrap items-center gap-2">
            <span data-testid="doc-ai-label">
              <Badge tone={d.status === "CONFIRMED" ? "ok" : "info"}>{d.status === "CONFIRMED" ? t("docs.confirmedLabel") : t("docs.aiLabel")}</Badge>
            </span>
            <span className="text-xs text-ink-3" data-testid="doc-reading">
              {d.reading_text ?? te("readstatus", d.reading_status)}
            </span>
          </div>
          {flags.length ? (
            <div className="mt-3" data-testid="doc-flags">
              <Callout tone={d.blocked ? "bad" : "warn"} title={t("docs.flags", { n: flags.length })}>
                {d.blocked ? <p className="mb-1 font-medium">{t("docs.flags.blocked")}</p> : null}
                <ul className="list-disc space-y-1 pl-5">
                  {d.flags.map((f, i) => (
                    <li key={i}>
                      {f.note} <span className="text-xs">“{f.quote}”</span>
                    </li>
                  ))}
                </ul>
              </Callout>
            </div>
          ) : null}
          {/* The ids, the entry number, who read it and the hash of the text are the audit level, not the page. */}
          <Disclosure className="mt-3 text-xs" summary={t("biz.auditDetails")} testId="doc-audit">
            <dl className="grid grid-cols-[max-content_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-xs text-ink-2">
              <dt>{t("docs.tech.id")}</dt>
              <dd className="break-all font-mono" data-testid="doc-id">
                {d.id}
              </dd>
              {d.decided_seq !== null && d.decided_seq !== undefined ? (
                <>
                  <dt>{t("docs.tech.seq")}</dt>
                  <dd className="font-mono" data-testid="doc-seq">
                    #{d.decided_seq}
                  </dd>
                </>
              ) : null}
              <dt>{t("docs.tech.reading")}</dt>
              <dd className="break-words font-mono">{t("docs.compiler", { compiler: d.compiler, version: d.prompt_version, status: d.reading_status })}</dd>
              <dt>{t("docs.tech.hash")}</dt>
              <dd className="break-all font-mono">{d.doc_hash}</dd>
              {decision ? (
                <>
                  <dt>{t("audit.opId")}</dt>
                  <dd className="break-all font-mono">{decision.result.op_id}</dd>
                  <dt>{t("audit.executor")}</dt>
                  <dd className="break-words">{decision.result.message}</dd>
                </>
              ) : null}
            </dl>
          </Disclosure>
        </Card>

        <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
          {/* The text stays in view on a wide screen while the owner walks down the terms beside it. */}
          <Card id="doc-text" title={t("docs.text")} subtitle={t("docs.review.sub")} className="lg:sticky lg:top-28 lg:self-start">
            <div className="max-h-96 overflow-y-auto">
              <AnnotatedText
                ariaLabel={t("docs.annotated")}
                text={d.document.text}
                annotations={all.map((it) => ({ id: it.id, kind: it.kind, start: it.span.start, end: it.span.end, n: it.n, label: it.label }))}
                activeId={active}
                onActivate={setActive}
              />
            </div>
            <ul className="mt-3 flex flex-wrap gap-1.5" aria-label={t("docs.legend")}>
              {kinds.map((k) => (
                <li key={k} className={`rounded-pill border px-2 py-0.5 text-xs font-medium ${ANNOTATION_STYLE[k].chip}`}>
                  {te("termkind", k)}
                </li>
              ))}
            </ul>
          </Card>

          <div className="min-w-0 space-y-4">
            <Card id="doc-terms" title={lender ? t("docs.clauses", { n: read.length }) : t("docs.terms", { n: read.length })}>
              <ol className="space-y-2" data-testid="doc-terms">
                {read.map(itemRow)}
              </ol>
            </Card>

            {d.blanks?.length ? (
              <Card id="doc-blanks" title={t("docs.blanks", { n: d.blanks.length })}>
                <ul className="space-y-1.5" data-testid="doc-blanks">
                  {d.blanks.map((b) => (
                    <li key={b.field} className="text-sm">
                      <span className="font-medium text-ink">{te("contractfield", b.field) || b.label}</span>
                      <span className="block text-xs text-ink-3">{b.reason}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ) : null}

            {lender && d.facility ? (
              <Card id="doc-facility" title={t("docs.facility")} subtitle={d.facility.summary}>
                {d.facility.all_in_rate_display ? <p className="text-sm text-ink-2">{t("docs.allIn", { rate: d.facility.all_in_rate_display })}</p> : null}
                {d.compared_with && d.comparison?.length ? (
                  <div className="mt-3">
                    <TableWrap label={facility ? t("docs.compare", { name: facility }) : t("docs.compare.generic")}>
                      <table className={tableCls} data-testid="doc-compare">
                        <caption className="px-3 py-2 text-left text-xs font-medium text-ink-2">{facility ? t("docs.compare", { name: facility }) : t("docs.compare.generic")}</caption>
                        <thead>
                          <tr>
                            <th className={thCls}>{t("docs.col.term")}</th>
                            <th className={thCls}>{t("docs.col.agreement")}</th>
                            <th className={thCls}>{t("docs.col.books")}</th>
                            <th className={thCls}>
                              <span className="sr-only">{t("docs.same")}</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {d.comparison.map((r) => (
                            <tr key={r.label} data-same={r.same}>
                              <td className={tdCls}>{r.label}</td>
                              <td className={`${tdCls} tabular-nums`}>{r.agreement_display}</td>
                              <td className={`${tdCls} tabular-nums`}>{r.books_display ?? t("common.none")}</td>
                              <td className={tdCls}>
                                <Chip tone={r.same ? "ok" : "warn"}>{r.same ? t("docs.same") : t("docs.differs")}</Chip>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </TableWrap>
                  </div>
                ) : (
                  <p className="mt-2 text-sm text-ink-3">{t("docs.compare.none")}</p>
                )}
                {d.facility.tier3.length ? (
                  <div className="mt-3">
                    <Callout tone="bad" title={t("docs.tier3")}>
                      <ul className="list-disc pl-5">
                        {d.facility.tier3.map((c, i) => (
                          <li key={i}>
                            {te("clausefield", c.field)}: “{c.quote}”
                          </li>
                        ))}
                      </ul>
                    </Callout>
                  </div>
                ) : null}
              </Card>
            ) : null}

            {d.notes.length ? (
              <Card id="doc-notes" title={t("docs.notes")}>
                <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">
                  {d.notes.map((x, i) => (
                    <li key={i}>{x.reason}</li>
                  ))}
                </ul>
              </Card>
            ) : null}
          </div>
        </div>
      </div>

        {/* An undoable-looking choice that is not: the controls sit at the foot of the screen below the desktop layout (above the tab bar, clear of the Ask FLOW pill), so a
            phone never scrolls past eighteen terms to find them. Decided, the card is an ordinary one. It is a sibling of the review, not inside it: a sticky
          element stays within its parent, and the review starts below the page's list. */}
        <Card
          id="doc-decide"
          title={t("docs.decide")}
          tone={proposed ? "warn" : undefined}
          className={proposed ? "max-lg:sticky max-lg:bottom-(--dock-h) max-lg:z-20 sm:max-lg:pr-36" : ""}
        >
          {proposed ? (
            <>
              <p id={hintId} className="text-sm text-ink-2 max-sm:text-xs">
                {t("docs.decide.hint")}
              </p>
              {lender && d.suggested_facility_id ? (
                <label className="mt-2 flex min-h-11 cursor-pointer items-start gap-3 py-2 text-sm text-ink">
                  <input type="checkbox" checked={link} onChange={(e) => setLink(e.target.checked)} data-testid="doc-link" aria-describedby={linkHintId} className="mt-0.5 size-5 shrink-0" />
                  <span>
                    {facility ? t("docs.link", { name: facility }) : t("docs.link.generic")}
                    <span id={linkHintId} className="block text-xs text-ink-3 max-sm:sr-only">
                      {t("docs.link.hint")}
                    </span>
                  </span>
                </label>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  variant="primary"
                  className="max-sm:grow"
                  disabled={!d.can_confirm || busy !== null}
                  loading={busy === "confirm"}
                  aria-describedby={d.can_confirm ? hintId : `${reasonId} ${hintId}`}
                  onClick={() => void decide("confirm", d)}
                  data-testid="doc-confirm"
                >
                  {t("docs.confirm")}
                </Button>
                <Button className="max-sm:grow" disabled={busy !== null} loading={busy === "reject"} aria-describedby={hintId} onClick={() => void decide("reject", d)} data-testid="doc-reject">
                  {t("docs.reject")}
                </Button>
              </div>
              {d.can_confirm ? null : (
                <p id={reasonId} className="mt-2 text-xs text-ink-2" data-testid="doc-cannot-confirm">
                  {d.blocked ? t("docs.flags.blocked") : t("docs.cannotConfirm")}
                </p>
              )}
            </>
          ) : (
            <p className="text-sm text-ink-2" data-testid="doc-decided">
              {d.status === "CONFIRMED"
                ? decidedWhen
                  ? t("docs.decided.confirmed", { when: decidedWhen })
                  : t("docs.decided.confirmed.plain")
                : decidedWhen
                  ? t("docs.decided.rejected", { when: decidedWhen })
                  : t("docs.decided.rejected.plain")}
            </p>
          )}
          {decision ? (
            <div className="mt-3">
              <OperationResultBox
                status={decision.result.status}
                message={
                  (decision.result.kind === "REJECT_DOCUMENT" ? t("docs.result.rejected") : t("docs.result.confirmed")) +
                  (decision.document.linked_facility_id ? ` ${facility ? t("docs.result.linked", { name: facility }) : t("docs.result.linked.generic")}` : "")
                }
                testId="doc-result"
                kind={decision.result.kind}
              >
                <span className="text-sm font-medium text-ink">{te("opkind", decision.result.kind)}</span>
              </OperationResultBox>
            </div>
          ) : null}
          {problem?.kind === "error" ? (
            <div className="mt-3" data-testid="doc-problem" data-problem="error">
              <ErrorState error={problem.error} />
            </div>
          ) : problem ? (
            <div className="mt-3" role="alert" data-testid="doc-problem" data-problem={problem.kind}>
              <Callout tone={problem.kind === "decided" ? "info" : "bad"}>
                <p className="font-medium text-ink">
                  {problem.kind === "changed" ? t("docs.err.changed") : problem.kind === "decided" ? t("docs.err.decided") : problem.kind === "refused" ? t("docs.err.refused") : t("docs.err.generic")}
                </p>
                {problem.kind === "changed" || problem.kind === "refused" ? (
                  <Button className="mt-2" size="sm" onClick={reload} data-testid="doc-reload">
                    {t("docs.err.reload")}
                  </Button>
                ) : null}
              </Callout>
            </div>
          ) : null}
        </Card>
    </>
  );
}
