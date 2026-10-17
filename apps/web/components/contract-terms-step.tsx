"use client";

import { useEffect, useId, useRef, useState } from "react";
import { ClauseQuote } from "@/components/documents";
import { OperationResultBox } from "@/components/operation-result";
import { Button, Callout, Card, ErrorState, TableWrap, tableCls, tdCls, thCls } from "@/components/ui";
import { getContractTerms, setUpContractTerms, undoContractTerms } from "@/lib/api";
import { bump } from "@/lib/demo-store";
import { ApiError } from "@/lib/errors";
import { useI18n } from "@/lib/i18n";
import type { ContractTermsResult, ContractTermsView } from "@/lib/types";
import { useAsync } from "@/lib/use-async";

/** How long a confirmation dialog is open before its confirm takes a click (a double click on the opener never lands on it). */
const READY_MS = 400;

type Ask = { title: string; body: string; yes: string; no: string; run: () => Promise<void> };

/**
 * ADR-0014, "Set up these terms in your books": on a confirmed customer contract, what it would add to the books (its repeating invoice,
 * each figure beside the clause it comes from), what it never sets, and the forecast now and after; one button, a confirmation, and the
 * executor's answer. Once set up, one line and an undo. Every figure, date and sentence is the server's (GET /documents/{id}/terms); this
 * component computes nothing and writes no words of its own. Switched off on the server (FEATURE_CONTRACT_TERMS) it renders nothing.
 */
