"use client";

import { useState } from "react";
import { AnnotatedText } from "@/components/annotated-text";
import { TierBadge } from "@/components/badges";
import { CLAUSE_KIND, ClauseQuote, DocStatusBadge, FIELD_KIND } from "@/components/documents";
import { OperationResultBox } from "@/components/operation-result";
import { Badge, Button, Callout, Card, ErrorState, LoadingBlock, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { ANNOTATION_STYLE, type AnnotationKind } from "@/lib/annotation-style";
import { decideDocument, getDocument } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { useI18n, type I18n } from "@/lib/i18n";
import type { DocumentDecision, DocumentView, TextSpan, Tier } from "@/lib/types";
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

function itemsOf(d: DocumentView, te: I18n["te"]): { read: Item[]; flags: Item[] } {
  const read: Item[] = [];
  let n = 0;
  (d.terms ?? []).forEach((x, i) =>
    read.push({ id: `term:${i}`, n: ++n, kind: FIELD_KIND[x.field], span: x.span, label: te("contractfield", x.field) || x.label, value: x.value_display, clause: x.clause, quote: x.quote }),
  );
  (d.clauses ?? []).forEach((x, i) =>
    read.push({ id: `clause:${i}`, n: ++n, kind: CLAUSE_KIND[x.field] ?? "TERM_DUTY", span: x.span, label: te("clausefield", x.field), value: x.value_text, clause: null, quote: x.quote }),
  );
  const flags = d.flags.map((f, i) => ({ id: `flag:${i}`, n: ++n, kind: "DOCUMENT_FLAG" as const, span: f.span, label: f.kind, value: f.note, clause: null, quote: f.quote }));
  return { read, flags };
}

/** Brings the highlighted clause into view inside the document pane (keyboard focus on a term). */
function reveal(id: string): void {
  if (typeof document === "undefined") return;
  document.querySelector(`mark[data-annotation~="${id}"]`)?.scrollIntoView({ block: "nearest" });
}

/**
 * The review screen for one document: the text with every clause the agent read highlighted, each term beside its quote,
 * the fields left blank and why, the flags, and for a lender agreement the facility it describes against the one on the books.
 * Until the owner confirms it, the reading is labelled "AI-generated, for reference". Confirming is logged in the hash chain
 * and bound to the hash of this exact text; it never changes the books.
 */
export function DocumentReview({ id }: { id: string }) {
  const { t, te } = useI18n();
  const doc = useAsync(() => getDocument(id), [id]);
  const [active, setActive] = useState<string | null>(null);
  const [link, setLink] = useState(true);
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [decision, setDecision] = useState<DocumentDecision | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (doc.error) return <ErrorState error={doc.error} onRetry={doc.reload} />;
  if (!doc.data) return <LoadingBlock rows={3} />;
  const d = doc.data;
  const { read, flags } = itemsOf(d, te);
  const all = [...read, ...flags];
  const kinds = [...new Set(all.map((i) => i.kind))];
  const lender = d.kind === "LENDER_AGREEMENT";
  const linkTo = lender && link ? (d.suggested_facility_id ?? null) : null;

  async function decide(which: "confirm" | "reject", doc: DocumentView) {
    setBusy(which);
    setError(null);
    try {
      setDecision(await decideDocument(doc.id, which, doc.doc_hash, which === "confirm" ? linkTo : null));
      bump();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
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
      className={`rounded-md border px-3 py-2 outline-none focus-visible:ring-2 focus-visible:ring-brand-600 ${active === it.id ? "border-brand-600 bg-brand-50" : "border-line"}`}
    >
      <div className="flex flex-wrap items-baseline gap-2">
        <span className="inline-block rounded bg-ink px-1 text-[0.65rem] font-bold leading-4 text-white">{it.n}</span>
        <span className="text-xs font-medium text-ink-3">{it.label}</span>
        <span className={`ml-auto rounded border px-1.5 text-[11px] ${ANNOTATION_STYLE[it.kind].chip}`}>{te("termkind", it.kind)}</span>
      </div>
      <p className="mt-1 break-words text-sm font-medium text-ink">{it.value}</p>
      <ClauseQuote clause={it.clause} quote={it.quote} />
    </li>
  );

  return (
    <div className="space-y-6" data-testid="doc-review" data-id={d.id} data-status={d.status} data-kind={d.kind}>
      <Card
        id="doc-review"
        title={d.title}
        subtitle={`${d.id} · ${d.counterparty_name} · ${te("dockind", d.kind)} · ${t("common.dayN", { n: d.uploaded_day })}`}
        actions={<DocStatusBadge doc={d} />}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span data-testid="doc-ai-label">
            <Badge tone={d.status === "CONFIRMED" ? "ok" : "info"}>{d.status === "CONFIRMED" ? t("docs.confirmedLabel") : t("docs.aiLabel")}</Badge>
          </span>
          <span className="text-xs text-ink-3">{t("docs.compiler", { compiler: d.compiler, version: d.prompt_version, status: d.reading_status })}</span>
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
      </Card>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        {/* The text stays in view on a wide screen while the owner walks down the terms beside it. */}
        <Card id="doc-text" title={t("docs.text")} subtitle={t("docs.review.sub")} className="lg:sticky lg:top-28 lg:self-start">
          <div className="max-h-[60vh] overflow-y-auto">
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
              <li key={k} className={`rounded-md border px-1.5 py-0.5 text-xs font-medium ${ANNOTATION_STYLE[k].chip}`}>
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
                  <TableWrap label={t("docs.compare", { id: d.compared_with })}>
                    <table className={tableCls} data-testid="doc-compare">
                      <caption className="px-3 py-2 text-left text-xs font-medium text-ink-2">{t("docs.compare", { id: d.compared_with })}</caption>
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
                              <Badge tone={r.same ? "ok" : "warn"}>{r.same ? t("docs.same") : t("docs.differs")}</Badge>
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

      <Card id="doc-decide" title={t("docs.decide")} tone={d.status === "PROPOSED" ? "warn" : undefined}>
        {d.status === "PROPOSED" ? (
          <>
            <p className="text-sm text-ink-2">{t("docs.decide.hint")}</p>
            {lender && d.suggested_facility_id ? (
              <label className="mt-3 flex items-center gap-2 text-sm text-ink">
                <input type="checkbox" checked={link} onChange={(e) => setLink(e.target.checked)} data-testid="doc-link" className="size-4" />
                {t("docs.link", { id: d.suggested_facility_id })}
              </label>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button variant="primary" disabled={!d.can_confirm} loading={busy === "confirm"} onClick={() => void decide("confirm", d)} data-testid="doc-confirm">
                {t("docs.confirm")}
              </Button>
              <Button loading={busy === "reject"} onClick={() => void decide("reject", d)} data-testid="doc-reject">
                {t("docs.reject")}
              </Button>
            </div>
          </>
        ) : (
          <p className="text-sm text-ink-2" data-testid="doc-decided">
            {t("docs.decided", { day: d.decided_day ?? 0, seq: d.decided_seq ?? 0 })}
          </p>
        )}
        {decision ? (
          <div className="mt-3">
            <OperationResultBox status={decision.result.status} message={decision.result.message} testId="doc-result" kind={decision.result.kind}>
              <span className="text-sm font-medium text-ink">{te("opkind", decision.result.kind)}</span>
              <TierBadge tier={decision.result.tier as Tier} />
            </OperationResultBox>
          </div>
        ) : null}
        {error ? (
          <div className="mt-3">
            <ErrorState error={error} />
          </div>
        ) : null}
      </Card>
    </div>
  );
}