export function ContractTermsStep({ id }: { id: string }) {
  const { lang } = useI18n();
  const read = useAsync(() => getContractTerms(id, lang), [id, lang]);
  // The step as an answer re-read it (a set-up, an undo, a stale preview's 409), in the language it was read in; else the read.
  const [view, setView] = useState<ContractTermsView | null>(null);
  const [answer, setAnswer] = useState<ContractTermsResult | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [ask, setAsk] = useState<Ask | null>(null);
  const [busy, setBusy] = useState(false);

  if (read.error) return <ErrorState error={read.error} onRetry={read.reload} />;
  const v = view && view.lang === lang ? view : (read.data ?? null);
  if (!v) return null;

  async function act(run: () => Promise<ContractTermsResult>) {
    setBusy(true);
    setError(null);
    try {
      const res = await run();
      setAnswer(res);
      setView(res.terms);
      bump();
    } catch (e) {
      // A stale preview (409) carries the step read again: show it, and say why nothing changed.
      const detail = e instanceof ApiError ? (e.detail as { terms?: ContractTermsView; message?: string } | undefined) : undefined;
      if (detail?.terms) setView(detail.terms);
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setBusy(false);
    }
  }

  const quiet = v.status === "ALREADY" || v.status === "SET_UP";
  return (
    <section data-testid="terms-step" data-status={v.status} aria-labelledby="terms-step-title">
      <Card
        id="terms-step"
        title={<span id="terms-step-title">{v.title}</span>}
        subtitle={v.status_text}
        className={quiet ? "border-ok-line" : v.status === "READY" ? "" : "border-warn-line"}
      >
        {v.status === "READY" ? (
          <div className="space-y-5">
            <p className="text-sm text-ink-2" data-testid="terms-intro">
              {v.intro}
            </p>
            <div>
              <h3 className="text-sm font-bold text-ink">{v.labels.from_contract}</h3>
              <dl className="mt-2 grid gap-2 sm:grid-cols-2" data-testid="terms-rows">
                {v.terms.map((row) => (
                  <div key={row.field} className="rounded-tile border border-line px-3 py-2" data-testid={`terms-row-${row.field}`}>
                    <dt className="text-meta font-medium text-ink-3">{row.label}</dt>
                    <dd className="mt-0.5 text-sm font-semibold tabular-nums text-ink">{row.value_display}</dd>
                    {row.quote ? <ClauseQuote clause={row.clause} quote={row.quote} /> : null}
                  </div>
                ))}
              </dl>
            </div>
            {v.forecast ? (
              <div data-testid="terms-forecast">
                <TableWrap label={v.labels.forecast}>
                  <table className={tableCls}>
                    <caption className="px-3 py-2 text-left text-meta font-medium text-ink-2">{v.labels.forecast}</caption>
                    <thead>
                      <tr>
                        <th className={thCls}>
                          <span className="sr-only">{v.labels.forecast}</span>
                        </th>
                        <th className={thCls}>{v.labels.before}</th>
                        <th className={thCls}>{v.labels.after}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {v.forecast.rows.map((r) => (
                        <tr key={r.key} data-key={r.key} data-changed={r.changed}>
                          <th scope="row" className={`${tdCls} font-medium text-ink-2`}>
                            {r.label}
                          </th>
                          <td className={`${tdCls} tabular-nums`}>{r.before}</td>
                          <td className={`${tdCls} tabular-nums ${r.changed ? "font-semibold text-ink" : ""}`}>{r.after}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
                <p className="mt-2 text-sm text-ink-2" data-testid="terms-forecast-text">
                  {v.forecast.text}
                </p>
              </div>
            ) : null}
            {v.notes.length ? (
              <Callout tone="info">
                <ul className="list-disc space-y-1 pl-5" data-testid="terms-notes">
                  {v.notes.map((n) => (
                    <li key={n.code}>{n.text}</li>
                  ))}
                </ul>
              </Callout>
            ) : null}
            <NotSetUp v={v} />
            <div className="flex flex-wrap items-center gap-3">
              <Button
                variant="primary"
                loading={busy}
                disabled={busy || !v.can_set_up || !v.terms_hash}
                onClick={() =>
                  setAsk({
                    ...v.confirm,
                    run: () => act(() => setUpContractTerms(v.document_id, v.doc_hash, v.terms_hash as string, lang)),
                  })
                }
                data-testid="terms-set-up"
              >
                {busy ? v.labels.busy : v.button}
              </Button>
            </div>
          </div>
        ) : v.status === "SET_UP" && v.set_up ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-ink" data-testid="terms-set-up-text">
              {v.set_up.text}
            </p>
            {v.set_up.can_undo ? (
              <Button
                size="sm"
                loading={busy}
                disabled={busy}
                onClick={() => {
                  const s = v.set_up;
                  if (!s) return;
                  setAsk({ ...s.undo_confirm, run: () => act(() => undoContractTerms(v.document_id, s.op_id, lang)) });
                }}
                data-testid="terms-undo"
              >
                {busy ? v.labels.undo_busy : v.set_up.undo_button}
              </Button>
            ) : null}
          </div>
        ) : v.status === "CONFLICT" ? (
          <div className="space-y-1 text-sm text-ink-2" data-testid="terms-conflict">
            {v.existing ? <p>{v.existing.text}</p> : null}
            {v.existing?.contract_text ? <p>{v.existing.contract_text}</p> : null}
          </div>
        ) : v.status === "BLOCKED" ? (
          <div className="space-y-3">
            <div>
              <h3 className="text-sm font-bold text-ink">{v.labels.why_not}</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink-2" data-testid="terms-problems">
                {v.problems.map((p) => (
                  <li key={p.code} data-code={p.code}>
                    {p.text}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : null}
        {answer ? (
          <div className="mt-4">
            <OperationResultBox status={answer.result.status} message="" testId="terms-result" kind={answer.result.kind} showId={false}>
              <span className="text-sm font-medium text-ink">{answer.result_text}</span>
            </OperationResultBox>
          </div>
        ) : null}
        {error ? (
          <div className="mt-4" data-testid="terms-error">
            <ErrorState error={error} />
          </div>
        ) : null}
      </Card>
      <ConfirmDialog ask={ask} onClose={() => setAsk(null)} />
    </section>
  );
}

function NotSetUp({ v }: { v: ContractTermsView }) {
  if (!v.not_set_up.length) return null;
  return (
    <div>
      <h3 className="text-sm font-bold text-ink">{v.labels.not_set_up}</h3>
      <ul className="mt-1 space-y-1 text-sm" data-testid="terms-not-set-up">
        {v.not_set_up.map((x) => (
          <li key={x.field}>
            <span className="font-medium text-ink">{x.label}</span>
            <span className="block text-meta text-ink-3">{x.text}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The confirmation before the books change: a native modal dialog (the page behind is inert, Escape closes it), focus on the safe choice,
 * and a confirm that takes only a deliberate click once the dialog has been open for a moment.
 */
function ConfirmDialog({ ask, onClose }: { ask: Ask | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const opener = useRef<HTMLElement | null>(null);
  const [ready, setReady] = useState(false);
  const [running, setRunning] = useState(false);
  const titleId = useId();
  const bodyId = useId();
  const open = ask !== null;

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      d.showModal();
      d.querySelector<HTMLElement>("[data-cancel]")?.focus();
    }
    if (!open && d.open) {
      d.close();
      opener.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const t = window.setTimeout(() => setReady(true), READY_MS);
    return () => {
      window.clearTimeout(t);
      setReady(false);
    };
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={bodyId}
      data-testid="terms-dialog"
      onCancel={(e) => {
        e.preventDefault();
        if (!running) onClose();
      }}
      className="flow-f fixed inset-0 m-auto h-fit max-h-[calc(100dvh-2rem)] w-[min(32rem,calc(100vw-2rem))] overflow-y-auto overscroll-contain rounded-card border border-line bg-surface p-5 text-ink shadow-pop backdrop:bg-ink/40"
    >
      {ask ? (
        <>
          <h2 id={titleId} className="type-section text-balance text-ink">
            {ask.title}
          </h2>
          <p id={bodyId} className="mt-2 text-sm text-ink-2">
            {ask.body}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              loading={running}
              aria-disabled={!ready || undefined}
              className={ready ? "" : "opacity-60"}
              onClick={(e) => {
                if (e.detail > 1 || !ready || running) return;
                setRunning(true);
                void ask.run().finally(() => {
                  setRunning(false);
                  onClose();
                });
              }}
              data-testid="terms-dialog-yes"
            >
              {ask.yes}
            </Button>
            <Button onClick={() => !running && onClose()} data-cancel data-testid="terms-dialog-no">
              {ask.no}
            </Button>
          </div>
        </>
      ) : null}
    </dialog>
  );
}
